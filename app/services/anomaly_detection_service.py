"""
Anomaly Detection Service for SEC Climate Disclosure API

This service implements:
- Year-over-year variance detection for emissions data
- Statistical outlier detection for operational data
- Industry benchmark comparison capabilities
- Anomaly reports with actionable insights
"""

import logging
import math
import statistics
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from app.models.emissions import EmissionsCalculation
from app.models.user import User

logger = logging.getLogger(__name__)


class AnomalyType(str, Enum):
    """Types of anomalies that can be detected"""

    YEAR_OVER_YEAR_VARIANCE = "year_over_year_variance"
    STATISTICAL_OUTLIER = "statistical_outlier"
    INDUSTRY_BENCHMARK_DEVIATION = "industry_benchmark_deviation"
    OPERATIONAL_DATA_INCONSISTENCY = "operational_data_inconsistency"


class SeverityLevel(str, Enum):
    """Severity levels for anomalies"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AnomalyDetectionResult:
    """Result of anomaly detection analysis"""

    anomaly_type: AnomalyType
    severity: SeverityLevel
    description: str
    detected_value: float
    expected_range: Tuple[float, float]
    confidence_score: float
    recommendations: List[str]
    metadata: Dict


@dataclass
class AnomalyReport:
    """Comprehensive anomaly report for a company"""

    company_id: UUID
    reporting_year: int
    analysis_date: datetime
    total_anomalies: int
    anomalies_by_severity: Dict[SeverityLevel, int]
    detected_anomalies: List[AnomalyDetectionResult]
    overall_risk_score: float
    summary_insights: List[str]


class AnomalyDetectionService:
    """Service for detecting anomalies in emissions and operational data"""

    def __init__(self, db: Session):
        self.db = db

        # Configuration thresholds
        self.year_over_year_threshold = 0.20  # 20% variance threshold
        self.statistical_outlier_threshold = 2.0  # 2 standard deviations
        self.industry_benchmark_threshold = 0.30  # 30% deviation from industry average

        # Industry benchmark data (in real implementation, this would come from external sources)
        self.industry_benchmarks = {
            "manufacturing": {"scope1_per_revenue": 0.15, "scope2_per_revenue": 0.08},
            "technology": {"scope1_per_revenue": 0.02, "scope2_per_revenue": 0.05},
            "retail": {"scope1_per_revenue": 0.05, "scope2_per_revenue": 0.12},
            "energy": {"scope1_per_revenue": 0.45, "scope2_per_revenue": 0.15},
            "default": {"scope1_per_revenue": 0.10, "scope2_per_revenue": 0.08},
        }

    def detect_anomalies(
        self, company_id: UUID, reporting_year: int, user_id: UUID
    ) -> AnomalyReport:
        """
        Comprehensive anomaly detection for a company's emissions data

        Args:
            company_id: Company identifier
            reporting_year: Year to analyze
            user_id: User requesting the analysis

        Returns:
            AnomalyReport with detected anomalies and insights
        """
        logger.info(
            f"Starting anomaly detection for company {company_id}, year {reporting_year}"
        )

        try:
            # Get company's emissions data
            current_year_data = self._get_emissions_data(company_id, reporting_year)
            historical_data = self._get_historical_emissions_data(
                company_id, reporting_year
            )

            if not current_year_data:
                logger.warning(
                    f"No emissions data found for company {company_id} in year {reporting_year}"
                )
                return self._create_empty_report(company_id, reporting_year)

            detected_anomalies = []

            # 1. Year-over-year variance detection
            yoy_anomalies = self._detect_year_over_year_variance(
                current_year_data, historical_data
            )
            detected_anomalies.extend(yoy_anomalies)

            # 2. Statistical outlier detection
            statistical_anomalies = self._detect_statistical_outliers(
                current_year_data, historical_data
            )
            detected_anomalies.extend(statistical_anomalies)

            # 3. Industry benchmark comparison
            industry_anomalies = self._detect_industry_benchmark_deviations(
                current_year_data, company_id
            )
            detected_anomalies.extend(industry_anomalies)

            # 4. Operational data consistency checks
            operational_anomalies = self._detect_operational_inconsistencies(
                current_year_data, historical_data
            )
            detected_anomalies.extend(operational_anomalies)

            # Generate comprehensive report
            report = self._generate_anomaly_report(
                company_id, reporting_year, detected_anomalies
            )

            logger.info(
                f"Anomaly detection completed. Found {len(detected_anomalies)} anomalies"
            )
            return report

        except Exception as e:
            logger.error(f"Error in anomaly detection: {str(e)}")
            raise

    def _get_emissions_data(
        self, company_id: UUID, year: int
    ) -> List[EmissionsCalculation]:
        """Get emissions data for a specific company and year"""
        return (
            self.db.query(EmissionsCalculation)
            .filter(
                and_(
                    EmissionsCalculation.company_id == company_id,
                    func.extract("year", EmissionsCalculation.reporting_period_start)
                    == year,
                )
            )
            .all()
        )

    def _get_historical_emissions_data(
        self, company_id: UUID, current_year: int, years_back: int = 5
    ) -> List[EmissionsCalculation]:
        """Get historical emissions data for trend analysis"""
        start_year = current_year - years_back

        return (
            self.db.query(EmissionsCalculation)
            .filter(
                and_(
                    EmissionsCalculation.company_id == company_id,
                    func.extract("year", EmissionsCalculation.reporting_period_start)
                    >= start_year,
                    func.extract("year", EmissionsCalculation.reporting_period_start)
                    < current_year,
                )
            )
            .order_by(EmissionsCalculation.reporting_period_start)
            .all()
        )

    def _detect_year_over_year_variance(
        self,
        current_data: List[EmissionsCalculation],
        historical_data: List[EmissionsCalculation],
    ) -> List[AnomalyDetectionResult]:
        """Detect significant year-over-year variances"""
        anomalies = []

        if not historical_data:
            return anomalies

        # Get previous year data
        previous_year_data = [
            d
            for d in historical_data
            if d.reporting_period_start.year
            == max(d.reporting_period_start.year for d in historical_data)
        ]

        if not previous_year_data:
            return anomalies

        # Calculate totals for current and previous year
        current_scope1 = sum(calc.scope1_emissions or 0 for calc in current_data)
        current_scope2 = sum(calc.scope2_emissions or 0 for calc in current_data)

        prev_scope1 = sum(calc.scope1_emissions or 0 for calc in previous_year_data)
        prev_scope2 = sum(calc.scope2_emissions or 0 for calc in previous_year_data)

        # Check Scope 1 variance
        if prev_scope1 > 0:
            scope1_variance = abs(current_scope1 - prev_scope1) / prev_scope1
            if scope1_variance > self.year_over_year_threshold:
                severity = self._calculate_severity(
                    scope1_variance, self.year_over_year_threshold
                )
                anomalies.append(
                    AnomalyDetectionResult(
                        anomaly_type=AnomalyType.YEAR_OVER_YEAR_VARIANCE,
                        severity=severity,
                        description=f"Scope 1 emissions variance of {scope1_variance:.1%} from previous year",
                        detected_value=current_scope1,
                        expected_range=(prev_scope1 * 0.8, prev_scope1 * 1.2),
                        confidence_score=0.85,
                        recommendations=[
                            "Review operational changes that may have impacted fuel consumption",
                            "Verify data collection methodology consistency",
                            "Check for new facilities or equipment additions",
                        ],
                        metadata={
                            "current_year_scope1": current_scope1,
                            "previous_year_scope1": prev_scope1,
                            "variance_percentage": scope1_variance,
                        },
                    )
                )

        # Check Scope 2 variance
        if prev_scope2 > 0:
            scope2_variance = abs(current_scope2 - prev_scope2) / prev_scope2
            if scope2_variance > self.year_over_year_threshold:
                severity = self._calculate_severity(
                    scope2_variance, self.year_over_year_threshold
                )
                anomalies.append(
                    AnomalyDetectionResult(
                        anomaly_type=AnomalyType.YEAR_OVER_YEAR_VARIANCE,
                        severity=severity,
                        description=f"Scope 2 emissions variance of {scope2_variance:.1%} from previous year",
                        detected_value=current_scope2,
                        expected_range=(prev_scope2 * 0.8, prev_scope2 * 1.2),
                        confidence_score=0.85,
                        recommendations=[
                            "Review electricity consumption patterns",
                            "Check for changes in grid emission factors",
                            "Verify renewable energy procurement changes",
                        ],
                        metadata={
                            "current_year_scope2": current_scope2,
                            "previous_year_scope2": prev_scope2,
                            "variance_percentage": scope2_variance,
                        },
                    )
                )

        return anomalies

    def _detect_statistical_outliers(
        self,
        current_data: List[EmissionsCalculation],
        historical_data: List[EmissionsCalculation],
    ) -> List[AnomalyDetectionResult]:
        """Detect statistical outliers in emissions data"""
        anomalies = []

        if (
            len(historical_data) < 3
        ):  # Need at least 3 data points for statistical analysis
            return anomalies

        # Analyze monthly/quarterly patterns if available
        all_data = historical_data + current_data

        # Group by month and analyze patterns
        monthly_scope1 = {}
        monthly_scope2 = {}

        for calc in all_data:
            month = calc.reporting_period_start.month
            if month not in monthly_scope1:
                monthly_scope1[month] = []
                monthly_scope2[month] = []

            monthly_scope1[month].append(calc.scope1_emissions or 0)
            monthly_scope2[month].append(calc.scope2_emissions or 0)

        # Check for outliers in current year data
        for calc in current_data:
            month = calc.reporting_period_start.month

            if month in monthly_scope1 and len(monthly_scope1[month]) > 3:
                historical_values = [
                    v
                    for v in monthly_scope1[month]
                    if v != (calc.scope1_emissions or 0)
                ]
                if historical_values:
                    mean_val = statistics.mean(historical_values)
                    std_val = (
                        statistics.stdev(historical_values)
                        if len(historical_values) > 1
                        else 0
                    )

                    if std_val > 0:
                        z_score = abs((calc.scope1_emissions or 0) - mean_val) / std_val
                        if z_score > self.statistical_outlier_threshold:
                            severity = self._calculate_severity(
                                z_score, self.statistical_outlier_threshold
                            )
                            anomalies.append(
                                AnomalyDetectionResult(
                                    anomaly_type=AnomalyType.STATISTICAL_OUTLIER,
                                    severity=severity,
                                    description=f"Scope 1 emissions for {calc.reporting_period_start.strftime('%B')} is a statistical outlier (Z-score: {z_score:.2f})",
                                    detected_value=calc.scope1_emissions or 0,
                                    expected_range=(
                                        mean_val - 2 * std_val,
                                        mean_val + 2 * std_val,
                                    ),
                                    confidence_score=0.90,
                                    recommendations=[
                                        "Verify data entry accuracy for this period",
                                        "Check for unusual operational events",
                                        "Review calculation methodology",
                                    ],
                                    metadata={
                                        "z_score": z_score,
                                        "historical_mean": mean_val,
                                        "historical_std": std_val,
                                        "month": month,
                                    },
                                )
                            )

        return anomalies

    def _detect_industry_benchmark_deviations(
        self, current_data: List[EmissionsCalculation], company_id: UUID
    ) -> List[AnomalyDetectionResult]:
        """Detect deviations from industry benchmarks"""
        anomalies = []

        # Get company industry (in real implementation, this would come from company profile)
        industry = "default"  # Placeholder
        benchmarks = self.industry_benchmarks.get(
            industry, self.industry_benchmarks["default"]
        )

        # Calculate emissions intensity (emissions per revenue)
        # For this example, we'll use a placeholder revenue value
        estimated_revenue = 100_000_000  # $100M placeholder

        total_scope1 = sum(calc.scope1_emissions or 0 for calc in current_data)
        total_scope2 = sum(calc.scope2_emissions or 0 for calc in current_data)

        scope1_intensity = total_scope1 / estimated_revenue
        scope2_intensity = total_scope2 / estimated_revenue

        # Check Scope 1 intensity
        scope1_benchmark = benchmarks["scope1_per_revenue"]
        scope1_deviation = abs(scope1_intensity - scope1_benchmark) / scope1_benchmark

        if scope1_deviation > self.industry_benchmark_threshold:
            severity = self._calculate_severity(
                scope1_deviation, self.industry_benchmark_threshold
            )
            anomalies.append(
                AnomalyDetectionResult(
                    anomaly_type=AnomalyType.INDUSTRY_BENCHMARK_DEVIATION,
                    severity=severity,
                    description=f"Scope 1 emissions intensity deviates {scope1_deviation:.1%} from industry benchmark",
                    detected_value=scope1_intensity,
                    expected_range=(scope1_benchmark * 0.7, scope1_benchmark * 1.3),
                    confidence_score=0.75,
                    recommendations=[
                        "Compare operational efficiency with industry peers",
                        "Review energy management practices",
                        "Consider industry-specific emission reduction strategies",
                    ],
                    metadata={
                        "industry": industry,
                        "benchmark_value": scope1_benchmark,
                        "company_intensity": scope1_intensity,
                        "deviation_percentage": scope1_deviation,
                    },
                )
            )

        # Check Scope 2 intensity
        scope2_benchmark = benchmarks["scope2_per_revenue"]
        scope2_deviation = abs(scope2_intensity - scope2_benchmark) / scope2_benchmark

        if scope2_deviation > self.industry_benchmark_threshold:
            severity = self._calculate_severity(
                scope2_deviation, self.industry_benchmark_threshold
            )
            anomalies.append(
                AnomalyDetectionResult(
                    anomaly_type=AnomalyType.INDUSTRY_BENCHMARK_DEVIATION,
                    severity=severity,
                    description=f"Scope 2 emissions intensity deviates {scope2_deviation:.1%} from industry benchmark",
                    detected_value=scope2_intensity,
                    expected_range=(scope2_benchmark * 0.7, scope2_benchmark * 1.3),
                    confidence_score=0.75,
                    recommendations=[
                        "Evaluate electricity procurement strategies",
                        "Consider renewable energy options",
                        "Review facility energy efficiency",
                    ],
                    metadata={
                        "industry": industry,
                        "benchmark_value": scope2_benchmark,
                        "company_intensity": scope2_intensity,
                        "deviation_percentage": scope2_deviation,
                    },
                )
            )

        return anomalies

    def _detect_operational_inconsistencies(
        self,
        current_data: List[EmissionsCalculation],
        historical_data: List[EmissionsCalculation],
    ) -> List[AnomalyDetectionResult]:
        """Detect inconsistencies in operational data patterns"""
        anomalies = []

        # Check for unusual patterns in activity data
        for calc in current_data:
            activity_data = calc.activity_data or {}

            # Check for missing or zero values where they shouldn't be
            if calc.scope1_emissions and calc.scope1_emissions > 0:
                fuel_consumption = activity_data.get("fuel_consumption", 0)
                if fuel_consumption == 0:
                    anomalies.append(
                        AnomalyDetectionResult(
                            anomaly_type=AnomalyType.OPERATIONAL_DATA_INCONSISTENCY,
                            severity=SeverityLevel.MEDIUM,
                            description="Scope 1 emissions reported but no fuel consumption data",
                            detected_value=calc.scope1_emissions,
                            expected_range=(0, calc.scope1_emissions),
                            confidence_score=0.95,
                            recommendations=[
                                "Verify fuel consumption data entry",
                                "Check data collection processes",
                                "Ensure all fuel types are captured",
                            ],
                            metadata={
                                "calculation_id": str(calc.id),
                                "scope1_emissions": calc.scope1_emissions,
                                "fuel_consumption": fuel_consumption,
                            },
                        )
                    )

            if calc.scope2_emissions and calc.scope2_emissions > 0:
                electricity_consumption = activity_data.get(
                    "electricity_consumption", 0
                )
                if electricity_consumption == 0:
                    anomalies.append(
                        AnomalyDetectionResult(
                            anomaly_type=AnomalyType.OPERATIONAL_DATA_INCONSISTENCY,
                            severity=SeverityLevel.MEDIUM,
                            description="Scope 2 emissions reported but no electricity consumption data",
                            detected_value=calc.scope2_emissions,
                            expected_range=(0, calc.scope2_emissions),
                            confidence_score=0.95,
                            recommendations=[
                                "Verify electricity consumption data entry",
                                "Check utility bill data collection",
                                "Ensure all facilities are included",
                            ],
                            metadata={
                                "calculation_id": str(calc.id),
                                "scope2_emissions": calc.scope2_emissions,
                                "electricity_consumption": electricity_consumption,
                            },
                        )
                    )

        return anomalies

    def _calculate_severity(self, deviation: float, threshold: float) -> SeverityLevel:
        """Calculate severity level based on deviation from threshold"""
        if deviation < threshold * 1.5:
            return SeverityLevel.LOW
        elif deviation < threshold * 2.0:
            return SeverityLevel.MEDIUM
        elif deviation < threshold * 3.0:
            return SeverityLevel.HIGH
        else:
            return SeverityLevel.CRITICAL

    def _generate_anomaly_report(
        self,
        company_id: UUID,
        reporting_year: int,
        anomalies: List[AnomalyDetectionResult],
    ) -> AnomalyReport:
        """Generate comprehensive anomaly report"""

        # Count anomalies by severity
        severity_counts = {
            SeverityLevel.LOW: 0,
            SeverityLevel.MEDIUM: 0,
            SeverityLevel.HIGH: 0,
            SeverityLevel.CRITICAL: 0,
        }

        for anomaly in anomalies:
            severity_counts[anomaly.severity] += 1

        # Calculate overall risk score
        risk_score = self._calculate_overall_risk_score(anomalies)

        # Generate summary insights
        insights = self._generate_summary_insights(anomalies)

        return AnomalyReport(
            company_id=company_id,
            reporting_year=reporting_year,
            analysis_date=datetime.utcnow(),
            total_anomalies=len(anomalies),
            anomalies_by_severity=severity_counts,
            detected_anomalies=anomalies,
            overall_risk_score=risk_score,
            summary_insights=insights,
        )

    def _calculate_overall_risk_score(
        self, anomalies: List[AnomalyDetectionResult]
    ) -> float:
        """Calculate overall risk score based on detected anomalies"""
        if not anomalies:
            return 0.0

        severity_weights = {
            SeverityLevel.LOW: 1,
            SeverityLevel.MEDIUM: 2,
            SeverityLevel.HIGH: 4,
            SeverityLevel.CRITICAL: 8,
        }

        total_weight = sum(severity_weights[anomaly.severity] for anomaly in anomalies)
        max_possible_weight = len(anomalies) * severity_weights[SeverityLevel.CRITICAL]

        return min(total_weight / max_possible_weight * 100, 100.0)

    def _generate_summary_insights(
        self, anomalies: List[AnomalyDetectionResult]
    ) -> List[str]:
        """Generate actionable summary insights"""
        insights = []

        if not anomalies:
            insights.append("No significant anomalies detected in emissions data")
            return insights

        # Count by type
        type_counts = {}
        for anomaly in anomalies:
            type_counts[anomaly.anomaly_type] = (
                type_counts.get(anomaly.anomaly_type, 0) + 1
            )

        # Generate insights based on patterns
        if AnomalyType.YEAR_OVER_YEAR_VARIANCE in type_counts:
            insights.append(
                f"Detected {type_counts[AnomalyType.YEAR_OVER_YEAR_VARIANCE]} significant year-over-year variance(s) - review operational changes"
            )

        if AnomalyType.STATISTICAL_OUTLIER in type_counts:
            insights.append(
                f"Found {type_counts[AnomalyType.STATISTICAL_OUTLIER]} statistical outlier(s) - verify data accuracy"
            )

        if AnomalyType.INDUSTRY_BENCHMARK_DEVIATION in type_counts:
            insights.append(
                f"Identified {type_counts[AnomalyType.INDUSTRY_BENCHMARK_DEVIATION]} industry benchmark deviation(s) - consider peer benchmarking"
            )

        if AnomalyType.OPERATIONAL_DATA_INCONSISTENCY in type_counts:
            insights.append(
                f"Found {type_counts[AnomalyType.OPERATIONAL_DATA_INCONSISTENCY]} operational data inconsistency(ies) - review data collection processes"
            )

        # Overall recommendations
        critical_count = sum(
            1 for a in anomalies if a.severity == SeverityLevel.CRITICAL
        )
        if critical_count > 0:
            insights.append(
                f"URGENT: {critical_count} critical anomalies require immediate attention"
            )

        return insights

    def _create_empty_report(
        self, company_id: UUID, reporting_year: int
    ) -> AnomalyReport:
        """Create empty report when no data is available"""
        return AnomalyReport(
            company_id=company_id,
            reporting_year=reporting_year,
            analysis_date=datetime.utcnow(),
            total_anomalies=0,
            anomalies_by_severity={
                SeverityLevel.LOW: 0,
                SeverityLevel.MEDIUM: 0,
                SeverityLevel.HIGH: 0,
                SeverityLevel.CRITICAL: 0,
            },
            detected_anomalies=[],
            overall_risk_score=0.0,
            summary_insights=["No emissions data available for analysis"],
        )
    def get_anomaly_summary(
        self, company_id: UUID, reporting_year: int, user_id: UUID
    ) -> Dict[str, Any]:
        """Get anomaly summary for a company and year"""
        try:
            # Get full anomaly report
            report = self.detect_anomalies(company_id, reporting_year, user_id)
            
            # Create summary
            summary = {
                "company_id": str(company_id),
                "reporting_year": reporting_year,
                "total_anomalies": report.total_anomalies,
                "overall_risk_score": report.overall_risk_score,
                "anomalies_by_severity": report.anomalies_by_severity,
                "anomalies_by_type": report.anomalies_by_type,
                "requires_attention": report.total_anomalies > 0,
                "last_analysis_date": report.analysis_date,
                "summary_insights": report.summary_insights[:3]  # Top 3 insights
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting anomaly summary: {str(e)}")
            return {
                "company_id": str(company_id),
                "reporting_year": reporting_year,
                "total_anomalies": 0,
                "overall_risk_score": 0.0,
                "anomalies_by_severity": {"low": 0, "medium": 0, "high": 0, "critical": 0},
                "anomalies_by_type": {},
                "requires_attention": False,
                "last_analysis_date": datetime.utcnow(),
                "summary_insights": ["Analysis unavailable"]
            }

    def analyze_trends(
        self, company_id: UUID, start_year: int, end_year: int, user_id: UUID
    ) -> Dict[str, Any]:
        """Analyze anomaly trends over multiple years"""
        try:
            trends = []
            
            for year in range(start_year, end_year + 1):
                try:
                    report = self.detect_anomalies(company_id, year, user_id)
                    trends.append({
                        "year": year,
                        "total_anomalies": report.total_anomalies,
                        "risk_score": report.overall_risk_score,
                        "anomalies_by_severity": report.anomalies_by_severity,
                        "anomalies_by_type": report.anomalies_by_type
                    })
                except Exception as e:
                    logger.warning(f"Could not analyze year {year}: {str(e)}")
                    trends.append({
                        "year": year,
                        "total_anomalies": 0,
                        "risk_score": 0.0,
                        "anomalies_by_severity": {"low": 0, "medium": 0, "high": 0, "critical": 0},
                        "anomalies_by_type": {},
                        "error": str(e)
                    })
            
            # Calculate trend analysis
            trend_analysis = self._calculate_trend_analysis(trends)
            
            return {
                "company_id": str(company_id),
                "analysis_period": (start_year, end_year),
                "trend_data": trends,
                "trend_analysis": trend_analysis,
                "recommendations": self._generate_trend_recommendations(trend_analysis)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing trends: {str(e)}")
            raise

    def compare_with_industry_benchmarks(
        self, company_id: UUID, reporting_year: int, industry_sector: str, user_id: UUID
    ) -> Dict[str, Any]:
        """Compare company anomalies with industry benchmarks"""
        try:
            # Get company anomaly report
            company_report = self.detect_anomalies(company_id, reporting_year, user_id)
            
            # Get industry benchmarks (simplified - would normally come from external data)
            industry_benchmarks = self.industry_benchmarks.get(
                industry_sector.lower(), self.industry_benchmarks["default"]
            )
            
            # Calculate company metrics
            company_metrics = {
                "anomaly_rate": company_report.total_anomalies / max(len(self._get_emissions_data(company_id, reporting_year)), 1),
                "risk_score": company_report.overall_risk_score,
                "critical_anomaly_rate": company_report.anomalies_by_severity.get("critical", 0) / max(company_report.total_anomalies, 1)
            }
            
            # Calculate deviations from industry benchmarks
            deviations = {}
            percentile_ranking = {}
            
            for metric, company_value in company_metrics.items():
                benchmark_key = f"{metric}_benchmark"
                if benchmark_key in industry_benchmarks:
                    benchmark_value = industry_benchmarks[benchmark_key]
                    deviation = (company_value - benchmark_value) / benchmark_value if benchmark_value > 0 else 0
                    deviations[metric] = deviation
                    
                    # Simple percentile calculation (would be more sophisticated in real implementation)
                    if deviation < -0.2:
                        percentile_ranking[metric] = 90  # Top 10%
                    elif deviation < 0:
                        percentile_ranking[metric] = 70  # Top 30%
                    elif deviation < 0.2:
                        percentile_ranking[metric] = 50  # Average
                    else:
                        percentile_ranking[metric] = 20  # Bottom 20%
            
            # Generate recommendations
            recommendations = []
            for metric, deviation in deviations.items():
                if deviation > 0.2:
                    recommendations.append(
                        f"Consider improvement strategies for {metric} - currently {deviation:.1%} above industry average"
                    )
                elif deviation < -0.2:
                    recommendations.append(
                        f"Excellent performance in {metric} - {abs(deviation):.1%} below industry average"
                    )
            
            return {
                "company_id": str(company_id),
                "industry_sector": industry_sector,
                "reporting_year": reporting_year,
                "company_metrics": company_metrics,
                "industry_benchmarks": industry_benchmarks,
                "deviations": deviations,
                "percentile_ranking": percentile_ranking,
                "recommendations": recommendations
            }
            
        except Exception as e:
            logger.error(f"Error in industry benchmark comparison: {str(e)}")
            raise

    def _calculate_trend_analysis(self, trends: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistical trend analysis"""
        if len(trends) < 2:
            return {"trend": "insufficient_data", "direction": "unknown"}
        
        # Calculate trend direction for risk scores
        risk_scores = [t["risk_score"] for t in trends if "error" not in t]
        if len(risk_scores) >= 2:
            trend_direction = "increasing" if risk_scores[-1] > risk_scores[0] else "decreasing"
            avg_change = (risk_scores[-1] - risk_scores[0]) / len(risk_scores)
        else:
            trend_direction = "unknown"
            avg_change = 0
        
        return {
            "trend": "improving" if avg_change < -5 else "worsening" if avg_change > 5 else "stable",
            "direction": trend_direction,
            "average_change": avg_change,
            "data_points": len(trends)
        }

    def _generate_trend_recommendations(self, trend_analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on trend analysis"""
        recommendations = []
        
        if trend_analysis["trend"] == "worsening":
            recommendations.append("Anomaly trends are worsening - consider reviewing data quality processes")
            recommendations.append("Implement additional monitoring for high-risk emission sources")
        elif trend_analysis["trend"] == "improving":
            recommendations.append("Anomaly trends are improving - maintain current data quality practices")
        else:
            recommendations.append("Anomaly trends are stable - continue monitoring")
        
        if trend_analysis["data_points"] < 3:
            recommendations.append("Consider analyzing more historical data for better trend insights")
        
        return recommendations