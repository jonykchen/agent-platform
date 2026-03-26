"""知识库服务异常"""

from typing import Any, Optional


class KnowledgeServiceException(Exception):
    """知识库服务基础异常"""

    def __init__(
        self,
        message: str,
        code: str = "ERR_UNKNOWN",
        user_message: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code
        self.user_message = user_message or message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "user_message": self.user_message,
            "details": self.details,
        }


class DocumentNotFoundError(KnowledgeServiceException):
    """文档不存在"""

    def __init__(self, document_id: str):
        super().__init__(
            f"文档不存在: {document_id}",
            code="ERR_DOCUMENT_NOT_FOUND",
            user_message="文档不存在或已被删除",
            details={"document_id": document_id},
        )


class DocumentProcessingError(KnowledgeServiceException):
    """文档处理失败"""

    def __init__(self, document_id: str, reason: str):
        super().__init__(
            f"文档处理失败 [{document_id}]: {reason}",
            code="ERR_DOCUMENT_PROCESSING",
            user_message="文档处理失败，请检查文件格式",
            details={"document_id": document_id, "reason": reason},
        )


class EmbeddingServiceError(KnowledgeServiceException):
    """Embedding 服务错误"""

    def __init__(self, reason: str):
        super().__init__(
            f"Embedding 服务错误: {reason}",
            code="ERR_EMBEDDING_SERVICE",
            user_message="向量化服务暂时不可用",
            details={"reason": reason},
        )


class InvalidDocumentFormatError(KnowledgeServiceException):
    """无效的文档格式"""

    def __init__(self, extension: str, supported: list[str]):
        super().__init__(
            f"不支持的文档格式: {extension}",
            code="ERR_INVALID_DOCUMENT_FORMAT",
            user_message=f"支持的格式: {', '.join(supported)}",
            details={"extension": extension, "supported": supported},
        )


class FileSizeExceededError(KnowledgeServiceException):
    """文件大小超限"""

    def __init__(self, size_mb: float, max_mb: int):
        super().__init__(
            f"文件大小超限: {size_mb:.1f}MB > {max_mb}MB",
            code="ERR_FILE_SIZE_EXCEEDED",
            user_message=f"文件大小不能超过 {max_mb}MB",
            details={"size_mb": size_mb, "max_mb": max_mb},
        )
