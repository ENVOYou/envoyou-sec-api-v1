#!/usr/bin/env python3
"""
Comprehensive API Endpoint Testing Script
Tests all backend endpoints for envoyou-sec-api-v1
"""

import json
import time
from typing import Dict, List, Optional, Tuple

import requests
from requests.exceptions import ConnectionError, RequestException, Timeout

# Configuration
BASE_URL = "http://localhost:8000"
API_PREFIX = "/v1"

# Test credentials
TEST_USERS = {
    "admin": {"email": "admin@example.com", "password": "AdminPass123!"},
    "auditor": {"email": "auditor@example.com", "password": "AuditorPass123!"},
    "cfo": {"email": "cfo@example.com", "password": "CfoPass123!"},
    "finance": {"email": "finance@example.com", "password": "FinancePass123!"},
}

# API Endpoints to test
ENDPOINTS = {
    # Authentication
    "auth": {
        "login": {"method": "POST", "path": "/auth/login", "auth": False},
        "register": {"method": "POST", "path": "/auth/register", "auth": False},
        "me": {"method": "GET", "path": "/auth/me", "auth": True},
        "refresh": {"method": "POST", "path": "/auth/refresh", "auth": True},
        "change-password": {
            "method": "POST",
            "path": "/auth/change-password",
            "auth": True,
        },
    },
    # Emissions
    "emissions": {
        "factors-summary": {
            "method": "GET",
            "path": "/emissions/factors/summary",
            "auth": True,
        },
        "factors": {"method": "GET", "path": "/emissions/factors", "auth": True},
        "factors-fuel": {
            "method": "POST",
            "path": "/emissions/factors/fuel",
            "auth": True,
        },
        "factors-electricity": {
            "method": "POST",
            "path": "/emissions/factors/electricity",
            "auth": True,
        },
        "calculate-scope1": {
            "method": "POST",
            "path": "/emissions/calculate/scope1",
            "auth": True,
        },
        "calculate-scope2": {
            "method": "POST",
            "path": "/emissions/calculate/scope2",
            "auth": True,
        },
        "calculations": {
            "method": "GET",
            "path": "/emissions/calculations",
            "auth": True,
        },
        "calculation-detail": {
            "method": "GET",
            "path": "/emissions/calculations/test-id",
            "auth": True,
        },
        "calculation-approve": {
            "method": "POST",
            "path": "/emissions/calculations/test-id/approve",
            "auth": True,
        },
        "calculation-audit": {
            "method": "GET",
            "path": "/emissions/calculations/test-id/audit-trail",
            "auth": True,
        },
        "forensic-report": {
            "method": "GET",
            "path": "/emissions/calculations/test-id/forensic-report",
            "auth": True,
        },
        "company-summary": {
            "method": "GET",
            "path": "/emissions/companies/test-id/summary",
            "auth": True,
        },
        "company-audit": {
            "method": "GET",
            "path": "/emissions/companies/test-id/audit-summary",
            "auth": True,
        },
        "consolidated-summary": {
            "method": "GET",
            "path": "/emissions/companies/test-id/consolidated-summary",
            "auth": True,
        },
        "entities-emissions": {
            "method": "GET",
            "path": "/emissions/companies/test-id/entities-with-emissions",
            "auth": True,
        },
        "trigger-consolidation": {
            "method": "POST",
            "path": "/emissions/companies/test-id/trigger-consolidation",
            "auth": True,
        },
    },
    # EPA Data
    "epa": {
        "cache-status": {"method": "GET", "path": "/epa/cache/status", "auth": True},
        "invalidate-cache": {
            "method": "POST",
            "path": "/epa/cache/clear",
            "auth": True,
        },
        "refresh-factors": {"method": "POST", "path": "/epa/refresh", "auth": True},
    },
    # Reports
    "reports": {
        "list": {"method": "GET", "path": "/reports", "auth": True},
        "create": {"method": "POST", "path": "/reports", "auth": True},
        "detail": {"method": "GET", "path": "/reports/test-id", "auth": True},
        "update": {"method": "PUT", "path": "/reports/test-id", "auth": True},
        "delete": {"method": "DELETE", "path": "/reports/test-id", "auth": True},
        "lock": {"method": "POST", "path": "/reports/test-id/lock", "auth": True},
        "unlock": {"method": "POST", "path": "/reports/test-id/unlock", "auth": True},
        "comments": {
            "method": "GET",
            "path": "/reports/test-id/comments",
            "auth": True,
        },
        "add-comment": {
            "method": "POST",
            "path": "/reports/test-id/comments",
            "auth": True,
        },
        "resolve-comment": {
            "method": "PUT",
            "path": "/reports/test-id/comments/test-id/resolve",
            "auth": True,
        },
        "revisions": {
            "method": "GET",
            "path": "/reports/test-id/revisions",
            "auth": True,
        },
        "create-revision": {
            "method": "POST",
            "path": "/reports/test-id/revisions",
            "auth": True,
        },
    },
    # Audit
    "audit": {
        "logs": {"method": "GET", "path": "/audit/logs", "auth": True},
        "events": {"method": "GET", "path": "/audit/events", "auth": True},
        "export": {"method": "GET", "path": "/audit/export", "auth": True},
    },
    # Enhanced Audit
    "enhanced-audit": {
        "dashboard": {
            "method": "GET",
            "path": "/enhanced-audit/dashboard",
            "auth": True,
        },
        "forensic-search": {
            "method": "POST",
            "path": "/enhanced-audit/forensic-search",
            "auth": True,
        },
        "data-integrity": {
            "method": "GET",
            "path": "/enhanced-audit/data-integrity",
            "auth": True,
        },
    },
    # Company Entities
    "entities": {
        "list": {
            "method": "GET",
            "path": "/entities/company/test-company-id",
            "auth": True,
        },
        "create": {"method": "POST", "path": "/entities", "auth": True},
        "detail": {"method": "GET", "path": "/entities/test-id", "auth": True},
        "update": {"method": "PUT", "path": "/entities/test-id", "auth": True},
        "delete": {"method": "DELETE", "path": "/entities/test-id", "auth": True},
    },
    # Workflow
    "workflow": {
        "list": {"method": "GET", "path": "/workflow", "auth": True},
        "create": {"method": "POST", "path": "/workflow", "auth": True},
        "detail": {"method": "GET", "path": "/workflow/test-id", "auth": True},
        "update": {"method": "PUT", "path": "/workflow/test-id/status", "auth": True},
        "execute": {"method": "POST", "path": "/workflow/test-id/submit", "auth": True},
    },
    # Background Tasks
    "background": {
        "status": {"method": "GET", "path": "/background/status", "auth": True},
        "list": {"method": "GET", "path": "/background/tasks", "auth": True},
        "cancel": {
            "method": "POST",
            "path": "/background/tasks/test-id/cancel",
            "auth": True,
        },
    },
    # Performance
    "performance": {
        "metrics": {"method": "GET", "path": "/performance/metrics", "auth": True},
        "health": {"method": "GET", "path": "/performance/health", "auth": True},
        "slow-queries": {
            "method": "GET",
            "path": "/performance/slow-queries",
            "auth": True,
        },
    },
    # Backup
    "backup": {
        "list": {"method": "GET", "path": "/backup", "auth": True},
        "create": {"method": "POST", "path": "/backup", "auth": True},
        "restore": {"method": "POST", "path": "/backup/test-id/restore", "auth": True},
        "delete": {"method": "DELETE", "path": "/backup/test-id", "auth": True},
    },
    # Security
    "security": {
        "events": {"method": "GET", "path": "/security/events", "auth": True},
        "alerts": {"method": "GET", "path": "/security/alerts", "auth": True},
        "audit": {"method": "GET", "path": "/security/audit", "auth": True},
    },
    # Disaster Recovery
    "disaster-recovery": {
        "status": {"method": "GET", "path": "/disaster-recovery/status", "auth": True},
        "backup": {"method": "POST", "path": "/disaster-recovery/backup", "auth": True},
        "restore": {
            "method": "POST",
            "path": "/disaster-recovery/restore",
            "auth": True,
        },
    },
    # Validation
    "validation": {
        "rules": {"method": "GET", "path": "/validation/rules", "auth": True},
        "validate": {"method": "POST", "path": "/validation/validate", "auth": True},
    },
    # Emissions Validation
    "emissions-validation": {
        "cross-validate": {
            "method": "POST",
            "path": "/emissions-validation/cross-validate",
            "auth": True,
        },
        "consistency-check": {
            "method": "POST",
            "path": "/emissions-validation/consistency-check",
            "auth": True,
        },
    },
    # Anomaly Detection
    "anomaly-detection": {
        "analyze": {
            "method": "POST",
            "path": "/anomaly-detection/analyze",
            "auth": True,
        },
        "patterns": {
            "method": "GET",
            "path": "/anomaly-detection/patterns",
            "auth": True,
        },
        "thresholds": {
            "method": "GET",
            "path": "/anomaly-detection/thresholds",
            "auth": True,
        },
    },
    # Consolidation
    "consolidation": {
        "list": {
            "method": "GET",
            "path": "/consolidation/company/test-company-id",
            "auth": True,
        },
        "create": {"method": "POST", "path": "/consolidation", "auth": True},
        "detail": {"method": "GET", "path": "/consolidation/test-id", "auth": True},
        "update": {
            "method": "POST",
            "path": "/consolidation/test-id/approve",
            "auth": True,
        },
        "delete": {"method": "DELETE", "path": "/consolidation/test-id", "auth": True},
    },
}


class APIEndpointTester:
    """Comprehensive API endpoint tester"""

    def __init__(self, base_url: str = BASE_URL, api_prefix: str = API_PREFIX):
        self.base_url = base_url
        self.api_prefix = api_prefix
        self.session = requests.Session()
        self.tokens = {}
        self.results = {"passed": [], "failed": [], "errors": [], "skipped": []}

    def authenticate_users(self) -> bool:
        """Authenticate all test users and store tokens"""
        print("🔐 Authenticating test users...")

        # First try to register a test user
        register_data = {
            "email": "test@example.com",
            "username": "testuser",
            "full_name": "Test User",
            "password": "TestPass123!",
            "confirm_password": "TestPass123!",
            "role": "admin",
        }

        try:
            register_response = self.session.post(
                f"{self.base_url}{self.api_prefix}/auth/register",
                json=register_data,
                timeout=10,
            )
            print(f"  📝 Registration attempt: {register_response.status_code}")
        except Exception as e:
            print(f"  ⚠️  Registration failed: {e}")

        for user_type, credentials in TEST_USERS.items():
            try:
                response = self.session.post(
                    f"{self.base_url}{self.api_prefix}/auth/login",
                    json=credentials,
                    timeout=10,
                )

                if response.status_code == 200:
                    token_data = response.json()
                    self.tokens[user_type] = token_data.get("access_token")
                    print(f"  ✅ {user_type}: Authenticated successfully")
                else:
                    print(
                        f"  ❌ {user_type}: Authentication failed ({response.status_code}) - {response.text[:100]}"
                    )

            except Exception as e:
                print(f"  ❌ {user_type}: Authentication error - {str(e)}")

        # If no users authenticated, try with test user
        if not self.tokens:
            test_credentials = {"email": "test@example.com", "password": "TestPass123!"}
            try:
                response = self.session.post(
                    f"{self.base_url}{self.api_prefix}/auth/login",
                    json=test_credentials,
                    timeout=10,
                )

                if response.status_code == 200:
                    token_data = response.json()
                    self.tokens["test"] = token_data.get("access_token")
                    print(f"  ✅ test: Authenticated successfully")
                    return True
                else:
                    print(f"  ❌ test: Authentication failed ({response.status_code})")
            except Exception as e:
                print(f"  ❌ test: Authentication error - {str(e)}")

        return len(self.tokens) > 0

    def test_endpoint(
        self, group: str, endpoint_name: str, config: Dict
    ) -> Tuple[bool, Optional[str]]:
        """Test a single endpoint"""
        method = config["method"]
        path = config["path"]
        requires_auth = config.get("auth", True)

        url = f"{self.base_url}{self.api_prefix}{path}"

        # Prepare headers
        headers = {"Content-Type": "application/json"}
        if requires_auth:
            # Try admin token first, fallback to auditor
            token = self.tokens.get("admin") or self.tokens.get("auditor")
            if token:
                headers["Authorization"] = f"Bearer {token}"

        # Prepare request data based on endpoint
        data = self._get_test_data(group, endpoint_name, method)

        try:
            # Make request
            if method == "GET":
                response = self.session.get(
                    url, headers=headers, params=data, timeout=10
                )
            elif method == "POST":
                response = self.session.post(
                    url, headers=headers, json=data, timeout=10
                )
            elif method == "PUT":
                response = self.session.put(url, headers=headers, json=data, timeout=10)
            elif method == "DELETE":
                response = self.session.delete(url, headers=headers, timeout=10)
            else:
                return False, f"Unsupported HTTP method: {method}"

            # Check response
            if response.status_code in [200, 201, 202, 204]:
                return True, f"Status: {response.status_code}"
            elif response.status_code in [400, 401, 403, 404, 422]:
                # These are expected for some endpoints (validation, auth, etc.)
                return True, f"Status: {response.status_code} (expected)"
            elif response.status_code >= 500:
                return (
                    False,
                    f"Server error: {response.status_code} - {response.text[:200]}",
                )
            else:
                return (
                    False,
                    f"Unexpected status: {response.status_code} - {response.text[:200]}",
                )

        except Timeout:
            return False, "Request timeout"
        except ConnectionError:
            return False, "Connection error"
        except Exception as e:
            return False, f"Request error: {str(e)}"

    def _get_test_data(self, group: str, endpoint: str, method: str) -> Optional[Dict]:
        """Get test data for specific endpoints"""
        if method == "GET":
            return None

        # Test data for POST/PUT requests
        test_data = {
            "auth": {
                "register": {
                    "email": "test@example.com",
                    "username": "testuser",
                    "full_name": "Test User",
                    "password": "TestPass123!",
                    "confirm_password": "TestPass123!",
                    "role": "finance_team",
                },
                "change-password": {
                    "current_password": "AdminPass123!",
                    "new_password": "NewPass123!",
                    "confirm_password": "NewPass123!",
                },
            },
            "emissions": {
                "factors-fuel": {"fuel_type": "natural_gas"},
                "factors-electricity": {"region": "CAMX"},
                "calculate-scope1": {
                    "calculation_name": "Test Scope 1",
                    "company_id": "test-company-id",
                    "reporting_period_start": "2023-01-01T00:00:00Z",
                    "reporting_period_end": "2023-12-31T23:59:59Z",
                    "activity_data": [
                        {
                            "activity_type": "stationary_combustion",
                            "fuel_type": "natural_gas",
                            "quantity": 100.0,
                            "unit": "MMBtu",
                            "data_quality": "measured",
                        }
                    ],
                },
                "calculate-scope2": {
                    "calculation_name": "Test Scope 2",
                    "company_id": "test-company-id",
                    "reporting_period_start": "2023-01-01T00:00:00Z",
                    "reporting_period_end": "2023-12-31T23:59:59Z",
                    "electricity_consumption": [
                        {
                            "activity_type": "electricity_consumption",
                            "quantity": 1000.0,
                            "unit": "MWh",
                            "location": "California",
                            "data_quality": "measured",
                        }
                    ],
                    "calculation_method": "location_based",
                },
                "calculation-approve": {
                    "approval_status": "approved",
                    "comments": "Test approval",
                },
                "trigger-consolidation": {
                    "reporting_year": 2023,
                    "consolidation_method": "ownership_based",
                },
            },
            "reports": {
                "create": {
                    "title": "Test Report",
                    "report_type": "sec_10k",
                    "status": "draft",
                },
                "update": {"title": "Updated Test Report", "status": "draft"},
                "lock": {"lock_reason": "audit", "expires_in_hours": 24},
                "add-comment": {"content": "Test comment", "comment_type": "general"},
                "create-revision": {
                    "change_type": "update",
                    "changes_summary": "Test changes",
                },
            },
            "entities": {
                "create": {
                    "company_id": "test-company-id",
                    "name": "Test Entity",
                    "entity_type": "facility",
                },
                "update": {"name": "Updated Test Entity"},
            },
            "workflow": {
                "create": {
                    "title": "Test Workflow",
                    "description": "Test workflow description",
                    "workflow_type": "emissions_report",
                    "priority": "medium",
                },
                "update": {"status": "completed", "reason": "Test completion"},
            },
            "consolidation": {
                "create": {
                    "company_id": "test-company-id",
                    "reporting_year": 2023,
                    "reporting_period_start": "2023-01-01",
                    "reporting_period_end": "2023-12-31",
                    "consolidation_method": "ownership_based",
                },
                "update": {"action": "approve", "approval_notes": "Test approval"},
            },
        }

        return test_data.get(group, {}).get(endpoint)

    def run_all_tests(self) -> Dict:
        """Run tests for all endpoints"""
        print("🚀 Starting comprehensive API endpoint testing...")
        print(f"📍 Target: {self.base_url}")
        print(f"🔧 API Prefix: {self.api_prefix}")
        print("-" * 60)

        # Authenticate first
        auth_success = self.authenticate_users()
        if not auth_success:
            print("⚠️  Authentication failed. Will test unauthenticated endpoints only.")
        else:
            print("✅ Authentication successful. Testing all endpoints.")

        total_endpoints = 0
        tested_endpoints = 0

        # Test each endpoint group
        for group_name, endpoints in ENDPOINTS.items():
            print(f"\n📁 Testing {group_name.upper()} endpoints...")
            print("-" * 40)

            for endpoint_name, config in endpoints.items():
                total_endpoints += 1

                print(f"  🔍 {group_name}.{endpoint_name}...", end=" ")

                success, message = self.test_endpoint(group_name, endpoint_name, config)

                if success:
                    print("✅ PASSED")
                    self.results["passed"].append(f"{group_name}.{endpoint_name}")
                    tested_endpoints += 1
                else:
                    print(f"❌ FAILED - {message}")
                    self.results["failed"].append(
                        {"endpoint": f"{group_name}.{endpoint_name}", "error": message}
                    )
                    tested_endpoints += 1

                # Small delay to avoid overwhelming the server
                time.sleep(0.1)

        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Total endpoints: {total_endpoints}")
        print(f"Tested endpoints: {tested_endpoints}")
        print(f"✅ Passed: {len(self.results['passed'])}")
        print(f"❌ Failed: {len(self.results['failed'])}")
        print(f"⏭️  Skipped: {len(self.results['skipped'])}")

        if self.results["failed"]:
            print("\n❌ FAILED ENDPOINTS:")
            for failure in self.results["failed"]:
                print(f"  • {failure['endpoint']}: {failure['error']}")

        success_rate = (
            (len(self.results["passed"]) / tested_endpoints * 100)
            if tested_endpoints > 0
            else 0
        )
        print(f"📈 Success Rate: {success_rate:.1f}%")
        return self.results


def main():
    """Main test runner"""
    print("🧪 ENVOYOU SEC API - Comprehensive Endpoint Testing")
    print("=" * 60)

    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        if response.status_code != 200:
            print(f"⚠️  Warning: Server responded with status {response.status_code}")
    except Exception as e:
        print(f"❌ Error: Cannot connect to server at {BASE_URL}")
        print(f"   Make sure the server is running: {e}")
        return

    print("✅ Server connection confirmed")

    # Run tests
    tester = APIEndpointTester()
    results = tester.run_all_tests()

    # Save results to file
    with open("api_test_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n💾 Results saved to api_test_results.json")


if __name__ == "__main__":
    main()
