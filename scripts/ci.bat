@echo off
setlocal
REM ============================================================
REM  Agent Platform - Full CI Check (Windows)
REM ============================================================

echo.
echo ============================================================
echo  Agent Platform - CI Pipeline
echo ============================================================
echo.

set FAILED=0

REM 1. Lint
echo [1/3] Code quality check...
call scripts\lint.bat
if errorlevel 1 set FAILED=1

REM 2. Test
echo.
echo [2/3] Running tests...
call scripts\test.bat
if errorlevel 1 set FAILED=1

REM 3. Security Scan (optional)
echo.
echo [3/3] Security scan...
where trivy >nul 2>&1
if not errorlevel 1 (
    trivy fs --severity HIGH,CRITICAL .
) else (
    echo [SKIP] trivy not installed
)

echo.
echo ============================================================
if %FAILED% equ 0 (
    echo [SUCCESS] All CI checks passed
) else (
    echo [FAILED] CI checks failed
)
echo ============================================================
echo.

endlocal
exit /b %FAILED%