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
from app.models.user import User
from app.schemas.emissions import (
    Scope2CalculationRequest, ActivityDataInput, EmissionsCalculationResponse,
    CalculationValidationResult
)
from app.services.epa_cache_service import EPACachedService
from app.core.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class Scope2EmissionsCalculator:
    """Service for calculating Scope 2 (indirect energy) GHG emissions"""
    
    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = AuditLogger(db)
        self.epa_service = EPACachedService(db)
        
        # Comprehensive EPA eGRID regions mapping
        self.state_to_region = {
            # CAMX - California
            'CA': 'camx',
            
            # NWPP - Northwest Power Pool
            'WA': 'nwpp', 'OR': 'nwpp', 'ID': 'nwpp', 'MT': 'nwpp',
            'WY': 'nwpp', 'UT': 'nwpp', 'NV': 'nwpp',
            
            # AZNM - Arizona-New Mexico
            'AZ': 'aznm', 'NM': 'aznm',
            
            # ERCT - Electric Reliability Council of Texas
            'TX': 'erct',
            
            # FRCC - Florida Reliability Coordinating Council
            'FL': 'frcc',
            
            # HIOA - Hawaii and Other Islands
            'HI': 'hioa',
            
            # AKGD - Alaska Grid
            'AK': 'akgd',
            
            # NEWE - New England
            'CT': 'newe', 'MA': 'newe', 'ME': 'newe', 'NH': 'newe', 'RI': 'newe', 'VT': 'newe',
            
            # NYUP - New York Upstate
            'NY': 'nyup',
            
            # NYLI - New York Long Island
            # Note: Long Island would need more specific location parsing
            
            # NYIS - New York City/Westchester
            # Note: NYC would need more specific location parsing
            
            # PRMS - Puerto Rico and US Virgin Islands
            'PR': 'prms', 'VI': 'prms',
            
            # RFCE - RFC East
            'NJ': 'rfce', 'PA': 'rfce', 'DE': 'rfce', 'MD': 'rfce', 'DC': 'rfce',
            
            # RFCM - RFC Michigan
            'MI': 'rfcm',
            
            # RFCW - RFC West
            'OH': 'rfcw', 'WV': 'rfcw',
            
            # SRMV - SERC Mississippi Valley
            'AR': 'srmv', 'LA': 'srmv', 'MS': 'srmv',
            
            # SRMW - SERC Midwest
            'IL': 'srmw', 'IN': 'srmw', 'MO': 'srmw',
            
            # SRSO - SERC South
            'AL': 'srso', 'GA': 'srso',
            
            # SRTV - SERC Tennessee Valley
            'TN': 'srtv', 'KY': 'srtv', 'NC': 'srtv', 'VA': 'srtv', 'SC': 'srtv',
            
            # SPNO - SPP North
            'NE': 'spno', 'KS': 'spno', 'OK': 'spno',
            
            # SPSO - SPP South
            # Note: Some overlap with other regions, would need more specific mapping
            
            # MROW - MRO West
            'ND': 'mrow', 'SD': 'mrow', 'MN': 'mrow', 'IA': 'mrow', 'WI': 'mrow'
        }
        
        # Major city to region mapping for more precise location detection
        self.city_to_region = {
            'NEW YORK CITY': 'nyis',
            'NYC': 'nyis',
            'MANHATTAN': 'nyis',
            'BROOKLYN': 'nyis',
            'QUEENS': 'nyis',
            'BRONX': 'nyis',
            'WESTCHESTER': 'nyis',
            'LONG ISLAND': 'nyli',
            'NASSAU': 'nyli',
            'SUFFOLK': 'nyli',
            'LOS ANGELES': 'camx',
            'SAN FRANCISCO': 'camx',
            'CHICAGO': 'srmw',
            'HOUSTON': 'erct',
            'DALLAS': 'erct',
        }
    
    async def calculate_scope2_emissions(
        self, 
        request: Scope2CalculationRequest, 
        user_id: str
    ) -> EmissionsCalculationResponse:
        """Calculate Scope 2 emissions from electricity consumption data"""
        try:
            logger.info(f"Starting Scope 2 calculation: {request.calculation_name}")
            start_time = datetime.utcnow()
            
            # Validate request
            validation_result = await self._validate_calculation_request(request)
            if not validation_result.is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Validation failed: {validation_result.errors}"
                )
            
            # Verify company exists
            company = self._verify_company_exists(request.company_id)
            
            # Generate unique calculation code
            calculation_code = self._generate_calculation_code("SC2", company.ticker or company.name)
            
            # Create calculation record
            calculation = EmissionsCalculation(
                calculation_name=request.calculation_name,
                calculation_code=calculation_code,
                company_id=uuid.UUID(request.company_id),
                entity_id=None,  # Scope 2 typically at company level
                scope="scope_2",
                method=request.calculation_method,
                reporting_period_start=request.reporting_period_start,
                reporting_period_end=request.reporting_period_end,
                status="in_progress",
                calculated_by=uuid.UUID(user_id),
                input_data=request.dict(),
                calculation_parameters=request.calculation_parameters or {},
                emission_factors_used={},  # Initialize as empty dict
                source_documents=request.source_documents or []
            )
            
            self.db.add(calculation)
            self.db.flush()  # Get the ID
            
            total_co2e = 0.0
            total_co2 = 0.0
            emission_factors_used = {}
            
            # Calculate emissions for each electricity consumption entry
            for electricity_data in request.electricity_consumption:
                try:
                    result = await self._calculate_electricity_emissions(
                        electricity_data,
                        calculation.id,
                        request.calculation_method
                    )
                    
                    total_co2e += result['co2e_emissions'] or 0.0
                    total_co2 += result['co2_emissions'] or 0.0
                    
                    # Track emission factors used
                    emission_factors_used[result['emission_factor_id']] = {
                        'value': result['emission_factor_value'],
                        'source': result['emission_factor_source'],
                        'unit': result['emission_factor_unit']
                    }
                
                except Exception as e:
                    logger.warning(f"Skipping electricity data due to error: {str(e)}")
                    continue
            
            # Update calculation record with totals
            calculation.total_co2e = total_co2e
            calculation.total_co2 = total_co2
            calculation.status = "completed"
            calculation.calculation_timestamp = datetime.utcnow()
            calculation.calculation_duration_seconds = (datetime.utcnow() - start_time).total_seconds()
            
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
                processing_time_ms=int(calculation.calculation_duration_seconds * 1000)
            )
            
            logger.info(f"Scope 2 calculation completed: {calculation_code}, {total_co2e:.2f} tCO2e")
            
            # Generate calculation insights
            calculation_insights = self._generate_calculation_insights(
                request.electricity_consumption, 
                total_co2e, 
                emission_factors_used,
                request.calculation_method
            )
            
            # Store insights in calculation
            calculation.calculation_insights = calculation_insights
            self.db.commit()
            
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
    
    async def _calculate_electricity_emissions(
        self, 
        electricity_data: ActivityDataInput, 
        calculation_id: uuid.UUID,
        calculation_method: str
    ) -> Dict[str, Any]:
        """Calculate emissions for electricity consumption"""
        
        # Determine electricity region
        region = self._determine_electricity_region(electricity_data.location)
        
        # Get appropriate emission factor using intelligent selection
        emission_factor = await self._get_electricity_emission_factor(region, calculation_method)
        
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
        
        # Handle renewable energy and market-based adjustments
        co2_emissions, co2e_emissions = self._apply_renewable_adjustments(
            co2_emissions, 
            co2e_emissions, 
            electricity_data, 
            calculation_method
        )
        
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
        """Enhanced EPA eGRID region determination from location"""
        if not location:
            return 'camx'  # Default to California region
        
        location_upper = location.upper().strip()
        
        # First, check for specific cities (more precise than state-level)
        for city, region in self.city_to_region.items():
            if city in location_upper:
                logger.info(f"Matched city '{city}' to region '{region}' for location: {location}")
                return region
        
        # Check for state codes (2-letter abbreviations)
        for state_code, region in self.state_to_region.items():
            # Look for state code as separate word or with common separators
            if f" {state_code} " in f" {location_upper} " or f",{state_code}" in location_upper or f"-{state_code}" in location_upper:
                logger.info(f"Matched state code '{state_code}' to region '{region}' for location: {location}")
                return region
        
        # Check for full state names
        state_names = {
            'CALIFORNIA': 'camx',
            'TEXAS': 'erct',
            'FLORIDA': 'frcc',
            'NEW YORK': 'nyup',
            'MASSACHUSETTS': 'newe',
            'CONNECTICUT': 'newe',
            'MAINE': 'newe',
            'NEW HAMPSHIRE': 'newe',
            'RHODE ISLAND': 'newe',
            'VERMONT': 'newe',
            'WASHINGTON': 'nwpp',
            'OREGON': 'nwpp',
            'IDAHO': 'nwpp',
            'MONTANA': 'nwpp',
            'WYOMING': 'nwpp',
            'UTAH': 'nwpp',
            'NEVADA': 'nwpp',
            'ARIZONA': 'aznm',
            'NEW MEXICO': 'aznm',
            'HAWAII': 'hioa',
            'ALASKA': 'akgd',
            'NEW JERSEY': 'rfce',
            'PENNSYLVANIA': 'rfce',
            'DELAWARE': 'rfce',
            'MARYLAND': 'rfce',
            'MICHIGAN': 'rfcm',
            'OHIO': 'rfcw',
            'WEST VIRGINIA': 'rfcw',
            'ARKANSAS': 'srmv',
            'LOUISIANA': 'srmv',
            'MISSISSIPPI': 'srmv',
            'ILLINOIS': 'srmw',
           
        }
        
        # If no match found, default to California region
        logger.warning(f"No region match found for location: {location}, defaulting to 'camx'")
        return 'camx'
    
    async def _get_electricity_emission_factor(
        self, 
        region: str, 
        calculation_method: str
    ) -> Optional[EmissionFactor]:
        """Get appropriate EPA emission factor for electricity region and calculation method"""
        try:
            # Use the EPA cached service to get electricity emission factors
            factors = await self.epa_service.get_emission_factors(
                source="EPA_EGRID",  # Use eGRID data for electricity
                electricity_region=region,
                category="electricity"
            )
            
            if not factors:
                logger.warning(f"No emission factors found for electricity region {region}")
                return None
            
            # For location-based method, use the first available factor
            # For market-based method, we would need additional logic for renewable energy credits
            if calculation_method == "location_based":
                # Return the most recent factor
                return factors[0] if factors else None
            elif calculation_method == "market_based":
                # For market-based, we might need to adjust for renewable energy purchases
                # For now, return the location-based factor as fallback
                return factors[0] if factors else None
            else:
                logger.warning(f"Unknown calculation method: {calculation_method}, using location_based")
                return factors[0] if factors else None
                
        except Exception as e:
            logger.error(f"Error getting electricity emission factor for region {region}: {str(e)}")
            return None
    
    def _convert_electricity_units(
        self, 
        quantity: float, 
        from_unit: str, 
        to_unit: str
    ) -> float:
        """Convert electricity units (e.g., kWh to MWh)"""
        from_unit_norm = self._normalize_electricity_unit(from_unit)
        to_unit_norm = self._normalize_electricity_unit(to_unit)
        
        # If units are the same, no conversion needed
        if from_unit_norm == to_unit_norm:
            return quantity
        
        # Comprehensive electricity conversion factors
        conversion_factors = {
            # Energy conversions (electricity)
            ('kwh', 'mwh'): 0.001,
            ('mwh', 'kwh'): 1000.0,
            ('kwh', 'gwh'): 0.000001,
            ('gwh', 'kwh'): 1000000.0,
            ('mwh', 'gwh'): 0.001,
            ('gwh', 'mwh'): 1000.0,
            ('twh', 'gwh'): 1000.0,
            ('gwh', 'twh'): 0.001,
            ('twh', 'mwh'): 1000000.0,
            ('mwh', 'twh'): 0.000001,
            
            # Power to energy conversions (assuming 1 hour)
            ('kw', 'kwh'): 1.0,  # Assuming 1 hour operation
            ('mw', 'mwh'): 1.0,
            ('gw', 'gwh'): 1.0,
            
            # Energy to other energy units
            ('kwh', 'mj'): 3.6,
            ('mj', 'kwh'): 0.277778,
            ('kwh', 'btu'): 3412.14,
            ('btu', 'kwh'): 0.000293071,
            ('mwh', 'mmbtu'): 3.41214,
            ('mmbtu', 'mwh'): 0.293071,
            
            # Thermal energy conversions
            ('therms', 'kwh'): 29.3001,
            ('kwh', 'therms'): 0.0341296,
            ('mcf', 'kwh'): 293.001,  # Thousand cubic feet of natural gas
            ('kwh', 'mcf'): 0.00341296,
        }
        
        # Look for direct conversion
        conversion_key = (from_unit_norm, to_unit_norm)
        if conversion_key in conversion_factors:
            converted_value = quantity * conversion_factors[conversion_key]
            logger.debug(f"Converted {quantity} {from_unit} to {converted_value} {to_unit}")
            return converted_value
        
        # Try reverse conversion
        reverse_key = (to_unit_norm, from_unit_norm)
        if reverse_key in conversion_factors:
            converted_value = quantity / conversion_factors[reverse_key]
            logger.debug(f"Converted {quantity} {from_unit} to {converted_value} {to_unit} (reverse)")
            return converted_value
        
        # If no conversion found, log warning and return original
        logger.warning(f"No electricity unit conversion found for {from_unit} to {to_unit}, using original quantity")
        return quantity
    
    def _normalize_electricity_unit(self, unit: str) -> str:
        """Normalize electricity unit strings for consistent matching"""
        if not unit:
            return ""
        
        # Convert to lowercase and remove common variations
        normalized = unit.lower().strip()
        
        # Handle common electricity unit variations
        unit_mappings = {
            'kilowatt_hour': 'kwh',
            'kilowatt-hour': 'kwh',
            'kw_h': 'kwh',
            'kwhr': 'kwh',
            'kilowatthour': 'kwh',
            'megawatt_hour': 'mwh',
            'megawatt-hour': 'mwh',
            'mw_h': 'mwh',
            'mwhr': 'mwh',
            'megawatthour': 'mwh',
            'gigawatt_hour': 'gwh',
            'gigawatt-hour': 'gwh',
            'gw_h': 'gwh',
            'gwhr': 'gwh',
            'gigawatthour': 'gwh',
            'terawatt_hour': 'twh',
            'terawatt-hour': 'twh',
            'tw_h': 'twh',
            'twhr': 'twh',
            'terawatthour': 'twh',
            'kilowatt': 'kw',
            'megawatt': 'mw',
            'gigawatt': 'gw',
            'megajoule': 'mj',
            'british_thermal_unit': 'btu',
            'million_btu': 'mmbtu',
            'therm': 'therms',
            'thousand_cubic_feet': 'mcf',
            'mcf_gas': 'mcf'
        }
        
        return unit_mappings.get(normalized, normalized)
    
    def _apply_renewable_adjustments(
        self, 
        co2_emissions: Optional[float], 
        co2e_emissions: float, 
        electricity_data: ActivityDataInput, 
        calculation_method: str
    ) -> tuple[Optional[float], float]:
        """Apply renewable energy and market-based adjustments to emissions"""
        
        if not hasattr(electricity_data, 'additional_data') or not electricity_data.additional_data:
            return co2_emissions, co2e_emissions
        
        additional_data = electricity_data.additional_data
        
        # Handle different calculation methods
        if calculation_method == "market_based":
            # Market-based method considers contractual arrangements
            
            # Renewable Energy Certificates (RECs)
            recs_mwh = additional_data.get('recs_mwh', 0)
            if recs_mwh > 0:
                # Convert electricity quantity to MWh for REC calculation
                electricity_mwh = self._convert_electricity_units(
                    electricity_data.quantity, 
                    electricity_data.unit, 
                    'mwh'
                )
                
                # Calculate REC coverage percentage
                rec_coverage = min(100, (recs_mwh / electricity_mwh) * 100) if electricity_mwh > 0 else 0
                
                # Apply REC adjustment (RECs typically have zero emissions)
                adjustment_factor = (100 - rec_coverage) / 100
                co2_emissions = co2_emissions * adjustment_factor if co2_emissions else None
                co2e_emissions = co2e_emissions * adjustment_factor
                
                logger.info(f"Applied REC adjustment: {rec_coverage:.1f}% coverage, {adjustment_factor:.3f} factor")
            
            # Power Purchase Agreements (PPAs) with specific emission factors
            ppa_emission_factor = additional_data.get('ppa_emission_factor')
            if ppa_emission_factor is not None:
                # Use PPA-specific emission factor instead of grid average
                converted_quantity = self._convert_electricity_units(
                    electricity_data.quantity,
                    electricity_data.unit,
                    'mwh'  # Assume PPA factor is in tCO2e/MWh
                )
                
                co2e_emissions = converted_quantity * ppa_emission_factor
                co2_emissions = co2e_emissions  # Assume all CO2 for simplicity
                
                logger.info(f"Applied PPA emission factor: {ppa_emission_factor} tCO2e/MWh")
            
            # Green tariff programs
            green_tariff_pct = additional_data.get('green_tariff_percentage', 0)
            if green_tariff_pct > 0:
                adjustment_factor = (100 - green_tariff_pct) / 100
                co2_emissions = co2_emissions * adjustment_factor if co2_emissions else None
                co2e_emissions = co2e_emissions * adjustment_factor
                
                logger.info(f"Applied green tariff adjustment: {green_tariff_pct}% green energy")
        
        elif calculation_method == "location_based":
            # Location-based method uses grid average factors
            
            # On-site renewable generation offset
            onsite_renewable_mwh = additional_data.get('onsite_renewable_mwh', 0)
            if onsite_renewable_mwh > 0:
                electricity_mwh = self._convert_electricity_units(
                    electricity_data.quantity, 
                    electricity_data.unit, 
                    'mwh'
                )
                
                # Reduce grid electricity by on-site renewable generation
                net_grid_electricity = max(0, electricity_mwh - onsite_renewable_mwh)
                reduction_factor = net_grid_electricity / electricity_mwh if electricity_mwh > 0 else 0
                
                co2_emissions = co2_emissions * reduction_factor if co2_emissions else None
                co2e_emissions = co2e_emissions * reduction_factor
                
                logger.info(f"Applied on-site renewable offset: {onsite_renewable_mwh} MWh, {reduction_factor:.3f} factor")
            
            # Grid renewable percentage (if utility provides specific data)
            grid_renewable_pct = additional_data.get('grid_renewable_percentage')
            if grid_renewable_pct is not None:
                # This would typically be reflected in the emission factor already,
                # but can be used for validation or adjustment
                logger.info(f"Grid renewable percentage: {grid_renewable_pct}%")
        
        return co2_emissions, co2e_emissions
    
    async def _validate_calculation_request(self, request: Scope2CalculationRequest) -> CalculationValidationResult:
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
            factor = await self._get_electricity_emission_factor(region, request.calculation_method)
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
        """Enhanced data quality score calculation for electricity consumption"""
        if not electricity_data:
            return 0.0
        
        total_weighted_score = 0.0
        total_weight = 0.0
        
        for consumption in electricity_data:
            # Base quality score (electricity typically has higher base scores)
            quality_scores = {
                'measured': 95,      # Smart meters, utility bills
                'calculated': 85,    # Calculated from sub-meters
                'estimated': 70,     # Engineering estimates
                'default': 60
            }
            
            base_score = quality_scores.get(consumption.data_quality or 'measured', 60)
            
            # Apply modifiers based on data completeness
            modifiers = 0
            
            # Data source modifier (electricity-specific)
            if consumption.data_source:
                source_lower = consumption.data_source.lower()
                if 'smart meter' in source_lower or 'utility bill' in source_lower:
                    modifiers += 15  # High-quality electricity sources
                elif 'sub-meter' in source_lower or 'building meter' in source_lower:
                    modifiers += 10
                elif 'estimate' in source_lower:
                    modifiers -= 10
            
            # Location specificity modifier (important for regional factors)
            if consumption.location:
                if len(consumption.location) > 15:  # Detailed location with state/region
                    modifiers += 10
                elif len(consumption.location) > 5:  # Basic location
                    modifiers += 5
            
            # Measurement method modifier
            if consumption.measurement_method:
                method_lower = consumption.measurement_method.lower()
                if 'continuous' in method_lower or 'smart meter' in method_lower:
                    modifiers += 15
                elif 'monthly' in method_lower or 'periodic' in method_lower:
                    modifiers += 10
                elif 'annual' in method_lower:
                    modifiers += 5
            
            # Time period specificity (electricity billing cycles)
            if consumption.activity_period_start and consumption.activity_period_end:
                period_days = (consumption.activity_period_end - consumption.activity_period_start).days
                if period_days <= 31:  # Monthly billing
                    modifiers += 10
                elif period_days <= 92:  # Quarterly
                    modifiers += 5
            
            # Renewable energy data bonus
            if consumption.additional_data and consumption.additional_data.get('renewable_percentage') is not None:
                modifiers += 5  # Bonus for renewable energy tracking
            
            # Calculate final score for this consumption
            final_score = min(100, max(0, base_score + modifiers))
            
            # Weight by quantity (larger consumption has more impact)
            weight = consumption.quantity if consumption.quantity > 0 else 1.0
            total_weighted_score += final_score * weight
            total_weight += weight
        
        return total_weighted_score / total_weight if total_weight > 0 else 75.0
    
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
        """Generate comprehensive recommendations for improving Scope 2 calculations"""
        recommendations = []
        
        # Location-based recommendations (critical for regional factors)
        missing_locations = sum(1 for consumption in electricity_data if not consumption.location)
        if missing_locations > 0:
            recommendations.append(f"📍 Specify locations for {missing_locations} electricity consumption items for accurate regional eGRID factors - can impact emissions by ±50%")
        
        # Data quality improvements
        estimated_count = sum(1 for consumption in electricity_data if consumption.data_quality == 'estimated')
        if estimated_count > 0:
            recommendations.append(f"🎯 Obtain utility bills or smart meter data for {estimated_count} estimated consumption items to improve accuracy by up to 25%")
        
        # Smart meter recommendations
        non_continuous = sum(1 for consumption in electricity_data 
                           if not consumption.measurement_method or 'continuous' not in consumption.measurement_method.lower())
        if non_continuous > 0:
            recommendations.append(f"📊 Consider smart meter installation for {non_continuous} locations to enable continuous monitoring and better data quality")
        
        # Data source improvements
        missing_sources = sum(1 for consumption in electricity_data if not consumption.data_source)
        if missing_sources > 0:
            recommendations.append(f"📋 Add data sources for {missing_sources} electricity consumption items for better audit trail")
        
        # Regional accuracy recommendations
        regions_detected = set()
        for consumption in electricity_data:
            if consumption.location:
                region = self._determine_electricity_region(consumption.location)
                regions_detected.add(region)
        
        if len(regions_detected) > 3:
            recommendations.append(f"🗺️ Multiple electricity regions detected ({len(regions_detected)}). Consider region-specific tracking for better accuracy")
        
        # Method-specific recommendations
        if calculation_method == "location_based":
            recommendations.append("⚡ Consider implementing market-based method if you have renewable energy certificates or power purchase agreements")
            recommendations.append("🌱 Track renewable energy purchases (RECs, PPAs, green tariffs) to enable market-based calculations")
            recommendations.append("🏭 Document any on-site renewable generation to offset grid electricity consumption")
            
        elif calculation_method == "market_based":
            recommendations.append("📜 Ensure proper documentation for renewable energy claims and certificates")
            recommendations.append("✅ Verify renewable energy certificates (RECs) are properly retired and tracked")
            recommendations.append("🤝 Document power purchase agreements (PPAs) with specific emission factors")
            recommendations.append("💚 Track green tariff programs and utility renewable energy options")
        
        # Renewable energy data recommendations
        has_renewable_data = any(
            consumption.additional_data and (
                consumption.additional_data.get('renewable_percentage') is not None or
                consumption.additional_data.get('recs_mwh') is not None or
                consumption.additional_data.get('ppa_emission_factor') is not None
            )
            for consumption in electricity_data
        )
        
        if not has_renewable_data and calculation_method == "market_based":
            recommendations.append("🔋 Add renewable energy data (RECs, PPAs, green tariffs) to leverage market-based method benefits")
        
        # Time granularity recommendations
        annual_periods = sum(1 for consumption in electricity_data 
                           if consumption.activity_period_start and consumption.activity_period_end 
                           and (consumption.activity_period_end - consumption.activity_period_start).days > 365)
        if annual_periods > 0:
            recommendations.append(f"📅 Break down {annual_periods} annual electricity consumption periods into monthly data for seasonal accuracy")
        
        # Large consumption recommendations
        if electricity_data:
            sorted_consumption = sorted(electricity_data, key=lambda x: x.quantity, reverse=True)
            top_consumers = sorted_consumption[:3]  # Top 3 largest consumers
            
            for i, consumption in enumerate(top_consumers):
                if consumption.data_quality == 'estimated':
                    recommendations.append(f"⚡ High-consumption location #{i+1} uses estimated data - prioritize smart meter installation for maximum accuracy improvement")
        
        # Utility program recommendations
        recommendations.append("💡 Investigate utility renewable energy programs and green pricing options")
        recommendations.append("🔌 Consider demand response programs to optimize electricity usage and costs")
        
        # Scope 2 specific compliance recommendations
        recommendations.append("📊 Ensure electricity consumption data covers all facilities and subsidiaries for complete Scope 2 inventory")
        recommendations.append("🏛️ Verify all electricity data sources are auditable and SEC-compliant for climate disclosure requirements")
        recommendations.append("🔄 Implement dual reporting (location-based AND market-based) as recommended by GHG Protocol")
        
        # eGRID factor recommendations
        recommendations.append("✅ Verify EPA eGRID factors are current - system automatically uses latest available regional factors")
        
        return recommendations
        regions = set(self._determine_electricity_region(c.location) for c in electricity_data)
        if len(regions) > 1:
            recommendations.append(f"🗺️ Multiple electricity regions detected ({len(regions)}) - ensure location accuracy for optimal regional factors")
        
        # Smart meter recommendations
        no_smart_meter = sum(1 for consumption in electricity_data 
                           if not consumption.data_source or 'smart meter' not in consumption.data_source.lower())
        if no_smart_meter > 0:
            recommendations.append(f"📊 Consider smart meter installation for {no_smart_meter} consumption points for continuous monitoring")
        
        # SEC compliance
        recommendations.append("🏛️ Ensure all electricity data sources are auditable and documentation is SEC-compliant")
        recommendations.append("✅ Verify EPA eGRID factors are current - system uses latest available regional factors")
        
        # Market-based method specific
        if calculation_method == "market_based":
            recommendations.append("🔄 Consider dual reporting (location-based and market-based) for comprehensive disclosure")
        
        return recommendations
    
    def _generate_calculation_insights(
        self, 
        electricity_data: List[ActivityDataInput], 
        total_co2e: float,
        emission_factors_used: Dict[str, Any],
        calculation_method: str
    ) -> Dict[str, Any]:
        """Generate detailed insights about the Scope 2 calculation"""
        
        insights = {
            "summary": {},
            "breakdown": {},
            "quality_analysis": {},
            "benchmarks": {},
            "method_analysis": {},
            "recommendations": self._generate_recommendations(electricity_data, calculation_method)
        }
        
        # Summary statistics
        insights["summary"] = {
            "total_consumption_items": len(electricity_data),
            "total_co2e_tonnes": round(total_co2e, 2),
            "average_co2e_per_item": round(total_co2e / len(electricity_data), 2) if electricity_data else 0,
            "regions_count": len(set(self._determine_electricity_region(item.location) for item in electricity_data if item.location)),
            "calculation_method": calculation_method,
            "data_sources_count": len(set(item.data_source for item in electricity_data if item.data_source))
        }
        
        # Method-specific analysis
        insights["method_analysis"] = {
            "method_used": calculation_method,
            "renewable_data_available": any(
                item.additional_data and (
                    item.additional_data.get('recs_mwh') or
                    item.additional_data.get('ppa_emission_factor') or
                    item.additional_data.get('green_tariff_percentage')
                ) for item in electricity_data
            ),
            "regional_diversity": len(set(self._determine_electricity_region(item.location) for item in electricity_data if item.location))
        }
        
        return insights
        
    
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
    
    def _get_user_by_id(self, user_id: str):
        """Get user by ID - placeholder for actual user service"""
        # This would integrate with the actual user service
        return self.db.query(User).filter(User.id == user_id).first()
    
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
