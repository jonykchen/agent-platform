"""混合检索器

结合 BM25 关键词检索和向量相似度检索。
"""

import json
import structlog

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

logger = structlog.get_logger()


class HybridRetriever:
    """混合检索器"""

    def __init__(self, database_url: str | None = None):
        self.database_url = database_url
        self._pool = None

    async def _get_pool(self):
        if not HAS_ASYNCPG:
            return None

        if self._pool is None and self.database_url:
            self._pool = await asyncpg.create_pool(self.database_url, min_size=5, max_size=20)
        return self._pool

    async def search(
        self,
        query: str,
        tenant_id: str,
        doc_ids: list[str] | None = None,
        top_k: int = 10,
        alpha: float = 0.5,
    ) -> list[dict]:
        """混合检索

        Args:
            query: 查询文本
            tenant_id: 租户 ID
            doc_ids: 可选，限定文档范围
            top_k: 返回数量
            alpha: 向量检索权重 (1-alpha 为 BM25 权重)

        Returns:
            检索结果列表
        """
        pool = await self._get_pool()

        if pool is None:
            return self._mock_search(query, top_k)

        try:
            # 1. 向量相似度检索
            vector_results = await self._vector_search(pool, query, tenant_id, doc_ids, top_k * 2)

            # 2. BM25 关键词检索
            keyword_results = await self._keyword_search(pool, query, tenant_id, doc_ids, top_k * 2)

            # 3. 混合排序 (RRF)
            merged_results = self._reciprocal_rank_fusion(vector_results, keyword_results, alpha)

            return merged_results[:top_k]

        except Exception as e:
            logger.error("Hybrid search failed", error=str(e))
            return self._mock_search(query, top_k)

    async def _vector_search(
        self,
        pool,
        query: str,
        tenant_id: str,
        doc_ids: list[str] | None,
        top_k: int,
    ) -> list[dict]:
        """向量相似度检索

        使用 pgvector 的向量相似度搜索。
        """
        # TODO: 实现真实的 embedding 调用
        # 当前返回 Mock 数据
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

        使用 PostgreSQL 全文搜索。
        """
        # 构建 SQL
        sql = """
            SELECT
                id, document_id, chunk_index, content,
                ts_rank_cd(to_tsvector('simple', content), plainto_tsquery('simple', $1)) as score
            FROM knowledge_chunk
            WHERE tenant_id = $2
        """

        params = [query, tenant_id]

        if doc_ids:
            sql += " AND document_id = ANY($3)"
            params.append(doc_ids)

        sql += f" ORDER BY score DESC LIMIT {top_k}"

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

        合并多个检索结果，基于排名计算综合分数。
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

        # 返回结果
        return [
            {
                "chunk_id": r["data"]["chunk_id"],
                "document_id": r["data"]["document_id"],
                "content": r["data"]["content"],
                "score": r["rrf_score"],
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