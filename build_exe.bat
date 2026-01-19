@echo off
REM Скрипт для создания .exe файла
REM Использование: build_exe.bat

echo ========================================
echo   Building ITNELEP Tools .exe
echo ========================================
echo.

REM Проверка PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Очистка предыдущих сборок
echo.
echo [1/4] Cleaning previous builds...
if exist "build\" rmdir /s /q "build\"
if exist "dist\" rmdir /s /q "dist\"
if exist "ITNELEP_Tools.exe" del /q "ITNELEP_Tools.exe"

REM Сборка .exe
echo.
echo [2/4] Building executable...
echo This may take several minutes...
pyinstaller build_exe.spec

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

REM Копирование .exe в корень
echo.
echo [3/4] Copying executable...
if exist "dist\ITNELEP_Tools.exe" (
    copy "dist\ITNELEP_Tools.exe" "ITNELEP_Tools.exe"
    echo OK: ITNELEP_Tools.exe created!
) else (
    echo ERROR: Executable not found!
    pause
    exit /b 1
)

REM Очистка временных файлов
echo.
echo [4/4] Cleaning temporary files...
rmdir /s /q "build\"

echo.
echo ========================================
echo   Build Complete!
echo ========================================
echo.
echo File: ITNELEP_Tools.exe
echo Size: 
dir ITNELEP_Tools.exe | findstr "ITNELEP_Tools.exe"
echo.
echo You can now copy this file to any Windows PC!
echo.
pause
