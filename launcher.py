#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ITNELEP Tools - Launcher with auto-setup
Автоматически устанавливает необходимые компоненты при первом запуске
"""

import sys
import os
import subprocess
from pathlib import Path

def get_app_data_dir():
    """Получение директории для данных приложения"""
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA', '')
        if appdata:
            return Path(appdata) / 'ITNELEP_Tools'
    return Path.home() / '.itnelep_tools'

def is_first_run():
    """Проверка первого запуска"""
    app_dir = get_app_data_dir()
    flag_file = app_dir / '.initialized'
    return not flag_file.exists()

def mark_initialized():
    """Отметка об успешной инициализации"""
    app_dir = get_app_data_dir()
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / '.initialized').touch()

def check_playwright_browsers():
    """Проверка наличия браузеров Playwright"""
    try:
        from playwright.sync_api import sync_playwright
        
        # Попытка запустить браузер
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                browser.close()
                return True
            except Exception:
                return False
    except Exception:
        return False

def install_playwright_browsers():
    """Установка браузеров Playwright"""
    try:
        # Попытка импортировать PyQt5 для GUI диалога
        from PyQt5.QtWidgets import QApplication, QMessageBox
        import sys as sys_module
        
        # Создание приложения если его нет
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys_module.argv)
        
        # Показываем диалог
        reply = QMessageBox.question(
            None,
            "First Run Setup",
            "Playwright browsers are not installed.\n\n"
            "They are required for some features (Renamer, Greeting, Obrezka tabs).\n"
            "Download size: ~300MB\n\n"
            "Install now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply != QMessageBox.Yes:
            return False
        
        # Показываем прогресс
        msg = QMessageBox()
        msg.setWindowTitle("Installing Browsers")
        msg.setText("Installing Playwright browsers...\nThis may take a few minutes.")
        msg.setStandardButtons(QMessageBox.NoButton)
        msg.show()
        QApplication.processEvents()
        
    except ImportError:
        # PyQt5 недоступен - устанавливаем автоматически без запроса
        print("Installing Playwright browsers automatically...")
    
    try:
        # Установка через playwright CLI
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True
        )
        
        try:
            msg.accept()  # Закрываем диалог прогресса
            QMessageBox.information(
                None,
                "Success",
                "Playwright browsers installed successfully!"
            )
        except:
            print("✓ Playwright browsers installed successfully!")
        
        return True
    except subprocess.CalledProcessError:
        try:
            msg.accept()
            QMessageBox.warning(
                None,
                "Warning",
                "Could not install Playwright browsers.\n"
                "Some features may not work.\n\n"
                "You can install manually later:\n"
                "playwright install chromium"
            )
        except:
            print("⚠ Warning: Could not install Playwright browsers")
            print("Some features (Renamer, Greeting, Obrezka) may not work")
        
        return False

def setup_first_run():
    """Настройка при первом запуске"""
    try:
        from PyQt5.QtWidgets import QApplication
        import sys as sys_module
        
        # Создание приложения если его нет
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys_module.argv)
    except:
        pass
    
    # Проверка браузеров Playwright
    if not check_playwright_browsers():
        install_playwright_browsers()
    
    # Отметка об инициализации
    mark_initialized()

def main():
    """Главная функция"""
    # Проверка первого запуска
    if is_first_run():
        setup_first_run()
    
    # Запуск основного приложения
    try:
        import unified_app
        unified_app.main()
    except Exception as e:
        try:
            # Попытка показать ошибку через GUI
            from PyQt5.QtWidgets import QApplication, QMessageBox
            import sys as sys_module
            import traceback
            
            app = QApplication.instance()
            if app is None:
                app = QApplication(sys_module.argv)
            
            error_msg = f"Failed to start application:\n\n{str(e)}\n\nFull traceback:\n{traceback.format_exc()}"
            
            QMessageBox.critical(
                None,
                "Error - ITNELEP Tools",
                error_msg
            )
        except:
            # Если GUI недоступен, пишем в файл
            import traceback
            error_file = Path.home() / "itnelep_error.log"
            with open(error_file, 'w') as f:
                f.write(f"Error starting ITNELEP Tools:\n\n")
                f.write(f"{str(e)}\n\n")
                f.write(traceback.format_exc())
            
            # Попытка открыть файл лога
            try:
                if sys.platform == 'win32':
                    os.startfile(error_file)
            except:
                pass
        
        sys.exit(1)

if __name__ == "__main__":
    main()
