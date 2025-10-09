"""
Base Pydantic models for common functionality
Includes AuditMixin for audit trail support
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class AuditMixin(BaseModel):
    """Base model for audit trail functionality"""

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    updated_by: Optional[UUID] = None
    audit_trail_id: Optional[UUID] = None

    class Config:
        from_attributes = True
