@echo off
REM ============================================================
REM  Agent Platform - Windows Setup Script
REM  支持: Windows 10/11 (CMD / PowerShell)
REM ============================================================

setlocal enabledelayedexpansion

echo.
echo === Agent Platform - Windows Setup ===
echo.

REM 颜色定义（Windows 不支持 ANSI 颜色，使用简单文本）
set "GREEN=[OK]"
set "YELLOW=[!]"
set "RED=[X]"

REM ============================================================
REM  检查必需工具
REM ============================================================
echo === 检查必需工具 ===
echo.

REM Git
where git >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('git --version') do echo %GREEN% Git: %%i
) else (
    echo %RED% 未安装 Git
    echo   下载: https://git-scm.com/download/win
    exit /b 1
)

REM Python
where python >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo %GREEN% %%i
) else (
    where python3 >nul 2>&1
    if %errorlevel% equ 0 (
        for /f "tokens=*" %%i in ('python3 --version 2^>^&1') do echo %GREEN% %%i
    ) else (
        echo %RED% 未安装 Python
        echo   下载: https://www.python.org/downloads/
        exit /b 1
    )
)

REM Java
where java >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=3" %%i in ('java -version 2^>^&1 ^| findstr /i "version"') do echo %GREEN% Java: %%i
) else (
    echo %YELLOW% 未安装 Java (仅 Agent 编排不需要)
)

REM Docker
where docker >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('docker --version') do echo %GREEN% %%i
) else (
    echo %YELLOW% 未安装 Docker
    echo   下载: https://www.docker.com/products/docker-desktop
)

REM Make (Windows 通常没有)
where make >nul 2>&1
if %errorlevel% equ 0 (
    echo %GREEN% Make: 已安装
) else (
    echo %YELLOW% 未安装 Make (可选)
    echo   替代方案: 直接运行 scripts/ 目录下的脚本
)

echo.
echo === Python 工具 ===
echo.

REM pip
where pip >nul 2>&1
if %errorlevel% equ 0 (
    echo %GREEN% pip: 已安装
) else (
    where pip3 >nul 2>&1
    if %errorlevel% equ 0 (
        echo %GREEN% pip3: 已安装
    ) else (
        echo %YELLOW% 未安装 pip
    )
)

REM ruff
where ruff >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('ruff --version') do echo %GREEN% ruff: %%i
) else (
    echo %YELLOW% 未安装 ruff
    echo   安装: pip install ruff
)

REM pytest
where pytest >nul 2>&1
if %errorlevel% equ 0 (
    echo %GREEN% pytest: 已安装
) else (
    echo %YELLOW% 未安装 pytest
    echo   安装: pip install pytest
)

echo.
echo === Proto 工具 ===
echo.

REM buf
where buf >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('buf --version') do echo %GREEN% buf: %%i
) else (
    echo %YELLOW% 未安装 buf
    echo   下载: https://github.com/bufbuild/buf/releases
    echo   或使用: scoop install buf
)

echo.
echo === Claude Code 配置 ===
echo.

if exist "CLAUDE.md" (
    echo %GREEN% CLAUDE.md 存在
) else (
    echo %RED% CLAUDE.md 不存在
)

if exist ".claude" (
    echo %GREEN% .claude\ 目录存在
) else (
    echo %YELLOW% .claude\ 目录不存在
)

if exist ".claude\settings.json" (
    REM 验证 JSON (使用 Python)
    python -m json.tool .claude\settings.json >nul 2>&1
    if !errorlevel! equ 0 (
        echo %GREEN% settings.json 格式正确
    ) else (
        echo %RED% settings.json 格式错误
    )
) else (
    echo %RED% settings.json 不存在
)

echo.
echo === 设置检查完成 ===
echo.
echo 下一步:
echo   1. 启动开发环境: scripts\dev.bat
echo   2. 运行测试: scripts\test.bat
echo   3. 开始开发!
echo.

endlocal
