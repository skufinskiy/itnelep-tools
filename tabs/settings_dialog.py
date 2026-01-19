# -*- coding: utf-8 -*-
"""
Диалог настроек
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTabWidget, QWidget, QFormLayout, QLineEdit, QLabel
)
from PyQt5.QtCore import Qt


class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config.copy()
        
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Вкладки настроек
        tabs = QTabWidget()
        
        # Вкладка 1: Авторизация
        auth_tab = QWidget()
        auth_layout = QFormLayout()
        
        self.login_edit = QLineEdit(self.config.get("login", ""))
        auth_layout.addRow("Логин ITNELEP:", self.login_edit)
        
        self.password_edit = QLineEdit(self.config.get("password", ""))
        self.password_edit.setEchoMode(QLineEdit.Password)
        auth_layout.addRow("Пароль:", self.password_edit)
        
        auth_tab.setLayout(auth_layout)
        tabs.addTab(auth_tab, "Авторизация")
        
        # Вкладка 2: Google Sheets
        sheets_tab = QWidget()
        sheets_layout = QFormLayout()
        
        # Для Parser (первая вкладка)
        self.spreadsheet_id_edit = QLineEdit(self.config.get("spreadsheet_id", ""))
        sheets_layout.addRow("ID таблицы (Parser):", self.spreadsheet_id_edit)
        
        # Для Greeting (третья вкладка)
        sheets_layout.addWidget(QLabel(""))  # Разделитель
        greeting_label = QLabel("<b>Для Генератора приветствий:</b>")
        sheets_layout.addRow(greeting_label)
        
        self.sheet_inn_id_edit = QLineEdit(self.config.get("sheet_inn_id", ""))
        sheets_layout.addRow("ID таблицы с ИНН:", self.sheet_inn_id_edit)
        
        self.sheet_map_id_edit = QLineEdit(self.config.get("sheet_map_id", ""))
        sheets_layout.addRow("ID таблицы маппинга:", self.sheet_map_id_edit)
        
        self.sheet_map_tab_edit = QLineEdit(self.config.get("sheet_map_tab", "Айди"))
        sheets_layout.addRow("Название листа маппинга:", self.sheet_map_tab_edit)
        
        sheets_layout.addWidget(QLabel(""))  # Разделитель
        self.service_account_edit = QLineEdit(self.config.get("service_account_file", "service_account.json"))
        sheets_layout.addRow("Service Account файл:", self.service_account_edit)
        
        sheets_tab.setLayout(sheets_layout)
        tabs.addTab(sheets_tab, "Google Sheets")
        
        # Вкладка 3: API токены
        api_tab = QWidget()
        api_layout = QFormLayout()
        
        self.dadata_token_edit = QLineEdit(self.config.get("dadata_token", ""))
        api_layout.addRow("DaData Token:", self.dadata_token_edit)
        
        self.openai_key_edit = QLineEdit(self.config.get("openai_api_key", ""))
        self.openai_key_edit.setEchoMode(QLineEdit.Password)
        api_layout.addRow("OpenAI API Key:", self.openai_key_edit)
        
        api_tab.setLayout(api_layout)
        tabs.addTab(api_tab, "API")
        
        layout.addWidget(tabs)
        
        # Кнопки
        buttons = QHBoxLayout()
        buttons.addStretch()
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self.accept)
        save_btn.setDefault(True)
        buttons.addWidget(save_btn)
        
        layout.addLayout(buttons)
        
        self.setLayout(layout)
    
    def get_config(self):
        """Получение обновленной конфигурации"""
        return {
            "login": self.login_edit.text(),
            "password": self.password_edit.text(),
            "spreadsheet_id": self.spreadsheet_id_edit.text(),
            "sheet_inn_id": self.sheet_inn_id_edit.text(),
            "sheet_map_id": self.sheet_map_id_edit.text(),
            "sheet_map_tab": self.sheet_map_tab_edit.text(),
            "service_account_file": self.service_account_edit.text(),
            "dadata_token": self.dadata_token_edit.text(),
            "openai_api_key": self.openai_key_edit.text(),
            "credentials_file": self.config.get("credentials_file", "credentials.json")
        }
