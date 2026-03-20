@echo off
REM ============================================================
REM  Agent Platform - Run Tests (Windows)
REM ============================================================

echo.
echo === 运行测试 ===
echo.

REM 检查 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未安装 Python
    exit /b 1
)

REM 检查 pytest
where pytest >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] 安装 pytest...
    pip install pytest pytest-cov
)

echo === Python 测试 ===
echo.

if exist "services\orchestrator-python" (
    echo [orchestrator-python]
    cd services\orchestrator-python
    python -m pytest tests\ -v --tb=short
    cd ..\..
)

if exist "services\model-gateway-python" (
    echo [model-gateway-python]
    cd services\model-gateway-python
    python -m pytest tests\ -v --tb=short
    cd ..\..
)

if exist "services\knowledge-python" (
    echo [knowledge-python]
    cd services\knowledge-python
    python -m pytest tests\ -v --tb=short
    cd ..\..
)

echo.
echo [OK] 测试完成
echo.
