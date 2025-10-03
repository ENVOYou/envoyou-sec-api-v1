"""
Test authentication endpoints and functionality
"""

import pytest
from fastapi.testclient import TestClient

from app.models.user import UserRole


class TestAuthentication:
    """Test authentication endpoints"""
    
    def test_login_success(self, client: TestClient, test_user):
        """Test successful login"""
        response = client.post(
            "/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword123!"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_id"] == str(test_user.id)
        assert data["role"] == test_user.role.value
    
    def test_login_invalid_credentials(self, client: TestClient, test_user):
        """Test login with invalid credentials"""
        response = client.post(
            "/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]
    
    def test_login_nonexistent_user(self, client: TestClient):
        """Test login with non-existent user"""
        response = client.post(
            "/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "password123!"
            }
        )
        
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]
    
    def test_get_current_user(self, client: TestClient, auth_headers):
        """Test getting current user information"""
        response = client.get("/v1/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert "email" in data
        assert "role" in data
        assert data["email"] == "test@example.com"
    
    def test_get_user_permissions(self, client: TestClient, auth_headers):
        """Test getting user permissions"""
        response = client.get("/v1/auth/permissions", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "user_id" in data
        assert "role" in data
        assert "permissions" in data
        assert isinstance(data["permissions"], dict)
    
    def test_unauthorized_access(self, client: TestClient):
        """Test accessing protected endpoint without authentication"""
        response = client.get("/v1/auth/me")
        
        assert response.status_code == 401
    
    def test_invalid_token(self, client: TestClient):
        """Test accessing protected endpoint with invalid token"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/v1/auth/me", headers=headers)
        
        assert response.status_code == 401
    
    def test_refresh_token(self, client: TestClient, test_user):
        """Test token refresh functionality"""
        # First login to get tokens
        login_response = client.post(
            "/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword123!"
            }
        )
        
        assert login_response.status_code == 200
        refresh_token = login_response.json()["refresh_token"]
        
        # Use refresh token to get new access token
        refresh_response = client.post(
            "/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        
        assert refresh_response.status_code == 200
        data = refresh_response.json()
        
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    def test_logout(self, client: TestClient, auth_headers):
        """Test logout functionality"""
        response = client.post("/v1/auth/logout", headers=auth_headers)
        
        assert response.status_code == 200
        assert "Successfully logged out" in response.json()["message"]


class TestUserRegistration:
    """Test user registration (admin only)"""
    
    def test_register_user_as_admin(self, client: TestClient, admin_auth_headers):
        """Test user registration by admin"""
        user_data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "full_name": "New User",
            "password": "NewPassword123!",
            "role": "finance_team"
        }
        
        response = client.post(
            "/v1/auth/register",
            json=user_data,
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["email"] == user_data["email"]
        assert data["username"] == user_data["username"]
        assert data["role"] == user_data["role"]
    
    def test_register_user_as_non_admin(self, client: TestClient, auth_headers):
        """Test user registration by non-admin (should fail)"""
        user_data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "full_name": "New User",
            "password": "NewPassword123!",
            "role": "finance_team"
        }
        
        response = client.post(
            "/v1/auth/register",
            json=user_data,
            headers=auth_headers
        )
        
        assert response.status_code == 403
    
    def test_register_duplicate_user(self, client: TestClient, admin_auth_headers, test_user):
        """Test registering user with existing email"""
        user_data = {
            "email": test_user.email,
            "username": "differentusername",
            "full_name": "Different User",
            "password": "NewPassword123!",
            "role": "finance_team"
        }
        
        response = client.post(
            "/v1/auth/register",
            json=user_data,
            headers=admin_auth_headers
        )
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]


class TestPasswordChange:
    """Test password change functionality"""
    
    def test_change_password_success(self, client: TestClient, auth_headers):
        """Test successful password change"""
        password_data = {
            "current_password": "testpassword123!",
            "new_password": "NewPassword123!",
            "confirm_password": "NewPassword123!"
        }
        
        response = client.post(
            "/v1/auth/change-password",
            json=password_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert "Password changed successfully" in response.json()["message"]
    
    def test_change_password_wrong_current(self, client: TestClient, auth_headers):
        """Test password change with wrong current password"""
        password_data = {
            "current_password": "wrongpassword",
            "new_password": "NewPassword123!",
            "confirm_password": "NewPassword123!"
        }
        
        response = client.post(
            "/v1/auth/change-password",
            json=password_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "Current password is incorrect" in response.json()["detail"]
    
    def test_change_password_mismatch(self, client: TestClient, auth_headers):
        """Test password change with mismatched new passwords"""
        password_data = {
            "current_password": "testpassword123!",
            "new_password": "NewPassword123!",
            "confirm_password": "DifferentPassword123!"
        }
        
        response = client.post(
            "/v1/auth/change-password",
            json=password_data,
            headers=auth_headers
        )
        
        assert response.status_code == 422  # Validation error


class TestAuditSession:
    """Test audit session functionality"""
    
    def test_create_audit_session_as_auditor(self, client: TestClient, auditor_user):
        """Test audit session creation by auditor"""
        # Login as auditor
        login_response = client.post(
            "/v1/auth/login",
            json={
                "email": auditor_user.email,
                "password": "auditorpassword123!"
            }
        )
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.post("/v1/auth/audit-session", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "session_id" in data
        assert "auditor_id" in data
        assert "created_at" in data
        assert "expires_at" in data
    
    def test_create_audit_session_as_non_auditor(self, client: TestClient, auth_headers):
        """Test audit session creation by non-auditor (should fail)"""
        response = client.post("/v1/auth/audit-session", headers=auth_headers)
        
        assert response.status_code == 403
        assert "Only auditors can create audit sessions" in response.json()["detail"]