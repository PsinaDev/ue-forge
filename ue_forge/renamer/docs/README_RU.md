# Renamer

**[English](README.md) | Русский** | [Назад к UE Forge](../../../README_RU.md)

Переименование плагинов и проектов Unreal Engine с полной осведомлённостью о структуре исходников.

![renamer_ru.png](..%2Fscreenshots%2Frenamer_ru.png)

## Возможности

- **`.uplugin` / `.uproject` JSON** — обновляет `FriendlyName`, `Modules[].Name`, ссылки на плагины
- **`.Build.cs`** — переименовывает имена классов, конструкторы и параметры `ReadOnlyTargetRules` во всех `.cs` файлах (избегает ошибок `CS1520`)
- **API-макросы** — `MYMODULE_API` экспорт-макросы обновляются глобально
- **Include-пути** — `#include "OldName/..."` в C++ исходниках
- **Макросы модулей** — `IMPLEMENT_MODULE`, `IMPLEMENT_PRIMARY_GAME_MODULE`
- **Конфиг-файлы** — ссылки в секциях `DefaultEngine.ini`, `DefaultGame.ini`
- **Комментарии** — упоминания старого имени в `//` и `/* */`
- **Diff-превью** — категоризированный diff с раскрывающимися секциями до любых изменений файлов
- **Бэкап** — оригинальные исходники сохраняются в `Source_backup/` перед модификацией
- **Автообновление** — превью обновляется автоматически при любом изменении ввода

## Запуск

```bash
python -m ue_forge.renamer
# или в хосте:
python -m ue_forge   # → "Renamer" в сайдбаре
```

1. Выберите `.uplugin` или `.uproject` (или перетащите)
2. Введите новое имя
3. Просмотрите изменения в diff — каждая категория раскрывается
4. Нажмите **Rename**

## Что переименовывается

| Категория | Затронутые файлы | Пример |
|---|---|---|
| JSON-дескрипторы | `.uplugin`, `.uproject` | `"Name": "OldPlugin"` → `"Name": "NewPlugin"` |
| Скрипты сборки | `*.Build.cs` | `class OldPlugin : ModuleRules` → `class NewPlugin : ModuleRules` |
| API-макросы | `*.h`, `*.cpp` | `OLDPLUGIN_API` → `NEWPLUGIN_API` |
| Include-пути | `*.h`, `*.cpp` | `#include "OldPlugin/Public/..."` → `#include "NewPlugin/Public/..."` |
| Макросы модулей | `*.cpp` | `IMPLEMENT_MODULE(FOldPluginModule, OldPlugin)` |
| Конфиг-файлы | `*.ini` | `[/Script/OldPlugin.SomeSettings]` |
| Комментарии | `*.h`, `*.cpp`, `*.cs` | `// OldPlugin initialization` |

## Нюансы

Renamer работает на уровне текстовых паттернов, а не C++ AST. Стандартные UE-конвенции именования обрабатываются хорошо, но нестандартные паттерны могут быть пропущены. Всегда проверяйте diff-превью перед применением.
