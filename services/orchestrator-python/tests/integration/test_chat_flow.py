"""集成测试：Agent 编排流程

测试完整的 Agent 执行流程，包括：
- 用户输入处理
- 工具调用决策
- 多步骤任务执行

注意：这些测试需要外部依赖（Redis, 模型网关等）。
使用 pytest -m integration 运行集成测试。
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


class TestChatFlow:
    """对话流程集成测试"""

    def test_health_check(self, integration_client: TestClient):
        """测试健康检查端点"""
        response = integration_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "UP"

    def test_ready_check(self, integration_client: TestClient):
        """测试就绪检查端点"""
        response = integration_client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "READY"

    @pytest.mark.skip(reason="需要真实的模型网关连接")
    def test_simple_chat(self, integration_client: TestClient):
        """测试简单对话（需要模型网关）"""
        response = integration_client.post(
            "/api/v1/chat",
            json={
                "message": "你好",
                "session_id": "test-session-001",
            },
            headers={
                "X-Tenant-ID": "test-tenant",
                "X-User-ID": "test-user",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data or "content" in data

    @pytest.mark.skip(reason="需要完整的工具总线连接")
    def test_tool_calling_flow(self, integration_client: TestClient):
        """测试工具调用流程"""
        response = integration_client.post(
            "/api/v1/chat",
            json={
                "message": "查询订单 ORD123 的状态",
                "session_id": "test-session-002",
            },
            headers={
                "X-Tenant-ID": "test-tenant",
                "X-User-ID": "test-user",
            },
        )

        assert response.status_code == 200
        # 验证工具调用被正确处理
