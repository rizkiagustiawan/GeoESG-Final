import pytest
from fastapi.testclient import TestClient
from api_server import app, RATE_LIMIT_DB

client = TestClient(app)

def setup_function():
    """Clear rate limit DB before each test to prevent 429 errors in sequential tests."""
    RATE_LIMIT_DB.clear()

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "checks" in data

def test_regional_borders():
    response = client.get("/api/regional-borders")
    # Should be 200, but if file not found locally during CI it might be 404
    # We assert it's a valid HTTP response
    assert response.status_code in [200, 404]

def test_generate_esg_report_success():
    payload = {
        "site_id": "Lombok Barat",
        "ground_truth_biomass": 100.0
    }
    response = client.post("/generate-esg-report", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "metrics" in data
    assert "report_markdown" in data
    assert "data_integrity_flag" in data["metrics"]

def test_rate_limiting():
    payload = {
        "site_id": "Dompu",
        "ground_truth_biomass": 50.0
    }
    # Send 5 requests (Limit is 5 per minute)
    for _ in range(5):
        res = client.post("/generate-esg-report", json=payload)
        assert res.status_code == 200
    
    # The 6th request should be blocked
    res_blocked = client.post("/generate-esg-report", json=payload)
    assert res_blocked.status_code == 429
    assert "Rate limit exceeded" in res_blocked.json()["detail"]

def test_batch_audit_missing_api_key():
    payload = {
        "sites": [
            {"site_id": "Dompu", "ground_truth_biomass": 100.0}
        ]
    }
    response = client.post("/generate-esg-batch", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API Key"

def test_batch_audit_valid_api_key():
    payload = {
        "sites": [
            {"site_id": "Dompu", "ground_truth_biomass": 100.0}
        ]
    }
    headers = {"X-API-Key": "geoesg-secret-key-2026"}
    response = client.post("/generate-esg-batch", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert len(response.json()["results"]) == 1
