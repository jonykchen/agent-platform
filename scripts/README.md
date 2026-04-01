# Scripts 目录

开发助手脚本，按操作系统分类。

## 目录结构

```
scripts/
├── windows/
│   └── dev.ps1        # Windows 交互式开发助手 (PowerShell)
└── unix/
    └── dev.sh         # macOS/Linux 交互式开发助手
```

## 使用方法

### Windows

在 PowerShell 中执行：

```powershell
./scripts/windows/dev.ps1
```

也支持命令行参数直接执行：

```powershell
./scripts/windows/dev.ps1 up      # 启动开发环境
./scripts/windows/dev.ps1 down    # 停止开发环境
./scripts/windows/dev.ps1 test    # 运行测试
./scripts/windows/dev.ps1 lint    # 代码检查
./scripts/windows/dev.ps1 ci      # 完整 CI 流水线
```

### macOS / Linux / Git Bash

```bash
./scripts/unix/dev.sh
```

也支持命令行参数直接执行：

```bash
./scripts/unix/dev.sh up      # 启动开发环境
./scripts/unix/dev.sh down    # 停止开发环境
./scripts/unix/dev.sh test    # 运行测试
./scripts/unix/dev.sh lint    # 代码检查
./scripts/unix/dev.sh ci      # 完整 CI 流水线
```

## 功能列表

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

## 快捷方式

项目根目录的 Makefile 也提供了常用命令：

```bash
make dev        # 启动开发环境
make dev-down   # 停止开发环境
make test       # 运行测试
make lint       # 代码检查
make fmt        # 格式化代码
make ci         # CI 流水线
```
