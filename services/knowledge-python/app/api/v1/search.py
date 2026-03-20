"""检索 API"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(10, ge=1, le=100)
    filters: dict | None = None


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: dict


class SearchResponse(BaseModel):
    results: list[SearchResult]
    total: int


@router.post("/query", response_model=SearchResponse)
async def search_knowledge(request: SearchRequest):
    """检索知识库"""
    # TODO: 实现向量检索
    return SearchResponse(
        results=[
            SearchResult(
                chunk_id="chunk-001",
                document_id="doc-001",
                content="示例检索结果",
                score=0.95,
                metadata={"source": "example.pdf"},
            )
        ],
        total=1,
    )
