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

# Create all tables once at module load
Base.metadata.create_all(bind=engine)

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

    # Check if user already exists
    existing_user = db_session.query(User).filter(User.username == "testuser").first()
    if existing_user:
        return existing_user

    user = User(
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        hashed_password=security.get_password_hash("TestPass123!"),
        role=UserRole.FINANCE_TEAM,
        status=UserStatus.ACTIVE,
        is_active=True,
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
    import uuid

    # Use unique CIK and ticker based on UUID to avoid conflicts
    unique_suffix = uuid.uuid4().hex[:6].upper()
    unique_cik = f"{unique_suffix}"
    unique_ticker = f"TST{unique_suffix[:3]}"

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
