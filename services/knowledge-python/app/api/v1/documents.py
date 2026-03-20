"""文档管理 API"""

from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

router = APIRouter()


class DocumentInfo(BaseModel):
    document_id: str
    name: str
    status: str
    chunk_count: int


@router.post("/upload", response_model=DocumentInfo)
async def upload_document(file: UploadFile = File(...)):
    """上传文档"""
    # TODO: 实现文档上传和处理
    return DocumentInfo(
        document_id="doc-001",
        name=file.filename,
        status="processing",
        chunk_count=0,
    )


@router.get("/{document_id}", response_model=DocumentInfo)
async def get_document(document_id: str):
    """获取文档信息"""
    return DocumentInfo(
        document_id=document_id,
        name="example.pdf",
        status="ready",
        chunk_count=50,
    )
