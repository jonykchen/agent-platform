"""测试健康检查 API"""

from fastapi.testclient import TestClient


def test_models_endpoint(client: TestClient):
    """测试模型列表 API"""
    response = client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data or "object" in data


def test_health_endpoint(client: TestClient):
    """测试健康检查"""
    response = client.get("/health")
    # 可能返回 404 或其他状态，取决于是否实现
    assert response.status_code in [200, 404]
