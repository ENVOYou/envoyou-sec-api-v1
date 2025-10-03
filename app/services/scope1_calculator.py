"""
Scope 1 Emissions Calculator Service
Direct GHG emissions from sources owned or controlled by the company
"""

import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.emissions import (
    EmissionsCalculation, ActivityData, CalculationAuditTrail,
    Company, CompanyEntity
)
from app.models.epa_data import EmissionFactor
from app.schemas.emissions import (
    Scope1CalculationRequest, ActivityDataInput, EmissionsCalculationResponse,
    CalculationValidationResult
)
from app.services.epa_service import EPADataIngestionService
from app.core.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class Scope1EmissionsCalculator:
    """Service for calculating Scope 1 (direct) GHG emissions"""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = AuditLogger(db)
        self.epa_service = EPADataIngestionService(db)
        
        # GWP values for GHG gases (AR5, 100-year)
        self.gwp_values = {
            'co2': 1.0,
            'ch4': 28.0,  # Methane
            'n2o': 265.0  # Nitrous oxide
        }
    
    def calculate_scope1_emissions(
        self, 
        request: Scope1CalculationRequest, 
        user_id: str
    ) -> EmissionsCalculationResponse:
        """Calculate Scope 1 emissions from activity data"""
        try:
            logger.info(f"Starting Scope 1 calculation: {request.calculation_name}")
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
            calculation_code = self._generate_calculation_code("SC1", company.ticker or company.name)
            
            # Create calculation record
            calculation = EmissionsCalculation(
                calculation_name=request.calculation_name,
                calculation_code=calculation_code,
                company_id=uuid.UUID(request.company_id),
                entity_id=uuid.UUID(request.entity_id) if request.entity_id else None,
                scope="scope_1",
                method="fuel_combustion",
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
            
            # Process each activity data item
            total_co2 = 0.0
            total_ch4 = 0.0
            total_n2o = 0.0
            total_co2e = 0.0
            
            emission_factors_used = {}
            validation_errors = []
            validation_warnings = []
            
            for activity_input in request.activity_data:
                try:
                    # Calculate emissions for this activity
                    activity_result = self._calculate_activity_emissions(
                        activity_input, 
                        calculation.id
                    )
                    
                    # Add to totals
                    total_co2 += activity_result['co2_emissions'] or 0.0
                    total_ch4 += activity_result['ch4_emissions'] or 0.0
                    total_n2o += activity_result['n2o_emissions'] or 0.0
                    total_co2e += activity_result['co2e_emissions']
                    
                    # Track emission factors used
                    emission_factors_used[activity_result['activity_type']] = {
                        'factor_id': activity_result['emission_factor_id'],
                        'factor_value': activity_result['emission_factor_value'],
                        'factor_source': activity_result['emission_factor_source'],
                        'factor_unit': activity_result['emission_factor_unit']
                    }
                    
                except Exception as e:
                    error_msg = f"Error calculating {activity_input.activity_type}: {str(e)}"
                    validation_errors.append(error_msg)
                    logger.error(error_msg)
            
            # Calculate total CO2e using GWP values
            calculated_co2e = (
                total_co2 * self.gwp_values['co2'] +
                total_ch4 * self.gwp_values['ch4'] +
                total_n2o * self.gwp_values['n2o']
            )
            
            # Update calculation with results
            calculation_duration = (datetime.utcnow() - start_time).total_seconds()
            
            calculation.total_co2 = total_co2
            calculation.total_ch4 = total_ch4
            calculation.total_n2o = total_n2o
            calculation.total_co2e = calculated_co2e
            calculation.emission_factors_used = emission_factors_used
            calculation.calculation_duration_seconds = calculation_duration
            calculation.validation_errors = validation_errors
            calculation.validation_warnings = validation_warnings
            
            # Set status based on validation results
            if validation_errors:
                calculation.status = "failed"
            else:
                calculation.status = "completed"
                calculation.data_quality_score = self._calculate_data_quality_score(request.activity_data)
                calculation.uncertainty_percentage = self._estimate_uncertainty(request.activity_data)
            
            self.db.commit()
            self.db.refresh(calculation)
            
            # Create audit trail entry
            self._create_audit_trail_entry(
                calculation.id,
                "calculation_completed",
                f"Scope 1 calculation completed: {calculated_co2e:.2f} tCO2e",
                user_id
            )
            
            # Log calculation for audit
            self.audit_logger.log_calculation_event(
                user=self._get_user_by_id(user_id),
                calculation_type="scope_1",
                input_data=request.dict(),
                output_data={
                    "total_co2e": calculated_co2e,
                    "total_co2": total_co2,
                    "total_ch4": total_ch4,
                    "total_n2o": total_n2o
                },
                emission_factors_used=emission_factors_used,
                processing_time_ms=int(calculation_duration * 1000)
            )
            
            logger.info(f"Scope 1 calculation completed: {calculation_code}, {calculated_co2e:.2f} tCO2e")
            
            # Return response
            return self._build_calculation_response(calculation)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in Scope 1 calculation: {str(e)}")
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Calculation failed: {str(e)}"
            )
    
    def _calculate_activity_emissions(
        self, 
        activity_input: ActivityDataInput, 
        calculation_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Calculate emissions for a single activity"""
        
        # Get appropriate emission factor
        emission_factor = self._get_emission_factor(
            activity_input.activity_type,
            activity_input.fuel_type
        )
        
        if not emission_factor:
            raise ValueError(f"No emission factor found for {activity_input.activity_type} - {activity_input.fuel_type}")
        
        # Convert units if necessary
        converted_quantity = self._convert_units(
            activity_input.quantity,
            activity_input.unit,
            emission_factor.unit
        )
        
        # Calculate emissions
        co2_emissions = converted_quantity * emission_factor.co2_factor if emission_factor.co2_factor else None
        ch4_emissions = converted_quantity * emission_factor.ch4_factor if emission_factor.ch4_factor else None
        n2o_emissions = converted_quantity * emission_factor.n2o_factor if emission_factor.n2o_factor else None
        co2e_emissions = converted_quantity * emission_factor.co2e_factor
        
        # Create activity data record
        activity_data = ActivityData(
            calculation_id=calculation_id,
            activity_type=activity_input.activity_type,
            fuel_type=activity_input.fuel_type,
            activity_description=activity_input.activity_description,
            quantity=activity_input.quantity,
            unit=activity_input.unit,
            location=activity_input.location,
            activity_period_start=activity_input.activity_period_start,
            activity_period_end=activity_input.activity_period_end,
            data_source=activity_input.data_source,
            data_quality=activity_input.data_quality,
            measurement_method=activity_input.measurement_method,
            emission_factor_id=emission_factor.id,
            emission_factor_value=emission_factor.co2e_factor,
            emission_factor_unit=emission_factor.unit,
            emission_factor_source=emission_factor.source,
            co2_emissions=co2_emissions,
            ch4_emissions=ch4_emissions,
            n2o_emissions=n2o_emissions,
            co2e_emissions=co2e_emissions,
            notes=activity_input.notes,
            additional_data=activity_input.additional_data
        )
        
        self.db.add(activity_data)
        
        return {
            'activity_type': activity_input.activity_type,
            'co2_emissions': co2_emissions,
            'ch4_emissions': ch4_emissions,
            'n2o_emissions': n2o_emissions,
            'co2e_emissions': co2e_emissions,
            'emission_factor_id': str(emission_factor.id),
            'emission_factor_value': emission_factor.co2e_factor,
            'emission_factor_source': emission_factor.source,
            'emission_factor_unit': emission_factor.unit
        }
    
    def _get_emission_factor(self, activity_type: str, fuel_type: Optional[str]) -> Optional[EmissionFactor]:
        """Get appropriate EPA emission factor for activity"""
        query = self.db.query(EmissionFactor).filter(
            EmissionFactor.is_current == True,
            EmissionFactor.category == "fuel"
        )
        
        if fuel_type:
            query = query.filter(EmissionFactor.fuel_type == fuel_type)
        
        # Get the most recent factor
        factor = query.order_by(EmissionFactor.publication_year.desc()).first()
        
        return factor
    
    def _convert_units(self, quantity: float, from_unit: str, to_unit: str) -> float:
        """Convert units for emission factor calculation"""
        # Simplified unit conversion - in production, use a comprehensive unit conversion library
        conversion_factors = {
            ('gallons', 'liters'): 3.78541,
            ('liters', 'gallons'): 0.264172,
            ('mmbtu', 'gj'): 1.05506,
            ('gj', 'mmbtu'): 0.947817,
            ('tons', 'kg'): 1000.0,
            ('kg', 'tons'): 0.001,
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
    
    def _validate_calculation_request(self, request: Scope1CalculationRequest) -> CalculationValidationResult:
        """Validate calculation request"""
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
        
        # Validate activity data
        if not request.activity_data:
            errors.append("At least one activity data item is required")
        
        for i, activity in enumerate(request.activity_data):
            if activity.quantity <= 0:
                errors.append(f"Activity {i+1}: Quantity must be positive")
            
            if not activity.unit:
                errors.append(f"Activity {i+1}: Unit is required")
            
            # Check if emission factor exists for this activity
            factor = self._get_emission_factor(activity.activity_type, activity.fuel_type)
            if not factor:
                warnings.append(f"Activity {i+1}: No emission factor found for {activity.activity_type} - {activity.fuel_type}")
        
        # Calculate scores
        data_completeness = self._calculate_data_completeness(request.activity_data)
        data_quality = self._calculate_data_quality_score(request.activity_data)
        
        return CalculationValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            data_completeness_score=data_completeness,
            data_quality_score=data_quality,
            calculation_accuracy_score=85.0,  # Base score, would be calculated based on factors
            recommendations=self._generate_recommendations(request.activity_data)
        )
    
    def _calculate_data_completeness(self, activity_data: List[ActivityDataInput]) -> float:
        """Calculate data completeness score"""
        total_fields = 0
        completed_fields = 0
        
        for activity in activity_data:
            total_fields += 8  # Number of key fields
            
            if activity.quantity: completed_fields += 1
            if activity.unit: completed_fields += 1
            if activity.activity_type: completed_fields += 1
            if activity.fuel_type: completed_fields += 1
            if activity.location: completed_fields += 1
            if activity.data_source: completed_fields += 1
            if activity.data_quality: completed_fields += 1
            if activity.measurement_method: completed_fields += 1
        
        return (completed_fields / total_fields) * 100 if total_fields > 0 else 0
    
    def _calculate_data_quality_score(self, activity_data: List[ActivityDataInput]) -> float:
        """Calculate data quality score based on measurement methods and sources"""
        quality_scores = {
            'measured': 100,
            'calculated': 80,
            'estimated': 60
        }
        
        total_score = 0
        count = 0
        
        for activity in activity_data:
            quality = activity.data_quality or 'estimated'
            total_score += quality_scores.get(quality, 50)
            count += 1
        
        return total_score / count if count > 0 else 50
    
    def _estimate_uncertainty(self, activity_data: List[ActivityDataInput]) -> float:
        """Estimate uncertainty percentage for the calculation"""
        # Simplified uncertainty estimation
        uncertainty_by_quality = {
            'measured': 5.0,
            'calculated': 15.0,
            'estimated': 30.0
        }
        
        total_uncertainty = 0
        count = 0
        
        for activity in activity_data:
            quality = activity.data_quality or 'estimated'
            total_uncertainty += uncertainty_by_quality.get(quality, 35.0)
            count += 1
        
        return total_uncertainty / count if count > 0 else 25.0
    
    def _generate_recommendations(self, activity_data: List[ActivityDataInput]) -> List[str]:
        """Generate recommendations for improving data quality"""
        recommendations = []
        
        estimated_count = sum(1 for activity in activity_data if activity.data_quality == 'estimated')
        if estimated_count > 0:
            recommendations.append(f"Consider improving {estimated_count} estimated data points with measured values")
        
        missing_sources = sum(1 for activity in activity_data if not activity.data_source)
        if missing_sources > 0:
            recommendations.append(f"Add data sources for {missing_sources} activity data items")
        
        missing_locations = sum(1 for activity in activity_data if not activity.location)
        if missing_locations > 0:
            recommendations.append(f"Specify locations for {missing_locations} activities for better accuracy")
        
        return recommendations
    
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
            user_role="system",  # Would get from user context
            reason="Automated calculation process"
        )
        self.db.add(audit_entry)
    
    def _get_user_by_id(self, user_id: str):
        """Get user by ID - placeholder for actual user service"""
        # This would integrate with the actual user service
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