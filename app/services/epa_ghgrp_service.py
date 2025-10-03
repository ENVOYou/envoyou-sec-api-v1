"""
EPA GHGRP Data Integration Service
Integrates with EPA Greenhouse Gas Reporting Program database for data validation
and cross-verification of company emissions data
"""

import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.emissions import Company, EmissionsCalculation
from app.models.epa_data import EmissionFactor
from app.services.redis_cache import EPACacheService
from app.core.audit_logger import AuditLogger

logger = logging.getLogger(__name__)


class EPAGHGRPService:
    """Service for EPA GHGRP data integration and validation"""
    
    def __init__(self, db: Session):
        self.db = db
        self.cache_service = EPACacheService()
        self.audit_logger = AuditLogger(db)
        
        # EPA GHGRP API configuration
        self.ghgrp_base_url = "https://api.epa.gov/ghgrp"
        self.api_timeout = 30
        self.max_retries = 3
        self.retry_delay = 2
        
        # Company identification mappings
        self.company_identifiers = {
            "cik": "central_index_key",
            "ticker": "stock_ticker",
            "name": "company_name",
            "ein": "employer_identification_number"
        }
        
        # GHGRP sector mappings to our industry classifications
        self.sector_mappings = {
            "power_plants": "Electric Power Generation",
            "petroleum_refineries": "Petroleum Refining",
            "chemical_manufacturing": "Chemical Manufacturing",
            "cement_production": "Cement Manufacturing",
            "iron_steel": "Iron and Steel Production",
            "aluminum_production": "Aluminum Production",
            "pulp_paper": "Pulp and Paper Manufacturing",
            "glass_production": "Glass Manufacturing",
            "oil_gas_production": "Oil and Gas Production",
            "natural_gas_distribution": "Natural Gas Distribution"
        }
    
    async def search_company_in_ghgrp(
        self,
        company_id: str,
        search_criteria: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Search for company in EPA GHGRP database
        
        Args:
            company_id: Internal company ID
            search_criteria: Additional search criteria (CIK, ticker, name, etc.)
            
        Returns:
            Dict containing GHGRP company data and match confidence
        """
        try:
            # Get company from database
            company = self.db.query(Company).filter(Company.id == company_id).first()
            if not company:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Company {company_id} not found"
                )
            
            # Build search parameters
            search_params = self._build_search_parameters(company, search_criteria)
            
            # Search in GHGRP database
            ghgrp_matches = await self._search_ghgrp_api(search_params)
            
            # Rank and validate matches
            ranked_matches = self._rank_company_matches(company, ghgrp_matches)
            
            # Get best match details
            best_match = None
            if ranked_matches:
                best_match = await self._get_ghgrp_company_details(ranked_matches[0])
            
            search_result = {
                "company_id": company_id,
                "search_timestamp": datetime.utcnow().isoformat(),
                "search_criteria": search_params,
                "total_matches": len(ghgrp_matches),
                "ranked_matches": ranked_matches[:5],  # Top 5 matches
                "best_match": best_match,
                "match_confidence": ranked_matches[0]["confidence_score"] if ranked_matches else 0,
                "ghgrp_reporting_years": best_match.get("reporting_years", []) if best_match else []
            }
            
            # Cache the search result
            cache_key = f"ghgrp_search:{company_id}"
            self.cache_service.cache.set_with_ttl(
                cache_key, 
                search_result, 
                ttl_seconds=24 * 3600  # 24 hours
            )
            
            logger.info(f"GHGRP search completed for company {company_id}: {len(ghgrp_matches)} matches found")
            
            return search_result
            
        except Exception as e:
            logger.error(f"Error searching company in GHGRP: {str(e)}")
            raise
    
    async def get_ghgrp_emissions_data(
        self,
        company_id: str,
        reporting_year: int,
        ghgrp_facility_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get emissions data from GHGRP for a specific company and year
        
        Args:
            company_id: Internal company ID
            reporting_year: Year for emissions data
            ghgrp_facility_id: Specific GHGRP facility ID (optional)
            
        Returns:
            Dict containing GHGRP emissions data
        """
        try:
            # First search for company if not provided facility ID
            if not ghgrp_facility_id:
                search_result = await self.search_company_in_ghgrp(company_id)
                if not search_result["best_match"]:
                    return {
                        "company_id": company_id,
                        "reporting_year": reporting_year,
                        "ghgrp_data_available": False,
                        "error": "Company not found in GHGRP database"
                    }
                ghgrp_facility_id = search_result["best_match"]["facility_id"]
            
            # Get emissions data from GHGRP API
            emissions_data = await self._get_ghgrp_emissions_api(ghgrp_facility_id, reporting_year)
            
            # Process and normalize the data
            processed_data = self._process_ghgrp_emissions_data(emissions_data)
            
            result = {
                "company_id": company_id,
                "reporting_year": reporting_year,
                "ghgrp_facility_id": ghgrp_facility_id,
                "ghgrp_data_available": True,
                "data_retrieved_at": datetime.utcnow().isoformat(),
                "emissions_data": processed_data,
                "data_quality": self._assess_ghgrp_data_quality(processed_data),
                "scope_coverage": self._analyze_scope_coverage(processed_data)
            }
            
            # Cache the emissions data
            cache_key = f"ghgrp_emissions:{company_id}:{reporting_year}"
            self.cache_service.cache.set_with_ttl(
                cache_key,
                result,
                ttl_seconds=7 * 24 * 3600  # 7 days
            )
            
            logger.info(f"GHGRP emissions data retrieved for company {company_id}, year {reporting_year}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting GHGRP emissions data: {str(e)}")
            raise
    
    async def validate_company_emissions(
        self,
        company_id: str,
        calculation_id: str,
        reporting_year: int
    ) -> Dict[str, Any]:
        """
        Validate company emissions against GHGRP data
        
        Args:
            company_id: Internal company ID
            calculation_id: Emissions calculation ID to validate
            reporting_year: Reporting year for validation
            
        Returns:
            Dict containing validation results and discrepancies
        """
        try:
            # Get our calculation data
            calculation = self.db.query(EmissionsCalculation).filter(
                EmissionsCalculation.id == calculation_id
            ).first()
            
            if not calculation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Calculation {calculation_id} not found"
                )
            
            # Get GHGRP data
            ghgrp_data = await self.get_ghgrp_emissions_data(company_id, reporting_year)
            
            if not ghgrp_data["ghgrp_data_available"]:
                return {
                    "validation_status": "no_ghgrp_data",
                    "message": "No GHGRP data available for validation",
                    "company_id": company_id,
                    "calculation_id": calculation_id,
                    "reporting_year": reporting_year
                }
            
            # Perform validation comparison
            validation_result = self._compare_emissions_data(
                calculation, 
                ghgrp_data["emissions_data"]
            )
            
            # Calculate discrepancy analysis
            discrepancy_analysis = self._analyze_discrepancies(
                calculation,
                ghgrp_data["emissions_data"],
                validation_result
            )
            
            # Generate recommendations
            recommendations = self._generate_validation_recommendations(
                validation_result,
                discrepancy_analysis
            )
            
            final_result = {
                "validation_id": f"val_{company_id}_{calculation_id}_{reporting_year}",
                "validation_timestamp": datetime.utcnow().isoformat(),
                "company_id": company_id,
                "calculation_id": calculation_id,
                "reporting_year": reporting_year,
                "validation_status": validation_result["overall_status"],
                "ghgrp_data_quality": ghgrp_data["data_quality"],
                "comparison_results": validation_result,
                "discrepancy_analysis": discrepancy_analysis,
                "recommendations": recommendations,
                "confidence_level": self._calculate_validation_confidence(
                    validation_result, 
                    ghgrp_data["data_quality"]
                )
            }
            
            # Log validation event
            await self.audit_logger.log_event(
                event_type="GHGRP_VALIDATION_COMPLETED",
                user_id=None,  # System validation
                details={
                    "company_id": company_id,
                    "calculation_id": calculation_id,
                    "validation_status": final_result["validation_status"],
                    "confidence_level": final_result["confidence_level"]
                }
            )
            
            logger.info(f"GHGRP validation completed for calculation {calculation_id}")
            
            return final_result
            
        except Exception as e:
            logger.error(f"Error validating company emissions: {str(e)}")
            raise
    
    def _build_search_parameters(
        self, 
        company: Company, 
        additional_criteria: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build search parameters for GHGRP API"""
        params = {}
        
        # Add company identifiers
        if company.cik:
            params["cik"] = company.cik
        if company.ticker:
            params["ticker"] = company.ticker
        if company.name:
            params["company_name"] = company.name
        
        # Add additional criteria
        if additional_criteria:
            params.update(additional_criteria)
        
        # Add reporting year filter
        params["reporting_year"] = company.reporting_year
        
        return params
    
    async def _search_ghgrp_api(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Search GHGRP API with retry logic"""
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.api_timeout) as client:
                    # In production, this would be the actual EPA GHGRP API endpoint
                    # For now, we'll simulate the API response
                    response = await self._simulate_ghgrp_search_response(search_params)
                    return response
                    
            except httpx.TimeoutException:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="GHGRP API timeout"
                )
            except Exception as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise
    
    async def _simulate_ghgrp_search_response(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Simulate GHGRP API search response for testing"""
        # This would be replaced with actual EPA GHGRP API call in production
        simulated_matches = [
            {
                "facility_id": "1001234",
                "facility_name": f"{search_params.get('company_name', 'Test Company')} - Main Facility",
                "parent_company": search_params.get('company_name', 'Test Company'),
                "city": "Houston",
                "state": "TX",
                "zip_code": "77001",
                "naics_code": "221112",
                "sector": "power_plants",
                "reporting_years": [2022, 2023, 2024],
                "total_emissions_co2e": 1250000.5,
                "primary_fuel": "natural_gas",
                "facility_type": "power_generation"
            },
            {
                "facility_id": "1001235",
                "facility_name": f"{search_params.get('company_name', 'Test Company')} - Secondary Facility",
                "parent_company": search_params.get('company_name', 'Test Company'),
                "city": "Dallas",
                "state": "TX",
                "zip_code": "75201",
                "naics_code": "324110",
                "sector": "petroleum_refineries",
                "reporting_years": [2022, 2023],
                "total_emissions_co2e": 850000.2,
                "primary_fuel": "petroleum_products",
                "facility_type": "refinery"
            }
        ]
        
        # Filter based on search criteria
        if search_params.get('ticker'):
            # Simulate ticker-based matching
            return simulated_matches[:1]  # Return best match for ticker
        
        return simulated_matches
    
    def _rank_company_matches(
        self, 
        company: Company, 
        ghgrp_matches: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Rank GHGRP matches by confidence score"""
        ranked_matches = []
        
        for match in ghgrp_matches:
            confidence_score = 0
            match_factors = []
            
            # Company name matching
            if company.name and match.get("parent_company"):
                name_similarity = self._calculate_name_similarity(
                    company.name, 
                    match["parent_company"]
                )
                confidence_score += name_similarity * 40  # 40% weight
                match_factors.append(f"Name similarity: {name_similarity:.2f}")
            
            # Industry/sector matching
            if company.industry and match.get("sector"):
                sector_match = self._match_industry_to_sector(company.industry, match["sector"])
                confidence_score += sector_match * 30  # 30% weight
                match_factors.append(f"Sector match: {sector_match:.2f}")
            
            # Reporting year alignment
            if company.reporting_year in match.get("reporting_years", []):
                confidence_score += 20  # 20% weight
                match_factors.append("Reporting year match: 1.00")
            
            # Geographic proximity (if available)
            if company.headquarters_country == "United States":
                confidence_score += 10  # 10% weight for US companies
                match_factors.append("Geographic match: 1.00")
            
            ranked_match = {
                **match,
                "confidence_score": min(confidence_score, 100),  # Cap at 100%
                "match_factors": match_factors
            }
            
            ranked_matches.append(ranked_match)
        
        # Sort by confidence score (highest first)
        ranked_matches.sort(key=lambda x: x["confidence_score"], reverse=True)
        
        return ranked_matches
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between company names"""
        # Simple similarity calculation (in production, use more sophisticated algorithms)
        name1_clean = name1.lower().replace("inc", "").replace("corp", "").replace("llc", "").strip()
        name2_clean = name2.lower().replace("inc", "").replace("corp", "").replace("llc", "").strip()
        
        # Jaccard similarity on words
        words1 = set(name1_clean.split())
        words2 = set(name2_clean.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def _match_industry_to_sector(self, industry: str, ghgrp_sector: str) -> float:
        """Match company industry to GHGRP sector"""
        if not industry or not ghgrp_sector:
            return 0.0
        
        # Check direct mapping
        mapped_industry = self.sector_mappings.get(ghgrp_sector, "")
        if mapped_industry.lower() in industry.lower():
            return 1.0
        
        # Check partial matches
        industry_words = set(industry.lower().split())
        sector_words = set(ghgrp_sector.replace("_", " ").split())
        
        intersection = industry_words.intersection(sector_words)
        if intersection:
            return len(intersection) / max(len(industry_words), len(sector_words))
        
        return 0.0
    
    async def _get_ghgrp_company_details(self, match: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed company information from GHGRP"""
        # In production, this would make another API call for detailed data
        # For now, return enhanced match data
        return {
            **match,
            "detailed_info": {
                "facility_count": 2,
                "total_capacity": "1000 MW",
                "primary_activities": ["electricity_generation", "steam_production"],
                "emission_sources": ["combustion", "process"],
                "monitoring_methods": ["continuous", "periodic"],
                "data_quality_rating": "high"
            }
        }
    
    async def _get_ghgrp_emissions_api(
        self, 
        facility_id: str, 
        reporting_year: int
    ) -> Dict[str, Any]:
        """Get emissions data from GHGRP API"""
        # Simulate GHGRP emissions data response
        return {
            "facility_id": facility_id,
            "reporting_year": reporting_year,
            "emissions_data": {
                "scope_1": {
                    "total_co2e": 1250000.5,
                    "co2": 1200000.0,
                    "ch4": 1500.0,  # in CO2e
                    "n2o": 48500.5,  # in CO2e
                    "sources": {
                        "stationary_combustion": 1100000.0,
                        "process_emissions": 150000.5
                    }
                },
                "scope_2": {
                    "total_co2e": 85000.2,
                    "electricity_purchased": 195000,  # MWh
                    "steam_purchased": 50000,  # MMBtu
                    "emission_factor_electricity": 0.435  # tCO2e/MWh
                },
                "total_emissions": 1335000.7,
                "data_quality": {
                    "completeness": 98.5,
                    "accuracy_rating": "high",
                    "verification_status": "third_party_verified",
                    "monitoring_methods": ["continuous", "periodic"]
                }
            }
        }
    
    def _process_ghgrp_emissions_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and normalize GHGRP emissions data"""
        emissions_data = raw_data.get("emissions_data", {})
        
        processed = {
            "facility_id": raw_data.get("facility_id"),
            "reporting_year": raw_data.get("reporting_year"),
            "scope_1_emissions": {
                "total_co2e_tonnes": emissions_data.get("scope_1", {}).get("total_co2e", 0),
                "co2_tonnes": emissions_data.get("scope_1", {}).get("co2", 0),
                "ch4_co2e_tonnes": emissions_data.get("scope_1", {}).get("ch4", 0),
                "n2o_co2e_tonnes": emissions_data.get("scope_1", {}).get("n2o", 0),
                "emission_sources": emissions_data.get("scope_1", {}).get("sources", {})
            },
            "scope_2_emissions": {
                "total_co2e_tonnes": emissions_data.get("scope_2", {}).get("total_co2e", 0),
                "electricity_mwh": emissions_data.get("scope_2", {}).get("electricity_purchased", 0),
                "steam_mmbtu": emissions_data.get("scope_2", {}).get("steam_purchased", 0),
                "electricity_emission_factor": emissions_data.get("scope_2", {}).get("emission_factor_electricity", 0)
            },
            "total_emissions_co2e_tonnes": emissions_data.get("total_emissions", 0),
            "data_quality_metrics": emissions_data.get("data_quality", {}),
            "processed_timestamp": datetime.utcnow().isoformat()
        }
        
        return processed    

    def _assess_ghgrp_data_quality(self, processed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess the quality of GHGRP data"""
        quality_metrics = processed_data.get("data_quality_metrics", {})
        
        quality_assessment = {
            "overall_rating": "high",  # high, medium, low
            "completeness_score": quality_metrics.get("completeness", 0),
            "accuracy_rating": quality_metrics.get("accuracy_rating", "unknown"),
            "verification_status": quality_metrics.get("verification_status", "unverified"),
            "monitoring_methods": quality_metrics.get("monitoring_methods", []),
            "data_age_days": 0,  # Would calculate based on reporting date
            "reliability_factors": [
                "Third-party verified" if quality_metrics.get("verification_status") == "third_party_verified" else "Self-reported",
                f"Completeness: {quality_metrics.get('completeness', 0)}%",
                f"Monitoring: {', '.join(quality_metrics.get('monitoring_methods', []))}"
            ]
        }
        
        # Adjust overall rating based on metrics
        if quality_assessment["completeness_score"] < 80:
            quality_assessment["overall_rating"] = "low"
        elif quality_assessment["completeness_score"] < 95:
            quality_assessment["overall_rating"] = "medium"
        
        return quality_assessment
    
    def _analyze_scope_coverage(self, processed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze which emission scopes are covered in GHGRP data"""
        scope_coverage = {
            "scope_1_available": processed_data.get("scope_1_emissions", {}).get("total_co2e_tonnes", 0) > 0,
            "scope_2_available": processed_data.get("scope_2_emissions", {}).get("total_co2e_tonnes", 0) > 0,
            "scope_3_available": False,  # GHGRP typically doesn't include Scope 3
            "emission_sources": {
                "stationary_combustion": "scope_1_emissions" in processed_data,
                "process_emissions": bool(processed_data.get("scope_1_emissions", {}).get("emission_sources", {}).get("process_emissions")),
                "electricity_purchased": "scope_2_emissions" in processed_data,
                "steam_purchased": bool(processed_data.get("scope_2_emissions", {}).get("steam_mmbtu", 0) > 0)
            },
            "coverage_completeness": 0
        }
        
        # Calculate coverage completeness
        available_scopes = sum([
            scope_coverage["scope_1_available"],
            scope_coverage["scope_2_available"]
        ])
        scope_coverage["coverage_completeness"] = (available_scopes / 2) * 100  # Out of Scope 1 & 2
        
        return scope_coverage
    
    def _compare_emissions_data(
        self, 
        calculation: EmissionsCalculation, 
        ghgrp_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare our calculation with GHGRP data"""
        comparison_result = {
            "overall_status": "unknown",
            "scope_1_comparison": {},
            "scope_2_comparison": {},
            "total_emissions_comparison": {},
            "variance_analysis": {},
            "comparison_timestamp": datetime.utcnow().isoformat()
        }
        
        # Compare Scope 1 emissions
        if calculation.scope == "scope_1" or calculation.total_co2e:
            our_scope1 = calculation.total_co2e or 0
            ghgrp_scope1 = ghgrp_data.get("scope_1_emissions", {}).get("total_co2e_tonnes", 0)
            
            if ghgrp_scope1 > 0:
                variance_pct = ((our_scope1 - ghgrp_scope1) / ghgrp_scope1) * 100
                
                comparison_result["scope_1_comparison"] = {
                    "our_emissions": our_scope1,
                    "ghgrp_emissions": ghgrp_scope1,
                    "absolute_difference": our_scope1 - ghgrp_scope1,
                    "variance_percentage": variance_pct,
                    "status": self._classify_variance(variance_pct)
                }
        
        # Compare Scope 2 emissions (if available)
        if calculation.scope == "scope_2":
            our_scope2 = calculation.total_co2e or 0
            ghgrp_scope2 = ghgrp_data.get("scope_2_emissions", {}).get("total_co2e_tonnes", 0)
            
            if ghgrp_scope2 > 0:
                variance_pct = ((our_scope2 - ghgrp_scope2) / ghgrp_scope2) * 100
                
                comparison_result["scope_2_comparison"] = {
                    "our_emissions": our_scope2,
                    "ghgrp_emissions": ghgrp_scope2,
                    "absolute_difference": our_scope2 - ghgrp_scope2,
                    "variance_percentage": variance_pct,
                    "status": self._classify_variance(variance_pct)
                }
        
        # Overall comparison
        total_variance_statuses = []
        if comparison_result["scope_1_comparison"]:
            total_variance_statuses.append(comparison_result["scope_1_comparison"]["status"])
        if comparison_result["scope_2_comparison"]:
            total_variance_statuses.append(comparison_result["scope_2_comparison"]["status"])
        
        if total_variance_statuses:
            if all(status == "acceptable" for status in total_variance_statuses):
                comparison_result["overall_status"] = "acceptable"
            elif any(status == "significant_variance" for status in total_variance_statuses):
                comparison_result["overall_status"] = "significant_variance"
            else:
                comparison_result["overall_status"] = "minor_variance"
        
        return comparison_result
    
    def _classify_variance(self, variance_percentage: float) -> str:
        """Classify variance level based on percentage difference"""
        abs_variance = abs(variance_percentage)
        
        if abs_variance <= 5:
            return "acceptable"  # Within 5%
        elif abs_variance <= 15:
            return "minor_variance"  # 5-15%
        else:
            return "significant_variance"  # >15%
    
    def _analyze_discrepancies(
        self,
        calculation: EmissionsCalculation,
        ghgrp_data: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze potential causes of discrepancies"""
        discrepancy_analysis = {
            "potential_causes": [],
            "data_quality_factors": [],
            "methodological_differences": [],
            "temporal_factors": [],
            "recommendations": []
        }
        
        # Analyze potential causes based on variance
        if validation_result["overall_status"] == "significant_variance":
            discrepancy_analysis["potential_causes"].extend([
                "Different reporting boundaries (operational vs financial control)",
                "Different emission factor sources or vintages",
                "Timing differences in data collection",
                "Different calculation methodologies",
                "Incomplete data coverage"
            ])
        
        # Data quality factors
        our_quality = calculation.data_quality_score or 0
        ghgrp_quality = ghgrp_data.get("data_quality_metrics", {}).get("completeness", 0)
        
        if our_quality < 80 or ghgrp_quality < 80:
            discrepancy_analysis["data_quality_factors"].append(
                f"Low data quality: Our data {our_quality}%, GHGRP data {ghgrp_quality}%"
            )
        
        # Methodological differences
        if calculation.method:
            discrepancy_analysis["methodological_differences"].append(
                f"Our method: {calculation.method}, GHGRP method: regulatory_standard"
            )
        
        # Temporal factors
        calc_year = calculation.reporting_period_start.year if calculation.reporting_period_start else None
        ghgrp_year = ghgrp_data.get("reporting_year")
        
        if calc_year and ghgrp_year and calc_year != ghgrp_year:
            discrepancy_analysis["temporal_factors"].append(
                f"Year mismatch: Our data {calc_year}, GHGRP data {ghgrp_year}"
            )
        
        return discrepancy_analysis
    
    def _generate_validation_recommendations(
        self,
        validation_result: Dict[str, Any],
        discrepancy_analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []
        
        if validation_result["overall_status"] == "acceptable":
            recommendations.extend([
                "✅ Emissions data aligns well with GHGRP reporting",
                "📊 Consider using GHGRP data as benchmark for future calculations",
                "🔍 Monitor for consistency in future reporting periods"
            ])
        
        elif validation_result["overall_status"] == "minor_variance":
            recommendations.extend([
                "⚠️ Minor variance detected - review calculation methodology",
                "📋 Verify emission factor sources and vintages",
                "🔄 Consider adjusting for reporting boundary differences",
                "📈 Document variance explanation for audit purposes"
            ])
        
        elif validation_result["overall_status"] == "significant_variance":
            recommendations.extend([
                "🚨 Significant variance requires investigation",
                "🔍 Conduct detailed reconciliation of data sources",
                "📊 Review organizational and operational boundaries",
                "⚖️ Consider third-party verification of calculations",
                "📝 Document all assumptions and methodological choices",
                "🔄 Re-validate with updated or corrected data"
            ])
        
        # Add specific recommendations based on discrepancy analysis
        if "Low data quality" in str(discrepancy_analysis.get("data_quality_factors", [])):
            recommendations.append("📈 Improve data collection processes and quality controls")
        
        if discrepancy_analysis.get("temporal_factors"):
            recommendations.append("📅 Ensure temporal alignment of data sources")
        
        return recommendations
    
    def _calculate_validation_confidence(
        self,
        validation_result: Dict[str, Any],
        ghgrp_data_quality: Dict[str, Any]
    ) -> float:
        """Calculate confidence level in validation results"""
        base_confidence = 50.0  # Base confidence
        
        # Adjust based on GHGRP data quality
        ghgrp_quality_score = ghgrp_data_quality.get("completeness_score", 0)
        if ghgrp_quality_score >= 95:
            base_confidence += 30
        elif ghgrp_quality_score >= 80:
            base_confidence += 20
        elif ghgrp_quality_score >= 60:
            base_confidence += 10
        
        # Adjust based on verification status
        if ghgrp_data_quality.get("verification_status") == "third_party_verified":
            base_confidence += 15
        
        # Adjust based on variance level
        if validation_result["overall_status"] == "acceptable":
            base_confidence += 5
        elif validation_result["overall_status"] == "significant_variance":
            base_confidence -= 10
        
        return min(base_confidence, 100.0)  # Cap at 100%
    
    async def get_ghgrp_validation_summary(
        self,
        company_id: str,
        reporting_year: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get summary of all GHGRP validations for a company"""
        try:
            # Get company calculations
            query = self.db.query(EmissionsCalculation).filter(
                EmissionsCalculation.company_id == company_id
            )
            
            if reporting_year:
                query = query.filter(
                    func.extract('year', EmissionsCalculation.reporting_period_start) == reporting_year
                )
            
            calculations = query.all()
            
            validation_summary = {
                "company_id": company_id,
                "reporting_year": reporting_year,
                "total_calculations": len(calculations),
                "validations_performed": 0,
                "validation_results": [],
                "overall_compliance_status": "unknown",
                "summary_statistics": {
                    "acceptable_validations": 0,
                    "minor_variance_validations": 0,
                    "significant_variance_validations": 0,
                    "average_confidence": 0
                },
                "generated_at": datetime.utcnow().isoformat()
            }
            
            # This would be enhanced to actually perform validations
            # For now, return the summary structure
            
            return validation_summary
            
        except Exception as e:
            logger.error(f"Error generating GHGRP validation summary: {str(e)}")
            raise