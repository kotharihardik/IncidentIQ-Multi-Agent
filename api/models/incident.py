from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class IncidentTrigger(BaseModel):
    """Request body for POST /incidents/analyze"""
    service:       str   = Field(..., example="payment-service")
    reason:        str   = Field(..., example="high_error_rate")
    anomaly_score: float = Field(..., ge=0.0, le=1.0, example=0.72)
    triggered_at:  Optional[str] = Field(
        default=None,
        description="ISO-8601 timestamp; defaults to now if omitted"
    )


class IncidentResponse(BaseModel):
    incident_id:          str
    service:              str
    root_cause:           str
    confidence:           float
    error_rate:           float
    error_patterns:       List[str]
    fix_recommendations:  List[str]
    report:               str
    triggered_at:         str
    completed_at:         str


class LogQueryParams(BaseModel):
    service:    Optional[str] = None
    level:      Optional[str] = None
    start_time: Optional[str] = None
    end_time:   Optional[str] = None
    size:       int = Field(default=50, ge=1, le=500)
