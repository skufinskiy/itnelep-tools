# -*- coding: utf-8 -*-
"""
Вкладка Обрезка возраста
Полный функционал обрезки возраста ИНН → ID
"""

import os
import sys
import time
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QGroupBox, QFormLayout, QMessageBox,
    QCheckBox, QSpinBox, QDoubleSpinBox, QProgressBar,
    QPlainTextEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal as Signal


# ===================== CONFIG =====================

LOGIN_PATH = "/sign_in"
LOGIN_URL = "https://api.itnelep.com/sign_in"
BASE_URL = "https://api.itnelep.com/user_flows/{}"

PROCESSED_FILE = "processed_inns.txt"

# Login selectors
SEL_LOGIN = "#session_name"
SEL_PASSWORD = "#session_password"
SEL_SUBMIT = 'input[type="submit"][value="Войти"]'

# Birth range selectors
SEL_BIRTH_FROM = "#birth_range_from"
SEL_BIRTH_TO = "#birth_range_to"
SEL_BIRTH_SUBMIT = "#birth_range_submit_btn"
BTN_EDIT_TEXT = "✏️ Изменить"


class ObrezkaWorker(QThread):
    """Рабочий поток для обработки ИНН"""
    log = Signal(str)
    progress = Signal(int, int)  # current, total
    stats_update = Signal(int, int, int)  # ok, err, skip
    finished = Signal()
    
    def __init__(self, config, pairs, settings):
        super().__init__()
        self.config = config
        self.pairs = pairs
        self.settings = settings
        self._is_running = True
        self._is_paused = False
        self.stats = {"ok": 0, "err": 0, "skip": 0}
        
        self.play = None
        self.ctx = None
        self.page = None
    
    def stop(self):
        self._is_running = False
    
    def pause(self):
        self._is_paused = True
    
    def resume(self):
        self._is_paused = False
    
    def run(self):
        try:
            self.prepare_browser_and_data()
            
            if not self._is_running:
                return
            
            for idx, (inn, user_id) in enumerate(self.pairs):
                while self._is_paused and self._is_running:
                    time.sleep(0.1)
                
                if not self._is_running:
                    self.log.emit("⏹ Остановлено")
                    break
                
                self.log.emit(f"[{idx + 1}/{len(self.pairs)}] ИНН {inn} → {user_id}")
                
                ok = self.process_one(inn, user_id)
                
                if ok:
                    self.stats["ok"] += 1
                    with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
                        f.write(f"{inn}\n")
                else:
                    self.stats["err"] += 1
                
                self.progress.emit(idx + 1, len(self.pairs))
                self.stats_update.emit(self.stats["ok"], self.stats["err"], self.stats["skip"])
                
                if self.settings["delay"] > 0:
                    time.sleep(self.settings["delay"])
            
            self.log.emit("✅ Обработка завершена")
        except Exception as e:
            self.log.emit(f"FATAL ERROR: {str(e)}")
        finally:
            self.cleanup_browser()
            self.finished.emit()
    
    def prepare_browser_and_data(self):
        """Подготовка браузера и данных"""
        try:
            self.log.emit("🌐 Запуск браузера...")
            
            self.play = sync_playwright().start()
            self.ctx = self.play.chromium.launch_persistent_context(
                "pw_profile_obrezka",
                headless=self.settings["headless"],
                viewport={"width": 1280, "height": 800}
            )
            self.page = self.ctx.new_page()
            
            # Проверка авторизации
            inn0, id0 = self.pairs[0]
            first_url = BASE_URL.format(id0)
            self.log.emit(f"➡️ Открытие первой ссылки: {first_url}")
            self.page.goto(first_url, timeout=45000, wait_until="domcontentloaded")
            
            if not self.ensure_logged_in(return_url=first_url):
                raise Exception("Не удалось авторизоваться")
            
            self.log.emit("✅ Готово к обработке")
        except Exception as e:
            self.log.emit(f"Ошибка инициализации: {str(e)}")
            raise
    
    def ensure_logged_in(self, return_url: str) -> bool:
        """Проверка и выполнение авторизации"""
        try:
            url_now = self.page.url or ""
            needs = False
            
            if LOGIN_PATH in url_now:
                needs = True
            else:
                try:
                    self.page.locator(SEL_LOGIN).first.wait_for(timeout=1200)
                    needs = True
                except Exception:
                    needs = False
            
            if not needs:
                return True
            
            login = self.config.get("login", "").strip()
            password = self.config.get("password", "").strip()
            
            if not login or not password:
                self.log.emit("❌ Требуется авторизация, но логин/пароль не заданы")
                return False
            
            self.log.emit("🔐 Выполнение входа...")
            
            if LOGIN_PATH not in (self.page.url or ""):
                self.page.goto(LOGIN_URL, timeout=45000, wait_until="domcontentloaded")
            
            self.page.fill(SEL_LOGIN, login)
            self.page.fill(SEL_PASSWORD, password)
            self.page.click(SEL_SUBMIT)
            
            try:
                self.page.wait_for_selector(SEL_LOGIN, state="detached", timeout=15000)
            except Exception:
                if LOGIN_PATH in (self.page.url or ""):
                    self.log.emit("❌ Не удалось войти")
                    return False
            
            self.log.emit("✅ Вход выполнен")
            self.page.goto(return_url, timeout=45000, wait_until="domcontentloaded")
            return True
        
        except Exception as e:
            self.log.emit(f"❌ Ошибка авторизации: {str(e)}")
            return False
    
    def process_one(self, inn: str, user_id: str) -> bool:
        """Обработка одного ИНН"""
        target_url = BASE_URL.format(user_id)
        
        for attempt in range(1, self.settings["retries"] + 1):
            if not self._is_running:
                return False
            
            try:
                self.page.goto(target_url, timeout=45000, wait_until="domcontentloaded")
                
                if not self.ensure_logged_in(return_url=target_url):
                    return False
                
                # Открыть модальное окно
                self.page.get_by_role("button", name=BTN_EDIT_TEXT).click(timeout=15000)
                
                # Заполнить года
                self.page.fill(SEL_BIRTH_FROM, str(self.settings["birth_from"]))
                self.page.fill(SEL_BIRTH_TO, str(self.settings["birth_to"]))
                self.page.click(SEL_BIRTH_SUBMIT)
                
                return True
            
            except Exception as e:
                self.log.emit(f"Ошибка попытка {attempt}: {str(e)}")
                time.sleep(1.0)
        
        return False
    
    def cleanup_browser(self):
        """Очистка браузера"""
        try:
            if self.ctx:
                self.ctx.close()
        except:
            pass
        try:
            if self.play:
                self.play.stop()
        except:
            pass


class ObrezkaTab(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.worker = None
        self.pairs = []
        
        self.init_ui()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout()
        
        # Заголовок
        title = QLabel("✂️ Обрезка возраста — ИНН → ID")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)
        
        # Настройки обработки
        settings_group = QGroupBox("⚙️ Настройки обработки")
        settings_layout = QFormLayout()
        
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0, 10)
        self.delay_spin.setValue(1.0)
        self.delay_spin.setSingleStep(0.1)
        self.delay_spin.setSuffix(" сек")
        settings_layout.addRow("Задержка между ИНН:", self.delay_spin)
        
        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(1, 10)
        self.retries_spin.setValue(2)
        settings_layout.addRow("Повторов при ошибке:", self.retries_spin)
        
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 10000)
        self.limit_spin.setValue(0)
        self.limit_spin.setSpecialValueText("Все")
        settings_layout.addRow("Лимит строк:", self.limit_spin)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # Диапазон годов
        years_group = QGroupBox("📅 Диапазон годов рождения")
        years_layout = QHBoxLayout()
        
        self.birth_from_spin = QSpinBox()
        self.birth_from_spin.setRange(1900, 2026)
        self.birth_from_spin.setValue(1925)
        years_layout.addWidget(QLabel("От:"))
        years_layout.addWidget(self.birth_from_spin)
        
        self.birth_to_spin = QSpinBox()
        self.birth_to_spin.setRange(1900, 2026)
        self.birth_to_spin.setValue(1971)
        years_layout.addWidget(QLabel("До:"))
        years_layout.addWidget(self.birth_to_spin)
        
        self.headless_cb = QCheckBox("Headless (без окна браузера)")
        self.headless_cb.setChecked(True)  # По умолчанию включено
        years_layout.addWidget(self.headless_cb)
        years_layout.addStretch()
        
        years_group.setLayout(years_layout)
        layout.addWidget(years_group)
        
        # Прогресс
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        
        self.stat_label = QLabel("✔ 0   ✖ 0   ⏭ 0")
        layout.addWidget(self.stat_label)
        
        # Кнопки
        buttons = QHBoxLayout()
        
        self.btn_start = QPushButton("▶ Старт")
        self.btn_start.clicked.connect(self.start_processing)
        buttons.addWidget(self.btn_start)
        
        self.btn_pause = QPushButton("⏸ Пауза")
        self.btn_pause.clicked.connect(self.pause_processing)
        self.btn_pause.setEnabled(False)
        buttons.addWidget(self.btn_pause)
        
        self.btn_resume = QPushButton("▶ Продолжить")
        self.btn_resume.clicked.connect(self.resume_processing)
        self.btn_resume.setEnabled(False)
        buttons.addWidget(self.btn_resume)
        
        self.btn_stop = QPushButton("⏹ Стоп")
        self.btn_stop.clicked.connect(self.stop_processing)
        self.btn_stop.setEnabled(False)
        buttons.addWidget(self.btn_stop)
        
        buttons.addStretch()
        layout.addLayout(buttons)
        
        # Логи
        layout.addWidget(QLabel("Логи:"))
        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("background: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self.log_area)
        
        self.setLayout(layout)
    
    def start_processing(self):
        """Запуск обработки"""
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Внимание", "Обработка уже запущена")
            return
        
        # Проверка авторизации
        login = self.config.get("login", "").strip()
        password = self.config.get("password", "").strip()
        
        if not login or not password:
            reply = QMessageBox.question(
                self,
                "Внимание",
                "Логин/пароль не заполнены. Если сайт попросит авторизацию, программа не сможет войти.\n\n"
                "Откройте настройки (Ctrl+H) чтобы заполнить данные.\n\nПродолжить?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        # Проверка годов
        y1 = self.birth_from_spin.value()
        y2 = self.birth_to_spin.value()
        if y1 > y2:
            QMessageBox.warning(self, "Ошибка", "Год 'от' не может быть больше года 'до'")
            return
        
        # Загрузка данных
        try:
            self.log("📄 Чтение таблицы...")
            self.load_data()
            
            if not self.pairs:
                QMessageBox.information(self, "Готово", "Нет строк для обработки")
                return
            
            self.log(f"✅ Загружено {len(self.pairs)} строк для обработки")
        except Exception as e:
            self.log(f"❌ Ошибка загрузки данных: {str(e)}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные:\n{str(e)}")
            return
        
        # Настройки
        settings = {
            "delay": self.delay_spin.value(),
            "retries": self.retries_spin.value(),
            "birth_from": self.birth_from_spin.value(),
            "birth_to": self.birth_to_spin.value(),
            "headless": self.headless_cb.isChecked()
        }
        
        # Запуск worker
        self.progress.setValue(0)
        self.progress.setMaximum(len(self.pairs))
        
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_resume.setEnabled(False)
        self.btn_stop.setEnabled(True)
        
        self.worker = ObrezkaWorker(self.config, self.pairs, settings)
        self.worker.log.connect(self.log)
        self.worker.progress.connect(self.update_progress)
        self.worker.stats_update.connect(self.update_stats)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()
    
    def pause_processing(self):
        """Пауза обработки"""
        if self.worker:
            self.worker.pause()
            self.btn_pause.setEnabled(False)
            self.btn_resume.setEnabled(True)
            self.log("⏸ Пауза")
    
    def resume_processing(self):
        """Продолжение обработки"""
        if self.worker:
            self.worker.resume()
            self.btn_pause.setEnabled(True)
            self.btn_resume.setEnabled(False)
            self.log("▶ Продолжение")
    
    def stop_processing(self):
        """Остановка обработки"""
        if self.worker:
            self.worker.stop()
            self.btn_stop.setEnabled(False)
    
    def update_progress(self, current, total):
        """Обновление прогресса"""
        self.progress.setValue(current)
    
    def update_stats(self, ok, err, skip):
        """Обновление статистики"""
        self.stat_label.setText(f"✔ {ok}   ✖ {err}   ⏭ {skip}")
    
    def on_finished(self):
        """Завершение обработки"""
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_resume.setEnabled(False)
        self.btn_stop.setEnabled(False)
        QMessageBox.information(self, "Готово", "Обработка завершена!")
    
    def log(self, msg: str):
        """Добавление сообщения в лог"""
        self.log_area.appendPlainText(msg)
    
    def load_data(self):
        """Загрузка данных из Google Sheets"""
        service_account = self.config.get("service_account_file", "service_account.json")
        sheet_id = self.config.get("spreadsheet_id", "1U5LgHZMljA7DdjtxXCTaUB-GmK4uyxXCo5Io4pSScQk")
        tab_inn = "Молодняк"
        tab_map = "Айди"
        
        creds = Credentials.from_service_account_file(
            service_account,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly",
            ]
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_id)
        
        # Чтение ИНН
        inns = sh.worksheet(tab_inn).col_values(1)
        inns = [i.strip() for i in inns if i.strip()]
        if inns and not inns[0].isdigit():
            inns = inns[1:]
        
        # Чтение маппинга
        ws = sh.worksheet(tab_map)
        mapping = {}
        for i, d in zip(ws.col_values(1), ws.col_values(2)):
            if i and d:
                mapping[i.strip()] = d.strip()
        
        # Обработанные ИНН
        processed = set()
        if os.path.exists(PROCESSED_FILE):
            with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
                processed = set(x.strip() for x in f if x.strip())
        
        # Формирование пар
        pairs = []
        skip_count = 0
        for inn in inns:
            if inn in processed:
                skip_count += 1
            elif inn in mapping:
                pairs.append((inn, mapping[inn]))
        
        # Лимит
        limit = self.limit_spin.value()
        if limit > 0:
            pairs = pairs[:limit]
        
        self.pairs = pairs
        self.update_stats(0, 0, skip_count)
    
    def update_config(self, config):
        """Обновление конфигурации"""
        self.config = config
    
    def cleanup(self):
        """Очистка ресурсов"""
        try:
            if self.worker:
                self.worker.stop()
                self.worker.wait(3000)
        except:
            pass
