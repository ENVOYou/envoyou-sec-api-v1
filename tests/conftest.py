"""
Pytest configuration and fixtures for ENVOYOU SEC API tests
"""

import pytest
import asyncio
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import get_db, Base
from app.core.config import settings
from app.models.user import User, UserRole, UserStatus
from app.core.security import SecurityUtils

# Test database URL
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

# Create test engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

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


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session) -> Generator:
    """Create a test client"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def test_user(db_session):
    """Create a test user"""
    security = SecurityUtils()
    
    user = User(
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        hashed_password=security.get_password_hash("testpassword123!"),
        role=UserRole.FINANCE_TEAM,
        status=UserStatus.ACTIVE,
        is_active=True
    )
    
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    return user


@pytest.fixture
def admin_user(db_session):
    """Create an admin test user"""
    security = SecurityUtils()
    
    user = User(
        email="admin@example.com",
        username="admin",
        full_name="Admin User",
        hashed_password=security.get_password_hash("adminpassword123!"),
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        is_active=True
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
        hashed_password=security.get_password_hash("cfopassword123!"),
        role=UserRole.CFO,
        status=UserStatus.ACTIVE,
        is_active=True
    )
    
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    return user


@pytest.fixture
def auditor_user(db_session):
    """Create an auditor test user"""
    security = SecurityUtils()
    
    user = User(
        email="auditor@example.com",
        username="auditor",
        full_name="Auditor User",
        hashed_password=security.get_password_hash("auditorpassword123!"),
        role=UserRole.AUDITOR,
        status=UserStatus.ACTIVE,
        is_active=True
    )
    
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    return user


@pytest.fixture
def auth_headers(client, test_user):
    """Get authentication headers for test user"""
    response = client.post(
        "/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword123!"
        }
    )
    
    assert response.status_code == 200
    token = response.json()["access_token"]
    
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(client, admin_user):
    """Get authentication headers for admin user"""
    response = client.post(
        "/v1/auth/login",
        json={
            "email": admin_user.email,
            "password": "adminpassword123!"
        }
    )
    
    assert response.status_code == 200
    token = response.json()["access_token"]
    
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_emission_factor():
    """Sample emission factor data for testing"""
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
        "valid_from": "2023-01-01T00:00:00Z",
        "description": "Emission factor for natural gas combustion"
    }