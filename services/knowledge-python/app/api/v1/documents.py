"""文档管理 API - 生产级实现"""

import os
import uuid
from pathlib import Path
from datetime import datetime

import structlog
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request
from pydantic import BaseModel, Field

from app.core.config import config
from app.core.exceptions import (
    DocumentNotFoundError,
    DocumentProcessingError,
    InvalidDocumentFormatError,
    FileSizeExceededError,
)
from app.indexers.vector_indexer import get_vector_indexer, PgVectorIndexer
from app.processors.document_processor import PDFProcessor, DocxProcessor, TxtProcessor

logger = structlog.get_logger()
router = APIRouter()

# 支持的处理器
PROCESSORS = {
    ".pdf": PDFProcessor(),
    ".docx": DocxProcessor(),
    ".doc": DocxProcessor(),
    ".txt": TxtProcessor(),
    ".md": TxtProcessor(),
}


class DocumentInfo(BaseModel):
    """文档信息"""
    document_id: str
    name: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    created_at: str


class DocumentUploadResponse(BaseModel):
    """上传响应"""
    document_id: str
    name: str
    status: str
    message: str


def _get_tenant_id(request_headers: dict = None) -> str:
    """获取租户 ID（从请求头）

    【请求头约定】
    - X-Tenant-ID: 租户唯一标识
    - 如果未提供，使用默认租户（开发环境）
    """
    if request_headers:
        tenant_id = request_headers.get("X-Tenant-ID")
        if tenant_id:
            return tenant_id
    return "default_tenant"


def _chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> list[dict]:
    """文本分块

    【分块策略】
    1. 按段落分割
    2. 控制块大小
    3. 保留重叠（保持上下文）

    Args:
        text: 原始文本
        chunk_size: 块大小
        overlap: 重叠大小

    Returns:
        块列表
    """
    chunk_size = chunk_size or config.chunk_size
    overlap = overlap or config.chunk_overlap

    # 按段落分割
    paragraphs = text.split("\n\n")

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk += "\n\n" + para if current_chunk else para
        else:
            if current_chunk:
                chunks.append({"content": current_chunk, "metadata": {}})

            # 处理超长段落
            if len(para) > chunk_size:
                # 强制分割
                for i in range(0, len(para), chunk_size - overlap):
                    chunk_content = para[i:i + chunk_size]
                    chunks.append({"content": chunk_content, "metadata": {}})
                current_chunk = ""
            else:
                current_chunk = para

    if current_chunk:
        chunks.append({"content": current_chunk, "metadata": {}})

    return chunks


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
):
    """上传并处理文档

    【处理流程】
    1. 验证文件格式和大小
    2. 保存文件
    3. 提取文本
    4. 分块
    5. 生成 Embedding 并索引
    6. 返回文档信息

    Args:
        request: FastAPI 请求对象
        file: 上传的文件

    Returns:
        上传响应
    """
    tenant_id = _get_tenant_id(dict(request.headers))
    # 验证文件扩展名
    ext = Path(file.filename).suffix.lower()
    if ext not in PROCESSORS:
        raise InvalidDocumentFormatError(ext, list(PROCESSORS.keys()))

    # 验证文件大小
    content = await file.read()
    file_size = len(content)
    file_size_mb = file_size / (1024 * 1024)

    if file_size_mb > config.max_file_size_mb:
        raise FileSizeExceededError(file_size_mb, config.max_file_size_mb)

    # 创建文档记录
    indexer = get_vector_indexer()
    document_id = await indexer.create_document(
        tenant_id=tenant_id,
        name=file.filename,
        file_type=ext[1:],  # 去掉点
        file_size=file_size,
        metadata={"original_filename": file.filename},
    )

    logger.info(
        "document_upload_started",
        document_id=document_id,
        filename=file.filename,
        file_size_mb=file_size_mb,
    )

    try:
        # 保存文件到临时位置
        temp_dir = Path(config.storage_path) / tenant_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        temp_file = temp_dir / f"{document_id}{ext}"
        temp_file.write_bytes(content)

        # 提取文本
        processor = PROCESSORS[ext]
        text = await processor.extract_text(temp_file)

        if not text.strip():
            raise DocumentProcessingError(document_id, "无法从文档中提取文本")

        # 分块
        chunks = _chunk_text(text)

        if not chunks:
            raise DocumentProcessingError(document_id, "文档分块失败，请检查内容")

        # 索引
        await indexer.index(document_id, tenant_id, chunks)

        # 清理临时文件
        temp_file.unlink()

        logger.info(
            "document_upload_completed",
            document_id=document_id,
            chunk_count=len(chunks),
        )

        return DocumentUploadResponse(
            document_id=document_id,
            name=file.filename,
            status="ready",
            message=f"文档处理完成，共 {len(chunks)} 个片段",
        )

    except DocumentProcessingError:
        raise

    except Exception as e:
        logger.error(
            "document_upload_failed",
            document_id=document_id,
            error=str(e),
        )
        raise DocumentProcessingError(document_id, str(e))


@router.get("/{document_id}", response_model=DocumentInfo)
async def get_document(
    request: Request,
    document_id: str,
):
    """获取文档信息

    Args:
        request: FastAPI 请求对象
        document_id: 文档 ID

    Returns:
        文档信息
    """
    tenant_id = _get_tenant_id(dict(request.headers))
    indexer = get_vector_indexer()
    doc_info = await indexer.get_document_info(document_id, tenant_id)

    if not doc_info:
        raise DocumentNotFoundError(document_id)

    return DocumentInfo(
        document_id=doc_info["document_id"],
        name=doc_info["name"],
        file_type=doc_info["file_type"],
        file_size=doc_info["file_size"],
        status=doc_info["status"],
        chunk_count=doc_info["chunk_count"],
        created_at=doc_info["created_at"],
    )


@router.delete("/{document_id}")
async def delete_document(
    request: Request,
    document_id: str,
):
    """删除文档

    Args:
        request: FastAPI 请求对象
        document_id: 文档 ID

    Returns:
        删除结果
    """
    tenant_id = _get_tenant_id(dict(request.headers))
    indexer = get_vector_indexer()

    # 检查文档是否存在
    doc_info = await indexer.get_document_info(document_id, tenant_id)
    if not doc_info:
        raise DocumentNotFoundError(document_id)

    await indexer.delete_document(document_id, tenant_id)

    return {"message": "文档已删除", "document_id": document_id}


@router.get("/", response_model=list[DocumentInfo])
async def list_documents(
    request: Request,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
):
    """列出文档

    Args:
        request: FastAPI 请求对象
        status: 状态筛选
        limit: 返回数量
        offset: 偏移量

    Returns:
        文档列表
    """
    tenant_id = _get_tenant_id(dict(request.headers))
    indexer = get_vector_indexer()
    pool = await indexer._get_pool()

    # 构建查询
    sql = """
        SELECT id, tenant_id, name, file_type, file_size, status, chunk_count, created_at
        FROM knowledge_document
        WHERE tenant_id = $1
    """
    params = [tenant_id]
    param_idx = 2

    if status:
        sql += f" AND status = ${param_idx}"
        params.append(status)
        param_idx += 1

    sql += f" ORDER BY created_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
    params.extend([limit, offset])

    try:
        results = await pool.fetch(sql, *params)

        return [
            DocumentInfo(
                document_id=r["id"],
                name=r["name"],
                file_type=r["file_type"],
                file_size=r["file_size"],
                status=r["status"],
                chunk_count=r["chunk_count"],
                created_at=r["created_at"].isoformat(),
            )
            for r in results
        ]

    except Exception as e:
        logger.error("list_documents_failed", error=str(e))
        return []
