"""测试健康检查 API"""

from fastapi.testclient import TestClient


def test_health(client: TestClient):
    """测试健康检查"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UP"
    assert data["service"] == "orchestrator-python"


def test_ready(client: TestClient):
    """测试就绪检查"""
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "READY"
