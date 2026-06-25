# 快速启动指南

> 本指南帮助你在本地开发环境快速启动 Agent Platform

---

## 前置要求

| 工具 | 版本 | 说明 |
|------|------|------|
| Docker Desktop | 最新版 | 运行基础设施 |
| JDK | 21+ | Java 服务编译运行 |
| Python | 3.12+ | Python 服务 |
| uv | 最新版 | Python 包管理器 + 版本管理 |
| Node.js | 20+ | 前端开发 |
| pnpm | 8+ | 前端包管理器 (`npm install -g pnpm`) |
| Make | 任意 | 构建命令 (Windows 可用 Git Bash 运行) |

---

## 快速初始化

### 一键安装 uv 和 Python 环境

```powershell
# Windows PowerShell
./scripts/setup-uv.ps1

# macOS / Linux / Git Bash
./scripts/setup-uv.sh
```

脚本功能：
- 自动安装 uv（如未安装）
- 安装 Python 3.12（通过 uv 内置版本管理）
- 为所有 Python 服务创建虚拟环境
- 安装所有依赖（含开发依赖）

**可选参数**：
```powershell
# 强制重建虚拟环境
./scripts/setup-uv.ps1 -Force

# 跳过 Python 安装（已有 Python 3.12）
./scripts/setup-uv.ps1 -SkipPythonInstall
```

### 手动安装 uv

如需手动安装：
```powershell
# Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 配置环境变量

> ⚠️ **首次启动前必须配置环境变量！**

```bash
# 复制环境变量模板
cp .env.example .env.local

# 编辑 .env.local，填入必要的配置值（如数据库密码、JWT 密钥等）
# 开发环境可使用模板中的默认值
```

详细的配置说明请参考 `.env.example` 文件中的注释。

## 一键启动基础设施

```bash
# 精简环境（推荐日常开发，仅 PostgreSQL + Redis + MinIO，~1.5 GB）
make dev-slim

# 完整环境（含 Kafka/OTel/Prometheus/Grafana，~7.5 GB）
make dev

# 查看服务状态
docker ps

# 停止基础设施
make dev-down
```

> **提示**：`make dev-slim` 足以支撑全流程 Agent 对话测试。完整环境用于需要 Kafka 审批回调、链路追踪、监控看板的场景。

启动后可访问：
- **PostgreSQL**: `localhost:5432` (user: `app_user`，密码见 `.env.local`)
- **Redis**: `localhost:6379` (密码见 `.env.local`)
- **MinIO Console**: http://localhost:9001 (密码见 `.env.local`)
- **Kafka**: `localhost:9092` / `localhost:9093`
- **Grafana**: http://localhost:3000 (密码见 `.env.local`)
- **Prometheus**: http://localhost:9090

---

## 启动各服务

### 1. Orchestrator (Python) — Agent 编排核心

```bash
cd services/orchestrator-python

# 安装依赖
uv sync

# 启动开发服务
uv run uvicorn app.main:app --reload --port 8001

# 运行测试
uv run pytest tests/ -v
```

### 2. Model Gateway (Python) — 模型网关

```bash
cd services/model-gateway-python

# 安装依赖
uv sync

# 启动开发服务
uv run uvicorn app.main:app --reload --port 8002

# 运行测试
uv run pytest tests/ -v
```

### 3. Knowledge (Python) — 知识库服务

```bash
cd services/knowledge-python

# 安装依赖
uv sync

# 启动开发服务
uv run uvicorn app.main:app --reload --port 8003
```

### 4. Gateway (Java) — API 网关

```bash
cd services/gateway-java

# 编译
./mvnw package -DskipTests

# 运行
java -jar target/gateway-*.jar

# 或直接运行 (开发模式)
./mvnw spring-boot:run
```

### 5. Tool Bus (Java) — 工具总线

```bash
cd services/tool-bus-java

# 编译
./mvnw package -DskipTests

# 运行
./mvnw spring-boot:run
```

### 6. Governance (Java) — 治理服务

```bash
cd services/governance-java

# 编译
./mvnw package -DskipTests

# 运行
./mvnw spring-boot:run
```

### 7. Web Frontend (React)

```bash
cd services/web-frontend

# 安装依赖
pnpm install

# 启动开发服务
pnpm dev

# 运行测试
pnpm test

# 构建生产版本
pnpm build
```

前端启动后访问: http://localhost:5173

---

## 常用命令速查

| 命令 | 说明 |
|------|------|
| `make dev-slim` | 精简开发环境（PostgreSQL + Redis + MinIO，~1.5 GB） |
| `make dev` | 完整基础设施（含 Kafka/OTel/Prometheus/Grafana） |
| `make dev-down` | 停止基础设施 |
| `make build` | 构建所有服务 |
| `make test` | 运行所有测试 |
| `make lint` | 代码检查 |
| `make fmt` | 格式化代码 |
| `make ci` | 完整 CI 检查 |

---

## 服务端口一览

| 服务 | 端口 | 说明 |
|------|------|------|
| Gateway (Java) | 8080 | API 入口 |
| Orchestrator | 8000 (开发 8001) | Agent 编排 |
| Model Gateway | 8002 | 模型代理 |
| Knowledge | 8003 | 知识库 |
| Tool Bus | 8083 | 工具调用 |
| Governance | 8082 | 治理服务 |
| Web Frontend | 5173 | 前端开发服务 |

---

## 环境变量配置

各服务通过 `.env.local` 文件配置环境变量（已在 `.gitignore` 中），参考各服务目录下的 `.env.example`：

```bash
# orchestrator-python/.env.local 示例
DATABASE_URL=postgresql+asyncpg://app_user:dev_password@localhost:5432/agent_platform
REDIS_URL=redis://:dev_password@localhost:6379/0
DEEPSEEK_API_KEY=sk-xxx          # 聊天模型（DeepSeek）
QWEN_API_KEY=sk-xxx              # Embedding 模型（通义千问，RAG 必需）
DEFAULT_MODEL=deepseek-chat       # 默认聊天模型
OTEL_ENABLED=false                # 本地开发可关闭 OTel
```

> **RAG 说明**：知识库检索（RAG）需要 Embedding 向量化服务，使用通义千问 `text-embedding-v3`（1024 维）。需在 Model Gateway 和 Orchestrator 的 `.env.local` 中配置 `QWEN_API_KEY`。

---

## 常见问题

### Q: 端口被占用怎么办？

```bash
# Windows 查看端口占用
netstat -ano | findstr :8080

# 结束进程
taskkill /PID <PID> /F
```

### Q: Python 依赖安装失败？

推荐使用一键初始化脚本：
```powershell
./scripts/setup-uv.ps1 -Force
```

或手动安装 uv 后执行：
```bash
pip install uv
uv sync --all-extras
```

### Q: Java 编译报错？

确保 JDK 21+：
```bash
java -version
# 应显示 21.x.x
```

### Q: Docker 启动失败？

确保 Docker Desktop 已启动，且有足够内存 (建议 8GB+)。

---

## 下一步

- 阅读 [工程规范](01-engineering-standards.md) 了解代码结构
- 阅读 [通信契约](02-communication-contracts.md) 了解 API 规范
- 阅读 [安全规范](03-security-specification.md) 了解安全要求
