# Model Gateway Service

模型网关服务，提供统一的 LLM API 调用入口，支持多 Provider 路由和熔断降级。

## 技术栈

- Python 3.12 + FastAPI
- httpx (异步 HTTP 客户端)
- Redis (缓存)

## 开发

```bash
# 安装依赖
uv sync --all-extras

# 运行测试
uv run pytest tests/

# 启动服务
uv run uvicorn app.main:app --reload
```
