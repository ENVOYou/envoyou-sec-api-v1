"""
Scope 1 Emissions Calculator Service
Direct GHG emissions from sources owned or controlled by the company
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.audit_logger import AuditLogger
from app.models.emissions import (
    ActivityData,
    CalculationAuditTrail,
    Company,
    CompanyEntity,
    EmissionsCalculation,
)
from app.models.epa_data import EmissionFactor
from app.schemas.emissions import (
    ActivityDataInput,
    CalculationValidationResult,
    EmissionsCalculationResponse,
    Scope1CalculationRequest,
)
from app.services.epa_cache_service import EPACachedService

logger = logging.getLogger(__name__)


class Scope1EmissionsCalculator:
    """Service for calculating Scope 1 (direct) GHG emissions"""

    def __init__(self, db: Session):
        self.db = db
        self.audit_logger = AuditLogger(db)
        self.epa_service = EPACachedService(db)

        # GWP values for GHG gases (AR5, 100-year)
        self.gwp_values = {
            "co2": 1.0,
            "ch4": 28.0,  # Methane
            "n2o": 265.0,  # Nitrous oxide
        }

    async def calculate_scope1_emissions(
        self, request: Scope1CalculationRequest, user_id: str
    ) -> EmissionsCalculationResponse:
        """Calculate Scope 1 emissions from activity data"""
        try:
            logger.info(f"Starting Scope 1 calculation: {request.calculation_name}")
            start_time = datetime.utcnow()

            # Validate request
            validation_result = await self._validate_calculation_request(request)
            if not validation_result.is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Validation failed: {validation_result.errors}",
                )

            # Verify company and entity exist
            company = self._verify_company_exists(request.company_id)
            entity = None
            if request.entity_id:
                entity = self._verify_entity_exists(
                    request.entity_id, request.company_id
                )

            # Generate unique calculation code
            calculation_code = self._generate_calculation_code(
                "SC1", company.ticker or company.name
            )

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
                emission_factors_used={},  # Initialize as empty dict
                source_documents=request.source_documents or [],
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
                    activity_result = await self._calculate_activity_emissions(
                        activity_input, calculation.id
                    )

                    # Add to totals
                    total_co2 += activity_result["co2_emissions"] or 0.0
                    total_ch4 += activity_result["ch4_emissions"] or 0.0
                    total_n2o += activity_result["n2o_emissions"] or 0.0
                    total_co2e += activity_result["co2e_emissions"]

                    # Track emission factors used
                    emission_factors_used[activity_result["activity_type"]] = {
                        "factor_id": activity_result["emission_factor_id"],
                        "factor_value": activity_result["emission_factor_value"],
                        "factor_source": activity_result["emission_factor_source"],
                        "factor_unit": activity_result["emission_factor_unit"],
                    }

                except Exception as e:
                    error_msg = (
                        f"Error calculating {activity_input.activity_type}: {str(e)}"
                    )
                    validation_errors.append(error_msg)
                    logger.error(error_msg)

            # Calculate total CO2e using GWP values
            calculated_co2e = (
                total_co2 * self.gwp_values["co2"]
                + total_ch4 * self.gwp_values["ch4"]
                + total_n2o * self.gwp_values["n2o"]
            )

            # Convert from kg to metric tons CO2e
            calculated_co2e_mt = calculated_co2e / 1000.0

            # Update calculation with results
            calculation_duration = (datetime.utcnow() - start_time).total_seconds()

            calculation.total_co2 = total_co2 / 1000.0  # Convert kg to metric tons
            calculation.total_ch4 = total_ch4 / 1000.0  # Convert kg to metric tons
            calculation.total_n2o = total_n2o / 1000.0  # Convert kg to metric tons
            calculation.total_co2e = calculated_co2e_mt
            calculation.emission_factors_used = emission_factors_used
            calculation.calculation_duration_seconds = calculation_duration
            calculation.validation_errors = validation_errors
            calculation.validation_warnings = validation_warnings

            # Set status based on validation results
            if validation_errors:
                calculation.status = "failed"
            else:
                calculation.status = "completed"
                calculation.data_quality_score = self._calculate_data_quality_score(
                    request.activity_data
                )
                calculation.uncertainty_percentage = self._estimate_uncertainty(
                    request.activity_data
                )

            self.db.commit()
            self.db.refresh(calculation)

            # Create audit trail entry
            self._create_audit_trail_entry(
                calculation.id,
                "calculation_completed",
                f"Scope 1 calculation completed: {calculated_co2e_mt:.2f} tCO2e",
                user_id,
            )

            # Log calculation for audit
            self.audit_logger.log_calculation_event(
                user=self._get_user_by_id(user_id),
                calculation_type="scope_1",
                input_data=request.dict(),
                output_data={
                    "total_co2e": calculated_co2e_mt,
                    "total_co2": total_co2,
                    "total_ch4": total_ch4,
                    "total_n2o": total_n2o,
                },
                emission_factors_used=emission_factors_used,
                processing_time_ms=int(calculation_duration * 1000),
            )

            logger.info(
                f"Scope 1 calculation completed: {calculation_code}, {calculated_co2e_mt:.2f} tCO2e"
            )

            # Return response
            # Generate calculation insights
            calculation_insights = self._generate_calculation_insights(
                request.activity_data, calculated_co2e_mt, emission_factors_used
            )

            # Store insights in calculation
            calculation.calculation_insights = calculation_insights
            self.db.commit()

            return self._build_calculation_response(calculation)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in Scope 1 calculation: {str(e)}")
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Calculation failed: {str(e)}",
            )

    async def _calculate_activity_emissions(
        self, activity_input: ActivityDataInput, calculation_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Calculate emissions for a single activity"""

        # Get appropriate emission factor
        emission_factor = await self._get_emission_factor(
            activity_input.activity_type, activity_input.fuel_type
        )

        if not emission_factor:
            raise ValueError(
                f"No emission factor found for {activity_input.activity_type} - {activity_input.fuel_type}"
            )

        # Convert units if necessary
        converted_quantity = self._convert_units(
            activity_input.quantity, activity_input.unit, emission_factor.unit
        )

        # Calculate emissions
        co2_emissions = (
            converted_quantity * emission_factor.co2_factor
            if emission_factor.co2_factor
            else None
        )
        ch4_emissions = (
            converted_quantity * emission_factor.ch4_factor
            if emission_factor.ch4_factor
            else None
        )
        n2o_emissions = (
            converted_quantity * emission_factor.n2o_factor
            if emission_factor.n2o_factor
            else None
        )
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
            additional_data=activity_input.additional_data,
        )

        self.db.add(activity_data)

        return {
            "activity_type": activity_input.activity_type,
            "co2_emissions": co2_emissions,
            "ch4_emissions": ch4_emissions,
            "n2o_emissions": n2o_emissions,
            "co2e_emissions": co2e_emissions,
            "emission_factor_id": str(emission_factor.id),
            "emission_factor_value": emission_factor.co2e_factor,
            "emission_factor_source": emission_factor.source,
            "emission_factor_unit": emission_factor.unit,
        }

    async def _get_emission_factor(
        self, activity_type: str, fuel_type: Optional[str]
    ) -> Optional[EmissionFactor]:
        """Get appropriate EPA emission factor for activity using intelligent selection"""
        try:
            # Use the enhanced factor selection method
            return await self._select_best_emission_factor(activity_type, fuel_type)

        except Exception as e:
            logger.error(f"Error getting emission factor: {str(e)}")
            return None

    async def _select_best_emission_factor(
        self,
        activity_type: str,
        fuel_type: Optional[str],
        location: Optional[str] = None,
    ) -> Optional[EmissionFactor]:
        """Intelligently select the best EPA emission factor for the activity"""

        # Define factor selection priority
        factor_priorities = {
            "fuel_combustion": {
                "natural_gas": ["EPA_GHGRP", "EPA_AP42"],
                "diesel": ["EPA_GHGRP", "EPA_AP42"],
                "gasoline": ["EPA_GHGRP", "EPA_AP42"],
                "propane": ["EPA_GHGRP", "EPA_AP42"],
                "coal": ["EPA_GHGRP", "EPA_AP42"],
                "fuel_oil": ["EPA_GHGRP", "EPA_AP42"],
            }
        }

        # Try each source in priority order
        sources_to_try = factor_priorities.get(activity_type, {}).get(
            fuel_type, ["EPA_GHGRP", "EPA_AP42"]
        )

        for source in sources_to_try:
            try:
                # Get factors from cached service
                factors = await self.epa_service.get_emission_factors(
                    source=source, category="fuel_combustion", fuel_type=fuel_type
                )

                if factors:
                    # Find the best matching factor
                    best_factor = self._rank_emission_factors(
                        factors, activity_type, fuel_type
                    )
                    if best_factor:
                        # Convert to database model
                        db_factor = (
                            self.db.query(EmissionFactor)
                            .filter(
                                EmissionFactor.factor_code == best_factor.factor_code
                            )
                            .first()
                        )

                        if db_factor:
                            logger.info(
                                f"Selected emission factor: {db_factor.factor_code} from {source}"
                            )
                            return db_factor

            except Exception as e:
                logger.warning(f"Error getting factors from {source}: {str(e)}")
                continue

        # Fallback to direct database query with intelligent selection
        return await self._fallback_factor_selection(activity_type, fuel_type)

    def _rank_emission_factors(
        self, factors: List, activity_type: str, fuel_type: Optional[str]
    ):
        """Rank emission factors by relevance and quality"""
        if not factors:
            return None

        # Score factors based on multiple criteria
        scored_factors = []

        for factor in factors:
            score = 0

            # Exact fuel type match gets highest score
            if (
                fuel_type
                and hasattr(factor, "fuel_type")
                and factor.fuel_type == fuel_type
            ):
                score += 100

            # Recent publication year gets higher score
            if hasattr(factor, "publication_year") and factor.publication_year:
                current_year = datetime.now().year
                year_diff = current_year - factor.publication_year
                score += max(0, 50 - year_diff)  # Newer factors get higher scores

            # EPA GHGRP source gets preference
            if hasattr(factor, "source") and factor.source == "EPA_GHGRP":
                score += 25

            # Higher CO2e factor values might indicate more comprehensive data
            if hasattr(factor, "co2e_factor") and factor.co2e_factor:
                if factor.co2e_factor > 0:
                    score += 10

            scored_factors.append((factor, score))

        # Sort by score (highest first) and return the best factor
        scored_factors.sort(key=lambda x: x[1], reverse=True)
        return scored_factors[0][0] if scored_factors else None

    async def _fallback_factor_selection(
        self, activity_type: str, fuel_type: Optional[str]
    ) -> Optional[EmissionFactor]:
        """Fallback method for factor selection using database query"""
        try:
            query = self.db.query(EmissionFactor).filter(
                EmissionFactor.is_current == True,
                EmissionFactor.category.in_(["fuel_combustion", "fuel", "combustion"]),
            )

            if fuel_type:
                query = query.filter(EmissionFactor.fuel_type == fuel_type)

            # Order by preference: EPA_GHGRP first, then by publication year
            factors = query.order_by(
                EmissionFactor.source.desc(),  # EPA_GHGRP comes first alphabetically
                EmissionFactor.publication_year.desc(),
            ).all()

            if factors:
                logger.info(f"Using fallback factor: {factors[0].factor_code}")
                return factors[0]

            # Last resort: any current factor
            fallback_factor = (
                self.db.query(EmissionFactor)
                .filter(EmissionFactor.is_current == True)
                .order_by(EmissionFactor.publication_year.desc())
                .first()
            )

            if fallback_factor:
                logger.warning(
                    f"Using last resort factor: {fallback_factor.factor_code}"
                )

            return fallback_factor

        except Exception as e:
            logger.error(f"Error in fallback factor selection: {str(e)}")
            return None

    def _convert_units(self, quantity: float, from_unit: str, to_unit: str) -> float:
        """Enhanced unit conversion for emission factor calculations"""

        # Normalize unit strings
        from_unit_norm = self._normalize_unit(from_unit)
        to_unit_norm = self._normalize_unit(to_unit)

        # If units are the same, no conversion needed
        if from_unit_norm == to_unit_norm:
            return quantity

        # Comprehensive conversion factors
        conversion_factors = {
            # Volume conversions
            ("gallons", "liters"): 3.78541,
            ("liters", "gallons"): 0.264172,
            ("gallons", "m3"): 0.00378541,
            ("m3", "gallons"): 264.172,
            ("liters", "m3"): 0.001,
            ("m3", "liters"): 1000.0,
            # Energy conversions
            ("mmbtu", "gj"): 1.05506,
            ("gj", "mmbtu"): 0.947817,
            ("mmbtu", "mj"): 1055.06,
            ("mj", "mmbtu"): 0.000947817,
            ("kwh", "mj"): 3.6,
            ("mj", "kwh"): 0.277778,
            ("kwh", "mmbtu"): 0.00341214,
            ("mmbtu", "kwh"): 293.071,
            ("therm", "mmbtu"): 0.1,
            ("mmbtu", "therm"): 10.0,
            # Mass conversions
            ("tons", "kg"): 1000.0,
            ("kg", "tons"): 0.001,
            ("tons", "lbs"): 2204.62,
            ("lbs", "tons"): 0.000453592,
            ("kg", "lbs"): 2.20462,
            ("lbs", "kg"): 0.453592,
            ("tonnes", "kg"): 1000.0,
            ("kg", "tonnes"): 0.001,
            ("tonnes", "tons"): 1.10231,  # Metric to US tons
            ("tons", "tonnes"): 0.907185,  # US to metric tons
            # Distance conversions
            ("miles", "km"): 1.60934,
            ("km", "miles"): 0.621371,
            ("feet", "meters"): 0.3048,
            ("meters", "feet"): 3.28084,
            # Area conversions
            ("acres", "hectares"): 0.404686,
            ("hectares", "acres"): 2.47105,
            ("sq_ft", "sq_m"): 0.092903,
            ("sq_m", "sq_ft"): 10.7639,
        }

        # Look for direct conversion
        conversion_key = (from_unit_norm, to_unit_norm)
        if conversion_key in conversion_factors:
            converted_value = quantity * conversion_factors[conversion_key]
            logger.debug(
                f"Converted {quantity} {from_unit} to {converted_value} {to_unit}"
            )
            return converted_value

        # Try reverse conversion
        reverse_key = (to_unit_norm, from_unit_norm)
        if reverse_key in conversion_factors:
            converted_value = quantity / conversion_factors[reverse_key]
            logger.debug(
                f"Converted {quantity} {from_unit} to {converted_value} {to_unit} (reverse)"
            )
            return converted_value

        # Check for multi-step conversions (e.g., gallons -> liters -> m3)
        converted_value = self._try_multi_step_conversion(
            quantity, from_unit_norm, to_unit_norm, conversion_factors
        )
        if converted_value is not None:
            return converted_value

        # If no conversion found, log warning and return original
        logger.warning(
            f"No unit conversion found for {from_unit} to {to_unit}, using original quantity"
        )
        return quantity

    def _normalize_unit(self, unit: str) -> str:
        """Normalize unit strings for consistent matching"""
        if not unit:
            return ""

        # Convert to lowercase and remove common variations
        normalized = unit.lower().strip()

        # Handle common unit variations
        unit_mappings = {
            "gallon": "gallons",
            "gal": "gallons",
            "liter": "liters",
            "l": "liters",
            "kilogram": "kg",
            "kilogramme": "kg",
            "pound": "lbs",
            "lb": "lbs",
            "tonne": "tonnes",
            "metric_ton": "tonnes",
            "short_ton": "tons",
            "ton": "tons",
            "cubic_meter": "m3",
            "cubic_metre": "m3",
            "m^3": "m3",
            "megajoule": "mj",
            "gigajoule": "gj",
            "kilowatt_hour": "kwh",
            "kw_h": "kwh",
            "kwhr": "kwh",
            "million_btu": "mmbtu",
            "mmbtu/hr": "mmbtu",
            "kilometer": "km",
            "kilometre": "km",
            "mile": "miles",
            "foot": "feet",
            "ft": "feet",
            "meter": "meters",
            "metre": "meters",
            "m": "meters",
            "hectare": "hectares",
            "ha": "hectares",
            "acre": "acres",
            "square_foot": "sq_ft",
            "sq_foot": "sq_ft",
            "ft2": "sq_ft",
            "square_meter": "sq_m",
            "square_metre": "sq_m",
            "m2": "sq_m",
        }

        return unit_mappings.get(normalized, normalized)

    def _try_multi_step_conversion(
        self,
        quantity: float,
        from_unit: str,
        to_unit: str,
        conversion_factors: Dict[Tuple[str, str], float],
    ) -> Optional[float]:
        """Try to find a multi-step conversion path"""

        # Define common intermediate units for different categories
        intermediate_units = {
            "volume": ["liters", "m3"],
            "energy": ["mj", "gj"],
            "mass": ["kg"],
            "distance": ["meters"],
            "area": ["sq_m"],
        }

        # Try each category of intermediate units
        for category, intermediates in intermediate_units.items():
            for intermediate in intermediates:
                # Try: from_unit -> intermediate -> to_unit
                step1_key = (from_unit, intermediate)
                step2_key = (intermediate, to_unit)

                if step1_key in conversion_factors and step2_key in conversion_factors:
                    intermediate_value = quantity * conversion_factors[step1_key]
                    final_value = intermediate_value * conversion_factors[step2_key]
                    logger.debug(
                        f"Multi-step conversion: {quantity} {from_unit} -> {intermediate_value} {intermediate} -> {final_value} {to_unit}"
                    )
                    return final_value

        return None

    async def _validate_calculation_request(
        self, request: Scope1CalculationRequest
    ) -> CalculationValidationResult:
        """Validate calculation request"""
        errors = []
        warnings = []

        # Check if company exists
        company = (
            self.db.query(Company).filter(Company.id == request.company_id).first()
        )
        if not company:
            errors.append(f"Company {request.company_id} not found")

        # Check entity if provided
        if request.entity_id:
            entity = (
                self.db.query(CompanyEntity)
                .filter(
                    CompanyEntity.id == request.entity_id,
                    CompanyEntity.company_id == request.company_id,
                )
                .first()
            )
            if not entity:
                errors.append(
                    f"Entity {request.entity_id} not found for company {request.company_id}"
                )

        # Validate activity data
        if not request.activity_data:
            errors.append("At least one activity data item is required")

        for i, activity in enumerate(request.activity_data):
            if activity.quantity <= 0:
                errors.append(f"Activity {i+1}: Quantity must be positive")

            if not activity.unit:
                errors.append(f"Activity {i+1}: Unit is required")

            # Check if emission factor exists for this activity
            factor = await self._get_emission_factor(
                activity.activity_type, activity.fuel_type
            )
            if not factor:
                warnings.append(
                    f"Activity {i+1}: No emission factor found for {activity.activity_type} - {activity.fuel_type}"
                )

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
            recommendations=self._generate_recommendations(request.activity_data),
        )

    def _calculate_data_completeness(
        self, activity_data: List[ActivityDataInput]
    ) -> float:
        """Calculate data completeness score"""
        total_fields = 0
        completed_fields = 0

        for activity in activity_data:
            total_fields += 8  # Number of key fields

            if activity.quantity:
                completed_fields += 1
            if activity.unit:
                completed_fields += 1
            if activity.activity_type:
                completed_fields += 1
            if activity.fuel_type:
                completed_fields += 1
            if activity.location:
                completed_fields += 1
            if activity.data_source:
                completed_fields += 1
            if activity.data_quality:
                completed_fields += 1
            if activity.measurement_method:
                completed_fields += 1

        return (completed_fields / total_fields) * 100 if total_fields > 0 else 0

    def _calculate_data_quality_score(
        self, activity_data: List[ActivityDataInput]
    ) -> float:
        """Enhanced data quality score calculation"""
        if not activity_data:
            return 0.0

        total_weighted_score = 0.0
        total_weight = 0.0

        for activity in activity_data:
            # Base quality score
            quality_scores = {
                "measured": 100,
                "calculated": 80,
                "estimated": 60,
                "default": 40,
            }

            base_score = quality_scores.get(activity.data_quality or "estimated", 40)

            # Apply modifiers based on data completeness
            modifiers = 0

            # Data source modifier
            if activity.data_source:
                if (
                    "meter" in activity.data_source.lower()
                    or "invoice" in activity.data_source.lower()
                ):
                    modifiers += 10  # High-quality sources
                elif "estimate" in activity.data_source.lower():
                    modifiers -= 10  # Lower quality

            # Location specificity modifier
            if activity.location:
                if len(activity.location) > 10:  # Detailed location
                    modifiers += 5
                else:
                    modifiers += 2  # Basic location

            # Measurement method modifier
            if activity.measurement_method:
                if "continuous" in activity.measurement_method.lower():
                    modifiers += 15
                elif "periodic" in activity.measurement_method.lower():
                    modifiers += 10
                elif "annual" in activity.measurement_method.lower():
                    modifiers += 5

            # Time period specificity
            if activity.activity_period_start and activity.activity_period_end:
                period_days = (
                    activity.activity_period_end - activity.activity_period_start
                ).days
                if period_days <= 31:  # Monthly or better
                    modifiers += 10
                elif period_days <= 92:  # Quarterly
                    modifiers += 5

            # Calculate final score for this activity
            final_score = min(100, max(0, base_score + modifiers))

            # Weight by quantity (larger activities have more impact on overall score)
            weight = activity.quantity if activity.quantity > 0 else 1.0
            total_weighted_score += final_score * weight
            total_weight += weight

        return total_weighted_score / total_weight if total_weight > 0 else 50.0

    def _estimate_uncertainty(self, activity_data: List[ActivityDataInput]) -> float:
        """Estimate uncertainty percentage for the calculation"""
        # Simplified uncertainty estimation
        uncertainty_by_quality = {
            "measured": 5.0,
            "calculated": 15.0,
            "estimated": 30.0,
        }

        total_uncertainty = 0
        count = 0

        for activity in activity_data:
            quality = activity.data_quality or "estimated"
            total_uncertainty += uncertainty_by_quality.get(quality, 35.0)
            count += 1

        return total_uncertainty / count if count > 0 else 25.0

    def _generate_recommendations(
        self, activity_data: List[ActivityDataInput]
    ) -> List[str]:
        """Generate comprehensive recommendations for improving data quality and accuracy"""
        recommendations = []

        # Data quality recommendations
        estimated_count = sum(
            1 for activity in activity_data if activity.data_quality == "estimated"
        )
        if estimated_count > 0:
            recommendations.append(
                f"🎯 Improve {estimated_count} estimated data points with measured values to increase accuracy by up to 40%"
            )

        # Data source recommendations
        missing_sources = sum(
            1 for activity in activity_data if not activity.data_source
        )
        if missing_sources > 0:
            recommendations.append(
                f"📋 Add data sources for {missing_sources} activity items for better audit trail"
            )

        # Location specificity
        missing_locations = sum(
            1 for activity in activity_data if not activity.location
        )
        if missing_locations > 0:
            recommendations.append(
                f"📍 Specify locations for {missing_locations} activities for regional emission factor accuracy"
            )

        # Measurement method improvements
        missing_methods = sum(
            1 for activity in activity_data if not activity.measurement_method
        )
        if missing_methods > 0:
            recommendations.append(
                f"🔬 Define measurement methods for {missing_methods} activities to improve data quality score"
            )

        # Time period granularity
        annual_periods = sum(
            1
            for activity in activity_data
            if activity.activity_period_start
            and activity.activity_period_end
            and (activity.activity_period_end - activity.activity_period_start).days
            > 365
        )
        if annual_periods > 0:
            recommendations.append(
                f"📅 Consider breaking down {annual_periods} annual periods into monthly/quarterly data for better accuracy"
            )

        # Large emission sources
        if activity_data:
            sorted_activities = sorted(
                activity_data, key=lambda x: x.quantity, reverse=True
            )
            top_activities = sorted_activities[:3]  # Top 3 largest activities

            for i, activity in enumerate(top_activities):
                if activity.data_quality == "estimated":
                    recommendations.append(
                        f"⚡ High-impact activity #{i+1} ({activity.activity_type}) uses estimated data - prioritize measurement for maximum accuracy improvement"
                    )

        # Fuel type diversity
        fuel_types = set(
            activity.fuel_type for activity in activity_data if activity.fuel_type
        )
        if len(fuel_types) > 5:
            recommendations.append(
                "🔄 Consider consolidating similar fuel types or implementing fuel-specific tracking systems"
            )

        # Missing documentation
        missing_docs = sum(
            1
            for activity in activity_data
            if not activity.notes and not activity.additional_data
        )
        if missing_docs > 0:
            recommendations.append(
                f"📝 Add documentation/notes for {missing_docs} activities to support audit requirements"
            )

        # EPA factor availability
        recommendations.append(
            "✅ Verify EPA emission factors are current - system will automatically use latest available factors"
        )

        # SEC compliance
        recommendations.append(
            "🏛️ Ensure all data sources are auditable and documentation is SEC-compliant for climate disclosure requirements"
        )

        return recommendations

    def _generate_calculation_insights(
        self,
        activity_data: List[ActivityDataInput],
        total_co2e: float,
        emission_factors_used: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate detailed insights about the calculation"""

        insights = {
            "summary": {},
            "breakdown": {},
            "quality_analysis": {},
            "benchmarks": {},
            "recommendations": self._generate_recommendations(activity_data),
        }

        # Summary statistics
        insights["summary"] = {
            "total_activities": len(activity_data),
            "total_co2e_tonnes": round(total_co2e, 2),
            "average_co2e_per_activity": round(total_co2e / len(activity_data), 2)
            if activity_data
            else 0,
            "fuel_types_count": len(
                set(a.fuel_type for a in activity_data if a.fuel_type)
            ),
            "locations_count": len(
                set(a.location for a in activity_data if a.location)
            ),
            "data_sources_count": len(
                set(a.data_source for a in activity_data if a.data_source)
            ),
        }

        # Emissions breakdown by fuel type
        fuel_breakdown = {}
        for activity in activity_data:
            fuel_type = activity.fuel_type or "unknown"
            if fuel_type not in fuel_breakdown:
                fuel_breakdown[fuel_type] = {
                    "activity_count": 0,
                    "total_quantity": 0,
                    "estimated_co2e": 0,
                }

            fuel_breakdown[fuel_type]["activity_count"] += 1
            fuel_breakdown[fuel_type]["total_quantity"] += activity.quantity
            # Rough estimate - would be more accurate with actual calculation results
            fuel_breakdown[fuel_type]["estimated_co2e"] += (
                activity.quantity * 0.05
            )  # Placeholder

        insights["breakdown"]["by_fuel_type"] = fuel_breakdown

        # Data quality analysis
        quality_distribution = {}
        for activity in activity_data:
            quality = activity.data_quality or "estimated"
            quality_distribution[quality] = quality_distribution.get(quality, 0) + 1

        insights["quality_analysis"] = {
            "quality_distribution": quality_distribution,
            "measured_percentage": round(
                (quality_distribution.get("measured", 0) / len(activity_data)) * 100, 1
            )
            if activity_data
            else 0,
            "estimated_percentage": round(
                (quality_distribution.get("estimated", 0) / len(activity_data)) * 100, 1
            )
            if activity_data
            else 0,
            "data_completeness_score": self._calculate_data_completeness(activity_data),
            "overall_quality_score": self._calculate_data_quality_score(activity_data),
        }

        # Simple benchmarks (would be enhanced with industry data)
        insights["benchmarks"] = {
            "emissions_intensity": {
                "co2e_per_activity": round(total_co2e / len(activity_data), 2)
                if activity_data
                else 0,
                "benchmark_category": self._categorize_emissions_intensity(
                    total_co2e, len(activity_data)
                ),
            },
            "data_quality_rating": self._rate_data_quality(
                insights["quality_analysis"]["overall_quality_score"]
            ),
            "completeness_rating": self._rate_completeness(
                insights["quality_analysis"]["data_completeness_score"]
            ),
        }

        # EPA factors used summary
        insights["epa_factors"] = {
            "factors_used_count": len(emission_factors_used),
            "sources": list(
                set(
                    factor.get("factor_source", "unknown")
                    for factor in emission_factors_used.values()
                )
            ),
            "latest_factor_year": max(
                [2024] + [2020]
            ),  # Placeholder - would extract from actual factors
        }

        return insights

    def _categorize_emissions_intensity(
        self, total_co2e: float, activity_count: int
    ) -> str:
        """Categorize emissions intensity for benchmarking"""
        if activity_count == 0:
            return "no_data"

        intensity = total_co2e / activity_count

        if intensity < 1.0:
            return "low"
        elif intensity < 10.0:
            return "moderate"
        elif intensity < 50.0:
            return "high"
        else:
            return "very_high"

    def _rate_data_quality(self, quality_score: float) -> str:
        """Rate overall data quality"""
        if quality_score >= 90:
            return "excellent"
        elif quality_score >= 80:
            return "good"
        elif quality_score >= 70:
            return "fair"
        elif quality_score >= 60:
            return "poor"
        else:
            return "very_poor"

    def _rate_completeness(self, completeness_score: float) -> str:
        """Rate data completeness"""
        if completeness_score >= 95:
            return "complete"
        elif completeness_score >= 85:
            return "mostly_complete"
        elif completeness_score >= 70:
            return "partially_complete"
        else:
            return "incomplete"

    def _verify_company_exists(self, company_id: str) -> Company:
        """Verify company exists"""
        company = self.db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company {company_id} not found",
            )
        return company

    def _verify_entity_exists(self, entity_id: str, company_id: str) -> CompanyEntity:
        """Verify entity exists and belongs to company"""
        entity = (
            self.db.query(CompanyEntity)
            .filter(
                CompanyEntity.id == entity_id, CompanyEntity.company_id == company_id
            )
            .first()
        )
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entity {entity_id} not found for company {company_id}",
            )
        return entity

    def _generate_calculation_code(self, prefix: str, company_identifier: str) -> str:
        """Generate unique calculation code with microseconds and UUID for CI/CD safety"""
        import uuid as uuid_lib
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")  # Include microseconds
        company_code = company_identifier[:3].upper() if company_identifier else "UNK"
        unique_suffix = str(uuid_lib.uuid4())[:8]  # Add 8-char UUID for extra uniqueness
        return f"{prefix}-{company_code}-{timestamp}-{unique_suffix}"

    def _create_audit_trail_entry(
        self, calculation_id: uuid.UUID, event_type: str, description: str, user_id: str
    ):
        """Create audit trail entry"""
        audit_entry = CalculationAuditTrail(
            calculation_id=calculation_id,
            event_type=event_type,
            event_description=description,
            user_id=uuid.UUID(user_id),
            user_role="system",  # Would get from user context
            reason="Automated calculation process",
        )
        self.db.add(audit_entry)

    def _get_user_by_id(self, user_id: str):
        """Get user by ID - placeholder for actual user service"""
        # This would integrate with the actual user service
        from app.models.user import User

        return self.db.query(User).filter(User.id == user_id).first()

    def _build_calculation_response(
        self, calculation: EmissionsCalculation
    ) -> EmissionsCalculationResponse:
        """Build calculation response with activity data"""
        # Get activity data
        activity_data = (
            self.db.query(ActivityData)
            .filter(ActivityData.calculation_id == calculation.id)
            .all()
        )

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
            reviewed_by=str(calculation.reviewed_by)
            if calculation.reviewed_by
            else None,
            approved_by=str(calculation.approved_by)
            if calculation.approved_by
            else None,
            calculation_timestamp=calculation.calculation_timestamp,
            calculation_duration_seconds=calculation.calculation_duration_seconds,
            activity_data=[
                {
                    "id": str(ad.id),
                    "activity_type": ad.activity_type,
                    "fuel_type": ad.fuel_type,
                    "activity_description": ad.activity_description,
                    "quantity": ad.quantity,
                    "unit": ad.unit,
                    "location": ad.location,
                    "emission_factor_value": ad.emission_factor_value,
                    "emission_factor_unit": ad.emission_factor_unit,
                    "emission_factor_source": ad.emission_factor_source,
                    "co2_emissions": ad.co2_emissions,
                    "ch4_emissions": ad.ch4_emissions,
                    "n2o_emissions": ad.n2o_emissions,
                    "co2e_emissions": ad.co2e_emissions,
                    "data_quality": ad.data_quality,
                    "notes": ad.notes,
                }
                for ad in activity_data
            ],
            validation_errors=calculation.validation_errors,
            validation_warnings=calculation.validation_warnings,
            created_at=calculation.created_at,
            updated_at=calculation.updated_at,
        )
