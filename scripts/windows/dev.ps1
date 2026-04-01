#!/usr/bin/env pwsh
# ============================================================
#  Agent Platform - Windows 开发助手
#  用法: ./scripts/windows/dev.ps1 [操作]
#  支持: Windows PowerShell 5.1+, PowerShell Core 7+
# ============================================================

param(
    [string]$Action
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
Set-Location $ProjectRoot

# Python 服务列表（脚本级常量，便于统一维护）
$script:PythonServices = @(
    "orchestrator-python",
    "model-gateway-python",
    "knowledge-python"
)

# Docker Compose 文件路径
$script:DockerComposeFile = "infra/docker-compose.yml"

# ============================================================
#  工具可用性缓存
#  避免重复调用 Get-Command
# ============================================================
$script:ToolCache = @{}

function Test-ToolAvailable {
    param([string]$Name)
    if (-not $script:ToolCache.ContainsKey($Name)) {
        $script:ToolCache[$Name] = [bool](Get-Command $Name -ErrorAction SilentlyContinue)
    }
    return $script:ToolCache[$Name]
}

# ============================================================
#  颜色输出函数
# ============================================================
function Write-Status { param([string]$msg) Write-Host "[OK] " -ForegroundColor Green -NoNewline; Write-Host $msg }
function Write-Warn  { param([string]$msg) Write-Host "[*] " -ForegroundColor Yellow -NoNewline; Write-Host $msg }
function Write-Err   { param([string]$msg) Write-Host "[X] " -ForegroundColor Red -NoNewline; Write-Host $msg }
function Write-Info  { param([string]$msg) Write-Host "[i] " -ForegroundColor Cyan -NoNewline; Write-Host $msg }

# ============================================================
#  Docker Compose 兼容性辅助函数
# ============================================================
$script:DockerComposeCmd = $null

function Get-DockerComposeCmd {
    if ($script:DockerComposeCmd) { return $script:DockerComposeCmd }

    try {
        $null = docker compose version 2>&1
        $script:DockerComposeCmd = "docker compose"
    } catch {
        if (Test-ToolAvailable "docker-compose") {
            $script:DockerComposeCmd = "docker-compose"
        } else {
            Write-Err "未找到 docker compose 或 docker-compose"
            return $null
        }
    }
    return $script:DockerComposeCmd
}

function Invoke-DockerCompose {
    param([string[]]$Arguments)
    $cmd = Get-DockerComposeCmd
    if (-not $cmd) { return $false }

    $fullArgs = @("-f", $script:DockerComposeFile) + $Arguments
    if ($cmd -eq "docker compose") {
        & docker compose @fullArgs
    } else {
        & docker-compose @fullArgs
    }
    return $LASTEXITCODE -eq 0
}

# ============================================================
#  健康检查辅助函数
# ============================================================
function Wait-ForService {
    param(
        [string]$HostName = "localhost",
        [int]$Port,
        [int]$MaxAttempts = 30
    )

    if (-not $Port) {
        Write-Warn "Wait-ForService: 未指定端口，跳过健康检查"
        return
    }

    Write-Info "等待 ${HostName}:${Port} 就绪 (最多 ${MaxAttempts} 秒)..."

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            $tcpClient = New-Object System.Net.Sockets.TcpClient
            $tcpClient.Connect($HostName, $Port)
            $tcpClient.Close()
            Write-Status "${HostName}:${Port} 已就绪 (${attempt}s)"
            return
        } catch {
            Start-Sleep -Milliseconds 1000
        }
    }

    Write-Warn "${HostName}:${Port} 在 ${MaxAttempts} 秒内未就绪，继续执行..."
}

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
    if (Test-ToolAvailable "git") {
        $gitVersion = git --version
        Write-Status "Git: $gitVersion"
    } else {
        Write-Err "Git 未安装"
        Write-Host "  下载: https://git-scm.com/download/win"
    }

    # Python (version output goes to stderr on some versions)
    $pythonCmd = $null
    foreach ($cmd in @("python", "python3", "py")) {
        if (Test-ToolAvailable $cmd) {
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
    if (Test-ToolAvailable "java") {
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
    if (Test-ToolAvailable "docker") {
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
    if (Test-ToolAvailable "make") {
        Write-Status "Make: 已安装"
    } else {
        Write-Warn "Make 未安装"
        Write-Host "  安装: scoop install make 或 choco install make"
    }

    # uv
    if (Test-ToolAvailable "uv") {
        try {
            $uvVersion = (uv --version 2>&1 | Out-String).Trim()
            Write-Status "uv: $uvVersion"
        } catch {
            Write-Status "uv 已安装"
        }
    } else {
        Write-Warn "uv 未安装 (推荐用于 Python 管理)"
        Write-Host "  执行 [2] 安装"
    }

    # ruff
    if (Test-ToolAvailable "ruff") {
        try {
            $ruffVersion = (ruff --version 2>&1 | Out-String).Trim()
            Write-Status "ruff: $ruffVersion"
        } catch {
            Write-Status "ruff 已安装"
        }
    } else {
        Write-Warn "ruff 未安装"
        Write-Host "  安装: pip install ruff"
    }

    # buf
    if (Test-ToolAvailable "buf") {
        try {
            $bufVersion = (buf --version 2>&1 | Out-String).Trim()
            Write-Status "buf: $bufVersion"
        } catch {
            Write-Status "buf 已安装"
        }
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

    # Step 1: UV 安装
    Write-Host "Step 1: UV 安装" -ForegroundColor Cyan

    if (Test-ToolAvailable "uv") {
        try {
            $uvVersion = (uv --version 2>&1 | Out-String).Trim()
            Write-Status "uv: $uvVersion"
        } catch {
            Write-Status "uv 已安装"
        }
    } else {
        Write-Warn "uv 未安装"
        Write-Info "正在安装 uv..."

        # 安全安装：先下载到临时文件，校验文件非空后再执行
        $uvInstallTmp = Join-Path $env:TEMP "uv-install-$([guid]::NewGuid()).ps1"
        try {
            Invoke-WebRequest -Uri "https://astral.sh/uv/install.ps1" -OutFile $uvInstallTmp -UseBasicParsing

            if ((Get-Item $uvInstallTmp).Length -gt 0) {
                & $uvInstallTmp
            } else {
                Write-Err "uv 安装脚本下载失败 (空文件)"
                return
            }
        } catch {
            Write-Err "uv 安装脚本下载失败: $_"
            return
        } finally {
            Remove-Item $uvInstallTmp -Force -ErrorAction SilentlyContinue
        }

        # 刷新 PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")
        # 清除工具缓存
        $script:ToolCache.Remove("uv")

        if (Test-ToolAvailable "uv") {
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

    # Step 3: 配置 Python 服务
    Write-Host ""
    Write-Host "Step 3: 配置 Python 服务" -ForegroundColor Cyan

    foreach ($service in $script:PythonServices) {
        $servicePath = Join-Path $ProjectRoot "services\$service"

        if (-not (Test-Path $servicePath)) {
            Write-Warn "$service 不存在，跳过"
            continue
        }

        Write-Info "正在配置 $service..."
        Push-Location $servicePath
        try {
            if (-not (Test-Path "pyproject.toml")) {
                Write-Warn "${service}: 无 pyproject.toml，跳过"
                continue
            }

            if (-not (Test-Path ".venv")) {
                Write-Info "创建虚拟环境..."
                uv venv --python 3.12

                if ($LASTEXITCODE -ne 0) {
                    Write-Err "$service 虚拟环境创建失败"
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
        } finally {
            Pop-Location
        }
    }

    # Step 4: 验证安装
    Write-Host ""
    Write-Host "Step 4: 验证安装" -ForegroundColor Cyan

    $allOk = $true

    foreach ($service in $script:PythonServices) {
        $servicePath = Join-Path $ProjectRoot "services\$service"
        $venvPath = Join-Path $servicePath ".venv"

        if (-not (Test-Path $venvPath)) {
            Write-Warn "${service}: .venv 不存在"
            $allOk = $false
            continue
        }

        Push-Location $servicePath
        try {
            uv run python -c "import fastapi; import pydantic; print('OK')" 2>&1 | Out-Null

            if ($LASTEXITCODE -eq 0) {
                Write-Status "${service}: 依赖验证通过"
            } else {
                Write-Warn "${service}: 依赖验证失败"
                $allOk = $false
            }
        } finally {
            Pop-Location
        }
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

    if (-not (Test-ToolAvailable "docker")) {
        Write-Err "Docker 未安装"
        return
    }

    try {
        $null = docker info 2>&1
    } catch {
        Write-Err "Docker 未运行 - 请先启动 Docker Desktop"
        return
    }

    $upSucceeded = $false
    if ((Test-Path "Makefile") -and (Test-ToolAvailable "make")) {
        make dev
        $upSucceeded = ($LASTEXITCODE -eq 0)
    } else {
        $upSucceeded = Invoke-DockerCompose @("up", "-d")
    }

    if (-not $upSucceeded) {
        Write-Err "Docker 服务启动失败"
        return
    }

    # 健康检查：等待核心服务就绪
    Write-Host ""
    Write-Info "检查服务健康状态..."
    Wait-ForService -HostName "localhost" -Port 5432 -MaxAttempts 30
    Wait-ForService -HostName "localhost" -Port 6379 -MaxAttempts 30

    Write-Host ""
    Write-Status "服务已启动"
    Write-Host ""
    Write-Host "=== 服务状态 ===" -ForegroundColor Blue
    Invoke-DockerCompose @("ps") | Out-Null
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

    if ((Test-Path "Makefile") -and (Test-ToolAvailable "make")) {
        make dev-down
    } else {
        Invoke-DockerCompose @("down") | Out-Null
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

    if ((Test-Path "Makefile") -and (Test-ToolAvailable "make")) {
        make lint
    } else {
        $hasTool = $false
        foreach ($service in $script:PythonServices) {
            $servicePath = Join-Path $ProjectRoot "services\$service"
            if (-not (Test-Path $servicePath)) { continue }

            Push-Location $servicePath
            try {
                if (Test-ToolAvailable "uv") {
                    uv run ruff check .
                } elseif (Test-ToolAvailable "ruff") {
                    ruff check .
                } else {
                    continue
                }
                $hasTool = $true
            } finally {
                Pop-Location
            }
        }

        if (-not $hasTool) {
            Write-Warn "ruff 不可用，请安装: pip install ruff 或 uv tool install ruff"
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

    if ((Test-Path "Makefile") -and (Test-ToolAvailable "make")) {
        make fmt
    } else {
        $hasTool = $false
        foreach ($service in $script:PythonServices) {
            $servicePath = Join-Path $ProjectRoot "services\$service"
            if (-not (Test-Path $servicePath)) { continue }

            Push-Location $servicePath
            try {
                if (Test-ToolAvailable "uv") {
                    uv run ruff format .
                } elseif (Test-ToolAvailable "ruff") {
                    ruff format .
                } else {
                    continue
                }
                $hasTool = $true
            } finally {
                Pop-Location
            }
        }

        if (-not $hasTool) {
            Write-Warn "ruff 不可用，请安装: pip install ruff 或 uv tool install ruff"
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

    if ((Test-Path "Makefile") -and (Test-ToolAvailable "make")) {
        make test
    } else {
        $hasTool = $false
        foreach ($service in $script:PythonServices) {
            $servicePath = Join-Path $ProjectRoot "services\$service"
            if (-not (Test-Path $servicePath)) { continue }

            Push-Location $servicePath
            try {
                if (Test-ToolAvailable "uv") {
                    uv run pytest tests/ -v --tb=short
                } elseif (Test-ToolAvailable "pytest") {
                    pytest tests/ -v --tb=short
                } else {
                    continue
                }
                $hasTool = $true
            } finally {
                Pop-Location
            }
        }

        if (-not $hasTool) {
            Write-Warn "pytest 不可用，请安装: pip install pytest 或 uv sync"
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
    $servicesRunning = $false
    try {
        $psOutput = Invoke-DockerCompose @("ps") 2>$null
        if ($psOutput -match "running|Up") {
            $servicesRunning = $true
        }
    } catch {
        # docker compose ps 失败，认为服务未运行
    }

    if (-not $servicesRunning) {
        Write-Warn "服务未运行 - 正在启动..."
        if (-not (Invoke-DockerCompose @("up", "-d"))) {
            Write-Err "服务启动失败"
            return
        }

        # 健康检查轮询，替代固定 sleep
        Wait-ForService -HostName "localhost" -Port 5432 -MaxAttempts 30
        Wait-ForService -HostName "localhost" -Port 6379 -MaxAttempts 30
        Write-Info "等待额外 5 秒确保服务完全就绪..."
        Start-Sleep -Seconds 5
    }

    if (Test-Path "tests/e2e") {
        $e2eFailed = $false
        # 在项目根目录执行，与 bash 版行为一致
        if (Test-ToolAvailable "python") {
            python -m pytest tests/e2e/ -v --tb=short -m "not slow"
            if ($LASTEXITCODE -ne 0) { $e2eFailed = $true }
        } elseif (Test-ToolAvailable "python3") {
            python3 -m pytest tests/e2e/ -v --tb=short -m "not slow"
            if ($LASTEXITCODE -ne 0) { $e2eFailed = $true }
        } else {
            Write-Warn "Python 不可用，无法运行 E2E 测试"
            return
        }

        if ($e2eFailed) {
            Write-Warn "E2E 测试存在失败用例"
        }
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

    $ciFailed = $false

    if ((Test-Path "Makefile") -and (Test-ToolAvailable "make")) {
        make ci
        if ($LASTEXITCODE -ne 0) { $ciFailed = $true }
    } else {
        Write-Host "[1/3] 代码检查..."
        try { Invoke-Lint } catch { $ciFailed = $true }

        Write-Host ""
        Write-Host "[2/3] 运行测试..."
        try { Invoke-Test } catch { $ciFailed = $true }

        Write-Host ""
        Write-Host "[3/3] 安全扫描..."
        try { Invoke-Security } catch { $ciFailed = $true }
    }

    Write-Host ""

    if ($ciFailed) {
        Write-Warn "CI 流水线完成（存在失败项）"
    } else {
        Write-Status "CI 流水线完成"
    }
}

# ============================================================
#  [10] 安全扫描
# ============================================================
function Invoke-Security {
    Write-Host ""
    Write-Host "=== 安全扫描 ===" -ForegroundColor Blue
    Write-Host ""

    $securityFailed = $false

    if (Test-ToolAvailable "trivy") {
        Write-Host "运行 Trivy 扫描..."
        trivy fs --severity HIGH,CRITICAL .
        if ($LASTEXITCODE -ne 0) { $securityFailed = $true }
    } else {
        Write-Warn "trivy 未安装"
        Write-Host "  安装: scoop install trivy"
    }

    if (Test-ToolAvailable "gitleaks") {
        Write-Host "运行 Gitleaks 扫描..."
        gitleaks detect --source . --verbose
        if ($LASTEXITCODE -ne 0) { $securityFailed = $true }
    } else {
        Write-Warn "gitleaks 未安装"
        Write-Host "  安装: scoop install gitleaks"
    }

    Write-Host ""

    if ($securityFailed) {
        Write-Warn "安全扫描完成（发现风险）"
    } else {
        Write-Status "安全扫描完成"
    }
}

# ============================================================
#  主逻辑
# ============================================================

# 如果带参数运行，直接执行对应功能
if ($Action) {
    switch -Regex ($Action) {
        "^(1|setup|env)$"     { Invoke-Setup; exit 0 }
        "^(2|uv)$"            { Invoke-UvSetup; exit 0 }
        "^(3|up)$"            { Invoke-DevUp; exit 0 }
        "^(4|down)$"          { Invoke-DevDown; exit 0 }
        "^(5|lint)$"          { Invoke-Lint; exit 0 }
        "^(6|fmt|format)$"   { Invoke-Format; exit 0 }
        "^(7|test)$"          { Invoke-Test; exit 0 }
        "^(8|e2e)$"           { Invoke-E2ETest; exit 0 }
        "^(9|ci)$"            { Invoke-CI; exit 0 }
        "^(10|security)$"     { Invoke-Security; exit 0 }
        "^(-h|--help)$"       {
            Write-Host "用法: ./scripts/windows/dev.ps1 [操作]"
            Write-Host "操作: setup|uv|up|down|lint|fmt|test|e2e|ci|security"
            Write-Host "无参数时进入交互模式"
            exit 0
        }
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
