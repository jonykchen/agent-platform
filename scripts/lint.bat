@echo off
setlocal
REM ============================================================
REM  Agent Platform - Lint Check (Windows)
REM ============================================================

cd /d "%~dp0.."

echo.
echo === Code Quality Check ===
echo.

REM Python Lint
if exist "services\orchestrator-python" (
    echo [orchestrator-python]
    pushd services\orchestrator-python
    if exist "venv\Scripts\activate.bat" (
        call venv\Scripts\activate.bat
    )
    python -m ruff check . 2>nul
    if errorlevel 1 (
        pip install ruff && python -m ruff check .
    )
    popd
    echo.
)

if exist "services\model-gateway-python" (
    echo [model-gateway-python]
    pushd services\model-gateway-python
    python -m ruff check . 2>nul
    if errorlevel 1 (
        pip install ruff && python -m ruff check .
    )
    popd
    echo.
)

REM Proto Lint
where buf >nul 2>&1
if not errorlevel 1 (
    echo [proto]
    buf lint contracts\proto
    echo.
)

echo [OK] Lint check complete
echo.

endlocal