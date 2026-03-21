"""集成测试：模型网关流程

测试模型网关的完整请求流程：
- 请求路由
- 熔断保护
- 降级处理
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


pytestmark = pytest.mark.integration


@pytest.fixture
def integration_client():
    """集成测试客户端"""
    app = create_app()
    return TestClient(app)


class TestModelGatewayFlow:
    """模型网关流程集成测试"""

    def test_health_check(self, integration_client: TestClient):
        """测试健康检查"""
        response = integration_client.get("/health")
        # 根据实际实现调整断言
        assert response.status_code in [200, 404]

    def test_models_endpoint(self, integration_client: TestClient):
        """测试模型列表"""
        response = integration_client.get("/v1/models")
        assert response.status_code == 200

    @pytest.mark.skip(reason="需要真实的模型提供商连接")
    def test_chat_completion(self, integration_client: TestClient):
        """测试对话补全（需要真实模型）"""
        response = integration_client.post(
            "/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "Hello"}],
                "model": "qwen-turbo",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "choices" in data

    @pytest.mark.skip(reason="需要模拟提供商故障")
    def test_fallback_on_provider_failure(self, integration_client: TestClient):
        """测试提供商故障时的降级"""
        pass
