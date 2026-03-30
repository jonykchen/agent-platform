# Knowledge Service

知识库服务，提供 RAG 文档索引和检索能力。

## 技术栈

- Python 3.12 + FastAPI
- PostgreSQL + pgvector
- sentence-transformers (Embedding)

## 开发

```bash
# 安装依赖
uv sync --all-extras

# 运行测试
uv run pytest tests/

# 启动服务
uv run uvicorn app.main:app --reload
```
