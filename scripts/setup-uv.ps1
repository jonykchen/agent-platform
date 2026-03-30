#!/usr/bin/env pwsh
# ============================================================
#  Agent Platform - UV Setup Script (Windows PowerShell)
#  用法: ./scripts/setup-uv.ps1
# ============================================================

param(
    [switch]$SkipPythonInstall,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# 颜色函数
function Write-Status { param($msg) Write-Host "[OK] " -ForegroundColor Green -NoNewline; Write-Host $msg }
function Write-Warn  { param($msg) Write-Host "[*] " -ForegroundColor Yellow -NoNewline; Write-Host $msg }
function Write-Err   { param($msg) Write-Host "[X] " -ForegroundColor Red -NoNewline; Write-Host $msg }
function Write-Info  { param($msg) Write-Host "[i] " -ForegroundColor Cyan -NoNewline; Write-Host $msg }

# Python 服务列表
$PythonServices = @(
    "orchestrator-python",
    "model-gateway-python",
    "knowledge-python"
)

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host ""
Write-Host "=== Agent Platform - UV Setup ===" -ForegroundColor Blue
Write-Host "Project root: $ProjectRoot"
Write-Host ""

# ============================================================
#  1. 检查/安装 uv
# ============================================================
Write-Host "=== Step 1: UV Installation ===" -ForegroundColor Blue

$uvInstalled = $null -ne (Get-Command uv -ErrorAction SilentlyContinue)

if ($uvInstalled) {
    $uvVersion = uv --version 2>&1
    Write-Status "uv: $uvVersion"
} else {
    Write-Warn "uv not installed"
    Write-Info "Installing uv..."

    # 使用官方安装脚本
    $installScript = Invoke-RestMethod https://astral.sh/uv/install.ps1
    Invoke-Expression $installScript

    # 刷新环境变量
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")

    if ($null -ne (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Status "uv installed successfully"
    } else {
        Write-Err "Failed to install uv"
        Write-Host "  Please install manually: irm https://astral.sh/uv/install.ps1 | iex"
        exit 1
    }
}

# ============================================================
#  2. 检查/安装 Python 3.12
# ============================================================
Write-Host ""
Write-Host "=== Step 2: Python 3.12 ===" -ForegroundColor Blue

if (-not $SkipPythonInstall) {
    $pythonVersions = uv python list 2>&1

    if ($pythonVersions -match "3\.12") {
        Write-Status "Python 3.12 already installed"
    } else {
        Write-Info "Installing Python 3.12..."
        uv python install 3.12

        if ($LASTEXITCODE -eq 0) {
            Write-Status "Python 3.12 installed"
        } else {
            Write-Err "Failed to install Python 3.12"
            exit 1
        }
    }
} else {
    Write-Warn "Skipping Python installation (--SkipPythonInstall)"
}

# ============================================================
#  3. 为每个服务创建虚拟环境并安装依赖
# ============================================================
Write-Host ""
Write-Host "=== Step 3: Setup Python Services ===" -ForegroundColor Blue

foreach ($service in $PythonServices) {
    $servicePath = Join-Path $ProjectRoot "services\$service"

    if (-not (Test-Path $servicePath)) {
        Write-Warn "$service not found, skipping"
        continue
    }

    Write-Host ""
    Write-Info "Setting up $service..."

    Set-Location $servicePath

    # 检查 pyproject.toml
    if (-not (Test-Path "pyproject.toml")) {
        Write-Warn "${service}: no pyproject.toml, skipping"
        continue
    }

    # 创建虚拟环境（如果不存在或强制重建）
    if ((Test-Path ".venv") -and $Force) {
        Write-Info "Removing existing .venv..."
        Remove-Item -Recurse -Force ".venv"
    }

    if (-not (Test-Path ".venv")) {
        Write-Info "Creating virtual environment..."
        uv venv --python 3.12

        if ($LASTEXITCODE -ne 0) {
            Write-Err "Failed to create venv for $service"
            continue
        }
    } else {
        Write-Status ".venv already exists"
    }

    # 安装依赖（包含 dev 依赖）
    Write-Info "Installing dependencies..."
    uv sync --all-extras

    if ($LASTEXITCODE -eq 0) {
        Write-Status "$service setup complete"
    } else {
        Write-Err "Failed to install dependencies for $service"
    }

    Set-Location $ProjectRoot
}

# ============================================================
#  4. 验证安装
# ============================================================
Write-Host ""
Write-Host "=== Step 4: Verification ===" -ForegroundColor Blue

$allOk = $true

foreach ($service in $PythonServices) {
    $servicePath = Join-Path $ProjectRoot "services\$service"
    $venvPath = Join-Path $servicePath ".venv"

    if (-not (Test-Path $venvPath)) {
        Write-Warn "${service}: .venv not found"
        $allOk = $false
        continue
    }

    # 检查关键包
    Set-Location $servicePath
    uv run python -c "import fastapi; import pydantic; print('OK')" 2>&1 | Out-Null

    if ($LASTEXITCODE -eq 0) {
        Write-Status "${service}: packages verified"
    } else {
        Write-Warn "${service}: package verification failed"
        $allOk = $false
    }

    Set-Location $ProjectRoot
}

# ============================================================
#  完成
# ============================================================
Write-Host ""

if ($allOk) {
    Write-Status "All services setup successfully!"
} else {
    Write-Warn "Some services may need attention"
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Green
Write-Host "  1. Activate environment:  cd services/orchestrator-python && .venv\Scripts\Activate.ps1"
Write-Host "  2. Run tests:             make test"
Write-Host "  3. Start dev server:      make dev"
Write-Host ""
