@echo off
REM ============================================================
REM  Agent Platform - Stop Development Environment (Windows)
REM ============================================================

echo.
echo === 停止开发环境 ===
echo.

docker compose -f infra\docker-compose.yml down

echo.
echo [OK] 服务已停止
echo.
