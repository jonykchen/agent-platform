@echo off
setlocal enabledelayedexpansion

REM Switch to project root
cd /d "%~dp0.."

echo.
echo === Agent Platform - Windows Setup ===
echo Current directory: %CD%
echo.

set "GREEN=[OK]"
set "YELLOW=[*]"
set "RED=[X]"

echo === Checking Required Tools ===
echo.

REM Git
where git >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%i in ('git --version') do echo !GREEN! Git: %%i
) else (
    echo !RED! Git not installed
    echo   Download: https://git-scm.com/download/win
    exit /b 1
)

REM Python (priority: python > python3 > py)
set "PYTHON_CMD="

where python >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
) else (
    where python3 >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=python3"
    ) else (
        where py >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_CMD=py"
        )
    )
)

if defined PYTHON_CMD (
    for /f "tokens=*" %%i in ('!PYTHON_CMD! --version 2^>^&1') do echo !GREEN! %%i ^(command: !PYTHON_CMD!^)
) else (
    echo !RED! Python not installed
    echo   Download: https://www.python.org/downloads/
    echo   Note: Check "Add Python to PATH" during installation
    exit /b 1
)

REM Java
where java >nul 2>&1
if not errorlevel 1 (
    set "JAVA_VER="
    for /f "tokens=3" %%i in ('java -version 2^>^&1 ^| findstr /i "version"') do (
        if not defined JAVA_VER set "JAVA_VER=%%i"
    )
    if defined JAVA_VER (
        echo !GREEN! Java: !JAVA_VER!
    ) else (
        echo !GREEN! Java: installed ^(version parse failed^)
    )
) else (
    echo !YELLOW! Java not installed ^(only needed for Agent orchestration^)
)

REM Docker
where docker >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%i in ('docker --version') do echo !GREEN! %%i
) else (
    echo !YELLOW! Docker not installed
    echo   Download: https://www.docker.com/products/docker-desktop
)

REM Make
where make >nul 2>&1
if not errorlevel 1 (
    echo !GREEN! Make: installed
) else (
    echo !YELLOW! Make not installed ^(optional^)
    echo   Alternative: run scripts directly from scripts/ directory
)

echo.
echo === Python Tools ===
echo.

REM pip
if defined PYTHON_CMD (
    !PYTHON_CMD! -m pip --version >nul 2>&1
    if not errorlevel 1 (
        echo !GREEN! pip: installed
    ) else (
        echo !YELLOW! pip not installed
        echo   Install: !PYTHON_CMD! -m ensurepip
    )
) else (
    echo !YELLOW! pip not installed
)

REM ruff
where ruff >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%i in ('ruff --version') do echo !GREEN! ruff: %%i
) else (
    echo !YELLOW! ruff not installed
    echo   Install: pip install ruff
)

REM pytest
where pytest >nul 2>&1
if not errorlevel 1 (
    echo !GREEN! pytest: installed
) else (
    echo !YELLOW! pytest not installed
    echo   Install: pip install pytest
)

echo.
echo === Proto Tools ===
echo.

REM buf
where buf >nul 2>&1
if not errorlevel 1 (
    for /f "tokens=*" %%i in ('buf --version') do echo !GREEN! buf: %%i
) else (
    echo !YELLOW! buf not installed
    echo   Download: https://github.com/bufbuild/buf/releases
    echo   Or use: scoop install buf
)

echo.
echo === Claude Code Config ===
echo.

if exist "CLAUDE.md" (
    echo !GREEN! CLAUDE.md exists
) else (
    echo !RED! CLAUDE.md not found
)

if exist ".claude" (
    echo !GREEN! .claude\ directory exists
) else (
    echo !YELLOW! .claude\ directory not found
)

if exist ".claude\settings.json" (
    if defined PYTHON_CMD (
        !PYTHON_CMD! -m json.tool ".claude\settings.json" >nul 2>&1
        if not errorlevel 1 (
            echo !GREEN! settings.json format OK
        ) else (
            echo !RED! settings.json format error
        )
    ) else (
        echo !GREEN! settings.json exists ^(no Python, skip validation^)
    )
) else (
    echo !RED! settings.json not found
)

echo.
echo === Setup Check Complete ===
echo.
echo Next steps:
echo   1. Start dev environment: scripts\dev.bat
echo   2. Run tests: scripts\test.bat
echo   3. Start coding!
echo.

endlocal