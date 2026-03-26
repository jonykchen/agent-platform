"""检索 API - 生产级实现"""

import structlog
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.core.config import config
from app.indexers.vector_indexer import get_vector_indexer, EmbeddingClient
from app.retrievers.hybrid_retriever import get_hybrid_retriever

logger = structlog.get_logger()
router = APIRouter()


class SearchRequest(BaseModel):
    """检索请求"""
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(10, ge=1, le=100)
    filters: dict | None = None
    use_hybrid: bool = True  # 是否使用混合检索
    alpha: float = Field(0.7, ge=0, le=1)  # 向量检索权重


class SearchResult(BaseModel):
    """检索结果"""
    chunk_id: str
    document_id: str
    document_name: str
    content: str
    score: float
    metadata: dict
    source: str  # vector / keyword / hybrid


class SearchResponse(BaseModel):
    """检索响应"""
    results: list[SearchResult]
    total: int
    query: str
    latency_ms: int


def _get_tenant_id() -> str:
    """获取租户 ID"""
    return "default_tenant"


async def _get_query_embedding(query: str) -> list:
    """获取查询向量"""
    embedding_client = EmbeddingClient(
        base_url=config.embedding_service_url,
        model=config.embedding_model,
    )
    embedding = await embedding_client.embed(query)
    return embedding.tolist()


@router.post("/query", response_model=SearchResponse)
async def search_knowledge(
    request: SearchRequest,
    tenant_id: str = Depends(_get_tenant_id),
):
    """检索知识库

    【检索流程】
    1. 生成查询 Embedding
    2. 执行检索（纯向量或混合）
    3. 返回结果

    Args:
        request: 检索请求
        tenant_id: 租户 ID

    Returns:
        检索结果
    """
    import time

    start_time = time.time()

    logger.info(
        "search_request",
        query=request.query[:50],
        tenant_id=tenant_id,
        top_k=request.top_k,
        use_hybrid=request.use_hybrid,
    )

    try:
        # 获取查询向量
        query_embedding = await _get_query_embedding(request.query)

        # 执行检索
        if request.use_hybrid:
            # 混合检索
            retriever = get_hybrid_retriever()
            results = await retriever.search(
                query=request.query,
                tenant_id=tenant_id,
                doc_ids=request.filters.get("document_ids") if request.filters else None,
                top_k=request.top_k,
                alpha=request.alpha,
            )
        else:
            # 纯向量检索
            indexer = get_vector_indexer()
            results = await indexer.search(
                query_embedding=query_embedding,
                tenant_id=tenant_id,
                doc_ids=request.filters.get("document_ids") if request.filters else None,
                top_k=request.top_k,
            )

        # 格式化结果
        search_results = [
            SearchResult(
                chunk_id=r["chunk_id"],
                document_id=r["document_id"],
                document_name=r.get("document_name", ""),
                content=r["content"],
                score=r["score"],
                metadata=r.get("metadata", {}),
                source=r.get("source", "vector"),
            )
            for r in results
        ]

        latency_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "search_completed",
            query=request.query[:50],
            result_count=len(search_results),
            latency_ms=latency_ms,
        )

        return SearchResponse(
            results=search_results,
            total=len(search_results),
            query=request.query,
            latency_ms=latency_ms,
        )

    except Exception as e:
        logger.error(
            "search_failed",
            query=request.query[:50],
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "ERR_SEARCH_FAILED",
                "message": str(e),
            },
        )


@router.post("/similar/{chunk_id}", response_model=SearchResponse)
async def find_similar(
    chunk_id: str,
    tenant_id: str = Depends(_get_tenant_id),
    top_k: int = 10,
):
    """查找相似内容

    基于指定块查找相似内容。

    Args:
        chunk_id: 块 ID
        tenant_id: 租户 ID
        top_k: 返回数量

    Returns:
        相似内容列表
    """
    # TODO: 实现基于块的相似度检索
    return SearchResponse(
        results=[],
        total=0,
        query=f"similar:{chunk_id}",
        latency_ms=0,
    )
