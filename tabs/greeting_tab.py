# -*- coding: utf-8 -*-
"""
Вкладка Генератор приветствий
Полный перенос функционала из оригинального app.py
"""

import json
import re
import unicodedata
import multiprocessing as mp
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import requests
import gspread
from google.oauth2.service_account import Credentials

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QPlainTextEdit, QGroupBox, QFormLayout,
    QMessageBox, QScrollArea, QComboBox, QCheckBox,
    QTableWidget, QTableWidgetItem, QListWidget, QListWidgetItem,
    QSplitter, QTextEdit, QDialog, QDialogButtonBox, QSizePolicy,
    QAbstractItemView, QApplication
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal as Signal
from PyQt5.QtGui import QColor, QGuiApplication

from playwright.sync_api import sync_playwright

# Optional: morphological inflection
try:
    import pymorphy2
    _MORPH = pymorphy2.MorphAnalyzer()
except Exception:
    _MORPH = None


# ===========================
# MODELS & DATA STRUCTURES
# ===========================

@dataclass
class LeaderRow:
    fio: str
    last_backup_raw: str
    last_backup_dt: Optional[datetime] = None


@dataclass
class PersonInfo:
    fio: str
    parts: List[str]
    notes_line_idx: Optional[int] = None


# ===========================
# TEXT NORMALIZATION HELPERS
# ===========================

def _norm_text(text: str) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", str(text)).replace("\xa0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _norm_fio_key(text: str) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", str(text)).replace("\xa0", " ")
    t = re.sub(r"[^A-Za-zА-Яа-яЁё\-\s\.]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    t = t.replace(".", "")
    return t


def _tokenize_ru_words(text: str) -> List[str]:
    if not text:
        return []
    t = unicodedata.normalize("NFKC", str(text)).replace("\xa0", " ")
    t = re.sub(r"[^A-Za-zА-Яа-яЁё\-\s]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return [w for w in t.split() if w]


def normalize_fio_case(fio: str) -> str:
    """If FIO is mostly CAPS, convert to Title Case, keep initials."""
    if not fio:
        return ""
    s = unicodedata.normalize("NFKC", str(fio)).replace("\xa0", " ").strip()
    s = re.sub(r"\s+", " ", s)

    letters = [ch for ch in s if ch.isalpha()]
    if not letters:
        return s
    upper_ratio = sum(ch.isupper() for ch in letters) / max(1, len(letters))
    if upper_ratio < 0.65:
        return s

    def fix_token(tok: str) -> str:
        m = re.match(r"^([«\"(]*)([A-Za-zА-Яа-яЁё\.\-]+)([»\")]*[.,:]*)$", tok)
        if not m:
            return tok
        pre, core, post = m.group(1), m.group(2), m.group(3)
        if re.fullmatch(r"[А-ЯЁA-Z]\.?$", core) or re.fullmatch(r"(?:[А-ЯЁA-Z]\.){1,3}$", core):
            return pre + core.upper() + post
        parts = core.split("-")
        fixed = []
        for p in parts:
            if not p:
                fixed.append(p)
            else:
                fixed.append(p[:1].upper() + p[1:].lower())
        return pre + "-".join(fixed) + post

    return " ".join(fix_token(t) for t in s.split())


def normalize_org_name(name: str) -> str:
    """Делает название организации читабельным"""
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", str(name)).replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()

    LEGAL_ABBR = {
        "ооо", "ао", "пао", "зао", "оао", "ип", "нко",
        "огбу", "дпо", "гбу", "гуп", "муп", "фгбу", "фгуп", "му", "мо"
    }

    parts = re.split(r'(".*?")', s)

    def fix_outside_quotes(chunk: str) -> str:
        if not chunk:
            return chunk
        words = chunk.split()
        out_words = []
        for w in words:
            m = re.match(r"^([«(]*)([A-Za-zА-Яа-яЁё\-]+)([»)»]*[.,:]*)$", w)
            if not m:
                out_words.append(w)
                continue
            pre, core, post = m.group(1), m.group(2), m.group(3)
            low = core.lower()

            if low in LEGAL_ABBR:
                out_words.append(pre + low.upper() + post)
                continue

            if re.fullmatch(r"[A-ZА-ЯЁ]{2,}", core):
                out_words.append(pre + core + post)
                continue

            out_words.append(pre + (core[:1].upper() + core[1:].lower()) + post)

        return " ".join(out_words)

    fixed = []
    for p in parts:
        if not p:
            continue
        if p.startswith('"') and p.endswith('"'):
            fixed.append(p)
        else:
            fixed.append(fix_outside_quotes(p))

    return re.sub(r"\s+", " ", "".join(fixed)).strip()


def fio_to_short(fio: str) -> str:
    parts = fio.split()
    if len(parts) >= 2:
        last = parts[0]
        first = parts[1][:1] + "."
        middle = (parts[2][:1] + ".") if len(parts) >= 3 else ""
        return f"{last} {first}{middle}"
    return fio


def fio_to_last_first(fio: str) -> str:
    parts = fio.split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"
    return fio


# ===========================
# INFLECTION (СКЛОНЕНИЕ)
# ===========================

CASE_TO_TAGS = {
    "КТО (именительный)": set(),
    "КОМУ (дательный)": {"datv"},
    "ОТ КОГО (родительный)": {"gent"},
}


def _inflect_word(word: str, tags: set) -> str:
    if not tags or _MORPH is None:
        return word
    m = re.match(r"^([«\"(]*)([А-ЯЁа-яёA-Za-z\-]+)([»\")]*[.,:]*)$", word)
    if not m:
        return word
    pre, core, post = m.group(1), m.group(2), m.group(3)
    parsed = _MORPH.parse(core)[0]
    inf = parsed.inflect(tags)
    return pre + (inf.word if inf else core) + post


def inflect_phrase_ru(text: str, case_key: str) -> str:
    tags = CASE_TO_TAGS.get(case_key, set())
    if not tags or _MORPH is None:
        return text
    return " ".join(_inflect_word(w, tags) for w in text.split())


def inflect_fio_ru(fio: str, case_key: str) -> str:
    tags = CASE_TO_TAGS.get(case_key, set())
    if not tags or _MORPH is None:
        return fio
    parts = fio.split()
    out = []
    for p in parts:
        parsed = _MORPH.parse(p)[0]
        inf = parsed.inflect(tags)
        out.append(inf.word if inf else p)
    return " ".join(out)


# ===========================
# POSITION ABBREVIATION
# ===========================

def abbreviate_position_ru(text: str) -> str:
    if not text:
        return ""
    t = re.sub(r"\s+", " ", text).strip()

    t = re.sub(
        r"\bпомощник[а-яё]*\s+генеральн[а-яё]*\s+директор[а-яё]*\b",
        "помощник гендиректора",
        t,
        flags=re.IGNORECASE
    )

    t = re.sub(
        r"\bзаместител[ьяюем]*\s+директор[а-яё]*\b",
        "зам. гендиректора",
        t,
        flags=re.IGNORECASE
    )

    t = re.sub(
        r"\bгенеральн[а-яё]*\s+директор[а-яё]*\b",
        "гендиректор",
        t,
        flags=re.IGNORECASE
    )

    t = re.sub(
        r"(?<!ген)\bдиректор\b",
        "руководитель",
        t,
        flags=re.IGNORECASE
    )

    t = re.sub(
        r"\bзаместител[ьяюем]*\b",
        "зам",
        t,
        flags=re.IGNORECASE
    )

    t = re.sub(
        r"\bглавн[а-яё]*\b",
        "глав",
        t,
        flags=re.IGNORECASE
    )

    t = re.sub(r"\bзам\s+гендиректор\b", "зам гендиректора", t, flags=re.IGNORECASE)

    t = re.sub(r"\bперв(?:ый|ого|ому|ым|ом)\s+зам\s+гендиректор\b",
        lambda m: m.group(0).rsplit(" ", 1)[0] + " гендиректора",
        t, flags=re.IGNORECASE)

    t = re.sub(r"\s{2,}", " ", t).strip()
    return t


def _lower_first(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    return text[:1].lower() + text[1:]


# ===========================
# GREETING MESSAGES BUILDING
# ===========================

def build_messages(name: str, post: str, org: str) -> List[str]:
    """Строго по примерам из программы."""
    name = (name or "").strip()
    post = (post or "").strip()
    org = (org or "").strip()

    post_after_name = f", {post}" if post else ""
    post_before_org = f"{post} " if post else ""

    msgs = [
        f"— Это {name}{post_after_name} {org}. Перезвоните мне, я по делу",
        f"— Беспокоит Вас {name}{post_after_name} {org}. Ожидаю от Вас обратной связи",
        f"— {name} беспокоит, {post_before_org}{org}. Есть тема для разговора, перезвоните",
        f"— Это {post_before_org}{org}, {name}. Нужно с Вами переговорить, перезвоните",
        f"— Беспокоит Вас {name}{post_after_name} {org}. Ожидаю от Вас обратной связи, я по делу",
    ]

    out: List[str] = []
    for m in msgs:
        m = re.sub(r"\s+", " ", m).strip()
        m = m.replace(" ,", ",")
        m = re.sub(r",\s*,", ",", m)
        m = re.sub(r",\s+", ", ", m)
        out.append(m)
    return out


# ===========================
# GOOGLE SHEETS CLIENT
# ===========================

class SheetsClient:
    def __init__(self, service_account_path: str):
        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        creds = Credentials.from_service_account_file(service_account_path, scopes=scopes)
        self.gc = gspread.authorize(creds)

    def list_worksheets(self, spreadsheet_id: str) -> List[str]:
        sh = self.gc.open_by_key(spreadsheet_id)
        titles: List[str] = []
        try:
            meta = sh.fetch_sheet_metadata()
            for sheet in meta.get("sheets", []):
                props = (sheet or {}).get("properties", {}) or {}
                title = (props.get("title") or "").strip()
                hidden = bool(props.get("hidden", False))
                if title and not hidden:
                    titles.append(title)
        except Exception:
            titles = []

        if not titles:
            try:
                for ws in sh.worksheets():
                    props = getattr(ws, "_properties", {}) or {}
                    if not bool(props.get("hidden", False)):
                        if ws.title:
                            titles.append(ws.title)
            except Exception:
                titles = [ws.title for ws in sh.worksheets()]
        return titles

    def get_inns_by_date(self, spreadsheet_id: str, worksheet_title: str, date_text: str) -> List[str]:
        sh = self.gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet(worksheet_title)

        col_a = ws.col_values(1)  # INN
        col_e = ws.col_values(5)  # date

        inns = []
        for i in range(1, min(len(col_a), len(col_e))):
            if (col_e[i] or "").strip() == date_text.strip():
                inn = (col_a[i] or "").strip()
                if inn:
                    inns.append(inn)
        return sorted(set(inns))

    def get_flow_id_by_inn(self, spreadsheet_id: str, worksheet_title: str, inn: str) -> Optional[str]:
        sh = self.gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet(worksheet_title)

        col_a = ws.col_values(1)  # INN
        col_b = ws.col_values(2)  # ID
        inn = inn.strip()
        for i in range(1, min(len(col_a), len(col_b))):
            if (col_a[i] or "").strip() == inn:
                flow_id = (col_b[i] or "").strip()
                return flow_id if flow_id else None
        return None


# ===========================
# DADATA API
# ===========================

def get_org_name_by_inn_dadata(inn: str, token: str) -> Optional[str]:
    url = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Token {token}",
    }
    payload = {"query": inn, "branch_type": "MAIN"}
    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("suggestions"):
        return None
    party = data["suggestions"][0]["data"]
    name = party.get("name", {})
    return name.get("short_with_opf") or name.get("full_with_opf") or None


class DaDataWorker(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, inn: str, token: str):
        super().__init__()
        self.inn = inn
        self.token = token

    def run(self):
        try:
            name = get_org_name_by_inn_dadata(self.inn, self.token) or ""
            self.done.emit(name)
        except Exception as e:
            self.failed.emit(str(e))


# ===========================
# PLAYWRIGHT PARSING
# ===========================

def parse_backup_dt(raw: str) -> Optional[datetime]:
    m = re.search(r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})", raw or "")
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + " " + m.group(2), "%d.%m.%Y %H:%M")
    except Exception:
        return None


def extract_leaders_and_backups(page) -> List[LeaderRow]:
    rows: List[LeaderRow] = []
    backup_nodes = page.locator("div.text-xs.opacity-70").all()
    for node in backup_nodes:
        raw = (node.inner_text() or "").strip()
        if "Последний подкреп" not in raw:
            continue

        container = node.locator("xpath=ancestor::div[.//div[contains(@class,'font-medium')]][1]")
        if container.count() == 0:
            container = node.locator("xpath=ancestor::div[contains(@class,'flex')][1]")
        if container.count() == 0:
            container = node.locator("xpath=ancestor::div[1]")

        fio_node = container.locator("div.font-medium")
        if fio_node.count() == 0:
            continue

        fio = (fio_node.first.inner_text() or "").strip()
        if not fio:
            continue

        rows.append(LeaderRow(
            fio=fio,
            last_backup_raw=raw,
            last_backup_dt=parse_backup_dt(raw) if raw else None
        ))
    return rows


def extract_notes_text(page) -> str:
    loc = page.locator("textarea#js-textarea-notes")
    if loc.count() == 0:
        loc = page.locator('textarea[data-notes-target="input"]')
    if loc.count() == 0:
        return ""
    return loc.first.input_value() or ""


def _playwright_fetch_in_process(profile_dir: str, url: str, out_q: mp.Queue, login: str = "", password: str = "") -> None:
    """Безопасный парсинг с Playwright"""
    try:
        with sync_playwright() as p:
            user_data_dir = Path(profile_dir)
            user_data_dir.mkdir(parents=True, exist_ok=True)

            def needs_login(page) -> bool:
                u = (page.url or "").lower()
                if any(x in u for x in ("login", "auth", "signin", "sign-in")):
                    return True
                try:
                    if page.locator("input[type='password']").count() > 0:
                        return True
                except Exception:
                    pass
                return False
            
            def do_auto_login(page) -> bool:
                """Автоматическая авторизация если есть логин и пароль"""
                if not login or not password:
                    return False
                try:
                    # Ищем поля логина и пароля
                    login_input = page.locator("#session_name, input[name='session[name]'], input[type='text']").first
                    password_input = page.locator("#session_password, input[name='session[password]'], input[type='password']").first
                    
                    if login_input.count() > 0 and password_input.count() > 0:
                        login_input.fill(login)
                        password_input.fill(password)
                        password_input.press("Enter")
                        page.wait_for_timeout(3000)  # Ждём авторизации
                        return True
                except Exception:
                    pass
                return False

            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                headless=True,
            )
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded")

            try:
                page.wait_for_selector("div.font-medium", timeout=10000)
            except Exception:
                pass

            if needs_login(page):
                # Пробуем автоматическую авторизацию
                if login and password:
                    do_auto_login(page)
                    page.goto(url, wait_until="domcontentloaded")
                    try:
                        page.wait_for_selector("textarea#js-textarea-notes, textarea[data-notes-target='input']", timeout=10000)
                    except Exception:
                        pass
                else:
                    # Если нет данных для авторизации - открываем видимый браузер
                    ctx.close()
                    ctx = p.chromium.launch_persistent_context(
                        user_data_dir=str(user_data_dir),
                        headless=False,
                    )
                    page = ctx.new_page()
                    page.goto(url, wait_until="domcontentloaded")
                    try:
                        page.wait_for_selector("textarea#js-textarea-notes, textarea[data-notes-target='input']", timeout=240000)
                    except Exception:
                        pass

            leaders: List[LeaderRow] = []
            notes: str = ""
            for _ in range(3):
                try:
                    leaders = extract_leaders_and_backups(page)
                    notes = extract_notes_text(page)
                    if leaders and notes is not None:
                        break
                except Exception:
                    pass
                page.wait_for_timeout(1200)

            ctx.close()

        out_q.put({"ok": True, "leaders": leaders, "notes": notes})
    except Exception as e:
        out_q.put({"ok": False, "error": str(e)})


class FlowFetchWorker(QThread):
    status = Signal(str)
    loaded = Signal(list, str)  # leaders, notes_text
    failed = Signal(str)

    def __init__(self, profile_dir: str, url: str, login: str = "", password: str = "", process_timeout_sec: int = 180):
        super().__init__()
        self.profile_dir = profile_dir
        self.url = url
        self.login = login
        self.password = password
        self.process_timeout_sec = process_timeout_sec

    def run(self):
        try:
            if self.login and self.password:
                self.status.emit("Загрузка user_flow… (автоматическая авторизация)")
            else:
                self.status.emit("Загрузка user_flow… (если нужна авторизация — откроется окно браузера)")
            q: mp.Queue = mp.Queue()
            p = mp.Process(target=_playwright_fetch_in_process, args=(self.profile_dir, self.url, q, self.login, self.password))
            p.start()
            p.join(timeout=self.process_timeout_sec)

            if p.is_alive():
                try:
                    p.terminate()
                except Exception:
                    pass
                self.failed.emit("Playwright превысил таймаут и был остановлен. Попробуй ещё раз.")
                return

            try:
                result = q.get_nowait()
            except Exception:
                result = {"ok": False, "error": "Не удалось получить результат Playwright (пустой ответ)."}

            if result.get("ok"):
                self.loaded.emit(result.get("leaders", []), result.get("notes", ""))
            else:
                self.failed.emit(result.get("error") or "Неизвестная ошибка Playwright")
        except Exception as e:
            self.failed.emit(str(e))


# ===========================
# NOTES PARSING
# ===========================

def parse_people_from_notes(notes_text: str) -> Tuple[List[PersonInfo], List[str]]:
    """Вытаскиваем ФИО из notes"""
    notes_text = notes_text or ""
    lines = [ln.rstrip("\n") for ln in notes_text.splitlines()]
    raw_lines = [ln for ln in lines]

    NAME_WORD = r"(?:[А-ЯЁA-Z][а-яёa-z\-]{1,}|[А-ЯЁA-Z]{2,}|[А-ЯЁA-Z])"
    fio_in_line_re = re.compile(rf"\b({NAME_WORD})\s+({NAME_WORD})(?:\s+({NAME_WORD}))?\b")

    not_name_words = {
        "генеральный", "генерального", "генеральная", "генеральной",
        "главный", "главного", "главная", "главной",
        "заместитель", "заместителя", "зам", "врио",
        "директор", "директора",
        "инженер", "инженера",
        "механик", "механика",
        "энергетик", "энергетика",
        "метролог", "метролога",
        "по", "управлению", "персоналом", "управления"
    }

    people: List[PersonInfo] = []
    seen_keys = set()

    def best_fio_in_line(line: str) -> Optional[str]:
        best = None
        best_score = -1
        for m in fio_in_line_re.finditer(line or ""):
            w1, w2, w3 = m.group(1), m.group(2), m.group(3)
            if not w1 or not w2:
                continue
            if len(w1) < 2:
                continue
            if w1.isupper() and len(w1) <= 3 and w2.isupper() and len(w2) <= 3:
                continue
            lw1 = _norm_fio_key(w1)
            lw2 = _norm_fio_key(w2)
            if lw1 in not_name_words or lw2 in not_name_words:
                continue
            words = [w1, w2] + ([w3] if w3 else [])
            if w3 and _norm_fio_key(w3) in not_name_words:
                words = [w1, w2]
            fio = " ".join(words).strip()
            sc = 0
            sc += 10 if len(words) == 3 else 0
            sc += 2 if (not w1.isupper()) else 0
            sc += 2 if (not w2.isupper()) else 0
            sc += 1 if (w3 and (not w3.isupper())) else 0
            if sc > best_score:
                best_score = sc
                best = fio
        return best

    for idx, line in enumerate(raw_lines):
        fio_raw = best_fio_in_line(line)
        if not fio_raw:
            continue
        fio_norm = normalize_fio_case(fio_raw.strip())
        key = _norm_fio_key(fio_norm)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        parts = _tokenize_ru_words(fio_norm)[:3]
        people.append(PersonInfo(fio=fio_norm, parts=parts, notes_line_idx=idx))

    return people, raw_lines


def resolve_person_for_leader(leader_text: str, people: List[PersonInfo]) -> Optional[PersonInfo]:
    """Сопоставление leader->person"""
    if not leader_text or not people:
        return None
    tokens = _tokenize_ru_words(leader_text)
    if not tokens:
        return None
    token_set = set(tokens)
    initials = set(re.findall(r"\b([а-яёa-z])\b", " ".join(tokens)))

    best = None
    best_score = 0
    surname_hits: Dict[str, int] = {}

    for p in people:
        parts = p.parts or _tokenize_ru_words(p.fio)
        if not parts:
            continue
        surname = parts[0]
        score = 0
        if surname in token_set:
            score += 50
            surname_hits[surname] = surname_hits.get(surname, 0) + 1
        if len(parts) >= 2 and parts[1] in token_set:
            score += 35
        if len(parts) >= 3 and parts[2] in token_set:
            score += 20
        if len(parts) >= 2 and parts[1][:1] and parts[1][:1] in initials:
            score += 6
        if len(parts) >= 3 and parts[2][:1] and parts[2][:1] in initials:
            score += 4
        overlap = sum(1 for w in parts[:3] if w in token_set)
        score += overlap * 3

        if score > best_score:
            best_score = score
            best = p

    if not best:
        return None

    best_parts = best.parts or _tokenize_ru_words(best.fio)
    if best_parts:
        surname = best_parts[0]
        if surname_hits.get(surname, 0) >= 2:
            has_name = len(best_parts) >= 2 and (best_parts[1] in token_set or best_parts[1][:1] in initials)
            if not has_name:
                return None

    if best_score < 55:
        return None
    return best


def context_lines(lines: List[str], center_idx: int, window: int = 3) -> List[Tuple[int, str]]:
    if not lines or center_idx is None:
        return []
    lo = max(0, center_idx - window)
    hi = min(len(lines) - 1, center_idx + window)
    out = []
    for i in range(lo, hi + 1):
        out.append((i, lines[i]))
    return out


# ===========================
# POSITION HISTORY
# ===========================

def history_path() -> Path:
    return Path("positions_history.json")


def load_positions_history(path: Path) -> Dict[str, str]:
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            out = {}
            for k, v in data.items():
                kk = _norm_fio_key(k)
                if kk and isinstance(v, str):
                    out[kk] = v.strip()
            return out
    except Exception:
        pass
    return {}


def save_positions_history(path: Path, hist: Dict[str, str]) -> None:
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        try:
            path.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


# ===========================
# OPENAI WORKER
# ===========================

class OpenAIImproveWorker(QThread):
    done = Signal(list)   # list[str] size=3
    failed = Signal(str)

    def __init__(self, api_key: str, text: str):
        super().__init__()
        self.api_key = (api_key or "").strip()
        self.text = (text or "").strip()

    def run(self):
        try:
            if not self.api_key:
                self.failed.emit("openai_api_key не задан в config.json")
                return
            if not self.text:
                self.failed.emit("Пустой текст для проверки")
                return

            prompt_system = (
                "Ты редактор кратких холодных приветствий на русском.\n"
                "Задача: улучшить пунктуацию/естественность/логику, НЕ меняя смысл.\n"
                "ЖЁСТКИЕ ПРАВИЛА:\n"
                "1) НЕ добавляй приветствия: 'Здравствуйте', 'Добрый день' и т.п.\n"
                "2) Шаблон НЕ менять. Сохраняй тот же старт, что в исходнике.\n"
                "3) Должность: внутри фразы всегда с маленькой буквы.\n"
                "4) Организация: замени на разговорный короткий вариант.\n"
                "5) Верни РОВНО 3 варианта.\n"
                "ФОРМАТ ОТВЕТА: строго JSON-массив из 3 строк (без комментариев)."
            )
            prompt_user = self.text

            variants: List[str] = []

            try:
                # Try new SDK style
                from openai import OpenAI
                client = OpenAI(api_key=self.api_key)
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": prompt_system},
                        {"role": "user", "content": prompt_user},
                    ],
                    temperature=0.5,
                    max_tokens=450,
                )
                content = (resp.choices[0].message.content or "").strip()
                variants = _parse_three_variants(content)
                variants = [abbreviate_position_ru(v) for v in variants]

            except ImportError as ie:
                self.failed.emit(
                    "Библиотека openai не установлена!\n\n"
                    "Установите её командой:\n"
                    "pip install openai\n\n"
                    "Или через:\n"
                    "pip install -r requirements.txt"
                )
                return
            except Exception as e:
                # Try old SDK style as fallback
                try:
                    import openai
                    openai.api_key = self.api_key
                    resp = openai.ChatCompletion.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": prompt_system},
                            {"role": "user", "content": prompt_user},
                        ],
                        temperature=0.5,
                        max_tokens=450,
                    )
                    content = (resp["choices"][0]["message"]["content"] or "").strip()
                    variants = _parse_three_variants(content)
                    variants = [abbreviate_position_ru(v) for v in variants]
                except ImportError:
                    self.failed.emit(
                        "Библиотека openai не установлена!\n\n"
                        "Установите её командой:\n"
                        "pip install openai\n\n"
                        "Или через:\n"
                        "pip install -r requirements.txt"
                    )
                    return
                except Exception as e2:
                    self.failed.emit(f"Ошибка API: {str(e2)}")
                    return

            if len(variants) != 3:
                self.failed.emit("Не удалось получить 3 варианта (ответ модели не распознан).")
                return

            self.done.emit(variants)

        except Exception as e:
            self.failed.emit(str(e))


def _parse_three_variants(text: str) -> List[str]:
    """Parse JSON array of 3 strings; fallback: split lines."""
    s = (text or "").strip()
    try:
        data = json.loads(s)
        if isinstance(data, list) and len(data) == 3 and all(isinstance(x, str) for x in data):
            return [re.sub(r"\s+", " ", x).strip() for x in data]
    except Exception:
        pass

    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    cleaned = []
    for ln in lines:
        ln2 = re.sub(r"^\s*[\-\*\d\)\.]+?\s*", "", ln).strip()
        if ln2:
            cleaned.append(ln2)
    if len(cleaned) >= 3:
        return cleaned[:3]

    return []


# ===========================
# DIALOGS
# ===========================

class PositionPickerDialog(QDialog):
    """Показывает контекст вокруг ФИО для выбора должности"""
    def __init__(self, parent: QWidget, fio: str, ctx_lines: List[Tuple[int, str]]):
        super().__init__(parent)
        self.setWindowTitle("Выбор должности из notes (выделением)")
        self.resize(860, 420)
        self._result_position = ""

        root = QVBoxLayout()

        root.addWidget(QLabel(
            f"ФИО: <b>{fio}</b><br>"
            f"Выдели мышью фрагмент текста (должность) в блоке ниже и нажми <b>Применить</b>."
        ))

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QTextEdit.NoWrap)
        self.text.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)

        rendered = []
        for i, ln in ctx_lines:
            rendered.append(f"{i+1:>4}: {ln}")
        self.text.setPlainText("\n".join(rendered))
        root.addWidget(self.text, 1)

        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton("Применить выделение")
        self.clear_btn = QPushButton("Очистить")
        btn_row.addWidget(self.apply_btn)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self.setLayout(root)

        self.apply_btn.clicked.connect(self._apply_selection)
        self.clear_btn.clicked.connect(self._clear_selection)

    def _clear_selection(self):
        cursor = self.text.textCursor()
        cursor.clearSelection()
        self.text.setTextCursor(cursor)

    def _apply_selection(self):
        cursor = self.text.textCursor()
        sel = cursor.selectedText()
        sel = sel.replace("\u2029", "\n")
        sel = _norm_text(sel)
        if not sel:
            QMessageBox.warning(self, "Нужно выделение", "Выдели мышью должность и нажми Применить.")
            return
        sel = re.sub(r"(?m)^\s*\d+\s*:\s*", "", sel).strip()
        sel = re.sub(r"\s+", " ", sel).strip()
        if not sel:
            QMessageBox.warning(self, "Пусто", "Не удалось извлечь должность из выделения.")
            return
        self._result_position = sel
        self.accept()

    def get_position(self) -> str:
        return self._result_position


class VariantsDialog(QDialog):
    """Показывает 3 варианта от ChatGPT"""
    def __init__(self, parent: QWidget, original: str, variants: List[str]):
        super().__init__(parent)
        self.setWindowTitle("Выбери вариант замены")
        self.resize(900, 500)
        self._chosen = ""

        root = QVBoxLayout()
        root.addWidget(QLabel("<b>Исходный вариант:</b>"))
        orig = QTextEdit()
        orig.setReadOnly(True)
        orig.setPlainText(original)
        orig.setFixedHeight(90)
        root.addWidget(orig)

        root.addWidget(QLabel("<b>Варианты от ChatGPT (выбери один и нажми Применить):</b>"))

        self.list = QListWidget()
        for v in variants:
            it = QListWidgetItem(v)
            self.list.addItem(it)
        self.list.setCurrentRow(0)
        root.addWidget(self.list, 1)

        btn_row = QHBoxLayout()
        self.apply_btn = QPushButton("Применить")
        self.cancel_btn = QPushButton("Отмена")
        btn_row.addWidget(self.apply_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        self.setLayout(root)

        self.apply_btn.clicked.connect(self._apply)
        self.cancel_btn.clicked.connect(self.reject)

    def _apply(self):
        it = self.list.currentItem()
        if not it:
            QMessageBox.warning(self, "Нужно выбрать", "Выбери один вариант из списка.")
            return
        self._chosen = it.text().strip()
        self.accept()

    def chosen_text(self) -> str:
        return self._chosen


# ===========================
# GREETING CARD WIDGET
# ===========================

class GreetingCard(QWidget):
    """Карточка с приветствиями для одного руководителя"""
    def __init__(self, title: str, greetings: List[str], api_key: str, status_cb):
        super().__init__()
        self.api_key = (api_key or "").strip()
        self.status_cb = status_cb

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel(title)
        header.setStyleSheet("font-weight: 600; font-size: 14px;")
        layout.addWidget(header)

        for g in greetings:
            row = QHBoxLayout()

            lbl = QLabel(g)
            lbl.setWordWrap(True)
            lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)

            btn_copy = QPushButton("Копировать")
            btn_copy.setFixedWidth(110)
            btn_copy.clicked.connect(lambda _=False, text=g: QGuiApplication.clipboard().setText(text))

            btn_improve = QPushButton("Улучшить")
            btn_improve.setFixedWidth(110)

            row.addWidget(lbl, 1)
            row.addWidget(btn_copy, 0)
            row.addWidget(btn_improve, 0)
            layout.addLayout(row)

            btn_improve.clicked.connect(lambda _=False, label=lbl: self._improve_text(label))

        self.setLayout(layout)
        self.setStyleSheet("""
            QWidget {
                background-color: #252526;
                border: 1px solid rgba(150,150,150,0.25);
                border-radius: 12px;
            }
        """)

    def _improve_text(self, label: QLabel):
        text = label.text().strip()
        if not text:
            return
        if not self.api_key:
            QMessageBox.warning(self, "Нет ключа", "В config.json не задан openai_api_key.")
            return

        self.status_cb("Отправляю запрос в ChatGPT…")
        w = OpenAIImproveWorker(self.api_key, text)

        def _ok(variants: List[str]):
            self.status_cb("Ответ от ChatGPT получен ✅")
            dlg = VariantsDialog(self, text, variants)
            if dlg.exec() == QDialog.Accepted:
                chosen = dlg.chosen_text().strip()
                if chosen:
                    label.setText(chosen)

        def _fail(err: str):
            self.status_cb("Ошибка ChatGPT")
            QMessageBox.warning(self, "ChatGPT", f"Не удалось получить варианты:\n{err}")

        w.done.connect(_ok)
        w.failed.connect(_fail)
        self._last_worker = w
        w.start()


# ===========================
# MAIN TAB WIDGET
# ===========================

class GreetingTab(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.sheets = None
        
        self._leaders: List[LeaderRow] = []
        self._notes_text: str = ""
        self._notes_lines: List[str] = []
        self._people: List[PersonInfo] = []
        
        self._history_file = history_path()
        self._pos_hist: Dict[str, str] = load_positions_history(self._history_file)
        self._pos_override: Dict[str, str] = {}
        
        self.init_ui()
        self.init_sheets_client()
    
    def init_ui(self):
        """Инициализация интерфейса"""
        main_layout = QVBoxLayout()
        
        # Статус бар
        self.status_label = QLabel("Готово.")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #bdbdbd; padding: 5px;")
        main_layout.addWidget(self.status_label)
        
        # Сплиттер для 3 колонок
        splitter = QSplitter(Qt.Horizontal)
        
        # === LEFT PANEL ===
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        # Поиск по дате
        date_group = QGroupBox("1️⃣ Поиск ИНН по дате")
        date_layout = QVBoxLayout()
        
        date_form = QFormLayout()
        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("23.12.2025")
        date_form.addRow("Дата:", self.date_edit)
        
        self.sheet_combo = QComboBox()
        date_form.addRow("Лист:", self.sheet_combo)
        
        date_layout.addLayout(date_form)
        
        date_btns = QHBoxLayout()
        self.refresh_sheets_btn = QPushButton("Обновить листы")
        self.refresh_sheets_btn.clicked.connect(self.on_refresh_sheets)
        date_btns.addWidget(self.refresh_sheets_btn)
        
        self.load_inns_btn = QPushButton("Найти ИНН")
        self.load_inns_btn.clicked.connect(self.on_load_inns)
        date_btns.addWidget(self.load_inns_btn)
        date_layout.addLayout(date_btns)
        
        date_group.setLayout(date_layout)
        left_layout.addWidget(date_group)
        
        # Список ИНН
        inn_group = QGroupBox("2️⃣ Выбери ИНН")
        inn_layout = QVBoxLayout()
        
        self.inn_list = QListWidget()
        self.inn_list.itemClicked.connect(self.on_inn_selected)
        inn_layout.addWidget(self.inn_list)
        
        inn_group.setLayout(inn_layout)
        left_layout.addWidget(inn_group, 1)
        
        # Информация о выборе
        info_group = QGroupBox("3️⃣ Выбранный ИНН")
        info_layout = QVBoxLayout()
        
        self.selected_inn_label = QLabel("ИНН: —")
        self.flow_id_label = QLabel("ID: —")
        info_layout.addWidget(self.selected_inn_label)
        info_layout.addWidget(self.flow_id_label)
        
        self.open_flow_btn = QPushButton("Открыть user_flow")
        self.open_flow_btn.setEnabled(False)
        self.open_flow_btn.clicked.connect(self.on_open_flow)
        info_layout.addWidget(self.open_flow_btn)
        
        info_group.setLayout(info_layout)
        left_layout.addWidget(info_group)
        
        left_panel.setLayout(left_layout)
        splitter.addWidget(left_panel)
        
        # === CENTER PANEL ===
        center_panel = QWidget()
        center_layout = QVBoxLayout()
        center_layout.setContentsMargins(5, 5, 5, 5)
        
        # Организация
        org_group = QGroupBox("4️⃣ Организация")
        org_layout = QVBoxLayout()
        
        self.org_edit = QLineEdit()
        self.org_edit.setPlaceholderText("Название появится автоматически (DaData)")
        org_layout.addWidget(self.org_edit)
        
        org_group.setLayout(org_layout)
        center_layout.addWidget(org_group)
        
        # Настройки
        settings_group = QGroupBox("5️⃣ Настройки генерации")
        settings_layout = QFormLayout()
        
        self.case_combo = QComboBox()
        self.case_combo.addItems(list(CASE_TO_TAGS.keys()))
        settings_layout.addRow("Падеж:", self.case_combo)
        
        self.name_format_combo = QComboBox()
        self.name_format_combo.addItems(["ФИО полностью", "Фамилия Имя", "Фамилия И.О."])
        settings_layout.addRow("Формат:", self.name_format_combo)
        
        settings_group.setLayout(settings_layout)
        center_layout.addWidget(settings_group)
        
        # Таблица руководителей
        leaders_group = QGroupBox("6️⃣ Руководители")
        leaders_layout = QVBoxLayout()
        
        self.leaders_table = QTableWidget(0, 3)
        self.leaders_table.setHorizontalHeaderLabels(["✓", "ФИО", "Подкреп"])
        self.leaders_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.leaders_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.leaders_table.setColumnWidth(0, 40)
        self.leaders_table.setColumnWidth(2, 180)
        self.leaders_table.horizontalHeader().setStretchLastSection(False)
        self.leaders_table.horizontalHeader().setDefaultSectionSize(150)
        self.leaders_table.cellDoubleClicked.connect(self.on_leader_double_click)
        leaders_layout.addWidget(self.leaders_table)
        
        hint = QLabel("💡 Двойной клик по ФИО — выбрать должность вручную")
        hint.setStyleSheet("color: #bdbdbd;")
        hint.setWordWrap(True)
        leaders_layout.addWidget(hint)
        
        self.generate_btn = QPushButton("✨ Сгенерировать приветствия")
        self.generate_btn.setEnabled(False)
        self.generate_btn.clicked.connect(self.on_generate)
        self.generate_btn.setStyleSheet("font-weight: bold; font-size: 14px;")
        leaders_layout.addWidget(self.generate_btn)
        
        leaders_group.setLayout(leaders_layout)
        center_layout.addWidget(leaders_group, 1)
        
        center_panel.setLayout(center_layout)
        splitter.addWidget(center_panel)
        
        # === RIGHT PANEL ===
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(5, 5, 5, 5)
        
        output_label = QLabel("7️⃣ Результат")
        output_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        right_layout.addWidget(output_label)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.out_container = QWidget()
        self.out_layout = QVBoxLayout()
        self.out_layout.setContentsMargins(8, 8, 8, 8)
        self.out_layout.setSpacing(10)
        self.out_container.setLayout(self.out_layout)
        self.scroll.setWidget(self.out_container)
        right_layout.addWidget(self.scroll, 1)
        
        self.copy_all_btn = QPushButton("📋 Скопировать всё одним блоком")
        self.copy_all_btn.setEnabled(False)
        self.copy_all_btn.clicked.connect(self.on_copy_all)
        right_layout.addWidget(self.copy_all_btn)
        
        right_panel.setLayout(right_layout)
        splitter.addWidget(right_panel)
        
        # Пропорции колонок
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 2)
        
        main_layout.addWidget(splitter, 1)
        self.setLayout(main_layout)
    
    def init_sheets_client(self):
        """Инициализация Google Sheets клиента"""
        try:
            sa_file = self.config.get("service_account_file", "service_account.json")
            if Path(sa_file).exists():
                self.sheets = SheetsClient(sa_file)
                self.set_status("Google Sheets клиент инициализирован ✅")
            else:
                self.set_status(f"⚠️ Файл {sa_file} не найден")
        except Exception as e:
            self.set_status(f"⚠️ Ошибка инициализации Sheets: {e}")
    
    def set_status(self, text: str):
        """Обновление статуса"""
        self.status_label.setText(text)
    
    def update_config(self, config):
        """Обновление конфигурации"""
        self.config = config
        self.init_sheets_client()
    
    def on_refresh_sheets(self):
        """Обновление списка листов"""
        if not self.sheets:
            QMessageBox.warning(self, "Ошибка", "Google Sheets клиент не инициализирован")
            return
        
        try:
            sheet_inn_id = self.config.get("sheet_inn_id", "")
            if not sheet_inn_id:
                QMessageBox.warning(self, "Ошибка", "Не указан sheet_inn_id в настройках (Ctrl+H)")
                return
            
            self.set_status("Загрузка списка листов...")
            titles = self.sheets.list_worksheets(sheet_inn_id)
            
            self.sheet_combo.clear()
            self.sheet_combo.addItems(titles)
            self.set_status(f"Загружено {len(titles)} листов ✅")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить листы:\n{e}")
            self.set_status("Ошибка загрузки листов ❌")
    
    def on_load_inns(self):
        """Поиск ИНН по дате"""
        if not self.sheets:
            QMessageBox.warning(self, "Ошибка", "Google Sheets клиент не инициализирован")
            return
        
        date_text = self.date_edit.text().strip()
        if not date_text:
            QMessageBox.warning(self, "Ошибка", "Введите дату")
            return
        
        sheet_title = self.sheet_combo.currentText()
        if not sheet_title:
            QMessageBox.warning(self, "Ошибка", "Выберите лист")
            return
        
        try:
            self.set_status("Поиск ИНН по дате...")
            sheet_inn_id = self.config.get("sheet_inn_id", "")
            inns = self.sheets.get_inns_by_date(sheet_inn_id, sheet_title, date_text)
            
            self.inn_list.clear()
            for inn in inns:
                self.inn_list.addItem(inn)
            
            self.set_status(f"Найдено {len(inns)} ИНН ✅")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось найти ИНН:\n{e}")
            self.set_status("Ошибка поиска ИНН ❌")
    
    def on_inn_selected(self, item):
        """Обработка выбора ИНН"""
        inn = item.text().strip()
        self.selected_inn_label.setText(f"ИНН: {inn}")
        
        # Получение flow_id
        try:
            sheet_map_id = self.config.get("sheet_map_id", "")
            sheet_map_tab = self.config.get("sheet_map_tab", "Айди")
            
            if not sheet_map_id:
                QMessageBox.warning(self, "Ошибка", "Не указан sheet_map_id в настройках (Ctrl+H)")
                return
            
            flow_id = self.sheets.get_flow_id_by_inn(sheet_map_id, sheet_map_tab, inn)
            
            if flow_id:
                self.flow_id_label.setText(f"ID: {flow_id}")
                self.open_flow_btn.setEnabled(True)
                self._current_flow_id = flow_id
                self._current_inn = inn
                
                # Автоматически получить название через DaData
                self.fetch_org_name(inn)
            else:
                self.flow_id_label.setText("ID: не найден")
                self.open_flow_btn.setEnabled(False)
                QMessageBox.warning(
                    self, 
                    "Не найден", 
                    f"Flow ID для ИНН {inn} не найден в таблице маппинга.\n\n"
                    f"Проверьте:\n"
                    f"- sheet_map_id: {sheet_map_id}\n"
                    f"- sheet_map_tab: {sheet_map_tab}"
                )
                
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось получить flow_id:\n{e}")
    
    def fetch_org_name(self, inn: str):
        """Получение названия организации через DaData"""
        token = self.config.get("dadata_token", "").strip()
        if not token:
            self.set_status("⚠️ DaData токен не настроен")
            return
        
        self.set_status("Запрос в DaData...")
        worker = DaDataWorker(inn, token)
        
        def on_done(name: str):
            if name:
                self.org_edit.setText(name)
                self.set_status("Название организации получено ✅")
            else:
                self.set_status("⚠️ Организация не найдена в DaData")
        
        def on_failed(err: str):
            self.set_status(f"⚠️ Ошибка DaData: {err}")
        
        worker.done.connect(on_done)
        worker.failed.connect(on_failed)
        self._dadata_worker = worker
        worker.start()
    
    def on_open_flow(self):
        """Открытие user_flow и парсинг"""
        flow_id = getattr(self, "_current_flow_id", None)
        if not flow_id:
            return
        
        url = f"https://api.itnelep.com/user_flows/{flow_id}"
        profile_dir = self.config.get("playwright_profile_dir", "./pw_profile")
        login = self.config.get("login", "")
        password = self.config.get("password", "")
        
        self.set_status("Запуск Playwright...")
        self.open_flow_btn.setEnabled(False)
        
        worker = FlowFetchWorker(profile_dir, url, login, password)
        
        def on_status(msg: str):
            self.set_status(msg)
        
        def on_loaded(leaders: List[LeaderRow], notes: str):
            self._leaders = leaders
            self._notes_text = notes
            self._people, self._notes_lines = parse_people_from_notes(notes)
            
            self.populate_leaders_table()
            self.generate_btn.setEnabled(True)
            self.open_flow_btn.setEnabled(True)
            self.set_status(f"Загружено {len(leaders)} руководителей ✅")
        
        def on_failed(err: str):
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные:\n{err}")
            self.set_status("Ошибка загрузки ❌")
            self.open_flow_btn.setEnabled(True)
        
        worker.status.connect(on_status)
        worker.loaded.connect(on_loaded)
        worker.failed.connect(on_failed)
        self._flow_worker = worker
        worker.start()
    
    def populate_leaders_table(self):
        """Заполнение таблицы руководителей"""
        self.leaders_table.setRowCount(0)
        
        warn_bg = QColor(60, 50, 40)
        warn_fg = QColor(255, 200, 100)
        
        for r, row in enumerate(self._leaders):
            self.leaders_table.insertRow(r)
            
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk_item.setCheckState(Qt.Unchecked)
            
            fio_card = normalize_fio_case(row.fio)
            match_text = fio_card
            
            person = resolve_person_for_leader(match_text, self._people)
            
            notes_idx = person.notes_line_idx if person else None
            fio_full = person.fio if person else fio_card
            
            fio_item = QTableWidgetItem(fio_full)
            
            backup_dt = row.last_backup_dt
            if backup_dt:
                backup_str = backup_dt.strftime("%d.%m.%Y %H:%M")
            else:
                m = re.search(r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})", row.last_backup_raw or "")
                backup_str = (m.group(1) + " " + m.group(2)) if m else (row.last_backup_raw or "").strip()
            
            backup_item = QTableWidgetItem(backup_str)
            backup_item.setToolTip(row.last_backup_raw or "")
            
            meta = {
                "fio_card": fio_card,
                "fio_full": fio_full,
                "notes_line_idx": notes_idx,
                "last_backup_raw": row.last_backup_raw or "",
                "last_backup_dt": backup_str,
            }
            fio_item.setData(Qt.UserRole, json.dumps(meta, ensure_ascii=False))
            
            if notes_idx is None:
                fio_item.setBackground(warn_bg)
                fio_item.setForeground(warn_fg)
                fio_item.setToolTip("Не найдено соответствие ФИО в notes")
            else:
                fio_item.setToolTip("Двойной клик — выбрать должность вручную")
            
            self.leaders_table.setItem(r, 0, chk_item)
            self.leaders_table.setItem(r, 1, fio_item)
            self.leaders_table.setItem(r, 2, backup_item)
        
        self.leaders_table.resizeColumnsToContents()
    
    def get_selected_leaders(self) -> List[Tuple[str, Optional[int]]]:
        """Получение выбранных руководителей"""
        out = []
        for r in range(self.leaders_table.rowCount()):
            chk = self.leaders_table.item(r, 0)
            fio_item = self.leaders_table.item(r, 1)
            if chk and chk.checkState() == Qt.Checked and fio_item:
                meta_raw = fio_item.data(Qt.UserRole)
                try:
                    meta = json.loads(meta_raw) if meta_raw else {}
                except Exception:
                    meta = {}
                fio_full = (meta.get("fio_full") or fio_item.text() or "").strip()
                notes_idx = meta.get("notes_line_idx", None)
                out.append((fio_full, notes_idx))
        return out
    
    def on_leader_double_click(self, row: int, col: int):
        """Двойной клик по руководителю для выбора должности"""
        if col != 1:
            return
        fio_item = self.leaders_table.item(row, 1)
        if not fio_item:
            return
        
        meta_raw = fio_item.data(Qt.UserRole)
        try:
            meta = json.loads(meta_raw) if meta_raw else {}
        except Exception:
            meta = {}
        
        fio_full = (meta.get("fio_full") or fio_item.text() or "").strip()
        notes_idx = meta.get("notes_line_idx", None)
        
        if notes_idx is None or not self._notes_lines:
            QMessageBox.warning(self, "Нет контекста", "Не удалось найти строку ФИО в notes")
            return
        
        ctx = context_lines(self._notes_lines, notes_idx, window=3)
        dlg = PositionPickerDialog(self, fio_full, ctx)
        if dlg.exec() == QDialog.Accepted:
            pos = dlg.get_position().strip()
            if pos:
                key = _norm_fio_key(fio_full)
                self._pos_override[key] = pos
                self._pos_hist[key] = pos
                save_positions_history(self._history_file, self._pos_hist)
                QMessageBox.information(self, "Сохранено", f"Должность сохранена:\n{fio_full}\n→ {pos}")
                self.set_status("Должность сохранена ✅")
    
    def _clear_output(self):
        """Очистка области вывода"""
        while self.out_layout.count():
            item = self.out_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
    
    def on_generate(self):
        """Генерация приветствий"""
        org = self.org_edit.text().strip()
        if not org or org.startswith("…"):
            QMessageBox.warning(self, "Нужно поле", "Дождитесь названия от DaData или впишите вручную")
            return
        
        org = normalize_org_name(org)
        
        selected = self.get_selected_leaders()
        if not selected:
            QMessageBox.warning(self, "Нужно выбрать", "Отметьте галочками руководителей")
            return
        
        case_key = self.case_combo.currentText()
        name_fmt_idx = self.name_format_combo.currentIndex()
        use_last_first = (name_fmt_idx == 1)
        use_short = (name_fmt_idx == 2)
        
        if _MORPH is None and case_key != "КТО (именительный)":
            QMessageBox.information(
                self,
                "Склонения",
                "Для склонений установите:\n"
                "pip install pymorphy2 pymorphy2-dicts-ru\n"
                "Сейчас будут использованы исходные формы."
            )
        
        self._clear_output()
        blocks_for_copy_all = []
        
        api_key = (self.config.get("openai_api_key") or "").strip()
        
        for fio_full, _notes_idx in selected:
            fio_full = normalize_fio_case(fio_full)
            
            key = _norm_fio_key(fio_full)
            post_raw = (self._pos_override.get(key) or self._pos_hist.get(key) or "").strip()
            
            fio_case = inflect_fio_ru(fio_full, case_key).strip()
            name_display = fio_to_short(fio_case) if use_short else (fio_to_last_first(fio_case) if use_last_first else fio_case)
            
            post_case = inflect_phrase_ru(post_raw, case_key).strip() if post_raw else ""
            post_case = _lower_first(post_case)
            post_case = abbreviate_position_ru(post_case)
            
            greetings = build_messages(name=name_display, post=post_case, org=org)
            
            title = f"{fio_full}" + (f" — {post_raw}" if post_raw else "")
            
            card = GreetingCard(title, greetings, api_key, self.set_status)
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
            self.out_layout.addWidget(card)
            
            blocks_for_copy_all.append(title + "\n" + "\n\n".join(greetings))
        
        self.out_layout.addStretch(1)
        self._all_copy_text = "\n\n".join(blocks_for_copy_all).strip()
        self.copy_all_btn.setEnabled(True)
        self.set_status("Готово: приветствия сформированы ✅")
    
    def on_copy_all(self):
        """Копирование всех приветствий"""
        text = getattr(self, "_all_copy_text", "").strip()
        if text:
            QGuiApplication.clipboard().setText(text)
            self.set_status("Скопировано одним блоком ✅")
    
    def cleanup(self):
        """Очистка ресурсов"""
        # Останавливаем worker'ы если они активны
        if hasattr(self, '_dadata_worker'):
            try:
                self._dadata_worker.quit()
                self._dadata_worker.wait()
            except:
                pass
        
        if hasattr(self, '_flow_worker'):
            try:
                self._flow_worker.quit()
                self._flow_worker.wait()
            except:
                pass
