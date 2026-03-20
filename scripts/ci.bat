@echo off
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
echo [1/3] 代码质量检查...
call scripts\lint.bat
if %errorlevel% neq 0 set FAILED=1

REM 2. Test
echo.
echo [2/3] 运行测试...
call scripts\test.bat
if %errorlevel% neq 0 set FAILED=1

REM 3. Security Scan (optional)
echo.
echo [3/3] 安全扫描...
where trivy >nul 2>&1
if %errorlevel% equ 0 (
    trivy fs --severity HIGH,CRITICAL .
) else (
    echo [SKIP] trivy 未安装
)

echo.
echo ============================================================
if %FAILED% equ 0 (
    echo [SUCCESS] CI 检查全部通过
) else (
    echo [FAILED] CI 检查失败
)
echo ============================================================
echo.

exit /b %FAILED%
