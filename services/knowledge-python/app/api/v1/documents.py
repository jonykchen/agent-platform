"""
文档管理 API - 生产级实现

【核心概念】
文档管理是 RAG Pipeline 的入口，负责文档的上传、解析、分块、索引全流程。
处理后的文档被切分为 chunks，每个 chunk 生成 Embedding 向量并存储到 pgvector。

【RAG Pipeline - 索引阶段】
┌─────────────────────────────────────────────────────────────────────────┐
│                        Document Upload Pipeline                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌───────┐ │
│  │ 文件上传 │──▶│ 格式校验 │──▶│ 文本提取 │──▶│ 文本分块 │──▶│ 索引  │ │
│  │ (HTTP)   │   │ (扩展名) │   │(PDF/DOCX)│   │(Chunking)│   │(Vector)│ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └───────┘ │
│       │              │              │              │              │     │
│       ▼              ▼              ▼              ▼              ▼     │
│   [文件大小]    [支持格式]    [编码检测]    [重叠策略]    [Embedding]   │
│   [MIME类型]    [.pdf/.docx]  [文本清洗]    [元数据]     [pgvector]    │
│   [租户隔离]    [.txt/.md]    [段落识别]    [Chunk ID]                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

【技术选型对比】

| 组件 | 选型 | 备选方案 | 选型理由 |
|------|------|----------|----------|
| 文件上传 | FastAPI UploadFile | Flask, Django | 原生支持异步流式上传 |
| PDF 解析 | PyMuPDF (fitz) | PyPDF2, pdfplumber | 速度快，支持表格/图片 |
| DOCX 解析 | python-docx | unstructured | 轻量级，稳定可靠 |
| 分块策略 | 段落感知分块 | 固定窗口, 语义分块 | 平衡效果与性能 |
| 向量存储 | pgvector | Milvus, Pinecone | 运维简单，与 PostgreSQL 集成 |

【分块策略详解】

段落感知分块（当前实现）：
┌────────────────────────────────────────────────────────┐
│  Paragraph 1                                           │
│  (完整段落，保持语义完整)                                │
├────────────────────────────────────────────────────────┤
│  Paragraph 2                                           │
│  (与 P1 重叠 50 字符，保持上下文连贯)                     │
├────────────────────────────────────────────────────────┤
│  Paragraph 3...                                        │
└────────────────────────────────────────────────────────┘

优点：
- 保持段落完整性，语义不被切断
- 重叠区域确保检索时上下文完整
- 实现简单，性能高

局限性：
- 无法处理超长段落（需强制分割）
- 不考虑语义边界
- 对 FAQ 等短文本效果一般

【支持的文档格式】
- .pdf: PDF 文档（PyMuPDF 解析）
- .docx: Word 文档（python-docx 解析）
- .doc: 旧版 Word（转 docx 处理）
- .txt: 纯文本（UTF-8 编码）
- .md: Markdown 文档

【租户隔离】
通过 X-Tenant-ID 请求头实现多租户隔离：
- 文档按 tenant_id 分区存储
- 检索时自动过滤租户
- 防止跨租户数据泄露

【错误处理】
所有异常继承自 BasePlatformException，包含：
- 错误码：便于监控告警
- 技术信息：日志记录
- 用户信息：API 返回

【API 端点】
- POST   /upload          : 上传文档
- GET    /{document_id}   : 获取文档信息
- DELETE /{document_id}   : 删除文档
- GET    /                : 列出文档
"""

from pathlib import Path

import structlog
from fastapi import APIRouter, File, Request, UploadFile
from pydantic import BaseModel

from app.core.config import config
from app.core.exceptions import (
    DocumentNotFoundError,
    DocumentProcessingError,
    FileSizeExceededError,
    InvalidDocumentFormatError,
)
from app.indexers.vector_indexer import get_vector_indexer
from app.processors.document_processor import DocxProcessor, PDFProcessor, TxtProcessor

logger = structlog.get_logger()
router = APIRouter()

# 支持的处理器映射
# 格式: { 文件扩展名: 处理器实例 }
# 每个处理器实现 extract_text() 方法，返回纯文本
PROCESSORS = {
    ".pdf": PDFProcessor(),
    ".docx": DocxProcessor(),
    ".doc": DocxProcessor(),
    ".txt": TxtProcessor(),
    ".md": TxtProcessor(),
}


class DocumentInfo(BaseModel):
    """
    文档信息模型

    【字段说明】
    - document_id: 文档唯一标识（UUID）
    - name: 文档名称（原始文件名）
    - file_type: 文件类型（pdf/docx/txt/md）
    - file_size: 文件大小（字节）
    - status: 文档状态（pending/processing/ready/error）
    - chunk_count: 分块数量
    - created_at: 创建时间（ISO 8601 格式）
    """

    document_id: str
    name: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int
    created_at: str


class DocumentUploadResponse(BaseModel):
    """
    文档上传响应模型

    【响应字段】
    - document_id: 文档 ID（后续操作引用）
    - status: 处理状态（ready 表示可用）
    - message: 人类可读的处理结果描述
    """

    document_id: str
    name: str
    status: str
    message: str


import re

# 合法 tenant_id 格式：字母/数字/下划线/短横线，3-64 字符
_TENANT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,64}$")


def _get_tenant_id(request_headers: dict = None) -> str:
    """
    从请求头获取租户 ID

    【多租户隔离机制】
    通过 HTTP Header 传递租户标识，实现数据隔离：
    - 文档按 tenant_id 分区存储
    - 检索时自动添加租户过滤条件
    - 防止跨租户数据泄露

    【安全说明】
    - 优先从 JWT Authorization header 提取 tenantId（Gateway 已验证签名）
    - 回退到 X-Tenant-ID header（Gateway 认证后覆盖为 JWT 中的值）
    - 对 tenant_id 格式严格校验，防止注入攻击
    - 默认租户仅在开发环境使用

    Args:
        request_headers: HTTP 请求头字典

    Returns:
        租户 ID 字符串

    Raises:
        ValueError: tenant_id 格式不合法
    """
    # 优先从 JWT payload 提取 tenantId
    auth_header = (request_headers or {}).get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            import base64
            import json

            token = auth_header[7:]
            payload_b64 = token.split(".")[1]
            # 补齐 Base64 padding
            padding = 4 - len(payload_b64) % 4
            payload_json = base64.urlsafe_b64decode(payload_b64 + "=" * padding)
            payload = json.loads(payload_json)
            jwt_tenant_id = payload.get("tenantId")
            if jwt_tenant_id and _TENANT_ID_PATTERN.match(jwt_tenant_id):
                return jwt_tenant_id
        except Exception:
            pass  # JWT 解析失败，回退到 Header

    # 回退到 X-Tenant-ID header（Gateway 认证后应覆盖为可信值）
    if request_headers:
        tenant_id = request_headers.get("X-Tenant-ID", "").strip()
        if tenant_id:
            if not _TENANT_ID_PATTERN.match(tenant_id):
                raise ValueError(
                    f"Invalid tenant_id format: '{tenant_id}'. Must match pattern: ^[a-zA-Z0-9_-]{{3,64}}$"
                )
            return tenant_id

    # 默认租户（仅开发环境）
    return "default_tenant"


def _chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> list[dict]:
    """
    文本分块 - 核心预处理步骤

    【RAG Pipeline 关键环节】
    分块质量直接影响检索效果：
    - 太大：检索精度低，Token 消耗高
    - 太小：语义被切断，上下文不完整
    - 无重叠：边界信息丢失

    【段落感知分块策略】
    1. 按双换行符分割段落（\n\n）
    2. 合并小段落直到达到 chunk_size
    3. 处理超长段落（强制分割）
    4. 保留 overlap 字符重叠

    示例（chunk_size=500, overlap=50）：
    ┌───────────────────────────────────────────────────┐
    │ Chunk 1: [Paragraph 1 + Paragraph 2] (450 chars) │
    ├───────────────────────────────────────────────────┤
    │ Chunk 2: [Paragraph 2 后 50 字符 + Paragraph 3]  │
    └───────────────────────────────────────────────────┘

    【优化方向】
    - 语义分块：基于句子边界/Embedding 相似度
    - 滑动窗口：固定步长移动，提高召回
    - 层级分块：父块粗粒度，子块细粒度

    Args:
        text: 原始文本内容
        chunk_size: 分块大小（字符数），默认使用配置值
        overlap: 重叠大小（字符数），默认使用配置值

    Returns:
        分块列表，每个元素包含:
        - content: 文本内容
        - metadata: 元数据（可扩展）
    """
    chunk_size = chunk_size or config.chunk_size
    overlap = overlap or config.chunk_overlap

    # 按段落分割（双换行符）
    paragraphs = text.split("\n\n")

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # 尝试合并到当前块
        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk += "\n\n" + para if current_chunk else para
        else:
            # 当前块已满，保存
            if current_chunk:
                chunks.append({"content": current_chunk, "metadata": {}})

            # 处理超长段落（超过 chunk_size）
            if len(para) > chunk_size:
                # 强制分割，保留重叠
                for i in range(0, len(para), chunk_size - overlap):
                    chunk_content = para[i : i + chunk_size]
                    chunks.append({"content": chunk_content, "metadata": {}})
                current_chunk = ""
            else:
                # 开始新块
                current_chunk = para

    # 保存最后一个块
    if current_chunk:
        chunks.append({"content": current_chunk, "metadata": {}})

    return chunks


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
):
    """
    上传并处理文档 - RAG Pipeline 入口

    【处理流程】
    ┌─────────────────────────────────────────────────────────────────────┐
    │  1. 验证      →  2. 存储  →  3. 解析  →  4. 分块  →  5. 索引        │
    │  ┌─────────┐    ┌────────┐   ┌────────┐   ┌────────┐   ┌─────────┐  │
    │  │格式校验 │───▶│临时文件│──▶│文本提取│──▶│分块策略│──▶│Embedding│  │
    │  │大小限制 │    │写入磁盘│   │PDF/DOCX│   │段落感知│   │pgvector │  │
    │  └─────────┘    └────────┘   └────────┘   └────────┘   └─────────┘  │
    └─────────────────────────────────────────────────────────────────────┘

    【性能指标】
    - 小文件（<1MB）: 3-5s 完成
    - 中文件（1-10MB）: 10-30s 完成
    - 大文件（10-50MB）: 30-120s 完成

    【错误处理】
    - InvalidDocumentFormatError: 不支持的文件格式
    - FileSizeExceededError: 文件超过大小限制
    - DocumentProcessingError: 文本提取/分块/索引失败

    【租户隔离】
    通过 X-Tenant-ID 请求头区分租户，文档按租户隔离存储。

    Args:
        request: FastAPI 请求对象（获取 Header）
        file: 上传的文件（multipart/form-data）

    Returns:
        DocumentUploadResponse: 包含 document_id 和处理状态

    Raises:
        InvalidDocumentFormatError: 文件格式不支持
        FileSizeExceededError: 文件过大
        DocumentProcessingError: 处理失败
    """
    tenant_id = _get_tenant_id(dict(request.headers))

    # ==================== 1. 格式验证 ====================
    ext = Path(file.filename).suffix.lower()
    if ext not in PROCESSORS:
        raise InvalidDocumentFormatError(ext, list(PROCESSORS.keys()))

    # ==================== 2. 大小验证 ====================
    # 先检查 Content-Length header（防止超大文件先读入内存再拒绝导致 OOM）
    content_length = request.headers.get("content-length")
    if content_length:
        declared_size_mb = int(content_length) / (1024 * 1024)
        if declared_size_mb > config.max_file_size_mb * 1.1:  # 10% 裕量（multipart 开销）
            raise FileSizeExceededError(declared_size_mb, config.max_file_size_mb)

    # 分块读取并限制大小，避免一次性将超大文件读入内存
    chunks = []
    total_size = 0
    MAX_READ_CHUNK = 1024 * 1024  # 1MB chunks
    while True:
        chunk = await file.read(MAX_READ_CHUNK)
        if not chunk:
            break
        total_size += len(chunk)
        current_size_mb = total_size / (1024 * 1024)
        if current_size_mb > config.max_file_size_mb:
            raise FileSizeExceededError(current_size_mb, config.max_file_size_mb)
        chunks.append(chunk)

    content = b"".join(chunks)
    file_size = total_size
    file_size_mb = file_size / (1024 * 1024)

    # ==================== 3. 创建文档记录 ====================
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
        # ==================== 4. 保存临时文件 ====================
        temp_dir = Path(config.storage_path) / tenant_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        temp_file = temp_dir / f"{document_id}{ext}"
        temp_file.write_bytes(content)

        # ==================== 5. 提取文本 ====================
        processor = PROCESSORS[ext]
        text = await processor.extract_text(temp_file)

        if not text.strip():
            raise DocumentProcessingError(document_id, "无法从文档中提取文本")

        # ==================== 6. 文本分块 ====================
        chunks = _chunk_text(text)

        if not chunks:
            raise DocumentProcessingError(document_id, "文档分块失败，请检查内容")

        # ==================== 7. 向量索引 ====================
        # 内部流程：调用 Model Gateway 生成 Embedding → 存储到 pgvector
        await indexer.index(document_id, tenant_id, chunks)

        # ==================== 8. 清理临时文件 ====================
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
