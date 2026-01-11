"""
Test suite for Buyer Request Workflow API
Run with: pytest test_main.py -v
"""

import pytest
from fastapi.testclient import TestClient
from main import app, init_db
import os

# Initialize test database
if os.path.exists("workflow.db"):
    os.remove("workflow.db")
init_db()

client = TestClient(app)

class TestAuthentication:
    def test_buyer_login(self):
        response = client.post("/auth/login", json={
            "userId": "buyer1",
            "role": "buyer"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["role"] == "buyer"
        assert data["factoryId"] is None
    
    def test_factory_login(self):
        response = client.post("/auth/login", json={
            "userId": "factory_user1",
            "role": "factory",
            "factoryId": "F001"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["role"] == "factory"
        assert data["factoryId"] == "F001"
    
    def test_factory_login_without_factory_id(self):
        response = client.post("/auth/login", json={
            "userId": "factory_user1",
            "role": "factory"
        })
        assert response.status_code == 400

class TestEvidence:
    @pytest.fixture
    def factory_token(self):
        response = client.post("/auth/login", json={
            "userId": "factory_user1",
            "role": "factory",
            "factoryId": "F001"
        })
        return response.json()["token"]
    
    @pytest.fixture
    def buyer_token(self):
        response = client.post("/auth/login", json={
            "userId": "buyer1",
            "role": "buyer"
        })
        return response.json()["token"]
    
    def test_create_evidence_as_factory(self, factory_token):
        response = client.post("/evidence", 
            headers={"Authorization": f"Bearer {factory_token}"},
            json={
                "name": "Safety Test Report",
                "docType": "Test Report",
                "expiry": "2025-12-31",
                "notes": "Annual compliance"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "evidenceId" in data
        assert "versionId" in data
        assert data["evidenceId"].startswith("E")
        assert data["versionId"].startswith("V")
    
    def test_create_evidence_as_buyer_fails(self, buyer_token):
        response = client.post("/evidence",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={
                "name": "Test",
                "docType": "Report",
                "notes": "Should fail"
            }
        )
        assert response.status_code == 403
    
    def test_add_version(self, factory_token):
        # First create evidence
        create_response = client.post("/evidence",
            headers={"Authorization": f"Bearer {factory_token}"},
            json={
                "name": "Certificate",
                "docType": "ISO Certificate",
                "notes": "Version 1"
            }
        )
        evidence_id = create_response.json()["evidenceId"]
        
        # Add version
        version_response = client.post(f"/evidence/{evidence_id}/versions",
            headers={"Authorization": f"Bearer {factory_token}"},
            json={
                "notes": "Updated certificate",
                "expiry": "2026-06-30"
            }
        )
        assert version_response.status_code == 200
        assert version_response.json()["evidenceId"] == evidence_id

class TestRequests:
    @pytest.fixture
    def buyer_token(self):
        response = client.post("/auth/login", json={
            "userId": "buyer1",
            "role": "buyer"
        })
        return response.json()["token"]
    
    @pytest.fixture
    def factory_token(self):
        response = client.post("/auth/login", json={
            "userId": "factory_user1",
            "role": "factory",
            "factoryId": "F001"
        })
        return response.json()["token"]
    
    def test_create_request_as_buyer(self, buyer_token):
        response = client.post("/requests",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={
                "factoryId": "F001",
                "title": "Q1 Compliance",
                "items": [
                    {"docType": "Test Report"},
                    {"docType": "Certificate"}
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "requestId" in data
        assert data["status"] == "pending"
        assert len(data["itemIds"]) == 2
    
    def test_factory_get_requests(self, buyer_token, factory_token):
        # Buyer creates request
        client.post("/requests",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={
                "factoryId": "F001",
                "title": "Test Request",
                "items": [{"docType": "Report"}]
            }
        )
        
        # Factory retrieves requests
        response = client.get("/factory/requests",
            headers={"Authorization": f"Bearer {factory_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "requests" in data
        assert len(data["requests"]) > 0

class TestFulfillment:
    @pytest.fixture
    def setup_workflow(self):
        # Login
        buyer_response = client.post("/auth/login", json={
            "userId": "buyer1",
            "role": "buyer"
        })
        factory_response = client.post("/auth/login", json={
            "userId": "factory_user1",
            "role": "factory",
            "factoryId": "F001"
        })
        
        buyer_token = buyer_response.json()["token"]
        factory_token = factory_response.json()["token"]
        
        # Create evidence
        evidence_response = client.post("/evidence",
            headers={"Authorization": f"Bearer {factory_token}"},
            json={
                "name": "Test Evidence",
                "docType": "Test Report",
                "notes": "For testing"
            }
        )
        evidence_id = evidence_response.json()["evidenceId"]
        version_id = evidence_response.json()["versionId"]
        
        # Create request
        request_response = client.post("/requests",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={
                "factoryId": "F001",
                "title": "Test Request",
                "items": [{"docType": "Test Report"}]
            }
        )
        request_id = request_response.json()["requestId"]
        item_id = request_response.json()["itemIds"][0]
        
        return {
            "buyer_token": buyer_token,
            "factory_token": factory_token,
            "evidence_id": evidence_id,
            "version_id": version_id,
            "request_id": request_id,
            "item_id": item_id
        }
    
    def test_fulfill_request_item(self, setup_workflow):
        data = setup_workflow
        
        response = client.post(
            f"/requests/{data['request_id']}/items/{data['item_id']}/fulfill",
            headers={"Authorization": f"Bearer {data['factory_token']}"},
            json={
                "evidenceId": data["evidence_id"],
                "versionId": data["version_id"]
            }
        )
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["status"] == "fulfilled"

class TestAuditLog:
    @pytest.fixture
    def token(self):
        response = client.post("/auth/login", json={
            "userId": "user1",
            "role": "buyer"
        })
        return response.json()["token"]
    
    def test_get_audit_log(self, token):
        response = client.get("/audit",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            entry = data[0]
            assert "timestamp" in entry
            assert "actorUserId" in entry
            assert "actorRole" in entry
            assert "action" in entry
            assert "objectType" in entry
            assert "objectId" in entry
            assert "metadata" in entry

class TestSecurity:
    def test_cross_factory_access_prevented(self):
        # Create two factories
        factory1_response = client.post("/auth/login", json={
            "userId": "factory1",
            "role": "factory",
            "factoryId": "F001"
        })
        factory2_response = client.post("/auth/login", json={
            "userId": "factory2",
            "role": "factory",
            "factoryId": "F002"
        })
        
        f1_token = factory1_response.json()["token"]
        f2_token = factory2_response.json()["token"]
        
        # Factory 1 creates evidence
        evidence_response = client.post("/evidence",
            headers={"Authorization": f"Bearer {f1_token}"},
            json={
                "name": "F001 Evidence",
                "docType": "Report",
                "notes": "Factory 1"
            }
        )
        evidence_id = evidence_response.json()["evidenceId"]
        
        # Factory 2 tries to add version to F001's evidence
        version_response = client.post(f"/evidence/{evidence_id}/versions",
            headers={"Authorization": f"Bearer {f2_token}"},
            json={"notes": "Unauthorized version"}
        )
        assert version_response.status_code == 403
    
    def test_unauthorized_access(self):
        response = client.get("/factory/requests")
        assert response.status_code == 401
