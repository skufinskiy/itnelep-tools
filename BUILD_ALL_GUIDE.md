# 🚀 Универсальный скрипт сборки

## ⚡ Быстрый старт:

### На Windows:
```bash
python build_all.py
```
**Результат:** `ITNELEP_Tools.exe`

### На macOS:
```bash
python3 build_all.py
```
**Результат:** `ITNELEP Tools.app`

---

## 🎯 Что делает build_all.py:

1. ✅ **Автоматически определяет платформу** (Windows/macOS/Linux)
2. ✅ **Проверяет зависимости** (PyInstaller, Python версия)
3. ✅ **Устанавливает PyInstaller** если нужно
4. ✅ **Собирает правильный формат** (.exe на Windows, .app на macOS)
5. ✅ **Очищает временные файлы**
6. ✅ **Показывает инструкции** для другой платформы

---

## 📋 Альтернативные способы запуска:

### Windows:

```bash
# Способ 1: Универсальный скрипт
python build_all.py

# Способ 2: Через bat файл
BUILD.bat

# Способ 3: Старый способ (только .exe)
build_exe.bat
```

### macOS:

```bash
# Способ 1: Универсальный скрипт
python3 build_all.py

# Способ 2: Через shell скрипт
./build_macos.sh

# Способ 3: Напрямую PyInstaller
pyinstaller build_macos.spec
```

---

## ⚠️ Важно понимать:

### ❌ Невозможно:

- Создать .exe на Mac
- Создать .app на Windows
- Создать оба файла на одной машине

### ✅ Возможно:

- Создать .exe на Windows
- Создать .app на macOS
- Использовать CI/CD для автоматической сборки на обеих платформах

**Причина:** PyInstaller НЕ поддерживает кросс-компиляцию.

Подробнее: см. **CROSS_COMPILATION.md**

---

## 🔄 Workflow для обеих платформ:

### Вариант 1: Ручная сборка

**На Windows ПК:**
```bash
python build_all.py
# Получили: ITNELEP_Tools.exe ✅
```

**На Mac:**
```bash
python3 build_all.py
# Получили: ITNELEP Tools.app ✅
```

### Вариант 2: GitHub Actions (автоматика!)

1. **Настройте один раз:**
   - Скопируйте проект в GitHub репозиторий
   - GitHub Actions файл уже включен: `.github/workflows/build.yml`

2. **Создайте release:**
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

3. **Получите оба файла:**
   - GitHub автоматически соберёт .exe и .app
   - Скачайте из раздела "Releases"

**Преимущества:**
- ✅ Автоматическая сборка
- ✅ Не нужен Mac если у вас Windows (и наоборот)
- ✅ Профессиональный workflow
- ✅ Бесплатно для публичных репозиториев

---

## 📊 Сравнение методов:

| Метод | Команда | Платформа | Результат |
|-------|---------|-----------|-----------|
| build_all.py | `python build_all.py` | Текущая | .exe или .app |
| build_exe.bat | `build_exe.bat` | Windows | .exe |
| build_macos.sh | `./build_macos.sh` | macOS | .app |
| BUILD.bat | `BUILD.bat` | Windows | .exe |
| GitHub Actions | `git push` | Обе! | .exe + .app |

**Рекомендация:** Используйте `build_all.py` - самый универсальный!

---

## 🎨 Что происходит при сборке:

### Windows (.exe):

```
[DETECT] Platform: windows
[CHECK] Python version: 3.11.0
[CHECK] PyInstaller installed
[CLEAN] Removing previous builds...
[BUILD] Running PyInstaller with build_exe.spec...
  ... (5-10 минут) ...
[CLEAN] Removing temporary files...
✅ BUILD SUCCESSFUL!

📦 Output: ITNELEP_Tools.exe
📄 Don't forget: service_account.json

💻 To build for macOS (.app):
  1. Copy this project to a Mac
  2. Run: python3 build_all.py
```

### macOS (.app):

```
[DETECT] Platform: macos
[CHECK] Python version: 3.11.0
[CHECK] PyInstaller installed
[CLEAN] Removing previous builds...
[BUILD] Running PyInstaller with build_macos.spec...
  ... (5-10 минут) ...
[CLEAN] Removing temporary files...
✅ BUILD SUCCESSFUL!

📦 Output: ITNELEP Tools.app
📄 Don't forget: service_account.json

💻 To build for Windows (.exe):
  1. Copy this project to a Windows PC
  2. Run: python build_all.py
```

---

## 🔧 Опции и настройка:

### Очистка перед сборкой:

build_all.py автоматически очищает:
- `build/` - временные файлы PyInstaller
- `dist/` - предыдущие сборки
- Старые .exe/.app файлы

### Ручная очистка:

```bash
# Windows
rmdir /s /q build dist
del ITNELEP_Tools.exe

# macOS
rm -rf build dist "ITNELEP Tools.app"
```

### Если сборка не удалась:

```bash
# Переустановите PyInstaller
pip uninstall pyinstaller
pip install pyinstaller

# Попробуйте снова
python build_all.py --clean
```

---

## 📚 Связанная документация:

- **CROSS_COMPILATION.md** - Почему нельзя создать оба файла на одной машине
- **BUILD_EXE_GUIDE.md** - Подробно про Windows сборку
- **BUILD_MACOS_GUIDE.md** - Подробно про macOS сборку
- **README_EXE.md** - Инструкция для пользователей Windows
- **README_MACOS.md** - Инструкция для пользователей macOS

---

## ✅ Итого:

**Для простоты:**
```bash
python build_all.py
```
Этот скрипт делает всё автоматически!

**Для автоматизации:**
Используйте GitHub Actions - соберёт на обеих платформах автоматически!

**Для понимания:**
Читайте CROSS_COMPILATION.md - узнаете почему так работает!

🚀 **Удачной сборки!**
