@echo off
setlocal
REM ============================================================
REM  Agent Platform - Stop Development Environment (Windows)
REM ============================================================

cd /d "%~dp0.."

echo.
echo === Stop Development Environment ===
echo.

docker compose -f infra\docker-compose.yml down

echo.
echo [OK] Services stopped
echo.

endlocal