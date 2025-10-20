"""
Pytest configuration and fixtures for ENVOYOU SEC API tests
"""

import asyncio
import os
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment variable before any imports
os.environ["TESTING"] = "true"

from app.core.config import settings
from app.core.security import SecurityUtils
from app.db.database import Base, get_db
from app.main import app
from app.models.emissions import Company
from app.models.epa_data import EmissionFactor
from app.models.user import User, UserRole, UserStatus

# Test database URL
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_envoyou_sec.db"

# Create test engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Run Alembic migrations instead of just creating tables
print("DEBUG: Running database migrations...")
try:
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", SQLALCHEMY_DATABASE_URL)

    # Run migrations
    command.upgrade(alembic_cfg, "head")
    print("DEBUG: Database migrations completed")
except Exception as e:
    print(f"ERROR: Failed to run migrations: {e}")
    print("DEBUG: Falling back to creating tables from models...")
    Base.metadata.create_all(bind=engine)
    print("DEBUG: Database tables created from models")

    # Add missing columns to report_locks table that are in the model but not created by metadata.create_all
    try:
        with engine.connect() as conn:
            from sqlalchemy import text

            # Check if unlocked_at column exists, if not add it
            result = conn.execute(text("PRAGMA table_info(report_locks)"))
            columns = [col[1] for col in result.fetchall()]
            if "unlocked_at" not in columns:
                print("DEBUG: Adding missing unlocked_at column to report_locks table")
                conn.execute(
                    text("ALTER TABLE report_locks ADD COLUMN unlocked_at DATETIME")
                )
                conn.commit()
            if "unlocked_by" not in columns:
                print("DEBUG: Adding missing unlocked_by column to report_locks table")
                conn.execute(
                    text("ALTER TABLE report_locks ADD COLUMN unlocked_by VARCHAR(36)")
                )
                # Add foreign key constraint
                conn.execute(
                    text(
                        "CREATE INDEX ix_report_locks_unlocked_by ON report_locks (unlocked_by)"
                    )
                )
                conn.commit()
            print("DEBUG: Report locks table schema updated")
    except Exception as e:
        print(f"ERROR: Failed to update report_locks table: {e}")

    # Add missing columns to emissions_calculations table
    try:
        with engine.connect() as conn:
            from sqlalchemy import text

            # Check existing columns
            result = conn.execute(text("PRAGMA table_info(emissions_calculations)"))
            columns = [col[1] for col in result.fetchall()]

            missing_columns = []
            if "encrypted_input_data" not in columns:
                missing_columns.append(("encrypted_input_data", "TEXT"))
            if "encrypted_emission_factors" not in columns:
                missing_columns.append(("encrypted_emission_factors", "TEXT"))
            if "data_integrity_hash" not in columns:
                missing_columns.append(("data_integrity_hash", "VARCHAR(64)"))
            if "source_documents" not in columns:
                missing_columns.append(("source_documents", "TEXT"))
            if "third_party_verification" not in columns:
                missing_columns.append(
                    ("third_party_verification", "BOOLEAN DEFAULT 0")
                )
            if "validation_status" not in columns:
                missing_columns.append(("validation_status", "VARCHAR(50)"))
            if "calculation_date" not in columns:
                missing_columns.append(("calculation_date", "DATETIME"))

            for col_name, col_type in missing_columns:
                print(
                    f"DEBUG: Adding missing {col_name} column to emissions_calculations table"
                )
                conn.execute(
                    text(
                        f"ALTER TABLE emissions_calculations ADD COLUMN {col_name} {col_type}"
                    )
                )
                conn.commit()

            if missing_columns:
                print("DEBUG: Emissions calculations table schema updated")
    except Exception as e:
        print(f"ERROR: Failed to update emissions_calculations table: {e}")

    # Add missing email verification columns to users table
    try:
        with engine.connect() as conn:
            from sqlalchemy import text

            # Check existing columns in users table
            result = conn.execute(text("PRAGMA table_info(users)"))
            columns = [col[1] for col in result.fetchall()]

            missing_user_columns = []
            if "email_verification_token" not in columns:
                missing_user_columns.append(
                    ("email_verification_token", "VARCHAR(255)")
                )
            if "email_verification_token_expires" not in columns:
                missing_user_columns.append(
                    ("email_verification_token_expires", "DATETIME")
                )
            if "email_verified" not in columns:
                missing_user_columns.append(("email_verified", "BOOLEAN DEFAULT 0"))
            if "email_verified_at" not in columns:
                missing_user_columns.append(("email_verified_at", "DATETIME"))

            for col_name, col_type in missing_user_columns:
                print(f"DEBUG: Adding missing {col_name} column to users table")
                conn.execute(
                    text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                )
                conn.commit()

            if missing_user_columns:
                print(
                    "DEBUG: Users table schema updated with email verification fields"
                )
    except Exception as e:
        print(f"ERROR: Failed to update users table: {e}")

# Check if report_locks table exists and has required columns
try:
    from sqlalchemy import text

    result = engine.execute(text("PRAGMA table_info(report_locks)"))
    columns = result.fetchall()
    print(f"DEBUG: report_locks table columns: {[col[1] for col in columns]}")
    if "unlocked_at" not in [col[1] for col in columns]:
        print("WARNING: unlocked_at column missing from report_locks table")
    if "unlocked_by" not in [col[1] for col in columns]:
        print("WARNING: unlocked_by column missing from report_locks table")
except Exception as e:
    print(f"ERROR: Could not check report_locks table: {e}")

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function", autouse=True)
def db_session():
    """Create a fresh database session for each test"""
    # Create session
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        # Clean up: delete all data from tables in correct order
        db.rollback()
        try:
            # Disable foreign key constraints temporarily for SQLite
            from sqlalchemy import text

            db.execute(text("PRAGMA foreign_keys=OFF"))

            # Define cleanup order to handle foreign key dependencies
            cleanup_tables = [
                "notification_queue",
                "workflow_history",
                "approval_requests",
                "workflows",
                "workflow_templates",
                "consolidation_audit_trail",
                "consolidated_emissions",
                "emissions_calculations",
                "company_entities",
                "emission_factors",
                "companies",
                "users",
            ]

            # Clean up specific tables first
            for table_name in cleanup_tables:
                try:
                    db.execute(text(f"DELETE FROM {table_name}"))
                except Exception as e:
                    # Skip tables that don't exist
                    continue

            # Clean up any remaining tables
            for table in reversed(Base.metadata.sorted_tables):
                if table.name not in cleanup_tables:
                    try:
                        db.execute(table.delete())
                    except Exception as e:
                        continue

            # Reset sequences for SQLite
            db.execute(text("DELETE FROM sqlite_sequence"))

            # Re-enable foreign key constraints
            db.execute(text("PRAGMA foreign_keys=ON"))
            db.commit()
        except Exception as e:
            print(f"Warning: Database cleanup failed: {e}")
            db.rollback()
        finally:
            db.close()


@pytest.fixture(scope="function")
def client() -> Generator:
    """Create a test client"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    security = SecurityUtils()

    # Always recreate the test user with correct password
    existing_user = db_session.query(User).filter(User.username == "testuser").first()
    if existing_user:
        db_session.delete(existing_user)
        db_session.commit()

    user = User(
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        hashed_password=security.get_password_hash("TestPass123!"),
        role=UserRole.FINANCE_TEAM,
        status=UserStatus.ACTIVE,
        is_active=True,
        email_verified=True,  # Set to verified for test user
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def admin_user(db_session):
    """Create an admin test user"""
    security = SecurityUtils()

    # Check if user already exists
    existing_user = db_session.query(User).filter(User.username == "admin").first()
    if existing_user:
        return existing_user

    user = User(
        email="admin@example.com",
        username="admin",
        full_name="Admin User",
        hashed_password=security.get_password_hash("AdminPass123!"),
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        is_active=True,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def cfo_user(db_session):
    """Create a CFO test user"""
    security = SecurityUtils()

    # Check if user already exists
    existing_user = db_session.query(User).filter(User.username == "cfo").first()
    if existing_user:
        return existing_user

    user = User(
        email="cfo@example.com",
        username="cfo",
        full_name="CFO User",
        hashed_password=security.get_password_hash("CfoPass123!"),
        role=UserRole.CFO,
        status=UserStatus.ACTIVE,
        is_active=True,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def auditor_user(db_session):
    """Create an auditor test user"""
    import uuid

    security = SecurityUtils()
    unique_id = str(uuid.uuid4())[:8]

    # Check if user already exists
    existing_user = (
        db_session.query(User).filter(User.username == f"auditor{unique_id}").first()
    )
    if existing_user:
        return existing_user

    user = User(
        email=f"auditor{unique_id}@example.com",
        username=f"auditor{unique_id}",
        full_name="Auditor User",
        hashed_password=security.get_password_hash("AuditorPass123!"),
        role=UserRole.AUDITOR,
        status=UserStatus.ACTIVE,
        is_active=True,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def auth_headers(client, test_user):
    """Get authentication headers for test user"""
    response = client.post(
        "/v1/auth/login", json={"email": test_user.email, "password": "TestPass123!"}
    )

    assert response.status_code == 200
    token = response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(client, admin_user):
    """Get authentication headers for admin user"""
    response = client.post(
        "/v1/auth/login", json={"email": admin_user.email, "password": "AdminPass123!"}
    )

    assert response.status_code == 200
    token = response.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_emission_factor():
    """Sample emission factor data for testing"""
    from datetime import datetime

    return {
        "factor_name": "Natural Gas Combustion",
        "factor_code": "NG_COMB_001",
        "category": "fuel",
        "fuel_type": "natural_gas",
        "unit": "kg CO2e/MMBtu",
        "co2_factor": 53.06,
        "ch4_factor": 0.001,
        "n2o_factor": 0.0001,
        "co2e_factor": 53.11,
        "source": "EPA_GHGRP",
        "publication_year": 2023,
        "version": "2023.1",
        "valid_from": datetime(2023, 1, 1),
        "description": "Emission factor for natural gas combustion",
    }


@pytest.fixture
def test_company(db_session):
    """Create a test company for emissions calculations"""
    import time
    import uuid

    # Use unique CIK and ticker based on UUID and timestamp to avoid conflicts
    unique_suffix = (
        f"{uuid.uuid4().hex[:6].upper()}{int(time.time()*1000000) % 1000000}"
    )
    unique_cik = f"{unique_suffix}"
    unique_ticker = f"TST{unique_suffix[:5]}"

    company = Company(
        name="Test Company Inc.",
        ticker=unique_ticker,
        cik=unique_cik,
        industry="Manufacturing",
        sector="Industrial",
        headquarters_country="United States",
        fiscal_year_end="12-31",
        reporting_year=2023,
        is_public_company=True,
        market_cap_category="mid-cap",
    )

    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)

    return company


@pytest.fixture
def test_emission_factors(db_session):
    """Create test emission factors"""
    from datetime import datetime

    # Natural gas factor
    ng_factor = EmissionFactor(
        factor_name="Natural Gas Combustion",
        factor_code="NG_COMB_001",
        category="fuel",
        fuel_type="natural_gas",
        unit="kg CO2e/MMBtu",
        co2_factor=53.06,
        ch4_factor=0.001,
        n2o_factor=0.0001,
        co2e_factor=53.11,
        source="EPA_GHGRP",
        publication_year=2023,
        version="2023.1",
        valid_from=datetime(2023, 1, 1),
        is_current=True,
        description="EPA emission factor for natural gas combustion",
    )

    # Electricity factor for California
    elec_factor = EmissionFactor(
        factor_name="California Electricity Grid",
        factor_code="ELEC_CAMX_001",
        category="electricity",
        electricity_region="camx",
        unit="kg CO2e/MWh",
        co2_factor=200.5,
        ch4_factor=None,
        n2o_factor=None,
        co2e_factor=200.5,
        source="EPA_EGRID",
        publication_year=2023,
        version="2023.1",
        valid_from=datetime(2023, 1, 1),
        is_current=True,
        description="EPA eGRID emission factor for California",
    )

    db_session.add_all([ng_factor, elec_factor])
    db_session.commit()
    return {"natural_gas": ng_factor, "electricity": elec_factor}
