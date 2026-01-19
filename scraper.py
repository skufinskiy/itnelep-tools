import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


class Scraper:
    def __init__(self, headless: bool = False):
        options = Options()
        options.add_argument("--window-size=1500,1000")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--log-level=3")

        if headless:
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 20)

    def login(self, username, password):
        self.driver.get("https://api.itnelep.com/sign_in")

        name = self.wait.until(EC.presence_of_element_located((By.ID, "session_name")))
        pwd = self.driver.find_element(By.ID, "session_password")

        name.clear()
        pwd.clear()
        name.send_keys(username)
        pwd.send_keys(password)
        pwd.submit()

        self.wait.until_not(EC.url_contains("sign_in"))

    def _read_filter_count(self):
        """
        Читает:
        <span data-creeps-target="filterCount">Показано контактов: 96</span>
        и возвращает 96.
        """
        try:
            el = self.wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//span[@data-creeps-target='filterCount']")
                )
            )
            nums = re.findall(r"\d+", el.text)
            return int(nums[-1]) if nums else 0
        except:
            return 0

    def _extract_rich(self, text):
        """
        '💰 Богатых (>1 500 000₽): 45 (старых: 34, молодых: 11)'
        → 45
        """
        m = re.search(r"Богатых[^:]*:\s*([\d\s]+)", text)
        if m:
            digits = re.sub(r"\D", "", m.group(1))
            if digits:
                return int(digits)
        return 0

    def _extract_first_number_by_xpath(self, xpath):
        """
        Универсальный помощник: берёт ПЕРВОЕ число в тексте элемента.
        Используем, например, для 'Контактов Himera Finance: 142'
        """
        try:
            el = self.wait.until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            nums = re.findall(r"\d+", el.text)
            return int(nums[0]) if nums else 0
        except:
            return 0

    def _extract_old_without_delay(self):
        """
        Специальный разбор строки:
        '👴 Старых без отложки (55+): 97 (с тг: 11)'
        Нужно взять ЧИСЛО ПОСЛЕ ДВОЕТОЧИЯ → 97
        а не первое число (55).
        """
        try:
            el = self.wait.until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        "//p[contains(@class,'text-base-content') and contains(text(),'Старых без отложки')]",
                    )
                )
            )
            text = el.text
            # Ищем именно число после двоеточия
            m = re.search(r"Старых без отложки.*?:\s*([\d\s]+)", text)
            if m:
                digits = re.sub(r"\D", "", m.group(1))
                if digits:
                    return int(digits)

            # Фоллбэк: если по какой-то причине не нашли — берём второе число
            nums = re.findall(r"\d+", text)
            if len(nums) >= 2:
                return int(nums[1])
            return 0
        except:
            return 0

    def apply_filters(self, flt):
        """
        Применяем фильтры на странице и возвращаем количество контактов
        после фильтрации (по span[data-creeps-target="filterCount"]).
        """
        # Базовый фильтр 2 месяца + ошибки
        try:
            elem = self.wait.until(
                EC.element_to_be_clickable((By.ID, "filter-combined-ready-2months"))
            )
            self.driver.execute_script("arguments[0].click();", elem)
        except:
            pass
        time.sleep(2)

        if flt.get("old"):
            try:
                elem = self.wait.until(
                    EC.element_to_be_clickable((By.ID, "filter-old"))
                )
                self.driver.execute_script("arguments[0].click();", elem)
            except:
                pass
            time.sleep(2)

        if flt.get("min_deposit") is not None:
            try:
                elem = self.wait.until(
                    EC.element_to_be_clickable((By.ID, "filter-min-deposits"))
                )
                self.driver.execute_script("arguments[0].click();", elem)
            except:
                pass
            time.sleep(2)

            try:
                fld = self.wait.until(
                    EC.presence_of_element_located((By.ID, "min-deposits-amount"))
                )
                fld.clear()
                fld.send_keys(str(flt["min_deposit"]))
            except:
                pass

        time.sleep(5)
        return self._read_filter_count()

    def parse_metrics(self):
        """
        Читаем:

        👥 Всего контактов: 720
        💰 Богатых (>1 500 000₽): 45 (старых: 34, молодых: 11)
        🪙 Контактов Himera Finance: 142
        👴 Старых без отложки (55+): 97 (с тг: 11)
        """
        # 👥 Всего контактов
        total_el = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//p[contains(text(),'Всего контактов')]")
            )
        )
        total = int(re.findall(r"\d+", total_el.text)[-1])

        # 💰 Богатых (>1 500 000₽)
        rich_el = self.wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//p[contains(@class,'text-base-content') and contains(text(),'Богатых')]",
                )
            )
        )
        rich = self._extract_rich(rich_el.text)

        # 🪙 Контактов Himera Finance: 142  → берём первое число
        himera_finance = self._extract_first_number_by_xpath(
            "//p[contains(@class,'text-base-content') and contains(text(),'Контактов Himera Finance')]"
        )

        # 👴 Старых без отложки (55+): 97 (с тг: 11) → берём число после двоеточия
        old_without_delay = self._extract_old_without_delay()

        return total, rich, himera_finance, old_without_delay

    def parse_supports(self):
        """
        Собираем подкрепы: Имя — дата
        """
        try:
            names = self.driver.find_elements(By.CSS_SELECTOR, "div.font-medium")
            dates = self.driver.find_elements(
                By.CSS_SELECTOR, "div.text-xs.opacity-70"
            )

            res = []
            for n, d in zip(names, dates):
                nm = n.text.strip()
                dt = d.text.replace("Последний подкреп:", "").strip()
                if nm and dt:
                    res.append(f"{nm} — {dt}")
            return res
        except:
            return []

    def process_record(self, inn, userflow_id, filters):
        try:
            self.driver.get(f"https://api.itnelep.com/user_flows/{userflow_id}")
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            filtered = self.apply_filters(filters)
            total, rich, himera_finance, old_without_delay = self.parse_metrics()
            supports = self.parse_supports()

            return {
                "total": total,
                "rich": rich,
                "filtered": filtered,
                "himera_finance": himera_finance,
                "old_without_delay": old_without_delay,
                "supports": supports,
                "status": "OK",
            }

        except Exception as e:
            return {
                "total": None,
                "rich": None,
                "filtered": None,
                "himera_finance": None,
                "old_without_delay": None,
                "supports": [],
                "status": f"Ошибка: {e}",
            }

    def quit(self):
        try:
            self.driver.quit()
        except:
            pass
