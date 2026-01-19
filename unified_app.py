# -*- coding: utf-8 -*-
"""
Unified Application - Объединенное приложение
Включает функционал всех 4 программ в одном интерфейсе
"""

import sys
import json
import os
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout,
    QAction, QMessageBox, QShortcut
)
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QKeySequence

# Импорт вкладок
from tabs.parser_tab import ParserTab
from tabs.renamer_tab import RenamerTab
from tabs.greeting_tab import GreetingTab
from tabs.obrezka_tab import ObrezkaTab
from tabs.settings_dialog import SettingsDialog


class UnifiedApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Unified ITNELEP Tools")
        self.setGeometry(100, 100, 1400, 900)
        
        # Загрузка настроек
        self.settings = QSettings("UnifiedApp", "Settings")
        self.config = self.load_config()
        
        # Установка темы
        self.is_dark_theme = self.settings.value("dark_theme", True, type=bool)
        
        self.init_ui()
        self.apply_theme()
        self.setup_shortcuts()
        
    def init_ui(self):
        """Инициализация интерфейса"""
        # Создание меню
        menubar = self.menuBar()
        
        # Меню View
        view_menu = menubar.addMenu("Вид")
        
        # Переключатель темы
        self.theme_action = QAction("Светлая тема", self)
        self.theme_action.setCheckable(True)
        self.theme_action.setChecked(not self.is_dark_theme)
        self.theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(self.theme_action)
        
        # Создание вкладок
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Добавление вкладок
        self.parser_tab = ParserTab(self.config)
        self.renamer_tab = RenamerTab(self.config)
        self.greeting_tab = GreetingTab(self.config)
        self.obrezka_tab = ObrezkaTab(self.config)
        
        self.tabs.addTab(self.parser_tab, "📊 Parser + Sheets")
        self.tabs.addTab(self.renamer_tab, "✏️ Переименование ИНН")
        self.tabs.addTab(self.greeting_tab, "👋 Генератор приветствий")
        self.tabs.addTab(self.obrezka_tab, "✂️ Обрезка возраста")
        
    def setup_shortcuts(self):
        """Настройка горячих клавиш"""
        # Ctrl+H для открытия настроек
        settings_shortcut = QShortcut(QKeySequence("Ctrl+H"), self)
        settings_shortcut.activated.connect(self.show_settings)
        
    def show_settings(self):
        """Показать диалог настроек"""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec_():
            self.config = dialog.get_config()
            self.save_config()
            # Обновить конфиг во всех вкладках
            self.update_tabs_config()
            QMessageBox.information(self, "Настройки", "Настройки сохранены!")
    
    def update_tabs_config(self):
        """Обновить конфигурацию во всех вкладках"""
        self.parser_tab.update_config(self.config)
        self.renamer_tab.update_config(self.config)
        self.greeting_tab.update_config(self.config)
        self.obrezka_tab.update_config(self.config)
    
    def toggle_theme(self):
        """Переключение темы"""
        self.is_dark_theme = not self.is_dark_theme
        self.settings.setValue("dark_theme", self.is_dark_theme)
        self.theme_action.setChecked(not self.is_dark_theme)
        self.apply_theme()
        
    def apply_theme(self):
        """Применение темы"""
        if self.is_dark_theme:
            self.set_dark_theme()
        else:
            self.set_light_theme()
    
    def set_dark_theme(self):
        """Установка темной темы"""
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e1e;
                color: #e6e6e6;
                font-size: 13px;
            }
            QTabWidget::pane {
                border: 1px solid #3a3a3a;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #e6e6e6;
                padding: 10px 20px;
                border: 1px solid #3a3a3a;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: #ffffff;
                border-bottom: 2px solid #2d5d9f;
            }
            QTabBar::tab:hover {
                background-color: #3a3a3a;
            }
            QLabel {
                background: transparent;
                color: #e6e6e6;
            }
            QLineEdit, QComboBox, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
                background-color: #252526;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 6px;
                color: #e6e6e6;
                selection-background-color: #2d5d9f;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus {
                border: 1px solid #2d5d9f;
            }
            QPushButton {
                background-color: #2d5d9f;
                color: #ffffff;
                border: 1px solid #3870b8;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #3770be;
            }
            QPushButton:pressed {
                background-color: #2a5390;
            }
            QPushButton:disabled {
                background-color: #3a3a3a;
                color: #9a9a9a;
                border: 1px solid #4a4a4a;
            }
            QTableWidget {
                background-color: #252526;
                border: 1px solid #3a3a3a;
                gridline-color: #3a3a3a;
                color: #e6e6e6;
            }
            QTableWidget::item:selected {
                background: #2d5d9f;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #2b2b2b;
                color: #e6e6e6;
                padding: 8px;
                border: 1px solid #3a3a3a;
                font-weight: bold;
            }
            QCheckBox {
                color: #e6e6e6;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #3a3a3a;
                border-radius: 3px;
                background-color: #252526;
            }
            QCheckBox::indicator:checked {
                background-color: #2d5d9f;
                border: 1px solid #2d5d9f;
            }
            QRadioButton {
                color: #e6e6e6;
                spacing: 8px;
            }
            QProgressBar {
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                background-color: #252526;
                text-align: center;
                color: #e6e6e6;
            }
            QProgressBar::chunk {
                background-color: #2d5d9f;
                border-radius: 3px;
            }
            QMenuBar {
                background-color: #2d2d2d;
                color: #e6e6e6;
                border-bottom: 1px solid #3a3a3a;
            }
            QMenuBar::item:selected {
                background-color: #3a3a3a;
            }
            QMenu {
                background-color: #2d2d2d;
                color: #e6e6e6;
                border: 1px solid #3a3a3a;
            }
            QMenu::item:selected {
                background-color: #2d5d9f;
            }
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #2d5d9f;
            }
            QScrollBar:vertical {
                background: #252526;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #3a3a3a;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4a4a4a;
            }
        """)
    
    def set_light_theme(self):
        """Установка светлой темы"""
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #ffffff;
                color: #1a1a1a;
                font-size: 13px;
            }
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #f5f5f5;
                color: #1a1a1a;
                padding: 10px 20px;
                border: 1px solid #c0c0c0;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #000000;
                border-bottom: 2px solid #0066cc;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #e8e8e8;
            }
            QLabel {
                background: transparent;
                color: #1a1a1a;
            }
            QLineEdit, QComboBox, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
                background-color: #ffffff;
                border: 2px solid #c0c0c0;
                border-radius: 4px;
                padding: 6px;
                color: #000000;
                selection-background-color: #0066cc;
                selection-color: #ffffff;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus {
                border: 2px solid #0066cc;
                background-color: #f8f9fa;
            }
            QLineEdit:disabled, QComboBox:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {
                background-color: #f0f0f0;
                color: #666666;
                border: 2px solid #d0d0d0;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border: 2px solid #1a1a1a;
                width: 8px;
                height: 8px;
                border-width: 0 2px 2px 0;
                transform: rotate(45deg);
                margin-right: 8px;
            }
            QPushButton {
                background-color: #0066cc;
                color: #ffffff;
                border: none;
                padding: 10px 18px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0052a3;
            }
            QPushButton:pressed {
                background-color: #003d7a;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
            QTableWidget {
                background-color: #ffffff;
                border: 2px solid #c0c0c0;
                gridline-color: #d0d0d0;
                color: #000000;
            }
            QTableWidget::item {
                padding: 5px;
                color: #000000;
            }
            QTableWidget::item:selected {
                background: #0066cc;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                color: #000000;
                padding: 10px;
                border: 1px solid #c0c0c0;
                font-weight: bold;
            }
            QCheckBox {
                color: #1a1a1a;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #888888;
                border-radius: 3px;
                background-color: #ffffff;
            }
            QCheckBox::indicator:checked {
                background-color: #0066cc;
                border: 2px solid #0066cc;
                image: none;
            }
            QCheckBox::indicator:checked:after {
                content: "✓";
                color: #ffffff;
            }
            QRadioButton {
                color: #1a1a1a;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #888888;
                border-radius: 10px;
                background-color: #ffffff;
            }
            QRadioButton::indicator:checked {
                background-color: #0066cc;
                border: 2px solid #0066cc;
            }
            QProgressBar {
                border: 2px solid #c0c0c0;
                border-radius: 5px;
                background-color: #f0f0f0;
                text-align: center;
                color: #000000;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #0066cc;
                border-radius: 3px;
            }
            QMenuBar {
                background-color: #f8f9fa;
                color: #1a1a1a;
                border-bottom: 1px solid #c0c0c0;
            }
            QMenuBar::item {
                padding: 8px 12px;
                background: transparent;
            }
            QMenuBar::item:selected {
                background-color: #e0e0e0;
            }
            QMenu {
                background-color: #ffffff;
                color: #1a1a1a;
                border: 2px solid #c0c0c0;
            }
            QMenu::item {
                padding: 8px 30px;
            }
            QMenu::item:selected {
                background-color: #0066cc;
                color: #ffffff;
            }
            QGroupBox {
                border: 2px solid #c0c0c0;
                border-radius: 8px;
                margin-top: 16px;
                padding-top: 12px;
                font-weight: bold;
                color: #1a1a1a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                color: #0066cc;
                font-weight: bold;
                background-color: #ffffff;
            }
            QScrollBar:vertical {
                background: #f0f0f0;
                width: 14px;
                border-radius: 7px;
                border: 1px solid #d0d0d0;
            }
            QScrollBar::handle:vertical {
                background: #b0b0b0;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #909090;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            QScrollBar:horizontal {
                background: #f0f0f0;
                height: 14px;
                border-radius: 7px;
                border: 1px solid #d0d0d0;
            }
            QScrollBar::handle:horizontal {
                background: #b0b0b0;
                border-radius: 6px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #909090;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                border: none;
                background: none;
            }
        """)
    
    def load_config(self):
        """Загрузка конфигурации"""
        config_path = Path("config.json")
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        # Конфигурация по умолчанию
        return {
            "login": "",
            "password": "",
            "spreadsheet_id": "1U5LgHZMljA7DdjtxXCTaUB-GmK4uyxXCo5Io4pSScQk",
            "sheet_inn_id": "",
            "sheet_map_id": "1U5LgHZMljA7DdjtxXCTaUB-GmK4uyxXCo5Io4pSScQk",
            "sheet_map_tab": "Айди",
            "service_account_file": "service_account.json",
            "dadata_token": "",
            "openai_api_key": "",
            "credentials_file": "credentials.json"
        }
    
    def save_config(self):
        """Сохранение конфигурации"""
        config_path = Path("config.json")
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить конфигурацию: {e}")
    
    def closeEvent(self, event):
        """Обработка закрытия приложения"""
        try:
            # Очищаем ресурсы всех вкладок
            if hasattr(self.parser_tab, 'cleanup'):
                self.parser_tab.cleanup()
            if hasattr(self.renamer_tab, 'cleanup'):
                self.renamer_tab.cleanup()
            if hasattr(self.greeting_tab, 'cleanup'):
                self.greeting_tab.cleanup()
            if hasattr(self.obrezka_tab, 'cleanup'):
                self.obrezka_tab.cleanup()
        except Exception as e:
            print(f"Error during cleanup: {e}")
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Unified ITNELEP Tools")
    app.setOrganizationName("ITNELEP")
    
    window = UnifiedApp()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
