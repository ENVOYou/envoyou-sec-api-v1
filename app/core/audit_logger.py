"""
Audit logging service for SEC compliance
Comprehensive logging of all authentication and authorization events
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Text, Boolean
import uuid

from app.models.base import BaseModel, GUID, JSON
from app.models.user import User

logger = logging.getLogger(__name__)


class AuditLog(BaseModel):
    """Audit log model for compliance tracking"""
    __tablename__ = "audit_logs"
    
    # Event information
    event_type = Column(String(100), nullable=False, index=True)
    event_category = Column(String(50), nullable=False, index=True)  # AUTH, DATA, REPORT, etc.
    event_description = Column(Text, nullable=False)
    
    # User information
    user_id = Column(GUID(), nullable=True, index=True)
    user_email = Column(String(255), nullable=True)
    user_role = Column(String(50), nullable=True)
    
    # Request information
    request_id = Column(String(100), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    endpoint = Column(String(255), nullable=True)
    http_method = Column(String(10), nullable=True)
    
    # Event data
    event_data = Column(JSON, nullable=True)
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    
    # Status and metadata
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)
    processing_time_ms = Column(String(20), nullable=True)
    
    # Compliance fields
    retention_date = Column(DateTime(timezone=True), nullable=True)
    is_sensitive = Column(Boolean, default=False, nullable=False)


class AuditLogger:
    """Audit logging service for SEC compliance requirements"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def log_authentication_event(
        self,
        event_type: str,
        user_email: str,
        success: bool,
        request_id: str = None,
        ip_address: str = None,
        user_agent: str = None,
        error_message: str = None,
        additional_data: Dict[str, Any] = None
    ):
        """Log authentication events"""
        try:
            audit_entry = AuditLog(
                event_type=event_type,
                event_category="AUTH",
                event_description=f"Authentication event: {event_type}",
                user_email=user_email,
                request_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
                success=success,
                error_message=error_message,
                event_data=additional_data or {},
                is_sensitive=True  # Authentication events are sensitive
            )
            
            self.db.add(audit_entry)
            self.db.commit()
            
            logger.info(f"Authentication audit logged: {event_type} for {user_email}")
            
        except Exception as e:
            logger.error(f"Failed to log authentication audit: {str(e)}")
            self.db.rollback()
    
    def log_authorization_event(
        self,
        event_type: str,
        user: User,
        resource: str,
        action: str,
        success: bool,
        request_id: str = None,
        ip_address: str = None,
        endpoint: str = None,
        http_method: str = None,
        error_message: str = None
    ):
        """Log authorization events"""
        try:
            audit_entry = AuditLog(
                event_type=event_type,
                event_category="AUTHZ",
                event_description=f"Authorization event: {action} on {resource}",
                user_id=user.id,
                user_email=user.email,
                user_role=user.role.value,
                request_id=request_id,
                ip_address=ip_address,
                endpoint=endpoint,
                http_method=http_method,
                success=success,
                error_message=error_message,
                event_data={
                    "resource": resource,
                    "action": action,
                    "user_permissions": self._get_user_permissions_summary(user)
                }
            )
            
            self.db.add(audit_entry)
            self.db.commit()
            
            logger.info(f"Authorization audit logged: {action} on {resource} for {user.email}")
            
        except Exception as e:
            logger.error(f"Failed to log authorization audit: {str(e)}")
            self.db.rollback()
    
    def log_data_access_event(
        self,
        user: User,
        resource_type: str,
        resource_id: str,
        action: str,
        request_id: str = None,
        ip_address: str = None,
        endpoint: str = None,
        before_state: Dict[str, Any] = None,
        after_state: Dict[str, Any] = None,
        additional_data: Dict[str, Any] = None
    ):
        """Log data access and modification events"""
        try:
            audit_entry = AuditLog(
                event_type="DATA_ACCESS",
                event_category="DATA",
                event_description=f"Data access: {action} on {resource_type}",
                user_id=user.id,
                user_email=user.email,
                user_role=user.role.value,
                request_id=request_id,
                ip_address=ip_address,
                endpoint=endpoint,
                success=True,
                before_state=before_state,
                after_state=after_state,
                event_data={
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "action": action,
                    **(additional_data or {})
                },
                is_sensitive=self._is_sensitive_resource(resource_type)
            )
            
            self.db.add(audit_entry)
            self.db.commit()
            
            logger.info(f"Data access audit logged: {action} on {resource_type} by {user.email}")
            
        except Exception as e:
            logger.error(f"Failed to log data access audit: {str(e)}")
            self.db.rollback()
    
    def log_calculation_event(
        self,
        user: User,
        calculation_type: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        emission_factors_used: Dict[str, Any],
        request_id: str = None,
        processing_time_ms: int = None
    ):
        """Log emissions calculation events for audit trail"""
        try:
            audit_entry = AuditLog(
                event_type="CALCULATION",
                event_category="EMISSIONS",
                event_description=f"Emissions calculation: {calculation_type}",
                user_id=user.id,
                user_email=user.email,
                user_role=user.role.value,
                request_id=request_id,
                success=True,
                processing_time_ms=str(processing_time_ms) if processing_time_ms else None,
                event_data={
                    "calculation_type": calculation_type,
                    "input_data": input_data,
                    "output_data": output_data,
                    "emission_factors_used": emission_factors_used
                },
                is_sensitive=True  # Emissions data is sensitive business information
            )
            
            self.db.add(audit_entry)
            self.db.commit()
            
            logger.info(f"Calculation audit logged: {calculation_type} by {user.email}")
            
        except Exception as e:
            logger.error(f"Failed to log calculation audit: {str(e)}")
            self.db.rollback()
    
    def get_audit_trail(
        self,
        user_id: Optional[str] = None,
        event_category: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> list:
        """Retrieve audit trail for compliance reporting"""
        try:
            query = self.db.query(AuditLog)
            
            if user_id:
                query = query.filter(AuditLog.user_id == user_id)
            
            if event_category:
                query = query.filter(AuditLog.event_category == event_category)
            
            if start_date:
                query = query.filter(AuditLog.created_at >= start_date)
            
            if end_date:
                query = query.filter(AuditLog.created_at <= end_date)
            
            return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
            
        except Exception as e:
            logger.error(f"Failed to retrieve audit trail: {str(e)}")
            return []
    
    def _get_user_permissions_summary(self, user: User) -> Dict[str, Any]:
        """Get summary of user permissions for audit logging"""
        return {
            "role": user.role.value,
            "can_approve_reports": user.can_approve_reports(),
            "can_access_audit_trails": user.can_access_audit_trails(),
            "can_manage_epa_data": user.can_manage_epa_data()
        }
    
    def _is_sensitive_resource(self, resource_type: str) -> bool:
        """Determine if resource type contains sensitive data"""
        sensitive_resources = [
            "emissions_data",
            "company_data",
            "financial_data",
            "audit_trails",
            "user_data"
        ]
        return resource_type.lower() in sensitive_resources