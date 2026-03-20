@echo off
REM ============================================================
REM  Agent Platform - Lint Check (Windows)
REM ============================================================

echo.
echo === 代码质量检查 ===
echo.

REM Python Lint
if exist "services\orchestrator-python" (
    echo [orchestrator-python]
    cd services\orchestrator-python
    if exist "venv\Scripts\activate.bat" (
        call venv\Scripts\activate.bat
    )
    python -m ruff check . 2>nul || pip install ruff && python -m ruff check .
    cd ..\..
    echo.
)

if exist "services\model-gateway-python" (
    echo [model-gateway-python]
    cd services\model-gateway-python
    python -m ruff check . 2>nul || pip install ruff && python -m ruff check .
    cd ..\..
    echo.
)

REM Proto Lint
where buf >nul 2>&1
if %errorlevel% equ 0 (
    echo [proto]
    buf lint contracts\proto
    echo.
)

echo [OK] Lint 检查完成
