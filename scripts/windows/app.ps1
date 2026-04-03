#!/usr/bin/env pwsh
# ============================================================
#  Agent Platform - Python 应用服务管理
#  用法: ./scripts/windows/app.ps1 [操作]
# ============================================================

param(
    [string]$Action
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
Set-Location $ProjectRoot

# Python 服务配置
$PythonServices = @(
    @{ Name = "orchestrator"; Port = 8001; Path = "services\orchestrator-python" },
    @{ Name = "model-gateway"; Port = 8002; Path = "services\model-gateway-python" },
    @{ Name = "knowledge"; Port = 8003; Path = "services\knowledge-python" }
)

# 日志目录
$LogDir = Join-Path $ProjectRoot "logs"
$PidDir = Join-Path $ProjectRoot "logs"

# 确保目录存在
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}
if (-not (Test-Path $PidDir)) {
    New-Item -ItemType Directory -Path $PidDir -Force | Out-Null
}

# 颜色函数
function Write-Status { param([string]$msg) Write-Host "[OK] " -ForegroundColor Green -NoNewline; Write-Host $msg }
function Write-Warn  { param([string]$msg) Write-Host "[*] " -ForegroundColor Yellow -NoNewline; Write-Host $msg }
function Write-Err   { param([string]$msg) Write-Host "[X] " -ForegroundColor Red -NoNewline; Write-Host $msg }
function Write-Info  { param([string]$msg) Write-Host "[i] " -ForegroundColor Cyan -NoNewline; Write-Host $msg }

# 显示菜单
function Show-Menu {
    Clear-Host
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Blue
    Write-Host " Agent Platform - Python 应用服务管理" -ForegroundColor Blue
    Write-Host "============================================================" -ForegroundColor Blue
    Write-Host ""
    Write-Host " === 可用操作 ===" -ForegroundColor Blue
    Write-Host ""
    Write-Host "   [1]  启动所有服务    - 启动 orchestrator/model-gateway/knowledge"
    Write-Host "   [2]  停止所有服务    - 停止所有 Python 服务"
    Write-Host "   [3]  查看服务状态    - 检查服务运行状态和端口"
    Write-Host "   [4]  查看日志        - 实时查看服务日志"
    Write-Host "   [5]  重启所有服务    - 停止后重新启动"
    Write-Host "   [0]  退出"
    Write-Host ""
}

# 检查基础设施是否就绪
function Test-Infrastructure {
    Write-Info "检查基础设施..."

    $pgReady = $false
    $redisReady = $false

    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("localhost", 5432)
        $tcp.Close()
        $pgReady = $true
    } catch {}

    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("localhost", 6379)
        $tcp.Close()
        $redisReady = $true
    } catch {}

    if (-not $pgReady) {
        Write-Err "PostgreSQL 未运行 (端口 5432)"
        Write-Host "  请先运行: ./scripts/windows/dev.ps1 up"
        return $false
    }

    if (-not $redisReady) {
        Write-Err "Redis 未运行 (端口 6379)"
        Write-Host "  请先运行: ./scripts/windows/dev.ps1 up"
        return $false
    }

    Write-Status "基础设施就绪"
    return $true
}

# 启动单个服务
function Start-PythonService {
    param($Service)

    $name = $Service.Name
    $port = $Service.Port
    $path = $Service.Path
    $servicePath = Join-Path $ProjectRoot $path
    $pidFile = Join-Path $PidDir "$name.pid"
    $logFile = Join-Path $LogDir "$name.log"

    # 检查是否已运行
    if (Test-Path $pidFile) {
        $procId = Get-Content $pidFile -ErrorAction SilentlyContinue
        if ($procId -and (Get-Process -Id $procId -ErrorAction SilentlyContinue)) {
            Write-Warn "$name 已在运行 (PID: $procId)"
            return $true
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }

    # 检查端口是否被占用
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("localhost", $port)
        $tcp.Close()
        Write-Err "$name 端口 $port 已被占用"
        return $false
    } catch {}

    Write-Info "启动 $name (端口 $port)..."

    Set-Location $servicePath

    # 启动服务（继承当前环境，避免 Winsock 加载失败）
    $process = Start-Process -FilePath "uv" `
        -ArgumentList "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", $port `
        -RedirectStandardOutput $logFile `
        -RedirectStandardError (Join-Path $LogDir "$name.err.log") `
        -PassThru

    $process.Id | Out-File $pidFile -Encoding UTF8

    Set-Location $ProjectRoot

    # 等待启动
    Start-Sleep -Milliseconds 500

    if (Get-Process -Id $process.Id -ErrorAction SilentlyContinue) {
        Write-Status "$name 启动成功 (PID: $($process.Id))"
        return $true
    } else {
        Write-Err "$name 启动失败，查看日志: $logFile"
        return $false
    }
}

# 停止单个服务
function Stop-PythonService {
    param($Service)

    $name = $Service.Name
    $pidFile = Join-Path $PidDir "$name.pid"

    if (-not (Test-Path $pidFile)) {
        Write-Warn "$name 未运行"
        return
    }

    $procId = Get-Content $pidFile -ErrorAction SilentlyContinue
    if (-not $procId) {
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        Write-Warn "$name 未运行"
        return
    }

    $process = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($process) {
        Write-Info "停止 $name (PID: $procId)..."
        $process.Kill()
        $process.WaitForExit(5000)
        Write-Status "$name 已停止"
    } else {
        Write-Warn "$name 进程已不存在"
    }

    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

# 查看服务状态
function Get-ServiceStatus {
    Write-Host ""
    Write-Host "=== 服务状态 ===" -ForegroundColor Blue
    Write-Host ""

    $allStopped = $true

    foreach ($service in $PythonServices) {
        $name = $service.Name
        $port = $service.Port
        $pidFile = Join-Path $PidDir "$name.pid"
        $logFile = Join-Path $LogDir "$name.log"

        $status = "未运行"
        $procId = "-"

        if (Test-Path $pidFile) {
            $procId = Get-Content $pidFile -ErrorAction SilentlyContinue
            if ($procId -and (Get-Process -Id $procId -ErrorAction SilentlyContinue)) {
                $status = "运行中"
                $allStopped = $false
            } else {
                $procId = "-"
            }
        }

        # 检查端口
        $portStatus = "空闲"
        try {
            $tcp = New-Object System.Net.Sockets.TcpClient
            $tcp.Connect("localhost", $port)
            $tcp.Close()
            $portStatus = "监听"
        } catch {}

        $statusColor = if ($status -eq "运行中") { "Green" } else { "Yellow" }

        Write-Host "  $name" -NoNewline
        Write-Host " [PID: $procId]" -ForegroundColor Gray -NoNewline
        Write-Host " 端口: $port ($portStatus)" -ForegroundColor Gray -NoNewline
        Write-Host " - " -NoNewline
        Write-Host $status -ForegroundColor $statusColor
    }

    Write-Host ""

    if ($allStopped) {
        Write-Info "日志目录: $LogDir"
    }
}

# 启动所有服务
function Start-AllServices {
    Write-Host ""
    Write-Host "=== 启动所有 Python 服务 ===" -ForegroundColor Blue
    Write-Host ""

    if (-not (Test-Infrastructure)) {
        return
    }

    $failed = @()

    foreach ($service in $PythonServices) {
        if (-not (Start-PythonService $service)) {
            $failed += $service.Name
        }
    }

    Write-Host ""

    if ($failed.Count -eq 0) {
        Write-Status "所有服务启动成功"
        Write-Host ""
        Write-Host "服务地址:" -ForegroundColor Green
        foreach ($service in $PythonServices) {
            Write-Host "  http://localhost:$($service.Port) ($($service.Name))"
        }
        Write-Host ""
        Write-Host "API 文档:" -ForegroundColor Green
        Write-Host "  http://localhost:8001/docs (orchestrator)"
        Write-Host "  http://localhost:8002/docs (model-gateway)"
        Write-Host "  http://localhost:8003/docs (knowledge)"
    } else {
        Write-Err "以下服务启动失败: $($failed -join ', ')"
        Write-Host "  查看日志: Get-Content $LogDir\*.log"
    }
}

# 停止所有服务
function Stop-AllServices {
    Write-Host ""
    Write-Host "=== 停止所有 Python 服务 ===" -ForegroundColor Blue
    Write-Host ""

    foreach ($service in $PythonServices) {
        Stop-PythonService $service
    }

    Write-Host ""
    Write-Status "所有服务已停止"
}

# 查看日志
function Watch-Logs {
    Write-Host ""
    Write-Host "=== 查看日志 ===" -ForegroundColor Blue
    Write-Host ""

    Write-Host "日志文件:" -ForegroundColor Cyan
    foreach ($service in $PythonServices) {
        $logFile = Join-Path $LogDir "$($service.Name).log"
        Write-Host "  $logFile"
    }
    Write-Host ""
    Write-Host "实时查看日志 (Ctrl+C 退出):" -ForegroundColor Cyan
    Write-Host "  Get-Content $LogDir\orchestrator.log -Wait"
    Write-Host ""

    $choice = Read-Host "是否实时查看所有日志? [y/N]"
    if ($choice -eq 'y' -or $choice -eq 'Y') {
        Get-Content (Join-Path $LogDir "*.log") -Wait
    }
}

# 重启所有服务
function Restart-AllServices {
    Stop-AllServices
    Start-Sleep -Seconds 2
    Start-AllServices
}

# 主逻辑
if ($Action) {
    switch -Regex ($Action) {
        "^(1|start)$"    { Start-AllServices }
        "^(2|stop)$"     { Stop-AllServices }
        "^(3|status)$"   { Get-ServiceStatus }
        "^(4|logs)$"     { Watch-Logs }
        "^(5|restart)$"  { Restart-AllServices }
        default {
            Write-Err "未知操作: $Action"
            Write-Host "可用操作: start, stop, status, logs, restart"
            exit 1
        }
    }
    exit 0
}

# 交互模式
while ($true) {
    Show-Menu
    $choice = Read-Host "请选择操作 (0-5)"

    switch ($choice) {
        "0" { Write-Host "再见!"; exit 0 }
        "1" { Start-AllServices }
        "2" { Stop-AllServices }
        "3" { Get-ServiceStatus }
        "4" { Watch-Logs }
        "5" { Restart-AllServices }
        default { Write-Err "无效选择" }
    }

    Write-Host ""
    Read-Host "按回车继续..."
}
