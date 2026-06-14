"""测试 RAG Retrieve 节点 - 知识库检索"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.graph.nodes.rag_retrieve import (
    _build_context_string,
    _call_knowledge_service,
    _format_results,
    rag_retrieve_node,
)
from app.graph.state import create_initial_state


@pytest.fixture
def base_state():
    """创建基础 Mock 状态"""
    return create_initial_state(
        input="如何申请退款？",
        session_id="sess_001",
        tenant_id="tenant_001",
        user_id="user_001",
        request_id="req_001",
        max_steps=10,
    )


def _mock_search_results():
    """构造 mock 检索结果"""
    return [
        {
            "chunk_id": "chunk_001",
            "document_id": "doc_001",
            "document_name": "退款政策手册",
            "chunk_index": 0,
            "content": "用户可在订单完成后7天内申请退款...",
            "score": 0.95,
            "source": "hybrid",
            "metadata": {"page": 1},
        },
        {
            "chunk_id": "chunk_002",
            "document_id": "doc_001",
            "document_name": "退款政策手册",
            "chunk_index": 1,
            "content": "退款将在3-5个工作日内到账...",
            "score": 0.88,
            "source": "vector",
            "metadata": {"page": 2},
        },
    ]


class TestRagRetrieveNode:
    """RAG Retrieve 节点测试"""

    @pytest.mark.asyncio
    async def test_should_retrieve_documents_successfully(self, base_state):
        """成功检索文档"""
        mock_results = _mock_search_results()

        with patch(
            "app.graph.nodes.rag_retrieve._call_knowledge_service",
            return_value=mock_results,
        ):
            result = await rag_retrieve_node(base_state)

        assert result["current_step"] == "thinking"
        assert len(result["retrieved_docs"]) == 2
        assert result["retrieved_docs"][0]["chunk_id"] == "chunk_001"
        assert result["retrieved_docs"][0]["document_name"] == "退款政策手册"
        assert result["step_count"] == 1

    @pytest.mark.asyncio
    async def test_should_handle_empty_search_results(self, base_state):
        """空检索结果"""
        with patch(
            "app.graph.nodes.rag_retrieve._call_knowledge_service",
            return_value=[],
        ):
            result = await rag_retrieve_node(base_state)

        assert result["current_step"] == "thinking"
        assert result["retrieved_docs"] == []
        assert result["step_count"] == 1

    @pytest.mark.asyncio
    async def test_should_degrade_gracefully_when_service_unavailable(self, base_state):
        """检索服务不可用时的降级"""
        with patch(
            "app.graph.nodes.rag_retrieve._call_knowledge_service",
            side_effect=Exception("Connection refused"),
        ):
            result = await rag_retrieve_node(base_state)

        assert result["current_step"] == "thinking"
        assert result["retrieved_docs"] == []
        assert result["error"] is not None
        assert "检索失败" in result["error"]
        assert result["error_code"] == "ERR_RAG_SEARCH_FAILED"
        # 应仍能继续推理
        assert result["step_count"] == 1

    @pytest.mark.asyncio
    async def test_should_degrade_on_timeout(self, base_state):
        """检索超时时的降级"""
        import httpx

        with patch(
            "app.graph.nodes.rag_retrieve._call_knowledge_service",
            side_effect=httpx.TimeoutException("Request timed out"),
        ):
            result = await rag_retrieve_node(base_state)

        assert result["current_step"] == "thinking"
        assert result["retrieved_docs"] == []
        assert result["error_code"] == "ERR_RAG_SEARCH_FAILED"

    @pytest.mark.asyncio
    async def test_should_increment_step_count(self, base_state):
        """检索后应递增 step_count"""
        base_state["step_count"] = 3

        with patch(
            "app.graph.nodes.rag_retrieve._call_knowledge_service",
            return_value=_mock_search_results(),
        ):
            result = await rag_retrieve_node(base_state)

        assert result["step_count"] == 4

    @pytest.mark.asyncio
    async def test_should_degrade_on_http_error(self, base_state):
        """HTTP 错误时的降级"""
        import httpx

        with patch(
            "app.graph.nodes.rag_retrieve._call_knowledge_service",
            side_effect=httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            ),
        ):
            result = await rag_retrieve_node(base_state)

        assert result["current_step"] == "thinking"
        assert result["retrieved_docs"] == []
        assert result["error_code"] == "ERR_RAG_SEARCH_FAILED"


class TestCallKnowledgeService:
    """_call_knowledge_service 单元测试"""

    @pytest.mark.asyncio
    async def test_should_call_search_api_and_return_results(self):
        """正确调用知识服务 API 并返回结果"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {
                    "chunk_id": "chunk_001",
                    "document_id": "doc_001",
                    "document_name": "测试文档",
                    "content": "测试内容",
                    "score": 0.9,
                    "source": "hybrid",
                },
            ],
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.graph.nodes.rag_retrieve.httpx.AsyncClient", return_value=mock_client):
            results = await _call_knowledge_service(
                query="如何退款",
                tenant_id="tenant_001",
                top_k=10,
            )

        assert len(results) == 1
        assert results[0]["chunk_id"] == "chunk_001"

    @pytest.mark.asyncio
    async def test_should_include_tenant_id_in_headers(self):
        """请求头应包含租户 ID"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"results": []}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.graph.nodes.rag_retrieve.httpx.AsyncClient", return_value=mock_client):
            await _call_knowledge_service(
                query="查询",
                tenant_id="tenant_abc",
            )

        call_args = mock_client.post.call_args
        headers = call_args[1]["headers"]
        assert headers["X-Tenant-ID"] == "tenant_abc"

    @pytest.mark.asyncio
    async def test_should_include_doc_ids_filter_when_provided(self):
        """提供 doc_ids 时应包含在 filters 中"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"results": []}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.graph.nodes.rag_retrieve.httpx.AsyncClient", return_value=mock_client):
            await _call_knowledge_service(
                query="查询",
                tenant_id="tenant_001",
                doc_ids=["doc_001", "doc_002"],
            )

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["filters"]["document_ids"] == ["doc_001", "doc_002"]

    @pytest.mark.asyncio
    async def test_should_not_include_filters_when_no_doc_ids(self):
        """无 doc_ids 时不应包含 filters"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"results": []}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("app.graph.nodes.rag_retrieve.httpx.AsyncClient", return_value=mock_client):
            await _call_knowledge_service(
                query="查询",
                tenant_id="tenant_001",
            )

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["filters"] is None


class TestFormatResults:
    """_format_results 单元测试"""

    def test_should_format_raw_results(self):
        """格式化原始检索结果"""
        raw = [
            {
                "chunk_id": "chunk_001",
                "document_id": "doc_001",
                "document_name": "退款政策",
                "chunk_index": 0,
                "content": "退款规则...",
                "score": 0.9,
                "source": "hybrid",
                "metadata": {"page": 1},
            },
        ]
        formatted = _format_results(raw)

        assert len(formatted) == 1
        assert formatted[0]["chunk_id"] == "chunk_001"
        assert formatted[0]["document_name"] == "退款政策"
        assert formatted[0]["content"] == "退款规则..."
        assert formatted[0]["score"] == 0.9

    def test_should_handle_missing_fields_with_defaults(self):
        """缺失字段应使用默认值"""
        raw = [{}]
        formatted = _format_results(raw)

        assert formatted[0]["chunk_id"] == ""
        assert formatted[0]["document_id"] == ""
        assert formatted[0]["document_name"] == ""
        assert formatted[0]["chunk_index"] == 0
        assert formatted[0]["content"] == ""
        assert formatted[0]["score"] == 0
        assert formatted[0]["source"] == "unknown"
        assert formatted[0]["metadata"] == {}

    def test_should_handle_empty_input(self):
        """空输入应返回空列表"""
        assert _format_results([]) == []


class TestBuildContextString:
    """_build_context_string 单元测试"""

    def test_should_build_context_from_docs(self):
        """从文档列表构建上下文"""
        docs = [
            {
                "document_name": "退款政策",
                "content": "7天内可退款",
            },
            {
                "document_name": "配送说明",
                "content": "配送时效3-5天",
            },
        ]
        context = _build_context_string(docs)

        assert "退款政策" in context
        assert "7天内可退款" in context
        assert "配送说明" in context
        assert "配送时效3-5天" in context
        assert "[文档1]" in context
        assert "[文档2]" in context

    def test_should_truncate_at_max_length(self):
        """超过最大长度时截断"""
        docs = [
            {
                "document_name": "长文档",
                "content": "A" * 5000,
            },
        ]
        context = _build_context_string(docs, max_length=100)

        assert len(context) <= 200  # 含标题和分隔符的余量

    def test_should_return_empty_string_for_no_docs(self):
        """空文档列表返回空字符串"""
        assert _build_context_string([]) == ""
