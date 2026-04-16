# Scripts 目录

开发助手脚本，按操作系统分类。

## 目录结构

```
scripts/
├── windows/
│   ├── dev.ps1        # 基础设施管理 (Docker 服务)
│   └── app.ps1        # Python 应用服务管理
└── unix/
    ├── dev.sh         # 基础设施管理 (Docker 服务)
    └── app.sh         # Python 应用服务管理
```

## 两套脚本

| 脚本 | 用途 | 管理内容 |
|------|------|----------|
| `dev.ps1/sh` | 基础设施 | PostgreSQL、Redis、Kafka、MinIO、Grafana、Prometheus |
| `app.ps1/sh` | 应用服务 | orchestrator、model-gateway、knowledge (Python) |

**Java 服务** 使用 IDE 启动（IntelliJ IDEA），不在脚本中管理。

## 使用方法

### 基础设施

**Windows：**
```powershell
./scripts/windows/dev.ps1          # 交互模式
./scripts/windows/dev.ps1 up       # 启动基础设施
./scripts/windows/dev.ps1 down     # 停止基础设施
```

**macOS / Linux：**
```bash
./scripts/unix/dev.sh              # 交互模式
./scripts/unix/dev.sh up           # 启动基础设施
./scripts/unix/dev.sh down         # 停止基础设施
```

### Python 应用服务

**Windows：**
```powershell
./scripts/windows/app.ps1          # 交互模式
./scripts/windows/app.ps1 start    # 启动所有 Python 服务
./scripts/windows/app.ps1 stop     # 停止所有 Python 服务
./scripts/windows/app.ps1 status   # 查看服务状态
./scripts/windows/app.ps1 logs     # 查看日志
./scripts/windows/app.ps1 restart  # 重启服务
```

**macOS / Linux：**
```bash
./scripts/unix/app.sh              # 交互模式
./scripts/unix/app.sh start        # 启动所有 Python 服务
./scripts/unix/app.sh stop         # 停止所有 Python 服务
./scripts/unix/app.sh status       # 查看服务状态
./scripts/unix/app.sh logs         # 查看日志
./scripts/unix/app.sh restart      # 重启服务
```

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| PostgreSQL | 5432 | 数据库 |
| Redis | 6379 | 缓存/会话 |
| Kafka | 9092/9094 | 消息队列 |
| MinIO | 9000/9001 | 对象存储 |
| Grafana | 3000 | 监控面板 |
| Prometheus | 9090 | 指标采集 |
| Alertmanager | 9093 | 告警管理 |
| orchestrator | 8001 | Agent 编排服务 |
| model-gateway | 8002 | LLM 模型网关 |
| knowledge | 8003 | 知识库服务 |

## 开发流程

推荐的开发启动顺序：

1. **启动基础设施**
   ```powershell
   ./scripts/windows/dev.ps1 up
   ```

2. **启动 Python 服务**
   ```powershell
   ./scripts/windows/app.ps1 start
   ```

3. **在 IDEA 中启动 Java 服务**
   - gateway-java (8080)
   - governance-java (8081)
   - tool-bus-java (8082)

## 日志管理

应用服务日志输出到 `logs/` 目录：

```
logs/
├── orchestrator.log      # orchestrator 服务日志
├── orchestrator.err.log  # orchestrator 错误日志
├── model-gateway.log     # model-gateway 服务日志
├── knowledge.log         # knowledge 服务日志
└── *.pid                 # 进程 ID 文件
```

实时查看日志：
```powershell
# Windows
Get-Content logs\orchestrator.log -Wait

# macOS / Linux
tail -f logs/orchestrator.log
```

## dev.ps1 功能列表

| 编号 | 功能 | 说明 |
|------|------|------|
| 1 | 环境检查 | 检查 Git/Python/Java/Docker/Make/uv/ruff/buf |
| 2 | UV 安装 | 安装 uv、Python 3.12，创建虚拟环境 |
| 3 | 启动开发环境 | 启动 PostgreSQL/Redis/MinIO/Grafana |
| 4 | 停止开发环境 | 停止 Docker 服务，清理容器 |
| 5 | 代码检查 | ruff lint 检查代码质量 |
| 6 | 格式化代码 | ruff format 格式化 Python 代码 |
| 7 | 运行测试 | pytest 运行单元测试 |
| 8 | 运行 E2E 测试 | 端到端集成测试 |
| 9 | 完整 CI 流水线 | lint + test + security |
| 10 | 安全扫描 | Trivy 漏洞 + Gitleaks 密钥泄露 |

## app.ps1 功能列表

| 编号 | 功能 | 说明 |
|------|------|------|
| 1 | 启动所有服务 | 启动 orchestrator/model-gateway/knowledge |
| 2 | 停止所有服务 | 停止所有 Python 服务 |
| 3 | 查看服务状态 | 检查运行状态和端口监听 |
| 4 | 查看日志 | 实时查看服务日志 |
| 5 | 重启所有服务 | 停止后重新启动 |

## 快捷方式

项目根目录的 Makefile 也提供了常用命令：

```bash
make dev        # 启动基础设施
make dev-down   # 停止基础设施
make test       # 运行测试
make lint       # 代码检查
make fmt        # 格式化代码
make ci         # CI 流水线
```