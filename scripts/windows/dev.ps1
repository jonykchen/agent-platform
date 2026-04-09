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

    # 优先检测 docker compose (V2 插件)
    if (Test-ToolAvailable "docker") {
        $null = docker compose version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $script:DockerComposeCmd = "docker compose"
            return $script:DockerComposeCmd
        }
    }

    # 回退到 docker-compose (独立安装)
    if (Test-ToolAvailable "docker-compose") {
        $script:DockerComposeCmd = "docker-compose"
        return $script:DockerComposeCmd
    }

    Write-Err "未找到 docker compose 或 docker-compose"
    return $null
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
#  管理员权限检测
# ============================================================
function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# ============================================================
#  Chocolatey 安装函数
# ============================================================
function Install-Chocolatey {
    Write-Host ""
    Write-Host "=== 安装 Chocolatey ===" -ForegroundColor Blue

    # 检查管理员权限
    if (-not (Test-IsAdmin)) {
        Write-Warn "Chocolatey 安装需要管理员权限"
        Write-Host ""
        Write-Host "  正在打开管理员窗口..." -ForegroundColor Yellow
        Write-Host "  请在新窗口中完成安装，完成后可关闭该窗口。" -ForegroundColor Cyan
        Write-Host ""
        $scriptPath = $MyInvocation.PSCommandPath
        if (-not $scriptPath) { $scriptPath = $PSCommandPath }
        Start-Process pwsh -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" install-choco"
        exit 0
    }

    Write-Info "正在安装 Chocolatey 包管理器..."
    Write-Host "  [1/2] 正在下载安装脚本..."

    try {
        $chocoInstallTmp = Join-Path $env:TEMP "choco-install-$([guid]::NewGuid()).ps1"
        Invoke-WebRequest -Uri "https://community.chocolatey.org/install.ps1" -OutFile $chocoInstallTmp -UseBasicParsing

        Write-Host "  [2/2] 正在执行安装脚本..."

        if ((Get-Item $chocoInstallTmp).Length -gt 0) {
            & $chocoInstallTmp
        } else {
            Write-Err "Chocolatey 安装脚本下载失败 (空文件)"
        }
    } catch {
        Write-Err "Chocolatey 安装失败: $_"
    } finally {
        Remove-Item $chocoInstallTmp -Force -ErrorAction SilentlyContinue
    }

    # 刷新 PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $script:ToolCache.Remove("choco")

    if (Test-ToolAvailable "choco") {
        Write-Status "Chocolatey 安装成功"
    } else {
        Write-Err "Chocolatey 安装失败"
        Write-Host "  手动安装: https://chocolatey.org/install"
    }

    Write-Host ""
    Write-Host "  按任意键关闭此窗口..." -ForegroundColor Cyan
    $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
    exit 0
}

# ============================================================
#  通用 Chocolatey 安装函数
# ============================================================
function Install-ViaChoco {
    param(
        [string]$ToolName,
        [string]$ChocoPackage,
        [string]$InstallAction  # 权限提升时传递的参数
    )

    if (-not $ChocoPackage) { $ChocoPackage = $ToolName }
    if (-not $InstallAction) { $InstallAction = "install-$ToolName" }

    # 检查管理员权限
    if (-not (Test-IsAdmin)) {
        Write-Warn "Chocolatey 安装软件需要管理员权限"
        Write-Host ""
        Write-Host "  正在打开管理员窗口..." -ForegroundColor Yellow
        Write-Host "  请在新窗口中完成安装，完成后可关闭该窗口。" -ForegroundColor Cyan
        Write-Host ""
        $scriptPath = $MyInvocation.PSCommandPath
        if (-not $scriptPath) { $scriptPath = $PSCommandPath }
        Start-Process pwsh -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" $InstallAction"
        exit 0
    }

    # 确保 chocolatey 可用
    if (-not (Test-ToolAvailable "choco")) {
        Write-Warn "Chocolatey 未安装"
        $installChoco = Read-Host "  是否安装 Chocolatey? [y/N]"
        if ($installChoco -match "^[yY]") {
            Install-Chocolatey
        } else {
            Write-Host "  手动安装: https://chocolatey.org/install"
            return $false
        }
    }

    if (-not (Test-ToolAvailable "choco")) {
        Write-Err "Chocolatey 不可用，无法继续"
        return $false
    }

    Write-Host "  [1/3] 正在下载 $ToolName..."

    $process = Start-Process -FilePath "choco" -ArgumentList "install", $ChocoPackage, "-y" -NoNewWindow -PassThru -RedirectStandardOutput "$env:TEMP\choco-${ChocoPackage}-out.log" -RedirectStandardError "$env:TEMP\choco-${ChocoPackage}-err.log"

    $spinner = @("|", "/", "-", "\")
    $spinnerIdx = 0

    while (-not $process.HasExited) {
        Write-Host "`r  [$($spinner[$spinnerIdx])] 安装中...    " -NoNewline -ForegroundColor Yellow
        $spinnerIdx = ($spinnerIdx + 1) % $spinner.Length
        Start-Sleep -Milliseconds 200
    }

    Write-Host "`r  [2/3] 安装完成，正在验证...    " -ForegroundColor Cyan

    # 输出日志
    if (Test-Path "$env:TEMP\choco-${ChocoPackage}-out.log") {
        $outContent = Get-Content "$env:TEMP\choco-${ChocoPackage}-out.log" -ErrorAction SilentlyContinue
        if ($outContent) {
            $outContent | Where-Object { $_ -match "installed|Chocolatey" } | ForEach-Object {
                Write-Host "  $_" -ForegroundColor Gray
            }
        }
        Remove-Item "$env:TEMP\choco-${ChocoPackage}-out.log" -Force -ErrorAction SilentlyContinue
    }
    Remove-Item "$env:TEMP\choco-${ChocoPackage}-err.log" -Force -ErrorAction SilentlyContinue

    # 刷新 PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $script:ToolCache.Remove($ToolName)

    if (Test-ToolAvailable $ToolName) {
        Write-Host "  [3/3] 验证通过" -ForegroundColor Green
        Write-Status "$ToolName 安装成功"
        return $true
    }

    Write-Err "$ToolName 安装失败"
    Write-Host "  手动安装: choco install $ChocoPackage -y"
    return $false
}

# ============================================================
#  Make 安装函数
# ============================================================
function Install-Make {
    Write-Host ""
    Write-Host "=== 安装 Make ===" -ForegroundColor Blue
    $result = Install-ViaChoco -ToolName "make" -ChocoPackage "make" -InstallAction "install-make"

    Write-Host ""
    Write-Host "  按任意键关闭此窗口..." -ForegroundColor Cyan
    $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
    exit 0
}

# ============================================================
#  Buf 安装函数
# ============================================================
function Install-Buf {
    Write-Host ""
    Write-Host "=== 安装 Buf ===" -ForegroundColor Blue

    # 检查是否已安装
    if (Test-ToolAvailable "buf") {
        $bufVersion = (buf --version 2>&1 | Out-String).Trim()
        Write-Status "buf 已安装: $bufVersion"
        Write-Host ""
        Write-Host "  按任意键关闭此窗口..." -ForegroundColor Cyan
        $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
        exit 0
    }

    # 方式 1: scoop (buf 在 scoop 仓库中)
    if (Test-ToolAvailable "scoop") {
        Write-Info "使用 scoop 安装 buf..."
        scoop install buf
        if ($LASTEXITCODE -eq 0) {
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")
            $script:ToolCache.Remove("buf")
            if (Test-ToolAvailable "buf") {
                Write-Status "buf 安装成功"
                Write-Host ""
                Write-Host "  按任意键关闭此窗口..." -ForegroundColor Cyan
                $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
                exit 0
            }
        }
        Write-Warn "scoop 安装失败，尝试其他方式..."
    }

    # 方式 2: 从 GitHub releases 直接下载
    Write-Info "从 GitHub releases 下载 buf..."
    Write-Host "  [1/4] 获取最新版本号..."

    $latestVersion = "1.47.2"  # 已知的最新版本，可后续更新
    $downloadUrl = "https://github.com/bufbuild/buf/releases/download/v${latestVersion}/buf-Windows-x86_64.exe"
    $installDir = Join-Path $env:LOCALAPPDATA "buf"
    $bufExePath = Join-Path $installDir "buf.exe"

    Write-Host "  [2/4] 创建安装目录..."
    if (-not (Test-Path $installDir)) {
        New-Item -ItemType Directory -Path $installDir -Force | Out-Null
    }

    Write-Host "  [3/4] 下载 buf v${latestVersion}..."
    try {
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $downloadUrl -OutFile $bufExePath -UseBasicParsing
        $ProgressPreference = 'Continue'

        if ((Get-Item $bufExePath).Length -lt 10000) {
            Write-Err "下载文件太小，可能下载失败"
            Remove-Item $bufExePath -Force -ErrorAction SilentlyContinue
        }
    } catch {
        Write-Err "下载失败: $_"
        Write-Host ""
        Write-Host "  手动安装方式:" -ForegroundColor Yellow
        Write-Host "    1. scoop install buf (推荐)" -ForegroundColor Cyan
        Write-Host "    2. 从 GitHub releases 下载: https://github.com/bufbuild/buf/releases" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "  按任意键关闭此窗口..." -ForegroundColor Cyan
        $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
        exit 0
    }

    Write-Host "  [4/4] 添加到 PATH..."
    $currentPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    if ($currentPath -notlike "*$installDir*") {
        [System.Environment]::SetEnvironmentVariable("Path", "$currentPath;$installDir", "User")
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    }

    $script:ToolCache.Remove("buf")

    # 直接验证文件是否存在（PATH 可能未立即生效）
    if ((Test-Path $bufExePath) -and (Get-Item $bufExePath).Length -gt 10000) {
        Write-Status "buf 安装成功 (v${latestVersion})"
        Write-Host ""
        Write-Host "  安装路径: $bufExePath" -ForegroundColor Gray
        Write-Host "  注意: 新终端窗口可直接使用 buf 命令" -ForegroundColor Yellow
    } else {
        Write-Err "buf 安装失败"
        Write-Host "  请手动安装: https://github.com/bufbuild/buf/releases" -ForegroundColor Cyan
    }

    Write-Host ""
    Write-Host "  按任意键关闭此窗口..." -ForegroundColor Cyan
    $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
    exit 0
}

# ============================================================
#  Ruff 安装函数
# ============================================================
function Install-Ruff {
    Write-Host ""
    Write-Host "=== 安装 Ruff ===" -ForegroundColor Blue
    $result = Install-ViaChoco -ToolName "ruff" -ChocoPackage "ruff" -InstallAction "install-ruff"

    Write-Host ""
    Write-Host "  按任意键关闭此窗口..." -ForegroundColor Cyan
    $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
    exit 0
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
        Write-Warn "Make 未安装 (构建工具)"
        Write-Host "  用途: 执行 Makefile 中的构建命令"
        $installMake = Read-Host "  是否安装 make? [y/N]"
        if ($installMake -match "^[yY]") {
            Install-Make
        } else {
            Write-Host "  手动安装: choco install make -y 或 scoop install make"
        }
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
        Write-Warn "ruff 未安装 (Python 代码检查工具)"
        Write-Host "  用途: 代码 lint 和格式化"
        $installRuff = Read-Host "  是否安装 ruff? [y/N]"
        if ($installRuff -match "^[yY]") {
            Install-Ruff
        } else {
            Write-Host "  手动安装: choco install ruff -y 或 pip install ruff"
        }
    }

    # buf (包含内置 protoc)
    $bufExePath = Join-Path $env:LOCALAPPDATA "buf\buf.exe"
    $bufAvailable = Test-ToolAvailable "buf" -or (Test-Path $bufExePath)
    if ($bufAvailable) {
        try {
            $bufCmd = if (Test-ToolAvailable "buf") { "buf" } else { $bufExePath }
            $bufVersion = (& $bufCmd --version 2>&1 | Out-String).Trim()
            Write-Status "buf: $bufVersion"
            Write-Info "buf 已内置 protoc，无需单独安装"
        } catch {
            Write-Status "buf 已安装"
        }
    } else {
        Write-Warn "buf 未安装 (Proto 代码生成工具)"
        Write-Host "  用途: 从 .proto 文件生成 gRPC Java/Python 代码"
        $installBuf = Read-Host "  是否安装 buf? [y/N]"
        if ($installBuf -match "^[yY]") {
            Install-Buf
        } else {
            Write-Host "  手动安装: scoop install buf 或从 https://github.com/bufbuild/buf/releases 下载"
        }
    }

    # protoc (原生编译器，仅当 buf 未安装时检测)
    if (-not (Test-ToolAvailable "buf") -and (Test-ToolAvailable "protoc")) {
        try {
            $protocVersion = (protoc --version 2>&1 | Out-String).Trim()
            Write-Status "protoc: $protocVersion"
        } catch {
            Write-Status "protoc 已安装"
        }
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
    $null = Invoke-DockerCompose @("ps")
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

    if (-not (Test-ToolAvailable "docker")) {
        Write-Warn "Docker 未安装，跳过停止"
        return
    }

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
        $cmd = Get-DockerComposeCmd
        if ($cmd) {
            $fullArgs = @("-f", $script:DockerComposeFile, "ps")
            $psOutput = if ($cmd -eq "docker compose") {
                & docker compose @fullArgs 2>&1 | Out-String
            } else {
                & docker-compose @fullArgs 2>&1 | Out-String
            }
            if ($psOutput -match "running|Up") {
                $servicesRunning = $true
            }
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
        Invoke-Lint
        if ($LASTEXITCODE -ne 0) { $ciFailed = $true }

        Write-Host ""
        Write-Host "[2/3] 运行测试..."
        Invoke-Test
        if ($LASTEXITCODE -ne 0) { $ciFailed = $true }

        Write-Host ""
        Write-Host "[3/3] 安全扫描..."
        Invoke-Security
        if ($LASTEXITCODE -ne 0) { $ciFailed = $true }
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
        Write-Host "  安装: choco install trivy -y 或 scoop install trivy"
    }

    if (Test-ToolAvailable "gitleaks") {
        Write-Host "运行 Gitleaks 扫描..."
        gitleaks detect --source . --verbose
        if ($LASTEXITCODE -ne 0) { $securityFailed = $true }
    } else {
        Write-Warn "gitleaks 未安装"
        Write-Host "  安装: choco install gitleaks -y 或 scoop install gitleaks"
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
        "^(1|setup|env)$"      { Invoke-Setup; exit 0 }
        "^(2|uv)$"             { Invoke-UvSetup; exit 0 }
        "^(3|up)$"             { Invoke-DevUp; exit 0 }
        "^(4|down)$"           { Invoke-DevDown; exit 0 }
        "^(5|lint)$"           { Invoke-Lint; exit 0 }
        "^(6|fmt|format)$"    { Invoke-Format; exit 0 }
        "^(7|test)$"           { Invoke-Test; exit 0 }
        "^(8|e2e)$"            { Invoke-E2ETest; exit 0 }
        "^(9|ci)$"             { Invoke-CI; exit 0 }
        "^(10|security)$"      { Invoke-Security; exit 0 }
        "^install-make$"       { Install-Make; exit 0 }
        "^install-buf$"        { Install-Buf; exit 0 }
        "^install-ruff$"       { Install-Ruff; exit 0 }
        "^install-choco$"      { Install-Chocolatey; exit 0 }
        "^(-h|--help)$"        {
            Write-Host "用法: ./scripts/windows/dev.ps1 [操作]"
            Write-Host "操作: setup|uv|up|down|lint|fmt|test|e2e|ci|security"
            Write-Host "      install-make|install-buf|install-ruff|install-choco"
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
