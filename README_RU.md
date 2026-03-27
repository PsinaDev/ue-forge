# UE Forge

**[English version](README.md)**

Десктопный тулкит для автоматизации работы с Unreal Engine. Frameless тёмный UI, модульная архитектура страниц, работает отдельно или как единое приложение.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.5%2B-green)
![License: MIT](https://img.shields.io/badge/license-MIT-brightgreen)
![Platform: Windows](https://img.shields.io/badge/platform-Windows-blue)

> **Заметка**: Этот проект заменяет [Unreal-Engine-Plugin-Builder](https://github.com/PsinaDev/Unreal-Engine-Plugin-Builder), который теперь в архиве.

---

## Инструменты

UE Forge — хост-окно с сайдбаром, в которое загружаются страницы инструментов. Каждый инструмент можно также запустить отдельно.

### [Plugin Builder](ue_forge/plugin_builder/docs/README_RU.md)

Сборка UE-плагинов из исходников через UAT. Автоматическое обнаружение установленных движков, валидация `.uplugin`, живая консоль сборки. Расширенные флаги, выбор платформ, настройки на каждый движок.

### [Renamer](ue_forge/renamer/docs/README_RU.md)

Полное переименование UE-плагинов и проектов. Обрабатывает `.uplugin` / `.uproject` JSON, имена классов и конструкторы в `.Build.cs`, API-макросы, include guard'ы, `IMPLEMENT_MODULE`, конфиги, комментарии. Diff-превью перед применением, бэкап при execute.

### [Include Optimizer](ue_forge/include_optimizer/docs/README_RU.md)

Оптимизация `#include` в C++ исходниках UE-проекта. Добавляет отсутствующие `UE_INLINE_GENERATED_CPP_BY_NAME`, заменяет `CoreMinimal.h` на конкретные используемые заголовки, удаляет дубликаты, исправляет инклюды внутри препроцессорных блоков. Рекурсивное сканирование плагинов с исключением по чекбоксам.

### [Commandlet Runner](ue_forge/commandlet_runner/docs/README_RU.md)

Обнаружение и запуск UE-командлетов. Сканирует исходники движка и проекта на `UCommandlet` подклассы, извлекает описания из комментариев и `HelpDescription`, генерирует usage из паттернов `FParse::Param`. Избранное, заметки, живой вывод консоли.

---

## Архитектура

```
ue_forge/
├── host/                  # Хост-окно — сайдбар, переключение страниц, заголовок
│   ├── host_window.py     # HostWindow (наследник FramelessWindow)
│   ├── single_page_shell.py
│   └── page_protocol.py   # Контракт интерфейса страницы
├── shared/                # Общая инфраструктура
│   ├── styles.py          # Цвета, шрифты, радиусы (zinc + cyan тема)
│   ├── icons.py           # Рендер SVG-иконок Lucide
│   ├── localization.py    # i18n (EN/RU), регистрация по модулям
│   ├── config.py          # Персистентные настройки (JSON)
│   ├── widgets/           # PathInput, ConsoleWidget, StatusBadge
│   └── dialogs/           # MessageDialog, SettingsDialog
├── plugin_builder/        # Модуль Plugin Builder
├── renamer/               # Модуль Renamer
├── include_optimizer/     # Модуль Include Optimizer
├── commandlet_runner/     # Модуль Commandlet Runner
└── __main__.py            # Единая точка входа

pyside_frameless/          # Git-подмодуль → github.com/PsinaDev/pyside-frameless
├── frameless_window.py    # FramelessWindow с Aero Snap
└── drop_overlay.py        # Анимированный оверлей для drag-and-drop
```

Каждый модуль следует одной структуре: `core.py` (чистый Python, без Qt), `page.py` (PySide6 UI), `strings.py` (переводы), `__main__.py` (standalone точка входа).

## Установка

```bash
git clone --recurse-submodules https://github.com/PsinaDev/ue-forge.git
cd ue-forge
pip install -r requirements.txt
```

### Запуск

```bash
# Все инструменты в одном окне
python -m ue_forge

# Отдельные инструменты
python -m ue_forge.plugin_builder
python -m ue_forge.renamer
python -m ue_forge.include_optimizer
python -m ue_forge.commandlet_runner
```

### Сборка standalone exe

```bash
pip install pyinstaller
pyinstaller specs/ue_forge.spec
```

Сборка отдельных инструментов: `specs/plugin_builder.spec`, `specs/renamer.spec`, `specs/include_optimizer.spec`.

## Зависимости

- **Python** ≥ 3.10
- **PySide6** ≥ 6.5
- **Pillow** ≥ 12.0
- **[pyside-frameless](https://github.com/PsinaDev/pyside-frameless)** — frameless-окно с Aero Snap (git-подмодуль)

## Лицензия

MIT
