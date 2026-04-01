#!/usr/bin/env pwsh
# ============================================================
#  Agent Platform - Windows 开发助手
#  用法: ./scripts/windows/dev.ps1
# ============================================================

param(
    [string]$Action
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# 颜色函数
function Write-Status { param($msg) Write-Host "[OK] " -ForegroundColor Green -NoNewline; Write-Host $msg }
function Write-Warn  { param($msg) Write-Host "[*] " -ForegroundColor Yellow -NoNewline; Write-Host $msg }
function Write-Err   { param($msg) Write-Host "[X] " -ForegroundColor Red -NoNewline; Write-Host $msg }
function Write-Info  { param($msg) Write-Host "[i] " -ForegroundColor Cyan -NoNewline; Write-Host $msg }

# 显示菜单
function Show-Menu {
    Clear-Host
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Blue
    Write-Host " Agent Platform - Windows 开发助手" -ForegroundColor Blue
    Write-Host "============================================================" -ForegroundColor Blue
    Write-Host ""
    Write-Host " === 可用功能 ===" -ForegroundColor Blue
    Write-Host ""
    Write-Host "   [1]  环境检查        - 检查 Git/Python/Java/Docker/Make/uv/ruff/buf"
    Write-Host "   [2]  UV 安装        - 安装 uv、Python 3.12，创建虚拟环境"
    Write-Host "   [3]  启动开发环境    - 启动 PostgreSQL/Redis/MinIO/Grafana"
    Write-Host "   [4]  停止开发环境    - 停止 Docker 服务，清理容器"
    Write-Host "   [5]  代码检查        - ruff lint 检查代码质量"
    Write-Host "   [6]  格式化代码      - ruff format 格式化 Python 代码"
    Write-Host "   [7]  运行测试        - pytest 运行单元测试"
    Write-Host "   [8]  运行 E2E 测试   - 端到端集成测试"
    Write-Host "   [9]  完整 CI 流水线  - lint + test + security"
    Write-Host "   [10] 安全扫描        - Trivy 漏洞 + Gitleaks 密钥泄露"
    Write-Host "   [0]  退出"
    Write-Host ""
}

# ============================================================
#  [1] 环境检查
# ============================================================
function Invoke-Setup {
    Write-Host ""
    Write-Host "=== 环境检查 ===" -ForegroundColor Blue
    Write-Host ""

    # Git
    if (Get-Command git -ErrorAction SilentlyContinue) {
        $gitVersion = git --version
        Write-Status "Git: $gitVersion"
    } else {
        Write-Err "Git 未安装"
        Write-Host "  下载: https://git-scm.com/download/win"
    }

    # Python (version output goes to stderr on some versions)
    $pythonCmd = $null
    foreach ($cmd in @("python", "python3", "py")) {
        if (Get-Command $cmd -ErrorAction SilentlyContinue) {
            $pythonCmd = $cmd
            break
        }
    }
    if ($pythonCmd) {
        try {
            $pyVersion = (& $pythonCmd --version 2>&1 | Out-String).Trim()
            Write-Status "$pyVersion (命令: $pythonCmd)"
        } catch {
            Write-Status "Python 已安装 (命令: $pythonCmd)"
        }
    } else {
        Write-Err "Python 未安装"
        Write-Host "  下载: https://www.python.org/downloads/"
    }

    # Java (version output goes to stderr)
    if (Get-Command java -ErrorAction SilentlyContinue) {
        try {
            $javaVersion = (java -version 2>&1 | Out-String).Trim() -split '\n' | Select-Object -First 1
            Write-Status "Java: $javaVersion"
        } catch {
            Write-Status "Java 已安装"
        }
    } else {
        Write-Warn "Java 未安装 (Agent 编排可选)"
    }

    # Docker
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        try {
            $null = docker info 2>&1
            $dockerVersion = docker --version
            Write-Status "$dockerVersion (运行中)"
        } catch {
            Write-Warn "Docker 已安装但未运行"
            Write-Host "  请先启动 Docker Desktop"
        }
    } else {
        Write-Warn "Docker 未安装"
        Write-Host "  下载: https://www.docker.com/products/docker-desktop"
    }

    # Make
    if (Get-Command make -ErrorAction SilentlyContinue) {
        Write-Status "Make: 已安装"
    } else {
        Write-Warn "Make 未安装"
        Write-Host "  安装: scoop install make 或 choco install make"
    }

    # uv
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        $uvVersion = uv --version 2>&1
        Write-Status "uv: $uvVersion"
    } else {
        Write-Warn "uv 未安装 (推荐用于 Python 管理)"
        Write-Host "  执行 [2] 安装"
    }

    # ruff
    if (Get-Command ruff -ErrorAction SilentlyContinue) {
        $ruffVersion = ruff --version 2>&1
        Write-Status "ruff: $ruffVersion"
    } else {
        Write-Warn "ruff 未安装"
        Write-Host "  安装: pip install ruff"
    }

    # buf
    if (Get-Command buf -ErrorAction SilentlyContinue) {
        $bufVersion = buf --version 2>&1
        Write-Status "buf: $bufVersion"
    } else {
        Write-Warn "buf 未安装 (Proto 可选)"
        Write-Host "  安装: scoop install buf"
    }

    Write-Host ""
    Write-Status "环境检查完成"
}

# ============================================================
#  [2] UV 安装
# ============================================================
function Invoke-UvSetup {
    Write-Host ""
    Write-Host "=== UV 安装 ===" -ForegroundColor Blue
    Write-Host ""

    $PythonServices = @(
        "orchestrator-python",
        "model-gateway-python",
        "knowledge-python"
    )

    # Step 1: UV Installation
    Write-Host "Step 1: UV Installation" -ForegroundColor Cyan

    if (Get-Command uv -ErrorAction SilentlyContinue) {
        try {
            $uvVersion = (uv --version 2>&1 | Out-String).Trim()
            Write-Status "uv: $uvVersion"
        } catch {
            Write-Status "uv 已安装"
        }
    } else {
        Write-Warn "uv 未安装"
        Write-Info "正在安装 uv..."

        $installScript = Invoke-RestMethod https://astral.sh/uv/install.ps1
        Invoke-Expression $installScript

        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")

        if (Get-Command uv -ErrorAction SilentlyContinue) {
            Write-Status "uv 安装成功"
        } else {
            Write-Err "uv 安装失败"
            Write-Host "  手动安装: irm https://astral.sh/uv/install.ps1 | iex"
            return
        }
    }

    # Step 2: Python 3.12
    Write-Host ""
    Write-Host "Step 2: Python 3.12" -ForegroundColor Cyan

    $pythonVersions = uv python list 2>&1
    if ($pythonVersions -match "3\.12") {
        Write-Status "Python 3.12 已安装"
    } else {
        Write-Info "正在安装 Python 3.12..."
        uv python install 3.12

        if ($LASTEXITCODE -eq 0) {
            Write-Status "Python 3.12 安装成功"
        } else {
            Write-Err "Python 3.12 安装失败"
            return
        }
    }

    # Step 3: Setup Python Services
    Write-Host ""
    Write-Host "Step 3: Setup Python Services" -ForegroundColor Cyan

    foreach ($service in $PythonServices) {
        $servicePath = Join-Path $ProjectRoot "services\$service"

        if (-not (Test-Path $servicePath)) {
            Write-Warn "$service 不存在，跳过"
            continue
        }

        Write-Info "正在配置 $service..."
        Set-Location $servicePath

        if (-not (Test-Path "pyproject.toml")) {
            Write-Warn "${service}: 无 pyproject.toml，跳过"
            Set-Location $ProjectRoot
            continue
        }

        if (-not (Test-Path ".venv")) {
            Write-Info "创建虚拟环境..."
            uv venv --python 3.12

            if ($LASTEXITCODE -ne 0) {
                Write-Err "$service 虚拟环境创建失败"
                Set-Location $ProjectRoot
                continue
            }
        } else {
            Write-Status ".venv 已存在"
        }

        Write-Info "安装依赖..."
        uv sync --all-extras

        if ($LASTEXITCODE -eq 0) {
            Write-Status "$service 配置完成"
        } else {
            Write-Err "$service 依赖安装失败"
        }

        Set-Location $ProjectRoot
    }

    # Step 4: Verification
    Write-Host ""
    Write-Host "Step 4: Verification" -ForegroundColor Cyan

    $allOk = $true

    foreach ($service in $PythonServices) {
        $servicePath = Join-Path $ProjectRoot "services\$service"
        $venvPath = Join-Path $servicePath ".venv"

        if (-not (Test-Path $venvPath)) {
            Write-Warn "${service}: .venv 不存在"
            $allOk = $false
            continue
        }

        Set-Location $servicePath
        uv run python -c "import fastapi; import pydantic; print('OK')" 2>&1 | Out-Null

        if ($LASTEXITCODE -eq 0) {
            Write-Status "${service}: 依赖验证通过"
        } else {
            Write-Warn "${service}: 依赖验证失败"
            $allOk = $false
        }

        Set-Location $ProjectRoot
    }

    Write-Host ""

    if ($allOk) {
        Write-Status "所有服务配置成功!"
    } else {
        Write-Warn "部分服务需要检查"
    }

    Write-Host ""
    Write-Host "下一步:" -ForegroundColor Green
    Write-Host "  1. 激活环境:  cd services/orchestrator-python && .venv\Scripts\Activate.ps1"
    Write-Host "  2. 运行测试:  make test"
    Write-Host "  3. 启动服务:  make dev"
    Write-Host ""
}

# ============================================================
#  [3] 启动开发环境
# ============================================================
function Invoke-DevUp {
    Write-Host ""
    Write-Host "=== 启动开发环境 ===" -ForegroundColor Blue
    Write-Host ""

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Err "Docker 未安装"
        return
    }

    try {
        $null = docker info 2>&1
    } catch {
        Write-Err "Docker 未运行 - 请先启动 Docker Desktop"
        return
    }

    if (Test-Path "Makefile") {
        make dev
    } else {
        docker compose -f infra/docker-compose.yml up -d
    }

    Write-Host ""
    Write-Status "服务已启动"
    Write-Host ""
    Write-Host "=== 服务状态 ===" -ForegroundColor Blue
    docker compose -f infra/docker-compose.yml ps
    Write-Host ""
    Write-Host "=== 可用服务 ===" -ForegroundColor Blue
    Write-Host "  PostgreSQL:  localhost:5432"
    Write-Host "  Redis:       localhost:6379"
    Write-Host "  MinIO:       http://localhost:9000"
    Write-Host "  Grafana:     http://localhost:3000"
    Write-Host ""
}

# ============================================================
#  [4] 停止开发环境
# ============================================================
function Invoke-DevDown {
    Write-Host ""
    Write-Host "=== 停止开发环境 ===" -ForegroundColor Blue
    Write-Host ""

    if (Test-Path "Makefile") {
        make dev-down
    } else {
        docker compose -f infra/docker-compose.yml down
    }

    Write-Host ""
    Write-Status "服务已停止"
}

# ============================================================
#  [5] 代码检查
# ============================================================
function Invoke-Lint {
    Write-Host ""
    Write-Host "=== 代码检查 ===" -ForegroundColor Blue
    Write-Host ""

    if (Test-Path "Makefile") {
        make lint
    } else {
        Write-Host "运行 ruff check..."
        if (Test-Path "services/orchestrator-python") {
            Push-Location services/orchestrator-python
            if (Get-Command uv -ErrorAction SilentlyContinue) {
                uv run ruff check .
            } elseif (Get-Command ruff -ErrorAction SilentlyContinue) {
                ruff check .
            } else {
                Write-Warn "ruff 不可用"
            }
            Pop-Location
        }
    }

    Write-Host ""
    Write-Status "代码检查完成"
}

# ============================================================
#  [6] 格式化代码
# ============================================================
function Invoke-Format {
    Write-Host ""
    Write-Host "=== 格式化代码 ===" -ForegroundColor Blue
    Write-Host ""

    if (Test-Path "Makefile") {
        make fmt
    } else {
        if (Test-Path "services/orchestrator-python") {
            Push-Location services/orchestrator-python
            if (Get-Command uv -ErrorAction SilentlyContinue) {
                uv run ruff format .
            } elseif (Get-Command ruff -ErrorAction SilentlyContinue) {
                ruff format .
            }
            Pop-Location
        }
    }

    Write-Host ""
    Write-Status "格式化完成"
}

# ============================================================
#  [7] 运行测试
# ============================================================
function Invoke-Test {
    Write-Host ""
    Write-Host "=== 运行单元测试 ===" -ForegroundColor Blue
    Write-Host ""

    if (Test-Path "Makefile") {
        make test
    } else {
        if (Test-Path "services/orchestrator-python") {
            Push-Location services/orchestrator-python
            if (Get-Command uv -ErrorAction SilentlyContinue) {
                uv run pytest tests/ -v --tb=short
            } elseif (Get-Command pytest -ErrorAction SilentlyContinue) {
                pytest tests/ -v --tb=short
            } else {
                Write-Warn "pytest 不可用"
            }
            Pop-Location
        }
    }

    Write-Host ""
    Write-Status "测试完成"
}

# ============================================================
#  [8] 运行 E2E 测试
# ============================================================
function Invoke-E2ETest {
    Write-Host ""
    Write-Host "=== 运行 E2E 测试 ===" -ForegroundColor Blue
    Write-Host ""

    # 检查服务是否运行
    Write-Host "检查服务是否运行..."
    $running = docker compose -f infra/docker-compose.yml ps 2>$null | Select-String "running"
    if (-not $running) {
        Write-Warn "服务未运行 - 正在启动..."
        docker compose -f infra/docker-compose.yml up -d
        Write-Host "等待 10 秒让服务就绪..."
        Start-Sleep -Seconds 10
    }

    if (Test-Path "tests/e2e") {
        Push-Location tests/e2e
        python -m pytest . -v --tb=short -m "not slow" 2>$null
        Pop-Location
    } else {
        Write-Warn "未找到 E2E 测试"
    }

    Write-Host ""
    Write-Status "E2E 测试完成"
}

# ============================================================
#  [9] 完整 CI 流水线
# ============================================================
function Invoke-CI {
    Write-Host ""
    Write-Host "=== 完整 CI 流水线 ===" -ForegroundColor Blue
    Write-Host ""

    if (Test-Path "Makefile") {
        make ci
    } else {
        Write-Host "[1/2] 代码检查..."
        Invoke-Lint
        Write-Host ""
        Write-Host "[2/2] 运行测试..."
        Invoke-Test
    }

    Write-Host ""
    Write-Status "CI 流水线完成"
}

# ============================================================
#  [10] 安全扫描
# ============================================================
function Invoke-Security {
    Write-Host ""
    Write-Host "=== 安全扫描 ===" -ForegroundColor Blue
    Write-Host ""

    if (Get-Command trivy -ErrorAction SilentlyContinue) {
        Write-Host "运行 Trivy 扫描..."
        trivy fs --severity HIGH,CRITICAL .
    } else {
        Write-Warn "trivy 未安装"
        Write-Host "  安装: scoop install trivy"
    }

    if (Get-Command gitleaks -ErrorAction SilentlyContinue) {
        Write-Host "运行 Gitleaks 扫描..."
        gitleaks detect --source . --verbose
    } else {
        Write-Warn "gitleaks 未安装"
        Write-Host "  安装: scoop install gitleaks"
    }

    Write-Host ""
    Write-Status "安全扫描完成"
}

# ============================================================
#  主逻辑
# ============================================================

# 如果带参数运行，直接执行对应功能
if ($Action) {
    switch -Regex ($Action) {
        "^(1|setup|env)$"     { Invoke-Setup; exit 0 }
        "^(2|uv)$"           { Invoke-UvSetup; exit 0 }
        "^(3|up)$"           { Invoke-DevUp; exit 0 }
        "^(4|down)$"         { Invoke-DevDown; exit 0 }
        "^(5|lint)$"         { Invoke-Lint; exit 0 }
        "^(6|fmt|format)$"   { Invoke-Format; exit 0 }
        "^(7|test)$"         { Invoke-Test; exit 0 }
        "^(8|e2e)$"          { Invoke-E2ETest; exit 0 }
        "^(9|ci)$"           { Invoke-CI; exit 0 }
        "^(10|security)$"    { Invoke-Security; exit 0 }
        default {
            Write-Err "未知操作: $Action"
            Write-Host "可用操作: setup, uv, up, down, lint, fmt, test, e2e, ci, security"
            exit 1
        }
    }
}

# 交互模式
while ($true) {
    Show-Menu
    $choice = Read-Host "请选择操作 (0-10)"

    switch ($choice) {
        "0"  { Write-Host "再见!"; exit 0 }
        "1"  { Invoke-Setup }
        "2"  { Invoke-UvSetup }
        "3"  { Invoke-DevUp }
        "4"  { Invoke-DevDown }
        "5"  { Invoke-Lint }
        "6"  { Invoke-Format }
        "7"  { Invoke-Test }
        "8"  { Invoke-E2ETest }
        "9"  { Invoke-CI }
        "10" { Invoke-Security }
        default { Write-Err "无效选择" }
    }

    Write-Host ""
    Read-Host "按回车继续..."
}
