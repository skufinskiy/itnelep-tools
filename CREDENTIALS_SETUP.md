# 🔑 Настройка credentials для разработки

## 📋 Для локальной разработки:

### Шаг 1: Скопируйте example файлы

```bash
# В папке проекта
cp service_account.json.example service_account.json
cp credentials.json.example credentials.json
cp config.json config.json  # если нет
```

### Шаг 2: Заполните реальными данными

#### service_account.json:

1. Откройте Google Cloud Console
2. Создайте Service Account
3. Скачайте JSON ключ
4. Замените содержимое `service_account.json`

#### credentials.json:

1. Откройте Google Cloud Console
2. Создайте OAuth 2.0 Client ID
3. Скачайте JSON
4. Замените содержимое `credentials.json`

#### config.json:

Заполните:
```json
{
  "login": "ваш_логин_itnelep",
  "password": "ваш_пароль_itnelep",
  "spreadsheet_id": "id_вашей_таблицы",
  "sheet_inn_id": "",
  "sheet_map_id": "id_вашей_таблицы",
  "sheet_map_tab": "Айди",
  "service_account_file": "service_account.json",
  "dadata_token": "ваш_dadata_token",
  "openai_api_key": "ваш_openai_key",
  "credentials_file": "credentials.json"
}
```

### Шаг 3: Готово!

Теперь можете запускать:
```bash
python start.py
```

---

## ⚠️ ВАЖНО:

### НЕ загружайте в Git:

- ❌ `service_account.json` (реальный)
- ❌ `credentials.json` (реальный)
- ❌ `config.json` (с вашими данными)

Они уже в `.gitignore`!

### Можно загружать:

- ✅ `service_account.json.example`
- ✅ `credentials.json.example`
- ✅ Весь остальной код

---

## 🔒 Безопасность:

Если случайно загрузили секретные файлы:

```bash
# 1. Удалите из Git истории
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch service_account.json" \
  --prune-empty --tag-name-filter cat -- --all

# 2. Force push
git push origin --force --all

# 3. Немедленно смените credentials в Google Cloud!
```

---

## 📊 Структура файлов:

```
проект/
├── service_account.json           ← реальный (в .gitignore)
├── service_account.json.example   ← шаблон (в Git) ✅
├── credentials.json               ← реальный (в .gitignore)
├── credentials.json.example       ← шаблон (в Git) ✅
├── config.json                    ← ваш (в .gitignore)
└── .gitignore                     ← защита
```

---

## 🎯 Итог:

1. Example файлы = шаблоны в Git
2. Реальные файлы = только на вашем компьютере
3. .gitignore = защита от случайной загрузки

**Ваши секреты в безопасности!** 🔒
