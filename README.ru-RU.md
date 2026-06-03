# WizTree CLI Agent

[![Version](https://img.shields.io/badge/version-1.5.0-blue.svg)](https://github.com/wiztree-cli-agent)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-400%2B%20passed-brightgreen.svg)](docs/TEST_REPORT.md)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

<p align="center">
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp;
  <a href="README.zh-CN.md">🇨🇳 中文</a> &nbsp;|&nbsp;
  <a href="README.fr-FR.md">🇫🇷 Français</a> &nbsp;|&nbsp;
  <a href="README.de-DE.md">🇩🇪 Deutsch</a> &nbsp;|&nbsp;
  <a href="README.ja-JP.md">🇯🇵 日本語</a> &nbsp;|&nbsp;
  <b><a href="README.ru-RU.md">🇷🇺 Русский</a></b>
</p>

> **ИИ-ассистент для очистки дискового пространства** — обёртка над WizTree CLI с интеграцией нескольких LLM-провайдеров,
> гибкой маршрутизацией запросов и безопасным удалением файлов через человеко-машинное взаимодействие.

---

## 📋 Содержание

- [Обзор проекта](#обзор-проекта)
- [Ключевые возможности](#ключевые-возможности)
- [Скриншоты](#скриншоты)
- [Быстрый старт](#быстрый-старт)
- [Архитектура](#архитектура)
- [LLM Router](#llm-router)
- [Конфигурация](#конфигурация)
- [Тестирование](#тестирование)
- [Лицензия](#лицензия)

---

## Обзор проекта

**WizTree CLI Agent** — это интеллектуальный помощник для анализа и очистки дискового пространства,
построенный на базе утилиты [WizTree](https://diskanalyzer.com/) и больших языковых моделей (LLM).

Проект решает три ключевые задачи:

1. **Быстрое сканирование** — использует WizTree CLI для чтения Master File Table (MFT) NTFS,
   обеспечивая сканирование диска за секунды вместо минут.
2. **Умный анализ** — через LLM Router (6 провайдеров, 4 стратегии маршрутизации) или встроенный
   RuleEngine (10 правил) определяет, какие файлы можно безопасно удалить.
3. **Безопасное удаление** — многоуровневая защита: чёрный список (38 системных путей),
   проверка файлов, SQLite-журнал аудита, диалог подтверждения, удаление в корзину.

---

## Ключевые возможности

### ⚡ Интеграция с WizTree CLI

- Прямое чтение MFT NTFS для молниеносного сканирования
- Парсинг CSV-вывода WizTree с потоковой обработкой
- Кэш результатов сканирования (TTL 1 час)
- Рекурсивный поиск по маске, глубокий поиск по каталогам
- Фильтрация по размеру, типу, дате изменения

### 🤖 LLM Router — универсальный шлюз ИИ

- **6 провайдеров**: DeepSeek, OpenAI, Anthropic, OpenRouter, SiliconFlow, Ollama
- **4 стратегии маршрутизации**: стоимость (COST), задержка (LATENCY), отказоустойчивость (FALLBACK), ручной выбор (MANUAL)
- **Динамическая маршрутизация**: LatencyProbe для измерения реальной скорости ответа, WeightedRouter для взвешенного распределения
- **Circuit Breaker**: автоматическое отключение проблемного провайдера после 3 ошибок, попытка восстановления через 60 с
- **batch_chat + RequestCoalescer**: объединение множественных запросов в пакеты для снижения затрат
- **Streaming JSON Parser**: потоковый разбор JSON-ответа от LLM с отображением в реальном времени

### 🛡️ RuleEngine — работа без API-ключа

- 10 предопределённых правил очистки: временные файлы, кэш браузеров, логи, установочные пакеты, корзина, `%TEMP%`, кэш npm/pip, prefetch, дампы памяти, папки `node_modules`
- Автоматическое переключение при отсутствии API-ключа (Lazy Init)
- Каждое правило включает описание, образец пути, риск-уровень и приоритет

### 🔒 Безопасность

- **Чёрный список** (Blocklist): 38 защищённых системных путей (Windows\System32, Program Files, корневые каталоги и т.д.)
- **Валидация файлов** (FileValidator): проверка существования, блокировки процессами, прав доступа
- **Журнал аудита** (AuditLogger): SQLite-лог всех деструктивных операций с возможностью восстановления
- **Диалог подтверждения** (ConfirmDialog): обязательное ручное подтверждение перед каждым удалением
- **Отправка в корзину**: приоритетное использование `send2trash` вместо необратимого удаления
- **Diff Preview**: просмотр деталей файла (размер, дата изменения) с предупреждением перед удалением

### 🎨 Графический интерфейс (GUI)

- **customtkinter**: современный интерфейс с настраиваемой темой
- **6 тёмных тем**: Steam Dark, Catppuccin Mocha, OLED Black, GitHub Dark, Nord, Dracula
- **TreemapView**: визуализация распределения файлов по размеру (алгоритм Squarified Treemap Bruls et al. 2000, чистая реализация Python)
- **SmoothProgressBar**: анимация прогресса 60fps
- **SkeletonScreen**: скелетная загрузка для улучшения восприятия производительности
- **Статус-бар**: отображение состояния (сканирование / анализ / готово / ошибка)
- **Горячие клавиши**: Ctrl+S (сканирование), Ctrl+R (обновление вкладки), Ctrl+L (очистка), Ctrl+, (настройки), Esc (отмена)
- **Drag & Drop**: перетаскивание папок и файлов в окно через tkinterdnd2
- **Вкладки**: файловые действия, история операций с восстановлением, каталог моделей, редактор промптов

### 💻 Командная строка (CLI)

- Интерактивный, пакетный и скриптовый режимы
- **--batch / --batch-file**: пакетное сканирование нескольких путей
- **--json / --csv**: экспорт результатов в JSON или CSV
- **--quiet**: подавление вывода (только ошибки)
- **--no-color**: отключение цветного вывода
- **Коды возврата**: 0 (успех), 1 (ошибка), 2 (неверные аргументы)
- **OutputFormatter**: единый интерфейс форматирования текста / JSON / CSV

### 📦 Производительность (v1.4.0+)

- **Virtual scrolling** (VirtualTreeview): рендеринг только видимых строк таблицы при навигации
- **__slots__ память**: оптимизация FileInfo через `__slots__` для снижения потребления ОЗУ
- **Кэш сканирования**: автоматическое кэширование результатов с TTL 1 час
- **Потоковый парсер CSV**: обработка больших CSV-файлов WizTree без полной загрузки в память
- **Экспорт в JSON/CSV** через единый модуль `src/exporters/`

---

## Скриншоты

![WizTree CLI Agent](docs/screenshot.png)

*Главное окно приложения с Treemap-визуализацией, панелью конфигурации и таблицей результатов.*

---

## Быстрый старт

### Установка

**Требования:** Python 3.10+, WizTree CLI (для сканирования).

```bash
pip install -r requirements.txt
```

### Запуск

```bash
# CLI-режим (без API-ключа — используется RuleEngine)
python app.py --cli

# Интерактивный режим
python cli.py --interactive

# Сканирование и анализ (указание пути)
python cli.py --scan "C:\Users" --analyze

# Пакетное сканирование нескольких путей
python cli.py --batch --batch-file paths.txt

# Экспорт результатов в JSON
python cli.py --scan "D:\Downloads" --analyze --json --output results.json

# GUI-режим (требуется tkinter)
python app.py

# Альтернативный запуск через bat-файлы:
.\run_cli.bat
.\run_gui.bat
```

### Первоначальная настройка

```bash
# Установка переменной окружения для LLM (опционально — без неё работает RuleEngine)
set DEEPSEEK_API_KEY=sk-your-key

# Или используйте безопасное хранилище credentials (v1.2.0+):
# через GUI: Settings → Credentials
```

---

## Архитектура

```
┌──────────────────────────────────────────────────────────────────┐
│                       WizTree CLI Agent                           │
│                          │                                       │
│    ┌─────────────────────┼─────────────────────┐                 │
│    │                     │                     │                 │
│    ▼                     ▼                     ▼                 │
│ ┌──────────┐       ┌──────────┐         ┌──────────┐            │
│ │ Scanner  │       │ Analyzer │         │  Safety  │            │
│ │ (сканер) │       │ (анализ) │         │ (безоп.) │            │
│ └────┬─────┘       └────┬─────┘         └────┬─────┘            │
│      │                  │                     │                  │
│      ▼            ┌─────┴─────┐               ▼                  │
│ ┌─────────┐  ┌──────────┐ ┌────────┐  ┌─────────────┐          │
│ │WizTree  │  │ LLMRouter│ │ Rule   │  │  Blocklist  │          │
│ │  CLI    │  │ 6 Prov.  │ │ Engine │  │ (38 путей)  │          │
│ └─────────┘  │ 4 Страт. │ │10 прав.│  │ AuditLogger │          │
│              └──────────┘ └────────┘  │ FileValidator│          │
│                                       │ ConfirmDialog│          │
│                                       └─────────────┘          │
└──────────────────────────────────────────────────────────────────┘
```

### Модули

| Модуль | Описание | Ключевые компоненты |
|--------|----------|---------------------|
| **Scanner** | Обёртка над WizTree CLI, сканирование MFT, рекурсивный поиск | `WizTreeScanner`, `DeepSearcher`, `PathValidator`, `ScanProgress`, `ScanOptions` |
| **Analyzer** | Анализ файлов через LLM или RuleEngine | `LLMRouter`, `LLMAnalyzer`, `RuleEngine`, `StreamingJsonParser`, `ModelCatalog`, `PromptStore` |
| **Safety** | Многоуровневая защита от небезопасных операций | `Blocklist`, `AuditLogger`, `FileValidator`, `ConfirmDialog`, `ComprehensiveSafetyManager` |
| **UI** | Графический интерфейс на customtkinter | `MainWindow`, `TreemapView`, `ModernTheme`, `SmoothProgressBar`, `SkeletonWidget`, `StatusBar`, `FileTable` |
| **Models** | Модели данных | `FileInfo`, `ScanResult`, `AnalysisResult`, `RiskLevel` |
| **Utils** | Утилиты | `ConfigLoader` (3-уровневая конфигурация), `CredentialStore` (keyring) |
| **Exporters** | Экспорт результатов | JSON, CSV экспорт |

### Поток данных

```
Пользовательский ввод (CLI / GUI)
        │
        ▼
  Scanner ──▶ WizTree CLI ──▶ CSV ──▶ FileInfo[]
        │
        ▼
  Analyzer ──▶ LLM Router (если есть API-ключ)
        │              └── LatencyProbe + WeightedRouter + Circuit Breaker
        │         или RuleEngine (без ключа, 10 правил)
        │
        ▼
  Safety  ──▶ Blocklist ──▶ FileValidator ──▶ AuditLogger
        │                                          │
        ▼                                          ▼
  ConfirmDialog ──▶ send2trash (корзина) ──▶ Запись аудита
```

---

## LLM Router

**LLMRouter** (`src/analyzer/llm_router.py:97`) — центральный компонент маршрутизации запросов
к большим языковым моделям. Поддерживает 6 провайдеров, 4 стратегии маршрутизации,
автоматический Circuit Breaker и пакетную обработку.

### Поддерживаемые провайдеры

| Провайдер | Переменная окружения | Бесплатные модели | Особенности |
|-----------|---------------------|-------------------|-------------|
| **DeepSeek** | `DEEPSEEK_API_KEY` | `deepseek-v4-flash` | Прямое подключение из Китая, отличное соотношение цены и качества |
| **OpenAI** | `OPENAI_API_KEY` | — | GPT-4o-mini, широкая совместимость |
| **Anthropic** | `ANTHROPIC_API_KEY` | — | Claude-3-haiku, длинный контекст |
| **OpenRouter** | `OPENROUTER_API_KEY` | `gemini-2.0-flash-exp:free` | Агрегатор 315+ моделей |
| **SiliconFlow** | `SILICONFLOW_API_KEY` | `DeepSeek-V3`, `Qwen2.5-7B` | Бесплатные модели из Китая |
| **Ollama** | Не требуется | `llama3.2`, `qwen2.5` | Локальный запуск, полная бесплатность |

### Стратегии маршрутизации

| Стратегия | Константа | Поведение | Сценарий использования |
|-----------|-----------|-----------|----------------------|
| **Стоимость** | `COST` | Выбор самой дешёвой модели | Ограниченный бюджет |
| **Задержка** | `LATENCY` | Выбор самого быстрого провайдера | Требуется быстрый ответ |
| **Отказоуст.** | `FALLBACK` | Автоматическое переключение на следующий доступный провайдер | Максимальная надёжность |
| **Ручной** | `MANUAL` | Использование только указанного провайдера | Точный контроль |

### Circuit Breaker

```
CLOSED (норма) → 3 ошибки → OPEN (отказ) → 60 с таймаут → HALF_OPEN (тест) → CLOSED
```

### Пример использования

```python
from src.analyzer import LLMRouter, RoutingStrategy

# Создание роутера
router = LLMRouter(
    strategy=RoutingStrategy.FALLBACK,
    default_model="deepseek-v4-flash"
)

# Отправка запроса
response = router.chat(
    messages=[{"role": "user", "content": "Какие файлы можно безопасно удалить?"}],
    model="deepseek-v4-flash"
)

# Смена стратегии
router.set_strategy(RoutingStrategy.COST)     # стоимость
router.set_strategy(RoutingStrategy.LATENCY)  # скорость

# Пакетный запрос (v1.5.0)
responses = router.batch_chat([
    {"role": "user", "content": "Анализ 1"},
    {"role": "user", "content": "Анализ 2"}
])
```

### Правила движка (10 правил)

| # | Правило | Описание | Пример пути | Риск |
|---|---------|----------|-------------|------|
| 1 | `temp_files` | Временные файлы Windows | `%TEMP%\*.tmp` | LOW |
| 2 | `browser_cache` | Кэш браузеров | `AppData\Local\*\Cache\*` | MEDIUM |
| 3 | `log_files` | Лог-файлы | `*.log` | LOW |
| 4 | `installers` | Установочные пакеты | `*.msi`, `*.exe` | MEDIUM |
| 5 | `recycle_bin` | Корзина | `$Recycle.Bin` | LOW |
| 6 | `temp_system` | Системный TEMP | `Windows\Temp\*` | LOW |
| 7 | `npm_cache` | Кэш npm | `node_modules\*` | HIGH |
| 8 | `pip_cache` | Кэш pip | `pip\cache\*` | LOW |
| 9 | `prefetch` | Prefetch-файлы | `Windows\Prefetch\*` | MEDIUM |
| 10 | `memory_dumps` | Дампы памяти | `*.dmp` | HIGH |

---

## Конфигурация

### Переменные окружения для API-ключей

```bash
# Windows CMD
set DEEPSEEK_API_KEY=sk-your-key
set OPENAI_API_KEY=sk-your-key
set ANTHROPIC_API_KEY=sk-ant-your-key
set OPENROUTER_API_KEY=sk-your-key
set SILICONFLOW_API_KEY=sk-your-key

# PowerShell
$env:DEEPSEEK_API_KEY = "sk-your-key"
```

> **Без API-ключа** система автоматически переключается на RuleEngine (10 правил).
> Для безопасного хранения ключей используйте встроенное хранилище credentials на базе keyring
> (Windows Credential Manager / DPAPI, macOS Keychain, Linux Secret Service).

### Конфигурация LLM Router

Файл: `config/llm_config.json` (автоматически мигрируется в `~/.wiztree-cli-agent/config.json`)

```json
{
  "strategy": "fallback",
  "default_model": "deepseek-v4-flash",
  "timeout": 30000,
  "max_retries": 2,
  "providers": [
    {
      "name": "deepseek",
      "base_url": "https://api.deepseek.com",
      "api_key_env": "DEEPSEEK_API_KEY",
      "priority": 1,
      "models": [
        {
          "id": "deepseek-v4-flash",
          "cost_input": 0.14,
          "cost_output": 0.28,
          "context_window": 1000000
        }
      ]
    }
  ]
}
```

### 3-уровневая конфигурация (v1.2.0+)

```
Уровень 1: Встроенные умолчания   (ConfigLoader, хардкод)
Уровень 2: Пользовательский файл  (~/.wiztree-cli-agent/config.json)
Уровень 3: Переопределения в ОЗУ  (runtime, не сохраняются)
```

Приоритет: `override > пользовательский > встроенный`

### Справочные цены на модели (на 1M токенов)

| Модель | Ввод | Вывод |
|--------|------|-------|
| DeepSeek V4 Flash | $0.14 | $0.28 |
| DeepSeek V4 Pro | $0.44 | $0.87 |
| GPT-4o-mini | $0.15 | $0.60 |
| Claude-3-haiku | $0.25 | $1.25 |

---

## Тестирование

### Запуск тестов

```bash
# Все тесты
pytest tests/ -v

# Конкретный модуль
pytest tests/test_scanner.py -v
pytest tests/test_safety.py -v

# Тесты LLM Router
pytest tests/test_router.py -v
pytest tests/test_router_v150.py -v

# Интеграционные тесты
pytest tests/test_integration_v150.py -v

# UI-тесты
pytest tests/test_ui.py -v

# Демонстрация роутера
python tests/demo_router.py

# С отчётом о покрытии
pytest tests/ --cov=src --cov-report=html
```

### Статистика тестов (v1.5.0)

| Категория | Количество | Статус |
|-----------|-----------|--------|
| Модульные тесты | 336+ | ✅ |
| Интеграционные тесты (v1.2.0) | 30 | ✅ |
| Интеграционные тесты (v1.5.0) | 19+ | ✅ |
| Пропущено (зависимость от окружения) | 116 | ⚠️ |
| **Всего пройдено** | **400+** | ✅ |

### Файлы тестов

| Файл | Покрываемый модуль |
|------|-------------------|
| `test_scanner.py` | Scanner, PathValidator |
| `test_analyzer.py` | JSON parser, RuleEngine |
| `test_safety.py` | Blocklist, FileValidator, SafetyManager |
| `test_router.py` | LLM Router, RoutingStrategy |
| `test_router_v150.py` | LatencyProbe, WeightedRouter, batch_chat |
| `test_cli_scriptable.py` | CLI сценарии, выходные коды |
| `test_cli_enhancements.py` | --quiet, --json, --no-color |
| `test_export.py` | JSON/CSV экспорт |
| `test_models.py` | Data models |
| `test_ui.py` | UI компоненты |
| `test_squarify.py` | Treemap алгоритм |
| `test_modern_theme.py` | 6 тёмных тем |
| `test_virtual_treeview.py` | Virtual scrolling |
| `test_scan_cache.py` | Scan cache TTL |
| `test_credential_store.py` | Keyring credentials |
| `test_integration_v120.py` | End-to-end v1.2.0 |
| `test_integration_v130.py` | End-to-end v1.3.0 |
| `test_integration_v150.py` | End-to-end v1.5.0 |

---

## Структура проекта

```
wiztree-cli-agent/
├── app.py                          # Точка входа GUI
├── cli.py                          # Точка входа CLI
├── build.py                        # Сценарий сборки PyInstaller
├── requirements.txt                # Зависимости Python
├── WizTreeCLIAgent.spec            # Спецификация PyInstaller
├── run_cli.bat                     # Запуск CLI (Windows)
├── run_gui.bat                     # Запуск GUI (Windows)
├── audit.db                        # SQLite журнал аудита (создаётся при работе)
│
├── config/
│   └── llm_config.json             # Конфигурация LLM Router
│
├── docs/                           # Документация
│   ├── ARCHITECTURE.md             # Архитектура проекта
│   ├── CONFIGURATION.md            # Руководство по конфигурации
│   ├── API_REFERENCE.md            # Справочник API
│   ├── CHANGELOG.md                # Журнал изменений
│   ├── DEVELOPMENT.md              # Руководство разработчика
│   └── screenshot.png              # Скриншот приложения
│
├── src/                            # Исходный код
│   ├── __init__.py                 # Пакет, __version__ = "1.5.0"
│   │
│   ├── scanner/                    # Модуль сканирования (6 файлов)
│   │   ├── interface.py            # ScannerInterface (ABC)
│   │   ├── wiztree_scanner.py      # WizTreeScanner (MFT, CSV, кэш)
│   │   ├── path_validator.py       # PathValidator
│   │   ├── scan_progress.py        # ScanProgress
│   │   ├── deep_search.py          # DeepSearcher
│   │   └── options.py              # ScanOptions
│   │
│   ├── analyzer/                   # Модуль анализа (7 файлов)
│   │   ├── interface.py            # AnalyzerInterface (ABC)
│   │   ├── llm_router.py           # LLMRouter (1241 строк, v1.5.0)
│   │   ├── llm_analyzer.py         # LLMAnalyzer (Lazy Init)
│   │   ├── json_parser.py          # StreamingJsonParser
│   │   ├── rule_engine.py          # RuleEngine (10 правил)
│   │   ├── model_catalog.py        # ModelCatalog
│   │   └── prompt_store.py         # PromptStore
│   │
│   ├── safety/                     # Модуль безопасности (6 файлов)
│   │   ├── interface.py            # SafetyInterface (ABC)
│   │   ├── blocklist.py            # Blocklist (38 путей)
│   │   ├── audit_logger.py         # AuditLogger (SQLite + восстановление)
│   │   ├── file_validator.py       # FileValidator
│   │   ├── confirm_dialog.py       # ConfirmDialog
│   │   └── __init__.py             # ComprehensiveSafetyManager
│   │
│   ├── ui/                         # Модуль интерфейса (16 файлов)
│   │   ├── main_window.py          # MainWindow (1202 строки)
│   │   ├── settings_dialog.py      # SettingsDialog
│   │   ├── keybindings.py          # 5 горячих клавиш
│   │   ├── config_panel.py         # ConfigPanel
│   │   ├── file_table.py           # FileTable
│   │   ├── results_view.py         # ResultsView
│   │   ├── interface.py            # UIInterface (ABC)
│   │   ├── components/             # Компоненты
│   │   │   ├── treemap_view.py     # TreemapView (matplotlib)
│   │   │   ├── squarify.py         # Pure-Python Squarified Treemap
│   │   │   ├── drill_down.py       # Детализация Treemap
│   │   │   ├── virtual_treeview.py # Виртуальная прокрутка
│   │   │   ├── skeleton.py         # Скелетная загрузка
│   │   │   └── status_bar.py       # Статус-бар
│   │   ├── tabs/                   # Вкладки
│   │   │   ├── diff_preview.py     # Diff Preview
│   │   │   ├── history_tab.py      # История аудита
│   │   │   ├── models_tab.py       # Каталог моделей
│   │   │   └── prompts_tab.py      # Редактор промптов
│   │   ├── themes/
│   │   │   └── modern_theme.py     # 6 тёмных тем
│   │   └── animations/
│   │       └── smooth_progress.py  # 60fps прогресс-бар
│   │
│   ├── models/                     # Модели данных (3 файла)
│   │   ├── file_info.py            # FileInfo (__slots__)
│   │   ├── scan_result.py          # ScanResult
│   │   └── analysis_result.py      # AnalysisResult, RiskLevel
│   │
│   ├── utils/                      # Утилиты (2 файла)
│   │   ├── config_loader.py        # 3-уровневая конфигурация
│   │   └── credential_store.py     # Безопасное хранилище ключей
│   │
│   └── exporters/                  # Экспорт (v1.5.0)
│       └── ...                     # JSON/CSV экспорт
│
└── tests/                          # Тесты (38 файлов)
    ├── test_scanner.py
    ├── test_analyzer.py
    ├── test_safety.py
    ├── test_router.py
    ├── test_router_v150.py
    ├── test_cli_scriptable.py
    ├── test_cli_enhancements.py
    ├── test_export.py
    ├── test_integration_v120.py
    ├── test_integration_v130.py
    ├── test_integration_v150.py
    └── ... (другие тесты)
```

---

## Технический стек

| Категория | Технология | Версия |
|-----------|-----------|--------|
| **Язык** | Python | 3.10+ |
| **GUI** | customtkinter | ≥ 5.2.0 |
| **LLM** | openai (SDK) | ≥ 1.0.0 |
| **Безопасное удаление** | send2trash | ≥ 1.8.0 |
| **Визуализация** | matplotlib | ≥ 3.7.0 |
| **Treemap** | Pure Python (Bruls 2000) | встроенный |
| **Хранилище ключей** | keyring | ≥ 24.0.0 |
| **Drag & Drop** | tkinterdnd2 | ≥ 0.4.2 |
| **HTTP** | requests | ≥ 2.28.0 |
| **База данных** | sqlite3 | встроенный |
| **Тестирование** | pytest + pytest-cov | ≥ 7.4.0 |
| **Сборка** | PyInstaller | последний |

---

## Часто задаваемые вопросы

### ❓ Нужен ли API-ключ для работы?

**Нет.** При отсутствии API-ключа система автоматически использует встроенный RuleEngine
с 10 предопределёнными правилами очистки. API-ключ требуется только для LLM-анализа.

### ❓ Какие модели бесплатны?

- **OpenRouter**: `google/gemini-2.0-flash-exp:free`
- **SiliconFlow**: `deepseek-ai/DeepSeek-V3`, `Qwen/Qwen2.5-7B-Instruct`
- **Ollama**: все модели локально, полностью бесплатно

### ❓ Как получить API-ключ?

- DeepSeek: [platform.deepseek.com](https://platform.deepseek.com)
- OpenAI: [platform.openai.com](https://platform.openai.com)
- OpenRouter: [openrouter.ai](https://openrouter.ai)
- SiliconFlow: [siliconflow.cn](https://siliconflow.cn)

### ❓ Как переключить стратегию маршрутизации?

```python
from src.analyzer import LLMRouter, RoutingStrategy

router = LLMRouter(strategy=RoutingStrategy.COST)     # стоимость
router.set_strategy(RoutingStrategy.LATENCY)          # скорость
router.set_strategy(RoutingStrategy.FALLBACK)         # отказоустойчивость
router.set_strategy(RoutingStrategy.MANUAL)           # ручной выбор
```

### ❓ На каких платформах работает?

Основная платформа — **Windows** (WizTree CLI использует MFT NTFS).
Частичная поддержка macOS и Linux (сканирование через DeepSearcher, RuleEngine, Safety — работают).

---

## История версий

| Версия | Дата | Ключевые изменения |
|--------|------|-------------------|
| **v1.0.0** | 2026-05-31 | Базовая версия: WizTree CLI, LLM Router (6 Provider, 4 стратегии), RuleEngine, Safety, Treemap |
| **v1.1.0** | 2026-06-01 | UI: темы оформления, 60fps прогресс-бар, карточки статистики, таблица файлов |
| **v1.2.0** | 2026-06-03 | Безопасность: keyring, 6 тёмных тем, горячие клавиши, drag & drop, журнал + восстановление, Diff Preview, Squarified Treemap |
| **v1.3.0** | 2026-06-03 | UX: SkeletonScreen, колбэки переключения тем, интеграция ttk стилей |
| **v1.4.0** | 2026-06-04 | Производительность: VirtualTreeview, `__slots__`, кэш сканирования (1 ч TTL), потоковый CSV |
| **v1.5.0** | 2026-06-04 | Роутинг: LatencyProbe, WeightedRouter, batch_chat; CLI: коды выхода, --quiet/--json/--no-color, --batch, JSON/CSV экспорт |

Полный журнал изменений: [docs/CHANGELOG.md](docs/CHANGELOG.md)

---

## Лицензия

MIT License. См. файл [LICENSE](LICENSE) для получения подробной информации.

---

## Вклад в проект

Приветствуются Issue и Pull Request. Пожалуйста, убедитесь, что тесты проходят перед отправкой PR:

```bash
pytest tests/ -v
```
