# Agent Platform

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB.svg)](https://www.python.org/)
[![Java 21+](https://img.shields.io/badge/Java-21+-ED8B00.svg)](https://openjdk.org/)
[![CI](https://github.com/jonykchen/agent-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/jonykchen/agent-platform/actions/workflows/ci.yml)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://docs.astral.sh/ruff/)

> 企业级 Agent 平台，采用 **Python 编排 + Java 核心服务 + 国内 LLM** 混合架构。

---

## 项目简介

本项目是一套可在生产环境稳定运行的完整企业级 Agent 平台，采用 `Python 编排 + Java 核心服务 + 国内 LLM` 的混合架构。

### 核心能力

- **对话式任务处理**: 支持多轮对话、知识问答、工具调用
- **风险控制**: 高风险动作风控拦截、人工审批、审计追踪
- **模型治理**: 多模型接入、替换、灰度发布、成本控制
- **企业集成**: 与现有 Java 核心业务系统平滑集成
- **工具权限**: 五层权限检查（RBAC → 租户开关 → ABAC → 配额 → 风险）
- **Feature Flag**: 动态功能开关、灰度发布、A/B 测试
- **性能优化**: Step 批量写入、熔断器、快速路径

## 快速开始

### 环境要求

| 工具 | 版本 | 说明 |
|------|------|------|
| Python | 3.12+ | Agent 编排 |
| Java | 21+ | 核心服务 |
| Docker | 最新 | 基础设施 |
| Git | 最新 | 版本控制 |

### 一键设置

**macOS / Linux / WSL:**
```bash
git clone https://github.com/jonykchen/agent-platform.git
cd agent-platform
./scripts/setup.sh
```

**Windows (CMD):**
```cmd
git clone https://github.com/jonykchen/agent-platform.git
cd agent-platform
scripts\setup.bat
```

### 启动开发环境

**macOS / Linux:**
```bash
make dev
# 或
docker compose -f infra/docker-compose.yml up -d
```

**Windows:**
```cmd
scripts\dev.bat
```

### 验证服务

| 服务 | 地址 | 说明 |
|------|------|------|
| PostgreSQL | localhost:5432 | 数据库（详见 .env.example） |
| Redis | localhost:6379 | 缓存 |
| MinIO | http://localhost:9000 | 对象存储 |
| Grafana | http://localhost:3000 | 监控面板 |

### 应用服务端口

| 服务 | HTTP 端口 | gRPC 端口 |
|------|----------|----------|
| Gateway | 8080 | 9091 |
| Orchestrator | 8001 | 50100 |
| Model Gateway | 8002 | - |
| Knowledge | 8003 | - |
| Tool Bus | 8083 | 40051 |
| Governance | 8082 | - |

### 构建与测试

**所有平台:**
```bash
# 使用 Make (需要安装)
make ci

# 或直接运行
# Python 测试
cd services/orchestrator-python && uv run pytest tests/ -v

# Lint 检查
ruff check .
```

## 项目结构

```
agent-platform/
├── docs/                   # 技术方案文档
├── contracts/              # 契约定义
│   ├── openapi/           # REST API
│   ├── proto/             # gRPC 接口
│   └── tool-schema/       # 工具定义
├── services/              # 微服务实现
│   ├── gateway-java/      # API 网关
│   ├── orchestrator-python/  # Agent 编排
│   ├── model-gateway-python/ # 模型网关
│   ├── tool-bus-java/     # 工具总线
│   ├── governance-java/   # 风控+审批
│   └── knowledge-python/  # 知识库
├── shared/                # 共享资产
│   ├── prompts/           # Prompt 模板
│   ├── evals/             # 评测集
│   └── sql/               # 数据库迁移
├── infra/                 # 基础设施配置
├── scripts/               # 跨平台脚本
│   ├── unix/              # macOS/Linux 脚本
│   └── windows/           # Windows 脚本
├── Makefile               # 统一构建入口
└── README.md
```

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| API 入口 | Java 21 + Spring Boot 3.2 |
| Agent 编排 | Python 3.12 + FastAPI + LangGraph |
| 模型网关 | Python 3.12 + FastAPI |
| 工具服务 | Java 21 + Spring Boot 3.2 |
| 数据库 | PostgreSQL 16 + pgvector |
| 缓存 | Redis 7 |
| 消息队列 | Kafka 3.6 |
| 对象存储 | MinIO |
| 观测 | OpenTelemetry + Prometheus + Grafana |

## 实施进度

| Phase | 状态 | 核心交付物 |
|-------|------|-----------|
| **Phase 1: MVP** | ✅ 已完成 | Gateway + Orchestrator + Model Gateway + Tool Bus + Governance + Knowledge |
| **Phase 2: 生产加固** | ✅ 已完成 | CI/CD + 安全加固 + 可观测性 + 测试体系 + 文档体系 |
| **Phase 3: 能力增强** | 📋 规划中 | 多模型灰度 / 高级 RAG / 插件系统 |
| **Phase 4: 规模化** | 📋 规划中 | 多租户 RLS 增强 / 配额管理 / 水平扩展 |

> 详细路线图见 [ROADMAP.md](ROADMAP.md)

## 使用示例

### 发送对话请求

```bash
# 登录获取 Token
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'

# 发送对话
curl -X POST http://localhost:8080/api/v1/chat/completions \
  -H "Authorization: Bearer <your_token>" \
  -H "X-Tenant-ID: tenant-123" \
  -H "X-User-ID: user-123" \
  -H "Content-Type: application/json" \
  -d '{"message": "你好，请帮我查询今天的订单状态"}'
```

### Python SDK 示例

```python
import requests

BASE_URL = "http://localhost:8080"
headers = {
    "Authorization": "Bearer <your_token>",
    "X-Tenant-ID": "tenant-123",
    "X-User-ID": "user-123",
}

# 发送对话
response = requests.post(
    f"{BASE_URL}/api/v1/chat/completions",
    headers=headers,
    json={"message": "你好", "stream": False},
)
print(response.json())
```

更多示例请参考 [API 参考文档](docs/api-reference.md)。

## 文档

- [技术方案总览](docs/00-index.md)
- [工程规范](docs/01-engineering-standards.md)
- [通信契约](docs/02-communication-contracts.md)
- [安全规范](docs/03-security-specification.md)
- [数据设计](docs/04-data-design-complete.md)
- [性能优化](docs/05-performance-optimization.md)
- [运维指南](docs/06-operability-guide.md)
- [扩展性设计](docs/07-scalability-patterns.md)
- [前端设计](docs/09-frontend-design.md)
- [架构图](docs/architecture-overview.md)
- [API 参考](docs/api-reference.md)
- [部署指南](docs/deployment-guide.md)
- [项目路线图](ROADMAP.md)

## 开发指南

### Proto 契约开发

```bash
# 安装 buf
# macOS: brew install bufbuild/buf/buf
# Windows: scoop install buf

# Lint 检查
buf lint contracts/proto

# 生成代码
buf generate
```

### 数据库迁移

```bash
# 连接数据库
psql -h localhost -U app_user -d agent_platform

# 查看表结构
\dt
```

### Python 服务开发

```bash
cd services/orchestrator-python

# 安装依赖
uv sync

# 运行测试
uv run pytest tests/ -v

# Lint
uv run ruff check .
uv run ruff format .
```

## 贡献

欢迎贡献！请阅读 [贡献指南](CONTRIBUTING.md) 了解如何参与项目开发。

发现安全漏洞？请参阅 [安全政策](SECURITY.md) 进行负责任披露。

## 许可证

本项目基于 [AGPL-3.0](LICENSE) 协议开源。
