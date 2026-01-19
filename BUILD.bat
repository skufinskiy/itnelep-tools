@echo off
REM Universal build script - automatically detects platform
REM Builds .exe on Windows, .app on macOS

echo ========================================
echo   ITNELEP Tools - Universal Builder
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not installed or not in PATH
    echo.
    echo Please install Python 3.8+ from https://www.python.org/
    echo.
    pause
    exit /b 1
)

REM Run universal build script
python build_all.py

if errorlevel 1 (
    echo.
    pause
    exit /b 1
)

echo.
pause
