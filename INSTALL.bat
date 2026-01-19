@echo off
REM Set UTF-8 encoding
chcp 65001 >nul 2>&1

cls
echo ========================================
echo   Installation of Dependencies
echo   Unified ITNELEP Tools
echo ========================================
echo.

echo [1/3] Installing Python packages...
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install packages
    echo Make sure Python and pip are installed
    pause
    exit /b 1
)

echo.
echo [2/3] Installing Playwright browsers...
playwright install chromium

if errorlevel 1 (
    echo.
    echo WARNING: Failed to install Playwright browsers
    echo Some features may not work
    echo.
)

echo.
echo [3/3] Checking installation...
python -c "import PyQt5; print('OK: PyQt5 installed')"
python -c "import selenium; print('OK: Selenium installed')"
python -c "import playwright; print('OK: Playwright installed')"
python -c "import gspread; print('OK: Google Sheets API installed')"

echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo To start the application use START.bat
echo or command: python unified_app.py
echo.
pause
