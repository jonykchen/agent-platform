"""RAG 检索节点 - 知识库检索

核心职责：
1. 调用 knowledge-service API 检索相关文档
2. 将检索结果更新到 state.retrieved_docs
3. 支持混合检索 + 分层重排序

检索流程：
┌─────────────────────────────────────────┐
│           thinking 节点判断              │
│               │                         │
│               ▼                         │
│        ┌─────────────┐                  │
│        │ RAG 检索     │                  │
│        └─────────────┘                  │
│               │                         │
│    ┌──────────┼──────────┐              │
│    │          │          │              │
│ [Query Rewrite] [Embedding Cache]      │
│    │          │          │              │
│    ▼          ▼          ▼              │
│ [Parallel Search (BM25+Vector)]        │
│    │                                   │
│    ▼                                   │
│ [Tiered Rerank]                        │
│    │                                   │
│    ▼                                   │
│ 更新 retrieved_docs                    │
│    │                                   │
│    ▼                                   │
│ 返回 thinking 继续推理                  │
└─────────────────────────────────────────┘

输出字段：
- retrieved_docs: 检索到的文档片段列表
- current_step: 下一步类型（通常是 thinking 继续推理）

【技术选型】RAG 调用方式
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 方案               │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 直接调用（当前）   │ • 简单直接                  │ • 服务依赖                  │
│                    │ • 解耦清晰                  │ • 需要网络调用              │
│                    │ • 知识服务独立部署          │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 内嵌检索器         │ • 无网络延迟                │ • 编排服务臃肿              │
│                    │ • 一体化部署                │ • 复用困难                  │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ MCP 工具           │ • 标准化接口                │ • 需要额外配置              │
│                    │ • 跨平台复用                │ • 调试复杂                  │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

选择直接调用的原因：
1. 知识服务独立部署，便于横向扩展
2. 检索逻辑复杂（Query改写+Embedding缓存+分层重排），不适合内嵌
3. 微服务架构下服务间调用标准化
"""

from __future__ import annotations

import time
import structlog

import httpx

from app.graph.state import AgentState
from app.core.config import config

logger = structlog.get_logger()

# 知识服务配置
KNOWLEDGE_SERVICE_URL = getattr(config, "knowledge_service_url", "http://localhost:8003")
KNOWLEDGE_SEARCH_TIMEOUT = 15.0  # 检索超时


async def rag_retrieve_node(state: AgentState) -> dict:
    """RAG 检索节点

    调用 knowledge-service 执行检索：
    1. Query 改写（可选）
    2. 混合检索（BM25 + 向量）
    3. 分层重排序

    输入状态：
    - input: 用户查询
    - tenant_id: 租户 ID（用于多租户隔离）
    - session_id: 会话 ID

    输出状态：
    - retrieved_docs: 检索到的文档片段
    - current_step: 下一步类型

    Returns:
        状态更新字典
    """
    start_time = time.time()
    request_id = state["request_id"]
    tenant_id = state["tenant_id"]
    query = state["input"]

    logger.info(
        "rag_retrieve_started",
        query_preview=query[:100] if query else "",
        tenant_id=tenant_id,
        request_id=request_id,
    )

    try:
        # 调用知识服务 API
        results = await _call_knowledge_service(
            query=query,
            tenant_id=tenant_id,
            top_k=10,
            use_hybrid=True,
            use_rerank=True,
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # 格式化检索结果
        retrieved_docs = _format_results(results)

        logger.info(
            "rag_retrieve_completed",
            doc_count=len(retrieved_docs),
            duration_ms=duration_ms,
            request_id=request_id,
        )

        return {
            "retrieved_docs": retrieved_docs,
            "current_step": "thinking",  # 返回 thinking 继续推理
            "step_count": state["step_count"] + 1,
        }

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)

        logger.error(
            "rag_retrieve_failed",
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms,
            request_id=request_id,
        )

        # 检索失败时返回空结果，让模型自己回答
        return {
            "retrieved_docs": [],
            "current_step": "thinking",
            "step_count": state["step_count"] + 1,
            "error": f"知识库检索失败: {str(e)}",
            "error_code": "ERR_RAG_SEARCH_FAILED",
        }


async def _call_knowledge_service(
    query: str,
    tenant_id: str,
    top_k: int = 10,
    use_hybrid: bool = True,
    use_rerank: bool = True,
    doc_ids: list[str] | None = None,
) -> list[dict]:
    """调用知识服务检索 API

    Args:
        query: 查询文本
        tenant_id: 租户 ID
        top_k: 返回数量
        use_hybrid: 是否使用混合检索
        use_rerank: 是否使用重排序
        doc_ids: 文档 ID 过滤

    Returns:
        检索结果列表
    """
    async with httpx.AsyncClient(
        base_url=KNOWLEDGE_SERVICE_URL,
        timeout=httpx.Timeout(KNOWLEDGE_SEARCH_TIMEOUT),
    ) as client:
        # 构建请求
        payload = {
            "query": query,
            "top_k": top_k,
            "use_hybrid": use_hybrid,
            "filters": {"document_ids": doc_ids} if doc_ids else None,
        }

        headers = {
            "X-Tenant-ID": tenant_id,
            "Content-Type": "application/json",
        }

        response = await client.post(
            "/api/v1/search/query",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()

        data = response.json()
        return data.get("results", [])


def _format_results(results: list[dict]) -> list[dict]:
    """格式化检索结果

    将知识服务返回的结果转换为 Agent 可用的格式：
    - chunk_id: 文档块 ID
    - document_name: 文档名称
    - content: 文档内容
    - score: 相关性分数
    - source: 来源类型

    Args:
        results: 知识服务返回的原始结果

    Returns:
        格式化后的文档列表
    """
    formatted = []
    for r in results:
        formatted.append({
            "chunk_id": r.get("chunk_id", ""),
            "document_id": r.get("document_id", ""),
            "document_name": r.get("document_name", ""),
            "chunk_index": r.get("chunk_index", 0),
            "content": r.get("content", ""),
            "score": r.get("score", 0),
            "source": r.get("source", "unknown"),
            "metadata": r.get("metadata", {}),
        })

    return formatted


def _build_context_string(docs: list[dict], max_length: int = 4000) -> str:
    """构建上下文字符串

    将检索结果拼接成 Prompt 上下文：
    - 限制总长度防止 Token 超限
    - 添加来源标注便于溯源

    Args:
        docs: 检索到的文档列表
        max_length: 最大字符长度

    Returns:
        上下文字符串
    """
    context_parts = []
    current_length = 0

    for i, doc in enumerate(docs):
        doc_text = f"[文档{i+1}] {doc.get('document_name', '未知')}\n{doc.get('content', '')}\n"

        if current_length + len(doc_text) > max_length:
            break

        context_parts.append(doc_text)
        current_length += len(doc_text)

    if not context_parts:
        return ""

    return "\n---\n".join(context_parts)


# 用于 LangGraph builder 导入
rag_retrieve = rag_retrieve_node