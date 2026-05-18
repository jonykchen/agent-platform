# ============================================================
# install-python.ps1
# Windows Python 3.12 Auto Installation Script (User-level, no admin required)
# ============================================================
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File install-python.ps1
#   powershell -ExecutionPolicy Bypass -File install-python.ps1 -Version 3.11.9
#
# ============================================================

param(
    [string]$Version = "3.12.10"
)

$ErrorActionPreference = "Stop"

function Main {
    $url = "https://www.python.org/ftp/python/$Version/python-$Version-amd64.exe"
    $outFile = Join-Path $env:TEMP "python-$Version-amd64.exe"
    $targetDir = Join-Path $env:LOCALAPPDATA "Programs\Python\Python$Version"

    Write-Host ""
    Write-Host "========================================"
    Write-Host "  Python $Version Installation Script"
    Write-Host "========================================"
    Write-Host ""

    # Check existing
    Write-Host "Checking existing Python installations..." -ForegroundColor Cyan
    $existingPythons = Get-ChildItem -Path "$env:LOCALAPPDATA\Programs\Python\Python*" -ErrorAction SilentlyContinue
    foreach ($py in $existingPythons) {
        $exe = Join-Path $py.FullName "python.exe"
        if (Test-Path $exe) {
            $ver = & $exe --version 2>&1
            Write-Host "Found: $($py.FullName) - $ver" -ForegroundColor Yellow
        }
    }

    # Check Windows Store stub
    $storeStub = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\python.exe"
    if (Test-Path $storeStub) {
        Write-Host "Found Windows Store stub: $storeStub" -ForegroundColor Yellow
        Write-Host "Recommend removing this stub to avoid conflicts" -ForegroundColor Yellow
    }

    Write-Host ""

    # Download
    Write-Host "Downloading Python $Version..." -ForegroundColor Cyan
    Write-Host "URL: $url" -ForegroundColor Gray

    try {
        $client = New-Object System.Net.WebClient
        $client.DownloadFile($url, $outFile)
        $sizeMB = [math]::Round((Get-Item $outFile).Length / 1MB, 2)
        Write-Host "Download complete: $outFile ($sizeMB MB)" -ForegroundColor Green
    }
    catch {
        Write-Host "Download failed: $_" -ForegroundColor Red
        Write-Host "Please download manually from: https://www.python.org/downloads/" -ForegroundColor Yellow
        exit 1
    }

    # Install
    Write-Host "Installing Python $Version..." -ForegroundColor Cyan
    Write-Host "Target directory: $targetDir" -ForegroundColor Gray

    $installArgs = @(
        "/quiet",
        "InstallAllUsers=0",
        "PrependPath=1",
        "Include_pip=1",
        "Include_test=0",
        "Include_doc=0",
        "Include_dev=0",
        "Include_launcher=1",
        "TargetDir=$targetDir"
    )

    try {
        $proc = Start-Process -FilePath $outFile -ArgumentList $installArgs -Wait -PassThru

        if ($proc.ExitCode -ne 0) {
            Write-Host "Installation failed with exit code: $($proc.ExitCode)" -ForegroundColor Red
            exit 1
        }

        Write-Host "Installation complete" -ForegroundColor Green
    }
    catch {
        Write-Host "Installation failed: $_" -ForegroundColor Red
        exit 1
    }

    # Cleanup
    if (Test-Path $outFile) {
        Remove-Item $outFile -Force
        Write-Host "Cleaned up installer" -ForegroundColor Gray
    }

    # Verify
    Write-Host "Verifying installation..." -ForegroundColor Cyan

    # Refresh PATH for current session
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")

    $pythonExe = Join-Path $targetDir "python.exe"
    $pipExe = Join-Path $targetDir "Scripts\pip.exe"

    if (-not (Test-Path $pythonExe)) {
        Write-Host "ERROR: python.exe not found at $pythonExe" -ForegroundColor Red
        exit 1
    }

    $pyVersion = & $pythonExe --version 2>&1
    Write-Host "Python version: $pyVersion" -ForegroundColor Green

    if (Test-Path $pipExe) {
        $pipVersion = & $pipExe --version 2>&1
        Write-Host "pip version: $pipVersion" -ForegroundColor Green
    }

    Write-Host "Install path: $targetDir" -ForegroundColor Green

    Write-Host ""
    Write-Host "========================================" -ForegroundColor White
    Write-Host "  Installation SUCCESSFUL!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor White
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Close and reopen terminal (refresh PATH)" -ForegroundColor Yellow
    Write-Host "  2. Run: python --version" -ForegroundColor Yellow
    Write-Host "  3. Install project dependencies: pip install -r requirements.txt" -ForegroundColor Yellow
    Write-Host ""

    # Add to PATH permanently if not already there
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $pythonPath = $targetDir
    $scriptsPath = Join-Path $targetDir "Scripts"

    if ($userPath -notlike "*$pythonPath*") {
        $newPath = "$pythonPath;$scriptsPath;$userPath"
        [System.Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        Write-Host "Added Python to user PATH" -ForegroundColor Green
    }
}

# Run
Main
