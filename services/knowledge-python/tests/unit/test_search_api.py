"""测试检索 API"""

from fastapi.testclient import TestClient


class TestSearchAPI:
    """检索 API 测试"""

    def test_search_query(self, client: TestClient):
        """测试检索查询"""
        response = client.post(
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

    def test_search_query_with_filters(self, client: TestClient):
        """测试带过滤器的检索"""
        response = client.post(
            "/api/v1/search/query",
            json={
                "query": "测试查询",
                "top_k": 10,
                "filters": {"source": "example.pdf"},
            },
        )

        assert response.status_code == 200

    def test_search_query_validation_empty(self, client: TestClient):
        """测试空查询验证"""
        response = client.post(
            "/api/v1/search/query",
            json={
                "query": "",
                "top_k": 5,
            },
        )

        # 应该返回验证错误
        assert response.status_code == 422

    def test_search_query_validation_top_k_min(self, client: TestClient):
        """测试 top_k 最小值验证"""
        response = client.post(
            "/api/v1/search/query",
            json={
                "query": "测试",
                "top_k": 0,
            },
        )

        assert response.status_code == 422

    def test_search_query_validation_top_k_max(self, client: TestClient):
        """测试 top_k 最大值验证"""
        response = client.post(
            "/api/v1/search/query",
            json={
                "query": "测试",
                "top_k": 101,
            },
        )

        assert response.status_code == 422

    def test_search_result_format(self, client: TestClient):
        """测试搜索结果格式"""
        response = client.post(
            "/api/v1/search/query",
            json={
                "query": "测试查询",
                "top_k": 5,
            },
        )

        data = response.json()
        assert "results" in data
        assert "total" in data

        # 检查结果结构
        if data["results"]:
            result = data["results"][0]
            assert "chunk_id" in result
            assert "document_id" in result
            assert "content" in result
            assert "score" in result
            assert "metadata" in result
