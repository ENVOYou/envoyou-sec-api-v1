"""
Scope 2 Emissions Calculator Service
Indirect GHG emissions from purchased electricity, steam, heating, and cooling
"""

import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.emissions import (
    EmissionsCalculation, ActivityData, CalculationAuditTrail,
    Company, CompanyEntity
)
from app.models.epa_data import EmissionFactor, ElectricityRegion
from app.schemas.emissions import (
    Scope2CalculationRequest, ActivityDataInput, EmissionsCalculationResponse,
    CalculationValidationResult
)
from app.services.epa_service import EPADataIngestionService
from app.core.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class Scope2EmissionsCalculator:
    """Service for calculating Scope 2 (indirect energy) GHG emissions"""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = AuditLogger(db)
        self.epa_service = EPADataIngestionService(db)
        
        # Default electricity regions mapping (simplified)
        self.state_to_region = {
            'CA': 'camx', 'NV': 'camx', 'AZ': 'aznm', 'NM': 'aznm',
            'TX': 'erct', 'FL': 'frcc', 'HI': 'hioa', 'AK': 'akgd',
            'NY': 'nyup', 'CT': 'newe', 'MA': 'newe', 'ME': 'newe',
            'NH': 'newe', 'RI': 'newe', 'VT': 'newe'
            # Add more state mappings as needed
        }
    
    def calculate_scope2_emissions(
        self, 
        request: Scope2CalculationRequest, 
        user_id: str
    ) -> EmissionsCalculationResponse:
        """Calculate Scope 2 emissions from electricity consumption data"""
        try:
            logger.info(f"Starting Scope 2 calculation: {request.calculation_name}")
            start_time = datetime.utcnow()
            
            # Validate request
            validation_result = self._validate_calculation_request(request)
            if not validation_result.is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Validation failed: {validation_result.errors}"
                )
            
            # Verify company and entity exist
            company = self._verify_company_exists(request.company_id)
            entity = None
            if request.entity_id:
                entity = self._verify_entity_exists(request.entity_id, request.company_id)
            
            # Generate unique calculation code
            calculation_code = self._generate_calculation_code("SC2", company.ticker or company.name)
            
            # Create calculation record
            calculation = EmissionsCalculation(
                calculation_name=request.calculation_name,
                calculation_code=calculation_code,
                company_id=uuid.UUID(request.company_id),
                entity_id=uuid.UUID(request.entity_id) if request.entity_id else None,
                scope="scope_2",
                method=f"electricity_{request.calculation_method}",
                reporting_period_start=request.reporting_period_start,
                reporting_period_end=request.reporting_period_end,
                status="in_progress",
                calculated_by=uuid.UUID(user_id),
                input_data=request.dict(),
                calculation_parameters=request.calculation_parameters or {},
                source_documents=request.source_documents or []
            )
            
            self.db.add(calculation)
            self.db.flush()  # Get the ID
            
            # Process electricity consumption data
            total_co2e = 0.0
            total_co2 = 0.0
            
            emission_factors_used = {}
            validation_errors = []
            validation_warnings = []
            
            for electricity_data in request.electricity_consumption:
                try:
                    # Calculate emissions for this electricity consumption
                    activity_result = self._calculate_electricity_emissions(
                        electricity_data,
                        calculation.id,
                        request.calculation_method
                    )
                    
                    # Add to totals
                    total_co2 += activity_result['co2_emissions'] or 0.0
                    total_co2e += activity_result['co2e_emissions']
                    
                    # Track emission factors used
                    region = self._determine_electricity_region(electricity_data.location)
                    emission_factors_used[f"electricity_{region}"] = {
                        'factor_id': activity_result['emission_factor_id'],
                        'factor_value': activity_result['emission_factor_value'],
                        'factor_source': activity_result['emission_factor_source'],
                        'factor_unit': activity_result['emission_factor_unit'],
                        'region': region,
                        'method': request.calculation_method
                    }
                    
                except Exception as e:
                    error_msg = f"Error calculating electricity emissions for {electricity_data.location}: {str(e)}"
                    validation_errors.append(error_msg)
                    logger.error(error_msg)
            
            # Update calculation with results
            calculation_duration = (datetime.utcnow() - start_time).total_seconds()
            
            calculation.total_co2 = total_co2
            calculation.total_ch4 = 0.0  # Scope 2 typically only reports CO2
            calculation.total_n2o = 0.0  # Scope 2 typically only reports CO2
            calculation.total_co2e = total_co2e
            calculation.emission_factors_used = emission_factors_used
            calculation.calculation_duration_seconds = calculation_duration
            calculation.validation_errors = validation_errors
            calculation.validation_warnings = validation_warnings
            
            # Set status based on validation results
            if validation_errors:
                calculation.status = "failed"
            else:
                calculation.status = "completed"
                calculation.data_quality_score = self._calculate_data_quality_score(request.electricity_consumption)
                calculation.uncertainty_percentage = self._estimate_uncertainty(request.electricity_consumption, request.calculation_method)
            
            self.db.commit()
            self.db.refresh(calculation)
            
            # Create audit trail entry
            self._create_audit_trail_entry(
                calculation.id,
                "calculation_completed",
                f"Scope 2 calculation completed ({request.calculation_method}): {total_co2e:.2f} tCO2e",
                user_id
            )
            
            # Log calculation for audit
            self.audit_logger.log_calculation_event(
                user=self._get_user_by_id(user_id),
                calculation_type="scope_2",
                input_data=request.dict(),
                output_data={
                    "total_co2e": total_co2e,
                    "total_co2": total_co2,
                    "calculation_method": request.calculation_method
                },
                emission_factors_used=emission_factors_used,
                processing_time_ms=int(calculation_duration * 1000)
            )
            
            logger.info(f"Scope 2 calculation completed: {calculation_code}, {total_co2e:.2f} tCO2e")
            
            # Return response
            return self._build_calculation_response(calculation)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in Scope 2 calculation: {str(e)}")
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Calculation failed: {str(e)}"
            )
    
    def _calculate_electricity_emissions(
        self, 
        electricity_data: ActivityDataInput, 
        calculation_id: uuid.UUID,
        calculation_method: str
    ) -> Dict[str, Any]:
        """Calculate emissions for electricity consumption"""
        
        # Determine electricity region
        region = self._determine_electricity_region(electricity_data.location)
        
        # Get appropriate emission factor
        emission_factor = self._get_electricity_emission_factor(region, calculation_method)
        
        if not emission_factor:
            raise ValueError(f"No emission factor found for electricity region {region} using {calculation_method} method")
        
        # Convert units if necessary (assume kWh input, factor might be in MWh)
        converted_quantity = self._convert_electricity_units(
            electricity_data.quantity,
            electricity_data.unit,
            emission_factor.unit
        )
        
        # Calculate emissions (Scope 2 typically only CO2)
        co2_emissions = converted_quantity * emission_factor.co2_factor if emission_factor.co2_factor else None
        co2e_emissions = converted_quantity * emission_factor.co2e_factor
        
        # Handle renewable energy percentage if provided
        if hasattr(electricity_data, 'additional_data') and electricity_data.additional_data:
            renewable_pct = electricity_data.additional_data.get('renewable_percentage', 0)
            if renewable_pct > 0:
                # Reduce emissions by renewable percentage
                adjustment_factor = (100 - renewable_pct) / 100
                co2_emissions = co2_emissions * adjustment_factor if co2_emissions else None
                co2e_emissions = co2e_emissions * adjustment_factor
        
        # Create activity data record
        activity_data = ActivityData(
            calculation_id=calculation_id,
            activity_type="electricity_consumption",
            fuel_type=None,
            activity_description=f"Electricity consumption - {region} region ({calculation_method})",
            quantity=electricity_data.quantity,
            unit=electricity_data.unit,
            location=electricity_data.location,
            activity_period_start=electricity_data.activity_period_start,
            activity_period_end=electricity_data.activity_period_end,
            data_source=electricity_data.data_source,
            data_quality=electricity_data.data_quality,
            measurement_method=electricity_data.measurement_method,
            emission_factor_id=emission_factor.id,
            emission_factor_value=emission_factor.co2e_factor,
            emission_factor_unit=emission_factor.unit,
            emission_factor_source=emission_factor.source,
            co2_emissions=co2_emissions,
            ch4_emissions=None,  # Scope 2 typically doesn't report CH4
            n2o_emissions=None,  # Scope 2 typically doesn't report N2O
            co2e_emissions=co2e_emissions,
            notes=electricity_data.notes,
            additional_data={
                **(electricity_data.additional_data or {}),
                'electricity_region': region,
                'calculation_method': calculation_method
            }
        )
        
        self.db.add(activity_data)
        
        return {
            'activity_type': 'electricity_consumption',
            'co2_emissions': co2_emissions,
            'ch4_emissions': None,
            'n2o_emissions': None,
            'co2e_emissions': co2e_emissions,
            'emission_factor_id': str(emission_factor.id),
            'emission_factor_value': emission_factor.co2e_factor,
            'emission_factor_source': emission_factor.source,
            'emission_factor_unit': emission_factor.unit,
            'electricity_region': region
        }
    
    def _determine_electricity_region(self, location: Optional[str]) -> str:
        """Determine EPA eGRID region from location"""
        if not location:
            return 'camx'  # Default to California region
        
        # Extract state code from location
        location_upper = location.upper()
        
        # Check for state codes in location string
        for state_code, region in self.state_to_region.items():
            if state_code in location_upper:
                return region
        
        # Check for full state names (simplified)
        state_names = {
            'CALIFORNIA': 'camx',
            'TEXAS': 'erct',
            'FLORIDA': 'frcc',
            'NEW YORK': 'nyup',
            'MASSACHUSETTS': 'newe'
        }
        
        for state_name, region in state_names.items():
            if state_name in location_upper:
                return region
        
        # Default to CAMX if no match found
        logger.warning(f"Could not determine electricity region for location: {location}, defaulting to CAMX")
        return 'camx'
    
    def _get_electricity_emission_factor(self, region: str, calculation_method: str) -> Optional[EmissionFactor]:
        """Get appropriate EPA eGRID emission factor for electricity"""
        query = self.db.query(EmissionFactor).filter(
            EmissionFactor.is_current == True,
            EmissionFactor.category == "electricity",
            EmissionFactor.electricity_region == region
        )
        
        # For market-based method, prefer factors with renewable attributes
        if calculation_method == "market_based":
            # In a full implementation, this would look for market-based factors
            # For now, use the same factors but could be enhanced
            pass
        
        # Get the most recent factor
        factor = query.order_by(EmissionFactor.publication_year.desc()).first()
        
        return factor
    
    def _convert_electricity_units(self, quantity: float, from_unit: str, to_unit: str) -> float:
        """Convert electricity units for emission factor calculation"""
        conversion_factors = {
            ('kwh', 'mwh'): 0.001,
            ('mwh', 'kwh'): 1000.0,
            ('kwh', 'gwh'): 0.000001,
            ('gwh', 'kwh'): 1000000.0,
            ('mwh', 'gwh'): 0.001,
            ('gwh', 'mwh'): 1000.0,
        }
        
        # If units are the same, no conversion needed
        if from_unit.lower() == to_unit.lower():
            return quantity
        
        # Look for conversion factor
        conversion_key = (from_unit.lower(), to_unit.lower())
        if conversion_key in conversion_factors:
            return quantity * conversion_factors[conversion_key]
        
        # If no conversion found, assume units are compatible
        logger.warning(f"No unit conversion found for {from_unit} to {to_unit}, using original quantity")
        return quantity
    
    def _validate_calculation_request(self, request: Scope2CalculationRequest) -> CalculationValidationResult:
        """Validate Scope 2 calculation request"""
        errors = []
        warnings = []
        
        # Check if company exists
        company = self.db.query(Company).filter(Company.id == request.company_id).first()
        if not company:
            errors.append(f"Company {request.company_id} not found")
        
        # Check entity if provided
        if request.entity_id:
            entity = self.db.query(CompanyEntity).filter(
                CompanyEntity.id == request.entity_id,
                CompanyEntity.company_id == request.company_id
            ).first()
            if not entity:
                errors.append(f"Entity {request.entity_id} not found for company {request.company_id}")
        
        # Validate electricity consumption data
        if not request.electricity_consumption:
            errors.append("At least one electricity consumption data item is required")
        
        for i, consumption in enumerate(request.electricity_consumption):
            if consumption.quantity <= 0:
                errors.append(f"Electricity consumption {i+1}: Quantity must be positive")
            
            if not consumption.unit:
                errors.append(f"Electricity consumption {i+1}: Unit is required")
            
            # Check if emission factor exists for this region
            region = self._determine_electricity_region(consumption.location)
            factor = self._get_electricity_emission_factor(region, request.calculation_method)
            if not factor:
                warnings.append(f"Electricity consumption {i+1}: No emission factor found for region {region}")
        
        # Calculate scores
        data_completeness = self._calculate_data_completeness(request.electricity_consumption)
        data_quality = self._calculate_data_quality_score(request.electricity_consumption)
        
        return CalculationValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            data_completeness_score=data_completeness,
            data_quality_score=data_quality,
            calculation_accuracy_score=90.0,  # Scope 2 typically more accurate than Scope 1
            recommendations=self._generate_recommendations(request.electricity_consumption, request.calculation_method)
        )
    
    def _calculate_data_completeness(self, electricity_data: List[ActivityDataInput]) -> float:
        """Calculate data completeness score for electricity data"""
        total_fields = 0
        completed_fields = 0
        
        for consumption in electricity_data:
            total_fields += 7  # Number of key fields for electricity
            
            if consumption.quantity: completed_fields += 1
            if consumption.unit: completed_fields += 1
            if consumption.location: completed_fields += 1
            if consumption.data_source: completed_fields += 1
            if consumption.data_quality: completed_fields += 1
            if consumption.activity_period_start: completed_fields += 1
            if consumption.activity_period_end: completed_fields += 1
        
        return (completed_fields / total_fields) * 100 if total_fields > 0 else 0
    
    def _calculate_data_quality_score(self, electricity_data: List[ActivityDataInput]) -> float:
        """Calculate data quality score for electricity consumption data"""
        quality_scores = {
            'measured': 95,  # Electricity is typically well-measured
            'calculated': 85,
            'estimated': 70
        }
        
        total_score = 0
        count = 0
        
        for consumption in electricity_data:
            quality = consumption.data_quality or 'measured'  # Default to measured for electricity
            total_score += quality_scores.get(quality, 60)
            count += 1
        
        return total_score / count if count > 0 else 75
    
    def _estimate_uncertainty(self, electricity_data: List[ActivityDataInput], calculation_method: str) -> float:
        """Estimate uncertainty percentage for Scope 2 calculation"""
        # Base uncertainty by calculation method
        method_uncertainty = {
            'location_based': 10.0,  # Location-based typically more uncertain
            'market_based': 15.0     # Market-based can be more uncertain due to renewable claims
        }
        
        base_uncertainty = method_uncertainty.get(calculation_method, 12.0)
        
        # Adjust based on data quality
        quality_adjustments = {
            'measured': 0.0,
            'calculated': 3.0,
            'estimated': 8.0
        }
        
        total_adjustment = 0
        count = 0
        
        for consumption in electricity_data:
            quality = consumption.data_quality or 'measured'
            total_adjustment += quality_adjustments.get(quality, 5.0)
            count += 1
        
        avg_adjustment = total_adjustment / count if count > 0 else 0
        
        return base_uncertainty + avg_adjustment
    
    def _generate_recommendations(self, electricity_data: List[ActivityDataInput], calculation_method: str) -> List[str]:
        """Generate recommendations for improving Scope 2 calculations"""
        recommendations = []
        
        # Check for missing locations
        missing_locations = sum(1 for consumption in electricity_data if not consumption.location)
        if missing_locations > 0:
            recommendations.append(f"Specify locations for {missing_locations} electricity consumption items for accurate regional factors")
        
        # Check for estimated data
        estimated_count = sum(1 for consumption in electricity_data if consumption.data_quality == 'estimated')
        if estimated_count > 0:
            recommendations.append(f"Consider obtaining utility bills for {estimated_count} estimated electricity consumption items")
        
        # Method-specific recommendations
        if calculation_method == "location_based":
            recommendations.append("Consider implementing market-based method if you have renewable energy certificates or power purchase agreements")
        elif calculation_method == "market_based":
            recommendations.append("Ensure you have proper documentation for renewable energy claims and certificates")
        
        # Check for renewable energy data
        has_renewable_data = any(
            consumption.additional_data and consumption.additional_data.get('renewable_percentage')
            for consumption in electricity_data
        )
        if not has_renewable_data and calculation_method == "market_based":
            recommendations.append("Include renewable energy percentage data for more accurate market-based calculations")
        
        return recommendations
    
    # Reuse helper methods from Scope1Calculator
    def _verify_company_exists(self, company_id: str) -> Company:
        """Verify company exists"""
        company = self.db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company {company_id} not found"
            )
        return company
    
    def _verify_entity_exists(self, entity_id: str, company_id: str) -> CompanyEntity:
        """Verify entity exists and belongs to company"""
        entity = self.db.query(CompanyEntity).filter(
            CompanyEntity.id == entity_id,
            CompanyEntity.company_id == company_id
        ).first()
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity {entity_id} not found for company {company_id}"
            )
        return entity
    
    def _generate_calculation_code(self, prefix: str, company_identifier: str) -> str:
        """Generate unique calculation code"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        company_code = company_identifier[:3].upper() if company_identifier else "UNK"
        return f"{prefix}-{company_code}-{timestamp}"
    
    def _create_audit_trail_entry(
        self, 
        calculation_id: uuid.UUID, 
        event_type: str, 
        description: str, 
        user_id: str
    ):
        """Create audit trail entry"""
        audit_entry = CalculationAuditTrail(
            calculation_id=calculation_id,
            event_type=event_type,
            event_description=description,
            user_id=uuid.UUID(user_id),
            user_role="system",
            reason="Automated calculation process"
        )
        self.db.add(audit_entry)
    
    def _get_user_by_id(self, user_id: str):
        """Get user by ID"""
        from app.models.user import User
        return self.db.query(User).filter(User.id == user_id).first()
    
    def _build_calculation_response(self, calculation: EmissionsCalculation) -> EmissionsCalculationResponse:
        """Build calculation response with activity data"""
        # Get activity data
        activity_data = self.db.query(ActivityData).filter(
            ActivityData.calculation_id == calculation.id
        ).all()
        
        return EmissionsCalculationResponse(
            id=str(calculation.id),
            calculation_name=calculation.calculation_name,
            calculation_code=calculation.calculation_code,
            company_id=str(calculation.company_id),
            entity_id=str(calculation.entity_id) if calculation.entity_id else None,
            scope=calculation.scope,
            method=calculation.method,
            status=calculation.status,
            reporting_period_start=calculation.reporting_period_start,
            reporting_period_end=calculation.reporting_period_end,
            total_co2e=calculation.total_co2e,
            total_co2=calculation.total_co2,
            total_ch4=calculation.total_ch4,
            total_n2o=calculation.total_n2o,
            data_quality_score=calculation.data_quality_score,
            uncertainty_percentage=calculation.uncertainty_percentage,
            calculated_by=str(calculation.calculated_by),
            reviewed_by=str(calculation.reviewed_by) if calculation.reviewed_by else None,
            approved_by=str(calculation.approved_by) if calculation.approved_by else None,
            calculation_timestamp=calculation.calculation_timestamp,
            calculation_duration_seconds=calculation.calculation_duration_seconds,
            activity_data=[
                {
                    'id': str(ad.id),
                    'activity_type': ad.activity_type,
                    'fuel_type': ad.fuel_type,
                    'activity_description': ad.activity_description,
                    'quantity': ad.quantity,
                    'unit': ad.unit,
                    'location': ad.location,
                    'emission_factor_value': ad.emission_factor_value,
                    'emission_factor_unit': ad.emission_factor_unit,
                    'emission_factor_source': ad.emission_factor_source,
                    'co2_emissions': ad.co2_emissions,
                    'ch4_emissions': ad.ch4_emissions,
                    'n2o_emissions': ad.n2o_emissions,
                    'co2e_emissions': ad.co2e_emissions,
                    'data_quality': ad.data_quality,
                    'notes': ad.notes
                } for ad in activity_data
            ],
            validation_errors=calculation.validation_errors,
            validation_warnings=calculation.validation_warnings,
            created_at=calculation.created_at,
            updated_at=calculation.updated_at
        )