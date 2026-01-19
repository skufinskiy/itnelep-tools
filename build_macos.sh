#!/bin/bash
# Build script for macOS
# Usage: ./build_macos.sh

echo "========================================"
echo "  Building ITNELEP Tools.app for macOS"
echo "========================================"
echo ""

# Check Python
echo "[CHECK] Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found!"
    echo "Please install Python 3.8+ from https://www.python.org/"
    exit 1
fi

python3 --version
echo ""

# Check/Install PyInstaller
echo "[CHECK] PyInstaller..."
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip3 install pyinstaller
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install PyInstaller!"
        exit 1
    fi
fi
echo "OK: PyInstaller installed"
echo ""

# Clean previous builds
echo "[1/4] Cleaning previous builds..."
rm -rf build dist "ITNELEP Tools.app"
echo "OK: Cleaned"
echo ""

# Build .app
echo "[2/4] Building application..."
echo "This may take 5-10 minutes..."
echo ""

pyinstaller build_macos.spec --clean

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Build failed!"
    exit 1
fi

# Move .app to root
echo ""
echo "[3/4] Moving application..."
if [ -d "dist/ITNELEP Tools.app" ]; then
    mv "dist/ITNELEP Tools.app" "ITNELEP Tools.app"
    echo "OK: ITNELEP Tools.app created!"
else
    echo "ERROR: Application not found!"
    exit 1
fi

# Clean temporary files
echo ""
echo "[4/4] Cleaning temporary files..."
rm -rf build
echo "OK: Cleaned"
echo ""

# Get app size
APP_SIZE=$(du -sh "ITNELEP Tools.app" | cut -f1)

# Success
echo "========================================"
echo "  Build Complete!"
echo "========================================"
echo ""
echo "File: ITNELEP Tools.app"
echo "Size: $APP_SIZE"
echo ""
echo "You can now copy this app to any macOS computer!"
echo ""
echo "To run:"
echo "  Double-click 'ITNELEP Tools.app'"
echo ""
echo "Don't forget to include service_account.json!"
echo ""
