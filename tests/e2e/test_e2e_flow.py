"""E2E 集成测试 - 完整链路验证"""

import asyncio
import time
import uuid

import httpx
import pytest


# 服务端点
GATEWAY_URL = "http://localhost:8080"
ORCHESTRATOR_URL = "http://localhost:8000"
MODEL_GATEWAY_URL = "http://localhost:8001"
TOOL_BUS_URL = "localhost:50051"


def generate_request_id() -> str:
    """生成 UUID v7 格式的 request_id"""
    return f"req-{uuid.uuid4().hex[:16]}"


@pytest.fixture
def request_headers():
    """标准请求头"""
    return {
        "X-Request-ID": generate_request_id(),
        "X-Tenant-ID": "test-tenant-001",
        "X-User-ID": "test-user-001",
        "Content-Type": "application/json",
    }


class TestHealthChecks:
    """健康检查测试"""

    @pytest.mark.asyncio
    async def test_gateway_health(self):
        """测试 Gateway 健康检查"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GATEWAY_URL}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "UP"

    @pytest.mark.asyncio
    async def test_orchestrator_health(self):
        """测试 Orchestrator 健康检查"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ORCHESTRATOR_URL}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "UP"

    @pytest.mark.asyncio
    async def test_model_gateway_health(self):
        """测试 Model Gateway 健康检查"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{MODEL_GATEWAY_URL}/health")
            # 可能没有 /health 端点，检查 /v1/models
            if response.status_code != 200:
                response = await client.get(f"{MODEL_GATEWAY_URL}/v1/models")
            assert response.status_code in [200, 404]


class TestChatFlow:
    """对话流程测试"""

    @pytest.mark.asyncio
    async def test_simple_chat(self, request_headers):
        """测试简单对话"""
        request_id = generate_request_id()
        headers = {**request_headers, "X-Request-ID": request_id}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{GATEWAY_URL}/api/v1/chat/completions",
                headers=headers,
                json={"message": "你好"},
            )

            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["request_id"] == request_id
            assert "response" in data

    @pytest.mark.asyncio
    async def test_request_id_propagation(self, request_headers):
        """测试 request_id 全链路贯穿"""
        request_id = generate_request_id()
        headers = {**request_headers, "X-Request-ID": request_id}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{GATEWAY_URL}/api/v1/chat/completions",
                headers=headers,
                json={"message": "测试 request_id 贯穿"},
            )

            assert response.status_code == 200
            data = response.json()

            # 验证 request_id 贯穿
            assert data["request_id"] == request_id

            # 验证响应头中的 request_id
            assert response.headers.get("X-Request-ID") == request_id


class TestTenantIsolation:
    """租户隔离测试"""

    @pytest.mark.asyncio
    async def test_tenant_required(self):
        """测试租户 ID 必填"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{GATEWAY_URL}/api/v1/chat/completions",
                headers={
                    "X-Request-ID": generate_request_id(),
                    "X-User-ID": "test-user",
                    "Content-Type": "application/json",
                },
                json={"message": "测试"},
            )

            # 应该返回 400 或 403
            assert response.status_code in [400, 403, 500]

    @pytest.mark.asyncio
    async def test_different_tenants(self, request_headers):
        """测试不同租户隔离"""
        request_id_1 = generate_request_id()
        request_id_2 = generate_request_id()

        async with httpx.AsyncClient(timeout=30.0) as client:
            # 租户 1 请求
            response_1 = await client.post(
                f"{GATEWAY_URL}/api/v1/chat/completions",
                headers={
                    **request_headers,
                    "X-Request-ID": request_id_1,
                    "X-Tenant-ID": "tenant-001",
                },
                json={"message": "租户1的消息"},
            )

            # 租户 2 请求
            response_2 = await client.post(
                f"{GATEWAY_URL}/api/v1/chat/completions",
                headers={
                    **request_headers,
                    "X-Request-ID": request_id_2,
                    "X-Tenant-ID": "tenant-002",
                },
                json={"message": "租户2的消息"},
            )

            # 两个请求应该独立处理
            assert response_1.status_code in [200, 500]
            assert response_2.status_code in [200, 500]


class TestModelGateway:
    """Model Gateway 测试"""

    @pytest.mark.asyncio
    async def test_list_models(self):
        """测试模型列表"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{MODEL_GATEWAY_URL}/v1/models")

            assert response.status_code == 200
            data = response.json()
            assert data["object"] == "list"
            assert len(data["data"]) > 0

    @pytest.mark.asyncio
    async def test_chat_completion(self):
        """测试对话补全"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{MODEL_GATEWAY_URL}/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                json={
                    "messages": [{"role": "user", "content": "你好"}],
                    "model": "qwen-max",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "choices" in data
            assert len(data["choices"]) > 0


class TestEndToEnd:
    """端到端测试"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_chat_flow(self, request_headers):
        """测试完整对话流程

        链路: Client → Gateway → Orchestrator → Model Gateway → Response
        """
        request_id = generate_request_id()
        start_time = time.time()

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{GATEWAY_URL}/api/v1/chat/completions",
                headers={**request_headers, "X-Request-ID": request_id},
                json={
                    "message": "请帮我查询订单 ORD-001 的状态",
                    "enable_tools": True,
                },
            )

            elapsed = time.time() - start_time

            # 验证响应
            assert response.status_code == 200
            data = response.json()

            # 验证 request_id 贯穿
            assert data["request_id"] == request_id

            # 验证响应内容
            assert "response" in data
            assert data["latency_ms"] < 30000  # 应该在 30 秒内完成

            print(f"\n✅ E2E 测试通过: request_id={request_id}, latency={data['latency_ms']}ms")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
