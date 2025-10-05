"""
Anomaly Detection Schemas for SEC Climate Disclosure API

Pydantic models for anomaly detection request/response validation
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from enum import Enum


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


class AnomalyDetectionRequest(BaseModel):
    """Request schema for anomaly detection"""
    company_id: UUID
    reporting_year: int
    analysis_options: Optional[Dict] = Field(
        default_factory=dict,
        description="Optional analysis configuration"
    )
    
    class Config:
        from_attributes = True


class AnomalyDetectionResultResponse(BaseModel):
    """Response schema for individual anomaly detection result"""
    anomaly_type: AnomalyType
    severity: SeverityLevel
    description: str
    detected_value: float
    expected_range: Tuple[float, float]
    confidence_score: float = Field(ge=0.0, le=1.0)
    recommendations: List[str]
    metadata: Dict
    
    class Config:
        from_attributes = True


class AnomalyReportResponse(BaseModel):
    """Response schema for comprehensive anomaly report"""
    company_id: UUID
    reporting_year: int
    analysis_date: datetime
    total_anomalies: int
    anomalies_by_severity: Dict[SeverityLevel, int]
    detected_anomalies: List[AnomalyDetectionResultResponse]
    overall_risk_score: float = Field(ge=0.0, le=100.0)
    summary_insights: List[str]
    
    class Config:
        from_attributes = True


class AnomalySummaryResponse(BaseModel):
    """Summary response for anomaly detection overview"""
    company_id: UUID
    reporting_year: int
    total_anomalies: int
    critical_anomalies: int
    high_anomalies: int
    overall_risk_score: float
    last_analysis_date: datetime
    requires_attention: bool
    
    class Config:
        from_attributes = True


class BatchAnomalyDetectionRequest(BaseModel):
    """Request schema for batch anomaly detection"""
    company_ids: List[UUID]
    reporting_year: int
    analysis_options: Optional[Dict] = Field(
        default_factory=dict,
        description="Optional analysis configuration"
    )
    
    class Config:
        from_attributes = True


class BatchAnomalyDetectionResponse(BaseModel):
    """Response schema for batch anomaly detection"""
    total_companies: int
    successful_analyses: int
    failed_analyses: int
    results: List[AnomalySummaryResponse]
    errors: List[Dict] = Field(default_factory=list)
    
    class Config:
        from_attributes = True


class AnomalyTrendRequest(BaseModel):
    """Request schema for anomaly trend analysis"""
    company_id: UUID
    start_year: int
    end_year: int
    anomaly_types: Optional[List[AnomalyType]] = None
    
    class Config:
        from_attributes = True


class AnomalyTrendDataPoint(BaseModel):
    """Data point for anomaly trend analysis"""
    year: int
    total_anomalies: int
    anomalies_by_type: Dict[AnomalyType, int]
    risk_score: float
    
    class Config:
        from_attributes = True


class AnomalyTrendResponse(BaseModel):
    """Response schema for anomaly trend analysis"""
    company_id: UUID
    analysis_period: Tuple[int, int]
    trend_data: List[AnomalyTrendDataPoint]
    trend_analysis: Dict = Field(
        description="Statistical analysis of trends"
    )
    recommendations: List[str]
    
    class Config:
        from_attributes = True


class IndustryBenchmarkRequest(BaseModel):
    """Request schema for industry benchmark comparison"""
    company_id: UUID
    industry_sector: Optional[str] = None
    reporting_year: int
    
    class Config:
        from_attributes = True


class IndustryBenchmarkResponse(BaseModel):
    """Response schema for industry benchmark comparison"""
    company_id: UUID
    industry_sector: str
    reporting_year: int
    company_metrics: Dict[str, float]
    industry_benchmarks: Dict[str, float]
    deviations: Dict[str, float]
    percentile_ranking: Dict[str, float]
    recommendations: List[str]
    
    class Config:
        from_attributes = True