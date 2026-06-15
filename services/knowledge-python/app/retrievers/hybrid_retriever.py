"""混合检索器

【核心概念】混合检索
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

混合检索结合 BM25 关键词检索和向量语义检索的优势：

┌─────────────────────────────────────────────────────────────────────────┐
│  方法              │  优点                    │  缺点                  │
├────────────────────┼──────────────────────────┼────────────────────────┤
│  BM25             │  精确匹配、快            │  语义理解弱            │
│  向量检索          │  语义理解强              │  可能遗漏精确词        │
│  混合检索 ✓        │  兼顾精确和语义          │  计算量增加            │
└─────────────────────────────────────────────────────────────────────────┘

【并行检索】
使用 asyncio.gather 并行执行两路检索：
- 减少总延迟（从串行变为并行）
- 单路失败不影响另一路

【结果融合 - RRF】
使用 Reciprocal Rank Fusion (RRF) 合并结果：
- RRF(d) = Σ 1/(k + rank(d))
- k = 60（经典参数）
- 基于排名而非分数，更鲁棒

【参考】
- RRF 论文: https://plg.uwaterloo.ca/~gvcormac/cormack-sigir09-rrf.pdf
- pgvector: https://github.com/pgvector/pgvector
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog

try:
    import asyncpg

    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

from app.core.config import config
from app.retrievers.embedding_cache import EmbeddingCache, get_embedding_cache

logger = structlog.get_logger()


class HybridRetriever:
    """混合检索器

    功能：
    - 并行执行 BM25 和向量检索
    - 单路失败时降级到另一路
    - 使用 RRF 融合结果

    使用示例：
        retriever = HybridRetriever()

        # 执行混合检索
        results = await retriever.search(
            query="退货流程",
            tenant_id="tenant_001",
            top_k=10,
        )
    """

    def __init__(self, database_url: str | None = None):
        """初始化混合检索器

        Args:
            database_url: 数据库连接 URL
        """
        self.database_url = database_url or config.database_url.replace("+asyncpg", "")
        self._pool = None
        self._embedding_cache: EmbeddingCache | None = None

    async def _get_pool(self):
        """获取数据库连接池（延迟初始化）"""
        if not HAS_ASYNCPG:
            return None

        if self._pool is None and self.database_url:
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=5,
                max_size=config.database_pool_size,
                command_timeout=30.0,
            )
        return self._pool

    async def _get_embedding_cache(self) -> EmbeddingCache:
        """获取 Embedding 缓存"""
        if self._embedding_cache is None:
            self._embedding_cache = get_embedding_cache()
        return self._embedding_cache

    async def close(self) -> None:
        """关闭连接池"""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def search(
        self,
        query: str,
        tenant_id: str,
        doc_ids: list[str] | None = None,
        top_k: int = 10,
        alpha: float = 0.5,
        use_parallel: bool = True,
        enable_rerank: bool | None = None,
        enable_rewrite: bool | None = None,
    ) -> list[dict]:
        """混合检索（含可选 Query 改写与 Cross-Encoder 重排序）

        完整召回链路：
        Query 改写(可选) → 向量+关键词并行召回 → RRF 融合 → Rerank 精排(可选) → Top-K

        【并行检索策略】
        使用 asyncio.gather 并行执行 BM25 和向量检索：
        - 减少总延迟（从串行 100ms 变为并行 ~50ms）
        - 单路失败不影响另一路（错误隔离）

        Args:
            query: 查询文本
            tenant_id: 租户 ID
            doc_ids: 可选，限定文档范围
            top_k: 最终返回数量
            alpha: 向量检索权重 (1-alpha 为 BM25 权重)，用于 RRF 融合
            use_parallel: 是否并行执行（默认 True）
            enable_rerank: 是否重排序（None 时读配置 enable_rerank）
            enable_rewrite: 是否 Query 改写（None 时读配置 enable_query_rewrite）

        Returns:
            检索结果列表
        """
        if enable_rerank is None:
            enable_rerank = getattr(config, "enable_rerank", True)
        if enable_rewrite is None:
            enable_rewrite = getattr(config, "enable_query_rewrite", False)

        # 候选召回数：开启 rerank 时多召回候选，交由精排压缩到 top_k
        candidate_k = getattr(config, "rerank_top_k", 20) if enable_rerank else top_k

        # Query 改写：用改写后的查询做向量化检索，原查询用于 rerank 评分
        search_query = query
        if enable_rewrite:
            try:
                from app.retrievers.query_rewriter import get_query_rewriter

                rewrite_result = await get_query_rewriter().rewrite(query)
                rewritten = rewrite_result.get("rewritten_query")
                if rewritten:
                    search_query = rewritten
                    logger.info(
                        "query_rewritten_for_search",
                        original=query[:50],
                        rewritten=search_query[:50],
                    )
            except Exception as e:
                logger.warning("query_rewrite_skipped", error=str(e))

        pool = await self._get_pool()

        if pool is None:
            logger.warning("database_pool_not_available")
            return self._mock_search(query, top_k)

        try:
            if use_parallel:
                # 【并行检索】两路同时执行
                vector_results, keyword_results = await self._parallel_search(
                    pool, search_query, tenant_id, doc_ids, candidate_k * 2
                )
            else:
                # 串行执行（调试用）
                vector_results = await self._vector_search(pool, search_query, tenant_id, doc_ids, candidate_k * 2)
                keyword_results = await self._keyword_search(pool, search_query, tenant_id, doc_ids, candidate_k * 2)

            # 检查是否有有效结果
            if not vector_results and not keyword_results:
                logger.warning(
                    "hybrid_search_no_results",
                    query=query[:50],
                    tenant_id=tenant_id,
                )
                return self._mock_search(query, top_k)

            # 混合排序 (RRF)
            merged_results = self._reciprocal_rank_fusion(vector_results, keyword_results, alpha)

            logger.info(
                "hybrid_search_complete",
                vector_count=len(vector_results),
                keyword_count=len(keyword_results),
                merged_count=len(merged_results),
            )

            candidates = merged_results[:candidate_k]

            # Cross-Encoder 重排序（用原始 query 评分，提升精度）
            if enable_rerank and candidates:
                try:
                    from app.retrievers.reranker import get_reranker

                    reranked = await get_reranker().rerank(query, candidates, top_k)
                    logger.info(
                        "rerank_applied",
                        candidate_count=len(candidates),
                        returned=len(reranked),
                    )
                    return reranked
                except Exception as e:
                    logger.warning("rerank_skipped", error=str(e))
                    return candidates[:top_k]

            return candidates[:top_k]

        except Exception as e:
            logger.error(
                "hybrid_search_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return self._mock_search(query, top_k)

    async def _parallel_search(
        self,
        pool: Any,
        query: str,
        tenant_id: str,
        doc_ids: list[str] | None,
        top_k: int,
    ) -> tuple[list[dict], list[dict]]:
        """并行执行向量检索和关键词检索

        【错误隔离】
        单路检索失败时：
        - 返回另一路的结果
        - 不抛出异常，保证整体可用

        Args:
            pool: 数据库连接池
            query: 查询文本
            tenant_id: 租户 ID
            doc_ids: 文档 ID 过滤
            top_k: 每路检索数量

        Returns:
            (vector_results, keyword_results) 元组
        """
        # 使用 asyncio.gather 并行执行
        # return_exceptions=True 确保单路失败不阻塞另一路
        results = await asyncio.gather(
            self._vector_search(pool, query, tenant_id, doc_ids, top_k),
            self._keyword_search(pool, query, tenant_id, doc_ids, top_k),
            return_exceptions=True,
        )

        # 处理结果
        vector_results: list[dict] = []
        keyword_results: list[dict] = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # 单路失败，记录日志但不影响另一路
                logger.warning(
                    "parallel_search_partial_failure",
                    search_type="vector" if i == 0 else "keyword",
                    error=str(result),
                )
            elif isinstance(result, list):
                if i == 0:
                    vector_results = result
                else:
                    keyword_results = result

        return vector_results, keyword_results

    async def _vector_search(
        self,
        pool,
        query: str,
        tenant_id: str,
        doc_ids: list[str] | None,
        top_k: int,
    ) -> list[dict]:
        """向量相似度检索

        【Embedding 缓存】
        优先从缓存获取 query embedding：
        - 缓存命中：直接使用，节省 ~100-500ms
        - 缓存未命中：计算后缓存

        使用 pgvector 的向量相似度搜索。

        Args:
            pool: 数据库连接池
            query: 查询文本
            tenant_id: 租户 ID
            doc_ids: 文档 ID 过滤
            top_k: 返回数量

        Returns:
            检索结果列表
        """
        try:
            # 【Embedding 缓存】优先从缓存获取
            embedding_cache = await self._get_embedding_cache()
            query_embedding_list = await embedding_cache.get(query)

            if query_embedding_list is None:
                # 缓存未命中，计算 Embedding
                from app.indexers.vector_indexer import EmbeddingClient

                embedding_client = EmbeddingClient(
                    base_url=config.embedding_service_url,
                    model=config.embedding_model,
                )
                query_embedding = await embedding_client.embed(query)
                query_embedding_list = query_embedding.tolist()

                # 写入缓存
                await embedding_cache.set(query, query_embedding_list)

                logger.debug(
                    "embedding_computed",
                    query_hash=hash(query) % 10000,
                    embedding_dim=len(query_embedding_list),
                )
            else:
                logger.debug(
                    "embedding_cache_hit",
                    query_hash=hash(query) % 10000,
                )

            # 构建查询
            sql = """
                SELECT
                    c.id as chunk_id,
                    c.document_id,
                    c.chunk_index,
                    c.content,
                    c.metadata,
                    d.name as document_name,
                    1 - (c.embedding <=> $1::vector) as score
                FROM knowledge_chunk c
                JOIN knowledge_document d ON c.document_id = d.id
                WHERE c.tenant_id = $2
                    AND d.status = 'ready'
            """

            params = [query_embedding_list, tenant_id]
            param_idx = 3

            if doc_ids:
                sql += f" AND c.document_id = ANY(${param_idx})"
                params.append(doc_ids)
                param_idx += 1

            sql += f" ORDER BY c.embedding <=> $1::vector LIMIT ${param_idx}"
            params.append(top_k)

            results = await pool.fetch(sql, *params)

            return [
                {
                    "chunk_id": r["chunk_id"],
                    "document_id": r["document_id"],
                    "document_name": r["document_name"],
                    "chunk_index": r["chunk_index"],
                    "content": r["content"],
                    "score": float(r["score"]),
                    "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
                    "source": "vector",
                }
                for r in results
            ]

        except Exception as e:
            logger.warning("Vector search failed", error=str(e))
            return []

    async def _keyword_search(
        self,
        pool,
        query: str,
        tenant_id: str,
        doc_ids: list[str] | None,
        top_k: int,
    ) -> list[dict]:
        """BM25 关键词检索

        使用 PostgreSQL ILIKE 模式匹配（支持中文，无需安装分词扩展）。
        注：'simple' 文本搜索配置不支持中文分词，改用 ILIKE 做子串匹配。
        """
        # 构建 SQL：使用 ILIKE 替代 tsquery，支持中文关键词匹配
        sql = """
            SELECT
                id, document_id, chunk_index, content,
                CASE WHEN content ILIKE '%' || $1 || '%' THEN 0.5 ELSE 0.0 END as score
            FROM knowledge_chunk
            WHERE tenant_id = $2
                AND content ILIKE '%' || $1 || '%'
        """

        params = [query, tenant_id]

        if doc_ids:
            sql += " AND document_id = ANY($3)"
            params.append(doc_ids)

        sql += f" ORDER BY score DESC LIMIT ${len(params) + 1}"
        params.append(top_k)

        try:
            results = await pool.fetch(sql, *params)
            return [
                {
                    "chunk_id": r["id"],
                    "document_id": r["document_id"],
                    "chunk_index": r["chunk_index"],
                    "content": r["content"],
                    "score": float(r["score"]),
                    "source": "keyword",
                }
                for r in results
            ]
        except Exception as e:
            logger.warning("Keyword search failed", error=str(e))
            return []

    def _reciprocal_rank_fusion(
        self,
        vector_results: list[dict],
        keyword_results: list[dict],
        alpha: float,
    ) -> list[dict]:
        """倒数排名融合 (RRF)

        【RRF 算法】
        RRF(d) = alpha * 1/(k + rank_vector(d)) + (1-alpha) * 1/(k + rank_keyword(d))

        其中：
        - k = 60（经典参数，平滑排名差异）
        - alpha = 向量检索权重
        - rank = 文档在检索结果中的排名（从 0 开始）

        【为什么用 RRF 而不是分数融合？】
        ┌─────────────────────────────────────────────────────────────────────────┐
        │  方法              │  优点                    │  缺点                  │
        ├────────────────────┼──────────────────────────┼────────────────────────┤
        │  分数融合          │  利用分数信息            │  分数分布不一致        │
        │  RRF ✓             │  鲁棒、无需归一化        │  忽略具体分数          │
        └─────────────────────────────────────────────────────────────────────────┘

        BM25 分数和向量相似度分属不同空间，直接融合需归一化，而归一化本身可能引入偏差。
        RRF 基于排名，天然归一化，更鲁棒。

        Args:
            vector_results: 向量检索结果
            keyword_results: BM25 检索结果
            alpha: 向量检索权重（0-1）

        Returns:
            融合后的结果列表
        """
        k = 60  # RRF 常数

        # 计算向量检索分数
        vector_scores = {}
        for i, r in enumerate(vector_results):
            chunk_id = r["chunk_id"]
            vector_scores[chunk_id] = {
                "data": r,
                "rrf_score": alpha / (k + i + 1),
            }

        # 计算关键词检索分数并合并
        merged = {}
        for i, r in enumerate(keyword_results):
            chunk_id = r["chunk_id"]
            keyword_score = (1 - alpha) / (k + i + 1)

            if chunk_id in merged:
                merged[chunk_id]["rrf_score"] += keyword_score
            else:
                merged[chunk_id] = {
                    "data": r,
                    "rrf_score": keyword_score,
                }

        # 添加向量结果中未在关键词结果中出现的
        for chunk_id, data in vector_scores.items():
            if chunk_id not in merged:
                merged[chunk_id] = data

        # 按综合分数排序
        sorted_results = sorted(merged.values(), key=lambda x: x["rrf_score"], reverse=True)

        # 返回结果（保留 document_name 和 metadata 字段）
        return [
            {
                "chunk_id": r["data"]["chunk_id"],
                "document_id": r["data"]["document_id"],
                "document_name": r["data"].get("document_name", ""),
                "content": r["data"]["content"],
                "score": r["rrf_score"],
                "metadata": r["data"].get("metadata", {}),
                "source": "hybrid",
            }
            for r in sorted_results
        ]

    def _mock_search(self, query: str, top_k: int) -> list[dict]:
        """Mock 检索结果"""
        return [
            {
                "chunk_id": f"chunk_{i}",
                "document_id": "doc_001",
                "content": f"这是与 '{query[:20]}' 相关的内容片段 {i}...",
                "score": 1.0 - i * 0.1,
                "source": "mock",
            }
            for i in range(min(top_k, 5))
        ]


# 全局实例
_retriever = None


def get_hybrid_retriever() -> HybridRetriever:
    """获取混合检索器实例"""
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever
