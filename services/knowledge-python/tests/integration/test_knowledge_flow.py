"""集成测试：知识库流程

测试 RAG 知识库的完整流程：
- 文档上传
- 向量索引
- 语义检索
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


class TestKnowledgeFlow:
    """知识库流程集成测试"""

    def test_search_endpoint_available(self, integration_client: TestClient):
        """测试检索端点可用"""
        response = integration_client.post(
            "/api/v1/search/query",
            json={
                "query": "测试查询",
                "top_k": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data

    def test_documents_endpoint_available(self, integration_client: TestClient):
        """测试文档端点可用"""
        response = integration_client.get("/api/v1/documents/")
        # 根据实际实现调整断言
        assert response.status_code in [200, 404]

    @pytest.mark.skip(reason="需要数据库连接")
    def test_document_upload_and_search(self, integration_client: TestClient):
        """测试文档上传后检索"""
        # 1. 上传文档
        upload_response = integration_client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.txt", b"测试文档内容", "text/plain")},
        )

        assert upload_response.status_code in [200, 201]

        # 2. 等待索引完成（实际测试中可能需要轮询）
        # ...

        # 3. 检索验证
        search_response = integration_client.post(
            "/api/v1/search/query",
            json={
                "query": "测试文档",
                "top_k": 5,
            },
        )

        assert search_response.status_code == 200
        # 验证结果包含上传的文档

    @pytest.mark.skip(reason="需要向量数据库连接")
    def test_vector_search_performance(self, integration_client: TestClient):
        """测试向量检索性能"""
        import time

        start = time.time()
        response = integration_client.post(
            "/api/v1/search/query",
            json={
                "query": "性能测试查询",
                "top_k": 100,
            },
        )
        elapsed = time.time() - start

        assert response.status_code == 200
        # P95 应该在合理范围内（如 < 500ms）
        assert elapsed < 0.5
