# Agent Platform

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
git clone <repository-url>
cd agent-platform
./scripts/setup.sh
```

**Windows (CMD):**
```cmd
git clone <repository-url>
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
| PostgreSQL | localhost:5432 | user: app_user, db: agent_platform |
| Redis | localhost:6379 | 无密码 |
| MinIO | http://localhost:9000 | user: minioadmin |
| Grafana | http://localhost:3000 | user: admin |

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
├── CLAUDE.md               # Claude 项目配置
├── .claude/                # Claude 配置目录
│   ├── settings.json       # 权限与自动化配置
│   ├── workflows.md        # 开发流程指南
│   └── projects/           # Memory 系统
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
│   ├── setup.sh           # macOS/Linux 设置
│   ├── setup.bat          # Windows 设置
│   ├── dev.bat            # Windows 启动脚本
│   └── test.bat           # Windows 测试脚本
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

## Claude Code 配置

本项目已配置 Claude Code 自动化开发环境：

### 功能清单

| 功能 | 说明 |
|------|------|
| **自动 Lint** | Python 文件保存后自动 ruff fix |
| **语法检查** | 写入前自动 Python 语法验证 |
| **安全防护** | 阻止敏感文件读写 |
| **Memory 系统** | 持久化项目上下文 |
| **跨平台支持** | macOS/Linux/Windows |

### 配置文件

| 文件 | 用途 |
|------|------|
| `CLAUDE.md` | 项目主配置文档 |
| `.claude/settings.json` | 权限与 Hooks |
| `.claude/workflows.md` | 开发流程指南 |
| `.claude/projects/*/memory/` | Memory 文件 |

### 快速命令

```bash
# 检查配置是否正确
python -m json.tool .claude/settings.json

# 查看项目阶段
cat .claude/projects/*/memory/project_phase.md

# 查看技术决策
cat .claude/projects/*/memory/tech_decisions.md
```

## 实施路线图

| Phase | 周期 | 核心交付物 | 状态 |
|-------|------|-----------|------|
| **Phase 1: MVP** | 第 1-4 周 | Gateway+Orchestrator+ModelGateway+Mock ToolBus | 🔧 开发中 |
| **Phase 2: 业务闭环** | 第 5-12 周 | Governance服务+真实工具+Kafka回调恢复 | 待启动 |
| **Phase 3: 能力增强** | 第 13-20 周 | Knowledge服务(RAG)+评测体系 | 待启动 |
| **Phase 4: 规模化** | 第 21 周+ | 多租户RLS+配额管理 | 待启动 |

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

## 许可证

内部项目，仅供授权使用。
