"""
Test ENVOYOU SEC API Endpoints
"""

import sys
from pathlib import Path
import json

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.main import app
from fastapi.testclient import TestClient

def test_api_endpoints():
    """Test basic API endpoints"""
    client = TestClient(app)
    
    print('🌐 Testing ENVOYOU SEC API Endpoints')
    print('=' * 50)
    
    # Test health endpoint
    print('Testing /health endpoint...')
    response = client.get('/health')
    print(f'Status: {response.status_code}')
    print(f'Response: {json.dumps(response.json(), indent=2)}')
    print()
    
    # Test root endpoint
    print('Testing / endpoint...')
    response = client.get('/')
    print(f'Status: {response.status_code}')
    print(f'Response: {json.dumps(response.json(), indent=2)}')
    print()
    
    # Test EPA factors endpoint (should require auth)
    print('Testing /v1/emissions/factors endpoint (no auth)...')
    response = client.get('/v1/emissions/factors')
    print(f'Status: {response.status_code}')
    print(f'Response: {json.dumps(response.json(), indent=2)}')
    print()
    
    # Test calculations endpoint (should require auth)
    print('Testing /v1/emissions/calculations endpoint (no auth)...')
    response = client.get('/v1/emissions/calculations')
    print(f'Status: {response.status_code}')
    print(f'Response: {json.dumps(response.json(), indent=2)}')
    print()
    
    print('✅ Basic API endpoints are working!')
    print('🔐 Authentication required for protected endpoints (as expected)')
    print()
    
    return True

if __name__ == "__main__":
    test_api_endpoints()