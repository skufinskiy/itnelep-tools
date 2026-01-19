@echo off
REM Quick test of the built .exe

echo ========================================
echo   Testing ITNELEP_Tools.exe
echo ========================================
echo.

if not exist "ITNELEP_Tools.exe" (
    echo ERROR: ITNELEP_Tools.exe not found!
    echo.
    echo Please build it first:
    echo   build_exe.bat
    echo.
    pause
    exit /b 1
)

if not exist "service_account.json" (
    echo WARNING: service_account.json not found!
    echo Google Sheets features will not work.
    echo.
)

echo Starting ITNELEP_Tools.exe...
echo.

start "" "ITNELEP_Tools.exe"

echo.
echo If the program starts successfully, the build is OK!
echo.
pause
