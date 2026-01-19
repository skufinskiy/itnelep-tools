import gspread
from oauth2client.service_account import ServiceAccountCredentials


class GoogleSheetsAPI:
    def __init__(self, creds_file, spreadsheet_id):
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            creds_file, scope
        )
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)

    def get_sheet(self, sheet_name):
        return self.spreadsheet.worksheet(sheet_name)

    def get_sheet_names(self):
        return [ws.title for ws in self.spreadsheet.worksheets()]

    def get_inn_id_mapping(self):
        """
        Лист "Айди":
        A — ИНН
        B — user_flow_id
        """
        ws = self.spreadsheet.worksheet("Айди")
        data = ws.get_all_values()
        mapping = {}
        for row in data[1:]:
            if len(row) < 2:
                continue
            inn = (row[0] or "").strip()
            user_flow_id = (row[1] or "").strip()
            if inn and user_flow_id:
                mapping[inn] = user_flow_id
        return mapping

    def update_row_metrics(
        self,
        sheet_name: str,
        row: int,
        total,
        rich,
        filtered,
        himera_finance,
        old_without_delay,
    ):
        """
        Запись метрик по одной строке:

        E — 👥 Всего контактов
        F — 💰 Богатых (>1 500 000₽)
        G — Показано контактов (после фильтров)
        H — "Контактов Himera Finance | Старых без отложки", например "142 | 97"
        """
        ws = self.get_sheet(sheet_name)

        if himera_finance is not None and old_without_delay is not None:
            h_value = f"{himera_finance} | {old_without_delay}"
        else:
            h_value = ""

        values = [total, rich, filtered, h_value]
        ws.update(f"E{row}:H{row}", [values])

    def update_supports(self, sheet_name, row, text: str):
        """
        Подкрепы пишем в колонку K.
        """
        ws = self.get_sheet(sheet_name)
        ws.update(f"K{row}", [[text]])
