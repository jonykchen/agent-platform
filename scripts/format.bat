@echo off
setlocal
REM ============================================================
REM  Agent Platform - Format Code (Windows)
REM ============================================================

cd /d "%~dp0.."

echo.
echo === Format Code ===
echo.

REM Python Format
if exist "services\orchestrator-python" (
    echo [orchestrator-python]
    pushd services\orchestrator-python
    python -m ruff format . 2>nul
    if errorlevel 1 (
        pip install ruff && python -m ruff format .
    )
    popd
    echo.
)

if exist "services\model-gateway-python" (
    echo [model-gateway-python]
    pushd services\model-gateway-python
    python -m ruff format . 2>nul
    if errorlevel 1 (
        pip install ruff && python -m ruff format .
    )
    popd
    echo.
)

if exist "services\knowledge-python" (
    echo [knowledge-python]
    pushd services\knowledge-python
    python -m ruff format . 2>nul
    if errorlevel 1 (
        pip install ruff && python -m ruff format .
    )
    popd
    echo.
)

echo [OK] Format complete
echo.

endlocal