# 企业级 Agent 平台

> **版本**: v2.1 | **状态**: 开发中 | **最后更新**: 2026-05-09

## 项目简介

本项目是一套可在生产环境稳定运行的企业级 Agent 平台，采用 `Python 编排 + Java 核心服务 + 国内 LLM` 的混合架构。

### 核心能力

- **对话式任务处理**: 支持多轮对话、知识问答、工具调用
- **风险控制**: 高风险动作风控拦截、人工审批、审计追踪
- **模型治理**: 多模型接入、替换、灰度发布、成本控制
- **企业集成**: 与现有 Java 核心业务系统平滑集成

## 架构概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        客户端层                                      │
│              Web / App / OpenAPI / 第三方集成                        │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP / WebSocket
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Gateway Service (Java)                            │
│         统一API入口 │ 鉴权 │ 限流 │ 租户 │ 请求追踪                   │
└──────┬──────────────────────┬────────────────────────────────┘
       │ 同步gRPC             │ 审计事件/异步通知
       ▼                      ▼
┌──────────────────┐    ┌───────────────────────────┐
│ Orchestrator(Python)│   │           Kafka             │
│ Agent状态机编排     │   │  异步/通知/回放             │
│ 会话记忆/RAG      │   └───────────────────────────┘
│ 任务分解/决策     │                │
└────────┬─────────┘                │
         │                          │
    同步HTTP  同步gRPC               │
         │       │                  │
         ▼       ▼                  │
┌─────────────────┐ ┌────────────┐  │
│ Model Gateway   │ │Tool Bus(J) │◄─┘
│ (Python)        │ │            │
│ 模型路由/超时    │ │Risk Svc    │
│ 重试/Fallback    │ │Approval Svc│
└─────────────────┘ └────────────┘

数据层: PostgreSQL │ Redis │ pgvector │ MinIO
观测层: OpenTelemetry │ Prometheus │ Grafana
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

## 快速开始

### 环境要求

- Python 3.12+
- Java 21+
- Docker & Docker Compose
- Make (可选)

### 启动开发环境

```bash
# 克隆项目
git clone <repository-url>
cd agent-platform

# 启动基础设施服务
make dev
# 或
docker compose -f infra/docker-compose.yml up -d

# 等待服务就绪
docker compose -f infra/docker-compose.yml ps
```

### 验证服务

```bash
# PostgreSQL
psql -h localhost -U app_user -d agent_platform -c "SELECT version();"

# Redis
redis-cli -a dev_password ping

# MinIO Console
open http://localhost:9001
# 用户名: minioadmin, 密码: minioadmin123

# Grafana
open http://localhost:3000
# 用户名: admin, 密码: admin
```

### 构建与测试

```bash
# 运行所有检查
make ci

# 或分步执行
make lint      # 代码风格检查
make test      # 运行测试
make build     # 构建所有服务
```

## 项目结构

```
agent-platform/
├── docs/                    # 技术方案文档
├── contracts/               # 契约定义
│   ├── openapi/            # REST API 定义
│   ├── proto/              # gRPC 接口定义
│   ├── events/             # 事件契约
│   └── tool-schema/        # 工具定义 Schema
├── services/               # 微服务实现
│   ├── gateway-java/       # API 网关
│   ├── orchestrator-python/# Agent 编排引擎
│   ├── model-gateway-python/# 模型网关
│   ├── tool-bus-java/      # 工具总线
│   ├── governance-java/    # 风控+审批
│   └── knowledge-python/   # 知识库服务
├── shared/                 # 共享资产
│   ├── prompts/           # Prompt 模板
│   ├── evals/             # 评测集
│   └── sql/               # 数据库迁移
├── infra/                  # 基础设施配置
├── scripts/                # 运维脚本
├── ci/                     # CI/CD 配置
├── Makefile               # 统一构建入口
└── docker-compose.yml     # 开发环境
```

## 实施路线图

| Phase | 周期 | 核心交付物 | 状态 |
|-------|------|-----------|------|
| **Phase 1: MVP** | 第 1-4 周 | Gateway+Orchestrator+ModelGateway+Mock ToolBus | 🔄 进行中 |
| **Phase 2: 业务闭环** | 第 5-12 周 | 真实工具+风控+审批+Kafka回调恢复 | ⏳ 待开始 |
| **Phase 3: 能力增强** | 第 13-20 周 | RAG知识库+多模态+评测体系+灰度 | ⏳ 待开始 |
| **Phase 4: 规模化** | 第 21 周+ | 多租户完整隔离+成本治理+自进化 | ⏳ 待开始 |

## 文档

- [技术方案总览](docs/00-index.md)
- [工程规范](docs/01-engineering-standards.md)
- [通信契约](docs/02-communication-contracts.md)
- [安全规范](docs/03-security-specification.md)
- [数据设计](docs/04-data-design-complete.md)
- [性能优化](docs/05-performance-optimization.md)
- [运维指南](docs/06-operability-guide.md)
- [扩展性设计](docs/07-scalability-patterns.md)

## 开发指南

### Proto 契约开发

```bash
# 安装 buf
brew install bufbuild/buf/buf

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

# 查看审计表触发器
\df+ block_audit_modification
```

## 许可证

内部项目，仅供授权使用。
