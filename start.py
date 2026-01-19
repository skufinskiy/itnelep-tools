#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launcher for Unified ITNELEP Tools
This file can be used to start the application without .bat files
"""

import sys
import os
import subprocess

def check_dependencies():
    """Check if all required packages are installed"""
    required = [
        'PyQt5',
        'selenium',
        'playwright',
        'gspread',
        'requests',
        'pandas',
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package.lower().replace('-', '_'))
        except ImportError:
            missing.append(package)
    
    return missing

def main():
    print("=" * 60)
    print("  Unified ITNELEP Tools - Launcher")
    print("=" * 60)
    print()
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("ERROR: Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    print(f"✓ Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Check dependencies
    print("\nChecking dependencies...")
    missing = check_dependencies()
    
    if missing:
        print(f"\n⚠ WARNING: Missing dependencies: {', '.join(missing)}")
        print("\nTo install dependencies, run:")
        print("  pip install -r requirements.txt")
        print("  playwright install chromium")
        print()
        
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)
    else:
        print("✓ All dependencies installed")
    
    # Check if required files exist
    required_files = [
        'unified_app.py',
        'google_api.py',
        'scraper.py',
        'config.json',
    ]
    
    print("\nChecking required files...")
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print(f"\n❌ ERROR: Missing files: {', '.join(missing_files)}")
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    print("✓ All required files present")
    
    # Start the application
    print("\n" + "=" * 60)
    print("  Starting application...")
    print("=" * 60)
    print()
    
    try:
        # Import and run
        import unified_app
        unified_app.main()
    except KeyboardInterrupt:
        print("\n\nApplication stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ ERROR: {str(e)}")
        print("\nFull error:")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()
