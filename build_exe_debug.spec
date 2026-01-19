# -*- mode: python ; coding: utf-8 -*-
# Debug version with console window

block_cipher = None

# Данные для включения в .exe
added_files = [
    ('config.json', '.'),
    ('service_account.json', '.'),
    ('credentials.json', '.'),
    ('tabs/*.py', 'tabs'),
    ('google_api.py', '.'),
    ('scraper.py', '.'),
    ('unified_app.py', '.'),
]

# Скрытые импорты (библиотеки, которые импортируются динамически)
hidden_imports = [
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'selenium',
    'selenium.webdriver',
    'selenium.webdriver.chrome.service',
    'selenium.webdriver.common.by',
    'selenium.webdriver.support.ui',
    'selenium.webdriver.support.expected_conditions',
    'webdriver_manager',
    'webdriver_manager.chrome',
    'playwright',
    'playwright.sync_api',
    'gspread',
    'google.oauth2.service_account',
    'google.auth',
    'oauth2client',
    'oauth2client.service_account',
    'requests',
    'pandas',
    'openai',
    'pymorphy2',
    'bs4',
    'lxml',
]

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ITNELEP_Tools_Debug',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # С консольным окном для отладки
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
