@echo off
setlocal
REM ============================================================
REM  Agent Platform - Start Development Environment (Windows)
REM ============================================================

cd /d "%~dp0.."

echo.
echo === Start Development Environment ===
echo.

REM Check Docker
where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker not installed
    echo Please install Docker Desktop: https://www.docker.com/products/docker-desktop
    exit /b 1
)

REM Check Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running
    echo Please start Docker Desktop first
    exit /b 1
)

echo [OK] Docker is running
echo.

REM Start services
echo Starting infrastructure services...
docker compose -f infra\docker-compose.yml up -d

if errorlevel 1 (
    echo [ERROR] Failed to start services
    exit /b 1
)

echo.
echo [OK] Services started
echo.
echo === Service Status ===
docker compose -f infra\docker-compose.yml ps

echo.
echo === Available Services ===
echo PostgreSQL:  localhost:5432  ^(user: app_user, db: agent_platform^)
echo Redis:       localhost:6379
echo MinIO:       http://localhost:9000 ^(user: minioadmin, pass: minioadmin123^)
echo Grafana:     http://localhost:3000 ^(user: admin, pass: admin^)
echo.

echo Development environment is ready!
echo.

endlocal