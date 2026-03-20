"""文档处理器 - 支持多种格式"""

from abc import ABC, abstractmethod
from pathlib import Path


class DocumentProcessor(ABC):
    """文档处理器基类"""

    @abstractmethod
    async def extract_text(self, file_path: Path) -> str:
        """提取文本内容"""
        pass

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """支持的文件扩展名"""
        pass


class PDFProcessor(DocumentProcessor):
    """PDF 处理器"""

    async def extract_text(self, file_path: Path) -> str:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text

    def supported_extensions(self) -> list[str]:
        return [".pdf"]


class DocxProcessor(DocumentProcessor):
    """Word 文档处理器"""

    async def extract_text(self, file_path: Path) -> str:
        from docx import Document

        doc = Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])

    def supported_extensions(self) -> list[str]:
        return [".docx", ".doc"]


class TxtProcessor(DocumentProcessor):
    """纯文本处理器"""

    async def extract_text(self, file_path: Path) -> str:
        return file_path.read_text(encoding="utf-8")

    def supported_extensions(self) -> list[str]:
        return [".txt", ".md"]
