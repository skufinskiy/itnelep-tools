# -*- coding: utf-8 -*-
"""
Вкладка Parser + Google Sheets
Полный функционал парсинга ITNELEP с записью в Google Sheets
"""

import sys
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QCheckBox,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPlainTextEdit,
    QGroupBox,
    QFormLayout,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal as Signal

# Локальные импорты
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from google_api import GoogleSheetsAPI
from scraper import Scraper


class ParserWorker(QThread):
    """Рабочий поток для обработки ИНН"""
    log = Signal(str)
    progress = Signal(int, int)  # current, total
    finished = Signal()
    
    def __init__(self, scraper, gs, tasks, sheet_name, row_map, filters):
        super().__init__()
        self.scraper = scraper
        self.gs = gs
        self.tasks = tasks
        self.sheet_name = sheet_name
        self.row_map = row_map
        self.filters = filters
        self._is_running = True
    
    def stop(self):
        self._is_running = False
    
    def run(self):
        try:
            for done, (gui_row, inn, ufid) in enumerate(self.tasks, start=1):
                if not self._is_running:
                    self.log.emit("⏹ Остановлено пользователем")
                    break
                    
                self.log.emit("-" * 40)
                self.log.emit(f"[ИНН {inn}] user_flow_id={ufid}")
                
                data = self.scraper.process_record(inn, ufid, self.filters)
                
                gs_row = self.row_map[gui_row]
                
                self.log.emit(
                    f"[ИНН {inn}] total={data['total']} rich={data['rich']} "
                    f"filtered={data['filtered']} himera={data['himera_finance']} "
                    f"old_no_delay={data['old_without_delay']}"
                )
                
                # Записываем в Google Sheets
                self.gs.update_row_metrics(
                    self.sheet_name,
                    gs_row,
                    data['total'],
                    data['rich'],
                    data['filtered'],
                    data['himera_finance'],
                    data['old_without_delay']
                )
                
                supports_text = "\n".join(data["supports"]) if data["supports"] else "Нет подкрепов"
                self.gs.update_supports(self.sheet_name, gs_row, supports_text)
                
                self.log.emit(f"[ИНН {inn}] записано в строку {gs_row}")
                
                self.progress.emit(done, len(self.tasks))
                
            self.log.emit("Готово ✔")
        except Exception as e:
            self.log.emit(f"ОШИБКА: {str(e)}")
        finally:
            self.finished.emit()


class ParserTab(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.scraper = None
        self.row_map = []
        self.gs = None
        self.worker = None
        
        self.init_ui()
        self.load_google_sheets()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        main = QHBoxLayout()
        left = QVBoxLayout()
        
        # Заголовок
        title = QLabel("📊 Parser + Google Sheets")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        left.addWidget(title)
        
        # Выбор листа
        sheet_group = QGroupBox("Выбор листа")
        sheet_layout = QVBoxLayout()
        
        self.sheet_combo = QComboBox()
        sheet_layout.addWidget(QLabel("Лист:"))
        sheet_layout.addWidget(self.sheet_combo)
        
        btn_refresh = QPushButton("🔄 Обновить")
        btn_refresh.clicked.connect(self.load_table)
        sheet_layout.addWidget(btn_refresh)
        
        sheet_group.setLayout(sheet_layout)
        left.addWidget(sheet_group)
        
        # Таблица ИНН
        left.addWidget(QLabel("Выберите строки для обработки:"))
        self.table = QTableWidget()
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["ИНН"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        left.addWidget(self.table)
        
        # Кнопки управления
        btns = QHBoxLayout()
        self.btn_run = QPushButton("▶ Обработать")
        self.btn_run.clicked.connect(self.process_inns)
        btns.addWidget(self.btn_run)
        
        self.btn_stop = QPushButton("⏹ Остановить")
        self.btn_stop.clicked.connect(self.stop_processing)
        self.btn_stop.setEnabled(False)
        btns.addWidget(self.btn_stop)
        
        left.addLayout(btns)
        
        # Прогресс
        self.progress = QProgressBar()
        left.addWidget(self.progress)
        
        # Правая панель
        right = QVBoxLayout()
        
        # Фильтры
        filters_group = QGroupBox("Фильтры")
        filters_layout = QVBoxLayout()
        
        filters_layout.addWidget(QLabel("<b>Основные фильтры:</b>"))
        self.cb_old = QCheckBox("Старые (55+)")
        filters_layout.addWidget(self.cb_old)
        
        self.cb_without_notes = QCheckBox("Без заметок")
        filters_layout.addWidget(self.cb_without_notes)
        
        dep_layout = QHBoxLayout()
        self.cb_min_dep = QCheckBox("Мин. депозит:")
        self.le_min_dep = QLineEdit("500000")
        self.le_min_dep.setMaximumWidth(100)
        dep_layout.addWidget(self.cb_min_dep)
        dep_layout.addWidget(self.le_min_dep)
        dep_layout.addStretch()
        filters_layout.addLayout(dep_layout)
        
        filters_layout.addWidget(QLabel("<b>Отложки:</b>"))
        info_label = QLabel("По умолчанию: 2 месяца + ошибки")
        info_label.setStyleSheet("font-style: italic; color: gray;")
        filters_layout.addWidget(info_label)
        
        filters_group.setLayout(filters_layout)
        right.addWidget(filters_group)
        
        # Настройка браузера
        browser_group = QGroupBox("Настройки браузера")
        browser_layout = QVBoxLayout()
        
        self.cb_headless = QCheckBox("Скрывать браузер (headless)")
        self.cb_headless.setChecked(True)
        browser_layout.addWidget(self.cb_headless)
        
        browser_group.setLayout(browser_layout)
        right.addWidget(browser_group)
        
        # Логи
        right.addWidget(QLabel("Логи:"))
        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("background: #1e1e1e; color: #d4d4d4;")
        self.log_area.setMaximumHeight(300)
        right.addWidget(self.log_area)
        
        # Добавление в главный layout
        main.addLayout(left, 3)
        main.addLayout(right, 1)
        self.setLayout(main)
    
    def load_google_sheets(self):
        """Загрузка Google Sheets API"""
        try:
            service_account = self.config.get("service_account_file", "service_account.json")
            spreadsheet_id = self.config.get("spreadsheet_id", "1U5LgHZMljA7DdjtxXCTaUB-GmK4uyxXCo5Io4pSScQk")
            
            self.gs = GoogleSheetsAPI(service_account, spreadsheet_id)
            
            allowed = ["1кк", "500к", "0", "2кк дальняк", "У чатеров"]
            sheets = [s for s in self.gs.get_sheet_names() if s in allowed]
            self.sheet_combo.clear()
            self.sheet_combo.addItems(sheets)
            self.sheet_combo.currentIndexChanged.connect(self.load_table)
            
            self.log("✅ Google Sheets подключен")
            self.load_table()
        except Exception as e:
            self.log(f"❌ Ошибка подключения к Google Sheets: {str(e)}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось подключиться к Google Sheets:\n{str(e)}")
    
    def load_table(self):
        """Загрузка таблицы с ИНН"""
        if not self.gs:
            return
            
        try:
            sheet = self.sheet_combo.currentText()
            if not sheet:
                return
                
            ws = self.gs.get_sheet(sheet)
            rows = ws.get_all_values()
            
            # Для листа "0" отключаем минимальный депозит
            if sheet == "0":
                self.cb_min_dep.setChecked(False)
                self.cb_min_dep.setEnabled(False)
                self.le_min_dep.setEnabled(False)
            else:
                self.cb_min_dep.setEnabled(True)
                self.le_min_dep.setEnabled(True)
            
            self.row_map = []
            inns = []
            
            for idx, row in enumerate(rows, start=1):
                if idx == 1:  # Пропускаем заголовок
                    continue
                if not row:
                    continue
                
                inn = (row[0] or "").strip()
                if inn:
                    inns.append(inn)
                    self.row_map.append(idx)
            
            self.table.setRowCount(len(inns))
            self.table.setColumnCount(1)
            self.table.setHorizontalHeaderLabels(["ИНН"])
            
            for i, inn in enumerate(inns):
                self.table.setItem(i, 0, QTableWidgetItem(inn))
            
            self.log(f"Загружен лист '{sheet}'. Найдено ИНН: {len(inns)}")
        except Exception as e:
            self.log(f"❌ Ошибка загрузки таблицы: {str(e)}")
    
    def get_filters(self):
        """Получение фильтров"""
        min_dep = None
        if self.cb_min_dep.isChecked():
            try:
                min_dep = int(self.le_min_dep.text())
            except:
                min_dep = None
        
        return {
            "old": self.cb_old.isChecked(),
            "without_notes": self.cb_without_notes.isChecked(),
            "min_deposit": min_dep,
        }
    
    def ensure_scraper(self):
        """Создание scraper если его нет"""
        if self.scraper is None:
            self.scraper = Scraper(headless=self.cb_headless.isChecked())
    
    def process_inns(self):
        """Обработка выбранных ИНН"""
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Внимание", "Обработка уже запущена")
            return
        
        selected_rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not selected_rows:
            QMessageBox.warning(self, "Ошибка", "Выберите строки для обработки")
            return
        
        # Проверка авторизации
        login = self.config.get("login", "").strip()
        password = self.config.get("password", "").strip()
        
        if not login or not password:
            QMessageBox.warning(
                self, 
                "Ошибка", 
                "Не указаны логин и пароль.\n\nОткройте настройки (Ctrl+H) и заполните данные для авторизации."
            )
            return
        
        # Получение маппинга ИНН -> user_flow_id
        mapping = self.gs.get_inn_id_mapping()
        tasks = []
        
        for gui_row in selected_rows:
            inn_item = self.table.item(gui_row, 0)
            if not inn_item:
                continue
            
            inn = inn_item.text().strip()
            if inn in mapping:
                tasks.append((gui_row, inn, mapping[inn]))
            else:
                self.log(f"[ИНН {inn}] Не найден user_flow_id")
        
        if not tasks:
            QMessageBox.warning(self, "Ошибка", "Нет user_flow_id для выбранных ИНН")
            return
        
        # Создание scraper и вход
        try:
            self.log("🌐 Запуск браузера...")
            self.ensure_scraper()
            
            self.log(f"🔐 Вход на сайт...")
            self.scraper.login(login, password)
            self.log("✅ Авторизация успешна")
        except Exception as e:
            self.log(f"❌ Ошибка входа: {str(e)}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось войти на сайт:\n{str(e)}")
            return
        
        # Запуск обработки
        self.progress.setValue(0)
        self.progress.setMaximum(len(tasks))
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        
        cur_sheet = self.sheet_combo.currentText()
        filters = self.get_filters()
        
        self.log(f"Начало обработки {len(tasks)} строк")
        
        self.worker = ParserWorker(self.scraper, self.gs, tasks, cur_sheet, self.row_map, filters)
        self.worker.log.connect(self.log)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()
    
    def stop_processing(self):
        """Остановка обработки"""
        if self.worker:
            self.worker.stop()
            self.btn_stop.setEnabled(False)
    
    def update_progress(self, current, total):
        """Обновление прогресса"""
        self.progress.setValue(current)
    
    def on_finished(self):
        """Завершение обработки"""
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        QMessageBox.information(self, "Готово", "Обработка завершена!")
    
    def log(self, msg: str):
        """Добавление сообщения в лог"""
        self.log_area.appendPlainText(msg)
    
    def update_config(self, config):
        """Обновление конфигурации"""
        self.config = config
        self.load_google_sheets()
    
    def cleanup(self):
        """Очистка ресурсов"""
        try:
            if self.worker:
                self.worker.stop()
                self.worker.wait(3000)
            if self.scraper:
                self.scraper.quit()
        except:
            pass
