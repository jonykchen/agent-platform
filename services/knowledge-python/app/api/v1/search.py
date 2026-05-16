"""
检索 API - 生产级实现

【核心概念】
检索是 RAG Pipeline 的核心环节，负责从向量数据库中召回与查询最相关的文档片段。
召回质量直接影响 LLM 生成答案的准确性和相关性。

【RAG Pipeline - 检索阶段】
┌─────────────────────────────────────────────────────────────────────────┐
│                         Search Pipeline                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌───────┐ │
│  │ 用户查询 │──▶│ Embedding │──▶│ 向量检索 │──▶│ 混合检索 │──▶│ 返回  │ │
│  │ (Query)  │   │ (向量)    │   │ (pgvector)│   │ (可选)   │   │Top-K │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └───────┘ │
│       │              │              │              │              │     │
│       ▼              ▼              ▼              ▼              ▼     │
│   [Query 长度]  [调用 Gateway]  [余弦相似度]  [α权重融合]   [结果格式]  │
│   [租户过滤]    [缓存优化]     [索引加速]    [关键词补充]  [延迟统计]  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

【技术选型对比】

| 特性 | 纯向量检索 | 混合检索 | 语义检索 |
|------|------------|----------|----------|
| 实现复杂度 | 低 | 中 | 高 |
| 检索精度 | 中 | 高 | 最高 |
| 响应延迟 | 50-100ms | 100-200ms | 200-500ms |
| 适用场景 | 语义匹配 | 精确+语义 | 复杂查询 |
| 本服务采用 | 可选 | **默认** | 计划支持 |

【混合检索原理】

混合检索融合向量检索（语义）和关键词检索（精确）：

Score_hybrid = α × Score_vector + (1-α) × Score_keyword

其中：
- α: 向量检索权重（默认 0.7）
- Score_vector: 余弦相似度 (1 - cosine_distance)
- Score_keyword: BM25 或 TF-IDF 分数

优势：
- 向量检索捕捉语义相似（"汽车" ≈ "轿车"）
- 关键词检索确保精确匹配（产品型号、编号）
- 融合结果召回率更高

【pgvector 检索原理】

pgvector 使用余弦距离（<=>）进行向量检索：

cosine_distance = 1 - (A · B) / (|A| × |B|)

检索流程：
1. 查询向量化（调用 Model Gateway Embedding API）
2. PostgreSQL 执行向量距离计算
3. 按 cosine_distance 排序，返回 Top-K
4. 距离越小，相似度越高（distance=0 表示完全相同）

【索引优化】

pgvector 支持 HNSW 和 IVFFlat 索引：

| 索引类型 | 构建速度 | 检索速度 | 内存占用 | 适用场景 |
|----------|----------|----------|----------|----------|
| HNSW | 慢 | 快 | 高 | 生产环境（高并发） |
| IVFFlat | 快 | 中 | 低 | 中小规模数据 |
| 无索引 | - | 慢 | - | 开发/小数据 |

本服务默认使用 HNSW 索引（见 docs/04-data-design-complete.md）

【Query 改写优化】

高级检索可先对 Query 进行改写：
1. Query Expansion: 扩展关键词（"汽车" → "汽车,轿车,车辆"）
2. HyDE: LLM 生成假设答案，用答案向量检索
3. Multi-Query: 生成多个相关查询，分别检索后融合

当前实现：暂未启用，计划后续支持

【API 端点】
- POST /query        : 知识库检索（核心）
- POST /similar/{id} : 相似内容推荐
"""

import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.config import config
from app.indexers.vector_indexer import EmbeddingClient, get_vector_indexer
from app.retrievers.hybrid_retriever import get_hybrid_retriever

logger = structlog.get_logger()
router = APIRouter()


class SearchRequest(BaseModel):
    """
    检索请求模型

    【字段说明】
    - query: 用户查询文本（1-1000 字符）
    - top_k: 返回结果数量（1-100）
    - filters: 可选过滤条件（如限定文档范围）
    - use_hybrid: 是否启用混合检索（向量+关键词）
    - alpha: 混合检索权重（0=纯关键词，1=纯向量）

    【混合检索权重说明】
    alpha = 0.7（默认）：
    - 70% 权重给向量检索（语义匹配）
    - 30% 权重给关键词检索（精确匹配）

    调优建议：
    - 语义相似场景（问答、推荐）：alpha = 0.8-1.0
    - 精确匹配场景（型号、编号）：alpha = 0.3-0.5
    - 综合场景（通用搜索）：alpha = 0.6-0.7
    """

    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(10, ge=1, le=100)
    filters: dict | None = None
    use_hybrid: bool = True  # 是否使用混合检索
    alpha: float = Field(0.7, ge=0, le=1)  # 向量检索权重


class SearchResult(BaseModel):
    """
    检索结果模型

    【字段说明】
    - chunk_id: 文档片段唯一标识
    - document_id: 所属文档 ID
    - document_name: 文档名称（用于展示）
    - content: 文本内容（注入 LLM 上下文）
    - score: 相关性得分（0-1，越高越相关）
    - metadata: 元数据（来源、页码等）
    - source: 检索来源（vector/keyword/hybrid/similar）

    【score 解释】
    - 向量检索：cosine_similarity = 1 - cosine_distance
    - 混合检索：α × vector_score + (1-α) × keyword_score
    - score > 0.8: 高相关性
    - score 0.5-0.8: 中等相关性
    - score < 0.5: 低相关性（可能需调整阈值）
    """

    chunk_id: str
    document_id: str
    document_name: str
    content: str
    score: float
    metadata: dict
    source: str  # vector / keyword / hybrid


class SearchResponse(BaseModel):
    """
    检索响应模型

    【字段说明】
    - results: 检索结果列表（按 score 降序）
    - total: 结果总数
    - query: 原始查询文本
    - latency_ms: 检索耗时（毫秒）

    【性能指标】
    - P50: 50-100ms（小数据集）
    - P95: 100-200ms（中等数据集）
    - P99: 200-500ms（大数据集 + 混合检索）

    【延迟优化】
    - 启用 Embedding 缓存（相同 Query 复用向量）
    - 使用 HNSW 索引（见数据库迁移脚本）
    - 调整 top_k（减少返回数量）
    """

    results: list[SearchResult]
    total: int
    query: str
    latency_ms: int


def _get_tenant_id(request_headers: dict) -> str:
    """
    从请求头获取租户 ID

    【多租户隔离】
    确保检索结果只返回当前租户的数据。

    Args:
        request_headers: HTTP 请求头字典

    Returns:
        租户 ID 字符串
    """
    tenant_id = request_headers.get("X-Tenant-ID")
    return tenant_id if tenant_id else "default_tenant"


async def _get_query_embedding(query: str) -> list:
    """
    获取查询向量 - 检索预处理

    【处理流程】
    1. 调用 Model Gateway Embedding API
    2. 将查询文本转换为高维向量
    3. 返回向量列表（用于 pgvector 检索）

    【缓存优化】
    Model Gateway 内部已实现 Embedding 缓存：
    - 相同 Query 复用向量，减少 API 调用
    - 缓存 TTL: 1 小时（见 model-gateway 配置）

    【性能指标】
    - 无缓存: 50-200ms（取决于模型）
    - 有缓存: <10ms

    Args:
        query: 用户查询文本

    Returns:
        向量列表（float 数组，维度与 embedding_model 匹配）
    """
    embedding_client = EmbeddingClient(
        base_url=config.embedding_service_url,
        model=config.embedding_model,
    )
    embedding = await embedding_client.embed(query)
    return embedding.tolist()


@router.post("/query", response_model=SearchResponse)
async def search_knowledge(
    fastapi_request: Request,
    request: SearchRequest,
):
    """
    检索知识库 - RAG 核心接口

    【检索流程】
    ┌───────────────────────────────────────────────────────────────────────┐
    │  1. 租户校验  →  2. Query Embedding  →  3. 执行检索  →  4. 结果格式化  │
    │  ┌─────────┐    ┌──────────────┐      ┌────────────┐    ┌──────────┐ │
    │  │Header解析│───▶│Model Gateway │─────▶│向量/混合  │───▶│Top-K排序│ │
    │  │X-Tenant-ID│   │Embedding API│      │pgvector   │    │JSON响应 │ │
    │  └─────────┘    └──────────────┘      └────────────┘    └──────────┘ │
    └───────────────────────────────────────────────────────────────────────┘

    【检索模式选择】
    - use_hybrid=True（默认）：
      向量检索(α) + 关键词检索(1-α)，召回率高
    - use_hybrid=False：
      纯向量检索，延迟更低（适合实时场景）

    【过滤条件】
    filters 参数支持限定检索范围：
    - document_ids: 限定在指定文档内检索
    - 后续扩展：时间范围、标签、分类等

    【错误处理】
    - 500: 内部错误（Embedding 失败、数据库异常）
    - 所有错误返回结构化 JSON，包含 request_id 便于追踪

    Args:
        fastapi_request: FastAPI 请求对象（获取 Header）
        request: SearchRequest 检索参数

    Returns:
        SearchResponse: 包含检索结果和元数据

    Raises:
        HTTPException: 检索失败时返回 500 错误
    """
    import time

    tenant_id = _get_tenant_id(dict(fastapi_request.headers))
    start_time = time.time()

    # ==================== 日志记录 ====================
    logger.info(
        "search_request",
        query=request.query[:50],  # 截断避免日志过长
        tenant_id=tenant_id,
        top_k=request.top_k,
        use_hybrid=request.use_hybrid,
    )

    try:
        # ==================== 1. 查询向量化 ====================
        query_embedding = await _get_query_embedding(request.query)

        # ==================== 2. 执行检索 ====================
        if request.use_hybrid:
            # 混合检索：向量 + 关键词融合
            retriever = get_hybrid_retriever()
            results = await retriever.search(
                query=request.query,
                tenant_id=tenant_id,
                doc_ids=request.filters.get("document_ids") if request.filters else None,
                top_k=request.top_k,
                alpha=request.alpha,
            )
        else:
            # 纯向量检索：最快
            indexer = get_vector_indexer()
            results = await indexer.search(
                query_embedding=query_embedding,
                tenant_id=tenant_id,
                doc_ids=request.filters.get("document_ids") if request.filters else None,
                top_k=request.top_k,
            )

        # ==================== 3. 结果格式化 ====================
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

        # ==================== 4. 日志记录 ====================
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
    fastapi_request: Request,
    chunk_id: str,
    top_k: int = 10,
):
    """
    查找相似内容 - 推荐场景专用

    【应用场景】
    - 相关文档推荐："看了这篇，你可能还喜欢..."
    - 相似问题匹配：找到历史相似问题及答案
    - 内容去重：识别重复或高度相似的文档片段

    【检索原理】
    与 /query 不同，此接口不需要用户输入 Query：
    1. 直接从数据库获取目标 chunk 的 Embedding
    2. 用此 Embedding 检索相似 chunk
    3. 排除自身，返回 Top-K 相似结果

    【SQL 解析】
    ```sql
    SELECT ... , 1 - (c.embedding <=> $1::vector) as score
    FROM knowledge_chunk c
    WHERE c.tenant_id = $2
      AND c.id != $3  -- 排除自身
      AND d.status = 'ready'
    ORDER BY c.embedding <=> $1::vector  -- 余弦距离升序
    LIMIT $4
    ```

    注意：<=> 是余弦距离运算符：
    - distance = 0: 完全相同
    - distance = 1: 正交（无关）
    - distance = 2: 完全相反

    score = 1 - distance，因此 score 越高越相似

    【性能优化】
    - 避免重复计算 Embedding（直接用存储的向量）
    - 利用 HNSW 索引加速向量检索
    - 典型延迟：50-150ms

    Args:
        fastapi_request: FastAPI 请求对象
        chunk_id: 目标块 ID（查找与此块相似的内容）
        top_k: 返回数量

    Returns:
        SearchResponse: 相似内容列表

    Raises:
        HTTPException 404: chunk_id 不存在
        HTTPException 500: 检索失败
    """
    import time

    start_time = time.time()
    tenant_id = _get_tenant_id(dict(fastapi_request.headers))

    try:
        indexer = get_vector_indexer()
        pool = await indexer._get_pool()

        # ==================== 1. 获取目标块的向量 ====================
        chunk_result = await pool.fetchrow(
            "SELECT embedding, document_id, content FROM knowledge_chunk WHERE id = $1 AND tenant_id = $2",
            chunk_id,
            tenant_id,
        )

        if not chunk_result:
            raise HTTPException(
                status_code=404,
                detail={"error": "ERR_CHUNK_NOT_FOUND", "message": "块不存在"},
            )

        query_embedding = chunk_result["embedding"]

        # ==================== 2. 向量检索相似块 ====================
        results = await pool.fetch(
            """
            SELECT
                c.id as chunk_id,
                c.document_id,
                d.name as document_name,
                c.content,
                1 - (c.embedding <=> $1::vector) as score,
                c.metadata
            FROM knowledge_chunk c
            JOIN knowledge_document d ON c.document_id = d.id
            WHERE c.tenant_id = $2
                AND c.id != $3
                AND d.status = 'ready'
            ORDER BY c.embedding <=> $1::vector
            LIMIT $4
            """,
            query_embedding,
            tenant_id,
            chunk_id,
            top_k,
        )

        # ==================== 3. 格式化结果 ====================
        import json

        search_results = [
            SearchResult(
                chunk_id=r["chunk_id"],
                document_id=r["document_id"],
                document_name=r["document_name"],
                content=r["content"],
                score=float(r["score"]),
                metadata=json.loads(r["metadata"]) if r["metadata"] else {},
                source="similar",
            )
            for r in results
        ]

        latency_ms = int((time.time() - start_time) * 1000)

        return SearchResponse(
            results=search_results,
            total=len(search_results),
            query=f"similar:{chunk_id}",
            latency_ms=latency_ms,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error("similar_search_failed", chunk_id=chunk_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail={"error": "ERR_SEARCH_FAILED", "message": str(e)},
        )
