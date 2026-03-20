@echo off
REM ============================================================
REM  Agent Platform - Start Development Environment (Windows)
REM ============================================================

echo.
echo === 启动开发环境 ===
echo.

REM 检查 Docker
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未安装 Docker
    echo 请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop
    exit /b 1
)

REM 检查 Docker 是否运行
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker 未运行
    echo 请先启动 Docker Desktop
    exit /b 1
)

echo [OK] Docker 运行中
echo.

REM 启动服务
echo 正在启动基础设施服务...
docker compose -f infra\docker-compose.yml up -d

if %errorlevel% neq 0 (
    echo [ERROR] 启动失败
    exit /b 1
)

echo.
echo [OK] 服务已启动
echo.
echo === 服务状态 ===
docker compose -f infra\docker-compose.yml ps

echo.
echo === 可用服务 ===
echo PostgreSQL:  localhost:5432  (user: app_user, db: agent_platform)
echo Redis:       localhost:6379
echo MinIO:       http://localhost:9000 (user: minioadmin, pass: minioadmin123)
echo Grafana:     http://localhost:3000 (user: admin, pass: admin)
echo.

echo 开发环境已就绪!
echo.
