"""Health API - 健康检查"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str
    service: str
    version: str
    timestamp: int


@router.get("/health", response_model=HealthResponse)
async def health():
    """健康检查"""
    return HealthResponse(
        status="UP",
        service="orchestrator-python",
        version="1.0.0",
        timestamp=int(1000 * __import__("time").time()),
    )


@router.get("/ready", response_model=HealthResponse)
async def ready():
    """就绪检查"""
    return HealthResponse(
        status="READY",
        service="orchestrator-python",
        version="1.0.0",
        timestamp=int(1000 * __import__("time").time()),
    )