# -*- coding: utf-8 -*-
"""
Вкладка Переименование ИНН
Полный перенос функционала из inn_renamer_tk.py
"""

import re
import json
import urllib.parse
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass

import requests
import pandas as pd

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QPlainTextEdit, QGroupBox, QFormLayout,
    QMessageBox, QCheckBox, QSpinBox, QProgressBar,
    QGridLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal as Signal

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError


# ===========================
# КОНСТАНТЫ
# ===========================

LOGIN_URL = "https://api.itnelep.com/sign_in"
FLOW_URL_PREFIX = "https://api.itnelep.com/user_flows/"
STATE_FILE = "processed_flows.json"

SHEET_NAMES_DEFAULT = ["1кк", "500к", "0", "2кк дальняк"]
SHEET_NAME_IDS_DEFAULT = "Айди"


# ===========================
# МОДЕЛИ
# ===========================

@dataclass
class RowItem:
    inn: str
    title: str
    flow_id: str
    sheet: str
    row_index: int


# ===========================
# УТИЛИТЫ
# ===========================

def gsheet_csv_url(spreadsheet_id: str, sheet_name: str) -> str:
    """URL для загрузки Google Sheets в формате CSV"""
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(sheet_name)}"


def normalize_inn(x):
    """Нормализация ИНН - только цифры"""
    return re.sub(r"\D", "", str(x or "").strip())


def safe_str(x):
    """Безопасное преобразование в строку"""
    return "" if str(x or "").strip().lower() == "nan" else str(x or "").strip()


def col_letter_to_index(letter: str) -> int:
    """Преобразование буквы колонки в индекс (A=0, B=1, ...)"""
    s = letter.strip().upper()
    idx = 0
    for ch in s:
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def load_processed_state() -> dict:
    """Загрузка состояния обработанных flow_id"""
    try:
        p = Path(STATE_FILE)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_processed_state(state: dict) -> None:
    """Сохранение состояния обработанных flow_id"""
    try:
        Path(STATE_FILE).write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass


# ===========================
# WORKER THREAD
# ===========================

class RenameWorker(QThread):
    """Воркер для переименования в фоновом потоке"""
    
    log = Signal(str)
    progress = Signal(int, int, str, str)  # current, total, inn, flow_id
    finished = Signal(int, int, int)  # ok, skipped, fail
    
    def __init__(self, email, password, items: List[RowItem], processed_state: dict):
        super().__init__()
        self.email = email
        self.password = password
        self.items = items
        self.processed_state = processed_state
        self._stop_flag = False
    
    def stop(self):
        """Остановка воркера"""
        self._stop_flag = True
    
    def run(self):
        """Основной цикл обработки"""
        ok = skipped = fail = 0
        
        try:
            total = len(self.items)
            
            if total == 0:
                self.log.emit("⚠️ Нет строк для обновления")
                self.finished.emit(ok, skipped, fail)
                return
            
            self.log.emit(f"📋 Загружено {total} записей для обработки")
            self.log.emit("🌐 Запуск браузера...")
            
            with sync_playwright() as p:
                # Запуск браузера
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                
                # Авторизация
                self.log.emit("🔐 Авторизация на api.itnelep.com...")
                page.goto(LOGIN_URL)
                page.locator("#session_name").fill(self.email)
                page.locator("#session_password").fill(self.password)
                page.keyboard.press("Enter")
                page.wait_for_load_state("networkidle")
                self.log.emit("✅ Авторизация успешна")
                
                # Обработка каждого элемента
                for idx, item in enumerate(self.items, start=1):
                    if self._stop_flag:
                        self.log.emit("⏸️ Остановлено пользователем")
                        break
                    
                    # Обновление прогресса
                    self.progress.emit(idx, total, item.inn, item.flow_id)
                    
                    # Проверка - уже обработан?
                    if item.flow_id in self.processed_state:
                        skipped += 1
                        self.log.emit(f"⭐ {item.inn} → ID {item.flow_id} (уже обработан)")
                        continue
                    
                    # Переход на страницу flow
                    url = FLOW_URL_PREFIX + item.flow_id
                    
                    try:
                        page.goto(url, wait_until="domcontentloaded")
                        
                        # Находим элемент заголовка и кликаем дважды
                        title_span = page.locator('[data-rename-target="title"]').first
                        title_span.dblclick()
                        
                        # Находим редактируемое поле и вставляем новый текст
                        editable = page.locator('[contenteditable="true"]').first
                        editable.fill(item.title)
                        
                        # Нажимаем Enter для сохранения
                        page.keyboard.press("Enter")
                        
                        # Небольшая задержка для сохранения
                        page.wait_for_timeout(500)
                        
                        # Сохраняем в состояние
                        self.processed_state[item.flow_id] = item.title
                        save_processed_state(self.processed_state)
                        
                        ok += 1
                        self.log.emit(f"✅ {item.inn} → ID {item.flow_id}: {item.title}")
                        
                    except PWTimeoutError:
                        fail += 1
                        self.log.emit(f"❌ {item.inn}: Таймаут загрузки страницы")
                    except Exception as e:
                        fail += 1
                        self.log.emit(f"❌ {item.inn}: {str(e)}")
                
                # Закрытие браузера
                browser.close()
                self.log.emit("🔒 Браузер закрыт")
            
            self.finished.emit(ok, skipped, fail)
            
        except Exception as e:
            self.log.emit(f"❌ Критическая ошибка: {str(e)}")
            self.finished.emit(ok, skipped, fail)


# ===========================
# MAIN TAB WIDGET
# ===========================

class RenamerTab(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.worker = None
        self.processed_state = load_processed_state()
        
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # === Заголовок ===
        header = QLabel("✏️ Переименование ИНН в user_flow")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        main_layout.addWidget(header)
        
        # Информация об авторизации
        auth_info = QLabel("ℹ️ Авторизация настраивается через Ctrl+H (Настройки → Авторизация)")
        auth_info.setStyleSheet("color: #888; font-style: italic; padding: 5px;")
        main_layout.addWidget(auth_info)
        
        # === Google Sheets настройки ===
        sheets_group = QGroupBox("📊 Google Sheets")
        sheets_layout = QVBoxLayout()
        
        # ID таблицы
        spreadsheet_layout = QFormLayout()
        self.spreadsheet_id_label = QLabel(self.config.get("spreadsheet_id", "Не указан"))
        self.spreadsheet_id_label.setStyleSheet("color: #888;")
        spreadsheet_layout.addRow("ID таблицы:", self.spreadsheet_id_label)
        sheets_layout.addLayout(spreadsheet_layout)
        
        # Выбор листов
        sheets_label = QLabel("Выберите листы для обработки:")
        sheets_layout.addWidget(sheets_label)
        
        self.sheet_checkboxes: Dict[str, QCheckBox] = {}
        checkboxes_layout = QGridLayout()
        
        for idx, sheet_name in enumerate(SHEET_NAMES_DEFAULT):
            cb = QCheckBox(sheet_name)
            cb.setChecked(True)
            self.sheet_checkboxes[sheet_name] = cb
            checkboxes_layout.addWidget(cb, idx // 2, idx % 2)
        
        sheets_layout.addLayout(checkboxes_layout)
        
        # Лист с маппингом
        ids_layout = QFormLayout()
        self.ids_sheet_edit = QLineEdit(SHEET_NAME_IDS_DEFAULT)
        ids_layout.addRow("Лист Айди (ИНН→ID):", self.ids_sheet_edit)
        sheets_layout.addLayout(ids_layout)
        
        sheets_group.setLayout(sheets_layout)
        main_layout.addWidget(sheets_group)
        
        # === Ограничения ===
        limits_group = QGroupBox("⚙️ Ограничения обработки")
        limits_layout = QFormLayout()
        
        self.max_per_sheet_spin = QSpinBox()
        self.max_per_sheet_spin.setRange(0, 1000000)
        self.max_per_sheet_spin.setValue(0)
        self.max_per_sheet_spin.setSpecialValueText("Все")
        limits_layout.addRow("Макс. строк с каждого листа:", self.max_per_sheet_spin)
        
        self.max_total_spin = QSpinBox()
        self.max_total_spin.setRange(0, 1000000)
        self.max_total_spin.setValue(0)
        self.max_total_spin.setSpecialValueText("Все")
        limits_layout.addRow("Макс. всего записей:", self.max_total_spin)
        
        limits_group.setLayout(limits_layout)
        main_layout.addWidget(limits_group)
        
        # === Прогресс ===
        progress_group = QGroupBox("📈 Прогресс")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar)
        
        info_layout = QHBoxLayout()
        self.lbl_total = QLabel("0 / 0")
        info_layout.addWidget(self.lbl_total)
        
        self.lbl_current = QLabel("Текущий: —")
        info_layout.addWidget(self.lbl_current)
        info_layout.addStretch()
        
        progress_layout.addLayout(info_layout)
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)
        
        # === Кнопки управления ===
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        self.start_btn = QPushButton("▶️ Начать переименование")
        self.start_btn.clicked.connect(self.on_start)
        self.start_btn.setStyleSheet("font-weight: bold; padding: 10px 20px;")
        buttons_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("⏸️ Остановить")
        self.stop_btn.clicked.connect(self.on_stop)
        self.stop_btn.setEnabled(False)
        buttons_layout.addWidget(self.stop_btn)
        
        main_layout.addLayout(buttons_layout)
        
        # === Логи ===
        log_group = QGroupBox("📋 Логи выполнения")
        log_layout = QVBoxLayout()
        
        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(300)
        log_layout.addWidget(self.log_area)
        
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)
        
        main_layout.addStretch()
        self.setLayout(main_layout)
        
        # Загрузка учетных данных из config
        self.load_credentials()
    
    def load_credentials(self):
        """Обновление отображаемой информации из конфига"""
        # Обновление ID таблицы
        spreadsheet_id = self.config.get("spreadsheet_id", "Не указан")
        self.spreadsheet_id_label.setText(spreadsheet_id)
    
    def update_config(self, config):
        """Обновление конфигурации"""
        self.config = config
        self.load_credentials()
    
    def log_msg(self, msg: str):
        """Добавление сообщения в лог"""
        self.log_area.appendPlainText(msg)
    
    def fetch_sheet_df(self, sheet_name: str) -> pd.DataFrame:
        """Загрузка Google Sheets в DataFrame"""
        spreadsheet_id = self.config.get("spreadsheet_id", "")
        url = gsheet_csv_url(spreadsheet_id, sheet_name)
        
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        
        from io import StringIO
        return pd.read_csv(StringIO(r.text), dtype=str)
    
    def build_items(self, selected_sheets: List[str]) -> List[RowItem]:
        """Построение списка элементов для обработки"""
        # Загрузка маппинга ИНН → flow_id
        ids_sheet = self.ids_sheet_edit.text().strip() or SHEET_NAME_IDS_DEFAULT
        
        self.log_msg(f"📥 Загрузка маппинга из листа '{ids_sheet}'...")
        df_ids = self.fetch_sheet_df(ids_sheet)
        
        inn_col_ids = col_letter_to_index("A")
        id_col_ids = col_letter_to_index("B")
        
        inn_to_id = {}
        for _, row in df_ids.iterrows():
            inn = normalize_inn(row.iloc[inn_col_ids])
            fid = safe_str(row.iloc[id_col_ids])
            if inn and fid:
                inn_to_id[inn] = fid
        
        self.log_msg(f"✅ Загружено {len(inn_to_id)} маппингов ИНН→ID")
        
        # Сбор элементов из выбранных листов
        items = []
        max_per_sheet = self.max_per_sheet_spin.value()
        max_total = self.max_total_spin.value()
        
        for sheet in selected_sheets:
            self.log_msg(f"📥 Загрузка листа '{sheet}'...")
            df = self.fetch_sheet_df(sheet)
            
            count = 0
            for ridx, row in df.iterrows():
                # Проверка лимитов
                if max_total > 0 and len(items) >= max_total:
                    break
                if max_per_sheet > 0 and count >= max_per_sheet:
                    break
                
                inn = normalize_inn(row.iloc[0])
                if not inn or inn not in inn_to_id:
                    continue
                
                # Формирование названия
                title = f"{inn} {safe_str(row.iloc[1])} {safe_str(row.iloc[3])}".strip()
                
                items.append(RowItem(
                    inn=inn,
                    title=title,
                    flow_id=inn_to_id[inn],
                    sheet=sheet,
                    row_index=int(ridx) + 2
                ))
                
                count += 1
            
            self.log_msg(f"✅ Из листа '{sheet}' загружено {count} записей")
        
        return items
    
    def on_start(self):
        """Запуск процесса переименования"""
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Процесс запущен", "Обработка уже выполняется")
            return
        
        # Проверка учетных данных из конфига
        email = self.config.get("login", "").strip()
        password = self.config.get("password", "").strip()
        
        if not email or not password:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Логин и пароль не указаны.\n\nОткройте настройки (Ctrl+H) → Вкладка 'Авторизация' и заполните данные для входа на api.itnelep.com"
            )
            return
        
        # Проверка выбранных листов
        selected_sheets = [
            name for name, cb in self.sheet_checkboxes.items()
            if cb.isChecked()
        ]
        
        if not selected_sheets:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Выберите хотя бы один лист для обработки"
            )
            return
        
        # Проверка ID таблицы
        if not self.config.get("spreadsheet_id"):
            QMessageBox.warning(
                self,
                "Ошибка",
                "ID таблицы не указан в настройках.\n\nНажмите Ctrl+H для настройки."
            )
            return
        
        # Очистка логов
        self.log_area.clear()
        self.log_msg("🚀 Запуск процесса переименования...")
        
        try:
            # Построение списка элементов
            items = self.build_items(selected_sheets)
            
            if not items:
                QMessageBox.warning(
                    self,
                    "Нет данных",
                    "Не найдено записей для обработки"
                )
                return
            
            self.log_msg(f"📋 Всего к обработке: {len(items)} записей")
            
            # Инициализация прогресса
            self.progress_bar.setMaximum(len(items))
            self.progress_bar.setValue(0)
            self.lbl_total.setText(f"0 / {len(items)}")
            
            # Запуск воркера
            self.worker = RenameWorker(email, password, items, self.processed_state)
            self.worker.log.connect(self.log_msg)
            self.worker.progress.connect(self.on_progress)
            self.worker.finished.connect(self.on_finished)
            
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            
            self.worker.start()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось запустить обработку:\n\n{str(e)}"
            )
            self.log_msg(f"❌ Ошибка: {str(e)}")
    
    def on_stop(self):
        """Остановка процесса"""
        if self.worker and self.worker.isRunning():
            self.log_msg("⏸️ Остановка процесса...")
            self.worker.stop()
            self.worker.wait()
    
    def on_progress(self, current: int, total: int, inn: str, flow_id: str):
        """Обновление прогресса"""
        self.progress_bar.setValue(current)
        self.lbl_total.setText(f"{current} / {total}")
        self.lbl_current.setText(f"ИНН {inn} → ID {flow_id}")
    
    def on_finished(self, ok: int, skipped: int, fail: int):
        """Завершение обработки"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        self.log_msg("")
        self.log_msg("=" * 50)
        self.log_msg(f"✅ Успешно обработано: {ok}")
        self.log_msg(f"⭐ Пропущено (уже обработаны): {skipped}")
        self.log_msg(f"❌ Ошибок: {fail}")
        self.log_msg("=" * 50)
        
        # Показываем итоги
        QMessageBox.information(
            self,
            "Готово",
            f"Обработка завершена!\n\n"
            f"✅ Успешно: {ok}\n"
            f"⭐ Пропущено: {skipped}\n"
            f"❌ Ошибок: {fail}"
        )
    
    def cleanup(self):
        """Очистка ресурсов"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
