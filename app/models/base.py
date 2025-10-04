"""
Base model classes and common fields
"""

from sqlalchemy import Column, DateTime, String, Boolean, TypeDecorator, CHAR, Text
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID, JSONB as PostgresJSONB
from sqlalchemy.sql import func
import uuid
import json
from datetime import datetime

from app.db.database import Base


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class GUID(TypeDecorator):
    """
    Platform-independent GUID type.
    Uses PostgreSQL's UUID type when available, otherwise uses CHAR(36).
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgresUUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            # For SQLite and other databases, always return string
            if isinstance(value, uuid.UUID):
                return str(value)
            elif isinstance(value, str):
                try:
                    # Validate it's a valid UUID string
                    uuid.UUID(value)
                    return value
                except ValueError:
                    # If not valid UUID, generate new one
                    return str(uuid.uuid4())
            else:
                return str(uuid.uuid4())

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            # For PostgreSQL, return UUID object
            if dialect.name == 'postgresql':
                if isinstance(value, uuid.UUID):
                    return value
                else:
                    try:
                        return uuid.UUID(str(value))
                    except (ValueError, TypeError):
                        return None
            else:
                # For SQLite and other databases, return string to avoid RETURNING issues
                if isinstance(value, str):
                    return value
                else:
                    return str(value)


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class UUIDMixin:
    """Mixin for UUID primary key"""
    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False)


class BaseModel(Base, UUIDMixin, TimestampMixin):
    """Base model with UUID primary key and timestamps"""
    __abstract__ = True


class JSON(TypeDecorator):
    """
    Platform-independent JSON type.
    Uses PostgreSQL's JSONB type when available, otherwise uses TEXT.
    """
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgresJSONB())
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value  # PostgreSQL handles JSON natively
        else:
            # For SQLite and other databases, serialize to JSON string
            return json.dumps(value, cls=DateTimeEncoder)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value  # PostgreSQL returns dict/list directly
        else:
            # For SQLite and other databases, deserialize from JSON string
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value

    def _json_serial(self, obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError("Type not serializable")


class AuditMixin:
    """Mixin for audit trail fields"""
    created_by = Column(GUID(), nullable=True)
    updated_by = Column(GUID(), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)