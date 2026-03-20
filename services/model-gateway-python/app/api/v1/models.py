"""Models API - 模型列表"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ModelInfo(BaseModel):
    """模型信息"""

    id: str
    object: str = "model"
    created: int
    owned_by: str


class ModelsResponse(BaseModel):
    """模型列表响应"""

    object: str = "list"
    data: list[ModelInfo]


@router.get("/models", response_model=ModelsResponse)
async def list_models():
    """获取可用模型列表"""
    import time

    return ModelsResponse(
        data=[
            ModelInfo(id="qwen-max", created=int(time.time()), owned_by="qwen"),
            ModelInfo(id="qwen-plus", created=int(time.time()), owned_by="qwen"),
            ModelInfo(id="qwen-turbo", created=int(time.time()), owned_by="qwen"),
            ModelInfo(id="glm-4", created=int(time.time()), owned_by="glm"),
            ModelInfo(id="kimi", created=int(time.time()), owned_by="kimi"),
            ModelInfo(id="deepseek-chat", created=int(time.time()), owned_by="deepseek"),
        ]
    )
