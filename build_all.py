#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Universal build script for ITNELEP Tools
Detects platform and builds appropriate executable
"""

import sys
import os
import platform
import subprocess
import shutil
from pathlib import Path

def detect_platform():
    """Определение платформы"""
    system = platform.system()
    if system == "Windows":
        return "windows"
    elif system == "Darwin":
        return "macos"
    elif system == "Linux":
        return "linux"
    else:
        return "unknown"

def clean_build():
    """Очистка предыдущих сборок"""
    print("\n[CLEAN] Removing previous builds...")
    
    dirs_to_remove = ["build", "dist"]
    files_to_remove = ["ITNELEP_Tools.exe", "ITNELEP Tools.app"]
    
    for d in dirs_to_remove:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"  ✓ Removed {d}/")
    
    for f in files_to_remove:
        if os.path.exists(f):
            if os.path.isdir(f):
                shutil.rmtree(f)
            else:
                os.remove(f)
            print(f"  ✓ Removed {f}")
    
    print("  ✓ Clean complete")

def check_pyinstaller():
    """Проверка установки PyInstaller"""
    try:
        import PyInstaller
        return True
    except ImportError:
        return False

def install_pyinstaller():
    """Установка PyInstaller"""
    print("\n[INSTALL] Installing PyInstaller...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        print("  ✓ PyInstaller installed")
        return True
    except subprocess.CalledProcessError:
        print("  ✗ Failed to install PyInstaller")
        return False

def build_windows():
    """Сборка для Windows"""
    print("\n" + "="*60)
    print("  Building for Windows (.exe)")
    print("="*60)
    
    spec_file = "build_exe.spec"
    
    if not os.path.exists(spec_file):
        print(f"  ✗ ERROR: {spec_file} not found!")
        return False
    
    print(f"\n[BUILD] Running PyInstaller with {spec_file}...")
    print("  This may take 5-10 minutes...\n")
    
    try:
        subprocess.run(["pyinstaller", spec_file, "--clean"], check=True)
        
        # Копирование .exe в корень
        exe_path = Path("dist/ITNELEP_Tools.exe")
        if exe_path.exists():
            shutil.copy(exe_path, "ITNELEP_Tools.exe")
            print("\n  ✓ ITNELEP_Tools.exe created successfully!")
            
            # Получение размера
            size = exe_path.stat().st_size / (1024 * 1024)
            print(f"  ✓ Size: {size:.1f} MB")
            
            # Очистка временных файлов
            print("\n[CLEAN] Removing temporary files...")
            shutil.rmtree("build")
            print("  ✓ Clean complete")
            
            return True
        else:
            print("\n  ✗ ERROR: ITNELEP_Tools.exe not found in dist/")
            return False
            
    except subprocess.CalledProcessError:
        print("\n  ✗ ERROR: Build failed!")
        return False

def build_macos():
    """Сборка для macOS"""
    print("\n" + "="*60)
    print("  Building for macOS (.app)")
    print("="*60)
    
    spec_file = "build_macos.spec"
    
    if not os.path.exists(spec_file):
        print(f"  ✗ ERROR: {spec_file} not found!")
        return False
    
    print(f"\n[BUILD] Running PyInstaller with {spec_file}...")
    print("  This may take 5-10 minutes...\n")
    
    try:
        subprocess.run(["pyinstaller", spec_file, "--clean"], check=True)
        
        # Перемещение .app в корень
        app_path = Path("dist/ITNELEP Tools.app")
        if app_path.exists():
            if os.path.exists("ITNELEP Tools.app"):
                shutil.rmtree("ITNELEP Tools.app")
            shutil.move(str(app_path), "ITNELEP Tools.app")
            print("\n  ✓ ITNELEP Tools.app created successfully!")
            
            # Получение размера
            total_size = 0
            for dirpath, dirnames, filenames in os.walk("ITNELEP Tools.app"):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    total_size += os.path.getsize(fp)
            size = total_size / (1024 * 1024)
            print(f"  ✓ Size: {size:.1f} MB")
            
            # Очистка временных файлов
            print("\n[CLEAN] Removing temporary files...")
            shutil.rmtree("build")
            print("  ✓ Clean complete")
            
            return True
        else:
            print("\n  ✗ ERROR: ITNELEP Tools.app not found in dist/")
            return False
            
    except subprocess.CalledProcessError:
        print("\n  ✗ ERROR: Build failed!")
        return False

def show_other_platform_instructions(current_platform):
    """Показать инструкции для другой платформы"""
    print("\n" + "="*60)
    print("  Multi-Platform Build Instructions")
    print("="*60)
    
    if current_platform == "windows":
        print("\n📱 To build for macOS (.app):")
        print("  1. Copy this project to a Mac")
        print("  2. Run: python3 build_all.py")
        print("  3. Or run: ./build_macos.sh")
        print("\n  Note: macOS .app can ONLY be built on Mac")
        
    elif current_platform == "macos":
        print("\n💻 To build for Windows (.exe):")
        print("  1. Copy this project to a Windows PC")
        print("  2. Run: python build_all.py")
        print("  3. Or run: build_exe.bat")
        print("\n  Note: Windows .exe can ONLY be built on Windows")
    
    print("\n⚠️  PyInstaller does NOT support cross-compilation!")
    print("   You need to build on each platform separately.")

def main():
    """Главная функция"""
    print("="*60)
    print("  ITNELEP Tools - Universal Build Script")
    print("="*60)
    
    # Определение платформы
    current_platform = detect_platform()
    print(f"\n[DETECT] Platform: {current_platform}")
    
    if current_platform == "unknown":
        print("  ✗ ERROR: Unknown platform!")
        print("  Supported platforms: Windows, macOS, Linux")
        return 1
    
    if current_platform == "linux":
        print("\n⚠️  Linux detected!")
        print("  For Linux, use the Python version directly:")
        print("    python3 start.py")
        print("\n  Or create a .deb/.rpm package using fpm or similar tools")
        return 0
    
    # Проверка Python версии
    print(f"[CHECK] Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    if sys.version_info < (3, 8):
        print("  ✗ ERROR: Python 3.8 or higher required!")
        return 1
    print("  ✓ Python version OK")
    
    # Проверка PyInstaller
    print("\n[CHECK] PyInstaller...")
    if not check_pyinstaller():
        print("  PyInstaller not found")
        if not install_pyinstaller():
            return 1
    else:
        print("  ✓ PyInstaller installed")
    
    # Очистка
    clean_build()
    
    # Сборка для текущей платформы
    success = False
    if current_platform == "windows":
        success = build_windows()
    elif current_platform == "macos":
        success = build_macos()
    
    if success:
        print("\n" + "="*60)
        print("  ✅ BUILD SUCCESSFUL!")
        print("="*60)
        
        if current_platform == "windows":
            print("\n  📦 Output: ITNELEP_Tools.exe")
            print("  📄 Don't forget: service_account.json")
        elif current_platform == "macos":
            print("\n  📦 Output: ITNELEP Tools.app")
            print("  📄 Don't forget: service_account.json")
        
        # Инструкции для другой платформы
        show_other_platform_instructions(current_platform)
        
        print("\n" + "="*60)
        print("  Ready to distribute!")
        print("="*60)
        print()
        
        return 0
    else:
        print("\n" + "="*60)
        print("  ✗ BUILD FAILED!")
        print("="*60)
        print("\n  Check the error messages above")
        print()
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Build cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
