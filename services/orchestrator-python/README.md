# Orchestrator Service

Agent 编排服务，基于 LangGraph 实现 Agent 状态机和工具调用流程。

## 技术栈

- Python 3.12 + FastAPI
- LangGraph + LangChain
- PostgreSQL + Redis + Kafka

## 开发

```bash
# 安装依赖
uv sync --all-extras

# 运行测试
uv run pytest tests/

# 启动服务
uv run uvicorn app.main:app --reload
```

## 目录结构

```
app/
├── api/          # 路由层
├── core/         # 配置、异常、常量
├── graph/        # LangGraph 状态机
├── memory/       # 对话记忆
├── tools/        # 工具客户端
└── schemas/      # Pydantic 模型
```
