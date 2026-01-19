# PowerShell script for building .exe
# Usage: .\build_exe.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Building ITNELEP Tools .exe" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "[CHECK] Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "OK: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python not found!" -ForegroundColor Red
    Write-Host "Please install Python 3.8+ from https://www.python.org/" -ForegroundColor Red
    pause
    exit 1
}

# Check/Install PyInstaller
Write-Host ""
Write-Host "[CHECK] PyInstaller..." -ForegroundColor Yellow
try {
    python -c "import PyInstaller" 2>$null
    Write-Host "OK: PyInstaller already installed" -ForegroundColor Green
} catch {
    Write-Host "Installing PyInstaller..." -ForegroundColor Yellow
    pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install PyInstaller!" -ForegroundColor Red
        pause
        exit 1
    }
    Write-Host "OK: PyInstaller installed" -ForegroundColor Green
}

# Clean previous builds
Write-Host ""
Write-Host "[1/4] Cleaning previous builds..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "ITNELEP_Tools.exe") { Remove-Item -Force "ITNELEP_Tools.exe" }
Write-Host "OK: Cleaned" -ForegroundColor Green

# Build .exe
Write-Host ""
Write-Host "[2/4] Building executable..." -ForegroundColor Yellow
Write-Host "This may take 5-10 minutes..." -ForegroundColor Gray
Write-Host ""

pyinstaller build_exe.spec --clean

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Build failed!" -ForegroundColor Red
    pause
    exit 1
}

# Copy .exe to root
Write-Host ""
Write-Host "[3/4] Copying executable..." -ForegroundColor Yellow
if (Test-Path "dist\ITNELEP_Tools.exe") {
    Copy-Item "dist\ITNELEP_Tools.exe" "ITNELEP_Tools.exe"
    Write-Host "OK: ITNELEP_Tools.exe created!" -ForegroundColor Green
} else {
    Write-Host "ERROR: Executable not found!" -ForegroundColor Red
    pause
    exit 1
}

# Clean temporary files
Write-Host ""
Write-Host "[4/4] Cleaning temporary files..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
Write-Host "OK: Cleaned" -ForegroundColor Green

# Get file size
$fileSize = (Get-Item "ITNELEP_Tools.exe").Length / 1MB

# Success
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Build Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "File: ITNELEP_Tools.exe" -ForegroundColor White
Write-Host ("Size: {0:N2} MB" -f $fileSize) -ForegroundColor White
Write-Host ""
Write-Host "You can now copy this file to any Windows PC!" -ForegroundColor Cyan
Write-Host ""
Write-Host "Don't forget to include service_account.json!" -ForegroundColor Yellow
Write-Host ""
pause
