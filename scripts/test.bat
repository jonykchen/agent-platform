@echo off
setlocal
REM ============================================================
REM  Agent Platform - Run Tests (Windows)
REM ============================================================

cd /d "%~dp0.."

echo.
echo === Run Tests ===
echo.

REM Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not installed
    exit /b 1
)

REM Check pytest
where pytest >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing pytest...
    pip install pytest pytest-cov
    if errorlevel 1 (
        echo [ERROR] Failed to install pytest
        exit /b 1
    )
)

echo === Python Tests ===
echo.

if exist "services\orchestrator-python" (
    echo [orchestrator-python]
    pushd services\orchestrator-python
    python -m pytest tests\ -v --tb=short
    popd
)

if exist "services\model-gateway-python" (
    echo [model-gateway-python]
    pushd services\model-gateway-python
    python -m pytest tests\ -v --tb=short
    popd
)

if exist "services\knowledge-python" (
    echo [knowledge-python]
    pushd services\knowledge-python
    python -m pytest tests\ -v --tb=short
    popd
)

echo.
echo [OK] Tests complete
echo.

endlocal