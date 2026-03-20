@echo off
REM ============================================================
REM  Agent Platform - Format Code (Windows)
REM ============================================================

echo.
echo === 格式化代码 ===
echo.

REM Python Format
if exist "services\orchestrator-python" (
    echo [orchestrator-python]
    cd services\orchestrator-python
    python -m ruff format . 2>nul || pip install ruff && python -m ruff format .
    cd ..\..
    echo.
)

if exist "services\model-gateway-python" (
    echo [model-gateway-python]
    cd services\model-gateway-python
    python -m ruff format . 2>nul || pip install ruff && python -m ruff format .
    cd ..\..
    echo.
)

if exist "services\knowledge-python" (
    echo [knowledge-python]
    cd services\knowledge-python
    python -m ruff format . 2>nul || pip install ruff && python -m ruff format .
    cd ..\..
    echo.
)

echo [OK] 格式化完成
