@echo off
REM Set UTF-8 encoding
chcp 65001 >nul 2>&1

cls
echo ========================================
echo   Unified ITNELEP Tools
echo ========================================
echo.
echo Starting application...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo.
    echo Please install Python 3.8 or higher
    echo Download from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Run the application
python unified_app.py

if errorlevel 1 (
    echo.
    echo ERROR: Failed to start application
    echo.
    echo Possible reasons:
    echo 1. Dependencies not installed - run INSTALL.bat
    echo 2. Missing configuration files
    echo 3. Python version is too old - need 3.8+
    echo.
    pause
)
