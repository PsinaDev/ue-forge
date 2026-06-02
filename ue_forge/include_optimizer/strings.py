"""Include Optimizer translations — registered at import time."""

from framekit.localization import register_translations

register_translations({
    "en": {
        # Sidebar label
        "include_optimizer": "Includes",

        # Page
        "opt_title": "Include Optimizer",
        "opt_description": "Optimize C++ includes across your UE project Source/ directory. Adds missing inline macros, replaces CoreMinimal.h with specific headers, and cleans up duplicates.",
        "opt_select_project": "Select .uproject / .uplugin or Source directory",
        "opt_path_placeholder": "Path to UE project or plugin...",
        "opt_drag_drop_hint": "Or drag & drop a project / plugin folder here",
        "opt_invalid_drop": "Not a valid UE project, plugin, or Source directory",

        # Scope
        "opt_scope": "Optimizations",
        "opt_scope_inline": "UE_INLINE_GENERATED_CPP_BY_NAME",
        "opt_scope_inline_desc": "Add missing inline macro to .cpp files whose .h has GENERATED_BODY()",
        "opt_scope_coreminimal": "Replace CoreMinimal.h",
        "opt_scope_coreminimal_desc": "Replace #include \"CoreMinimal.h\" with CoreTypes.h + only the specific headers actually used",
        "opt_scope_duplicates": "Remove duplicate includes",
        "opt_scope_duplicates_desc": "Remove duplicate #include lines within the same file",
        "opt_scope_ppfix": "Fix preprocessor block includes",
        "opt_scope_ppfix_desc": "Move UE_INLINE_GENERATED_CPP_BY_NAME out of #if/#ifdef blocks to top-level scope",
        "opt_scope_backup_desc": "Save original Source/ to Source_backup/",

        # Plugins
        "opt_plugins": "Plugins",
        "opt_include_plugins": "Include Plugins",
        "opt_include_plugins_desc": "Also scan and optimize includes in project plugins",

        # Preview
        "opt_preview_empty": "Load a UE project to scan for include optimizations",
        "opt_preview_clean": "No optimizations needed — source is already clean",
        "opt_changes_summary": "{count} optimizations across {files} files",
        "opt_source_project": "Project Source",

        # Execution
        "opt_execute": "Optimize Includes",
        "opt_confirm": "Apply {count} include optimizations?\n\nThis will modify source files on disk.",
        "opt_in_progress": "Optimization in Progress",
        "opt_cancel_and_exit": "Optimization is in progress. Cancel and exit?",
        "opt_complete": "Optimization Complete",
        "opt_successful": "Optimized successfully!\nApplied {count} changes to {files} files in {time:.1f}s",
        "opt_failed": "Optimization Failed",
        "opt_failed_msg": "Optimization failed:\n\n{error}",

        # Migrated from framekit shared strings
        "scope_backup": "Create backup before changes",
    },

    "ru": {
        # Sidebar label
        "include_optimizer": "Инклюды",

        # Page
        "opt_title": "Оптимизация инклюдов",
        "opt_description": "Оптимизация #include в исходниках UE-проекта. Добавление inline-макросов, замена CoreMinimal.h на конкретные заголовки, удаление дубликатов.",
        "opt_select_project": "Выберите .uproject / .uplugin или директорию Source",
        "opt_path_placeholder": "Путь к UE-проекту или плагину...",
        "opt_drag_drop_hint": "Или перетащите папку проекта / плагина сюда",
        "opt_invalid_drop": "Не является UE-проектом, плагином или директорией Source",

        # Scope
        "opt_scope": "Оптимизации",
        "opt_scope_inline": "UE_INLINE_GENERATED_CPP_BY_NAME",
        "opt_scope_inline_desc": "Добавить макрос в .cpp, у которых .h содержит GENERATED_BODY()",
        "opt_scope_coreminimal": "Замена CoreMinimal.h",
        "opt_scope_coreminimal_desc": "Заменить #include \"CoreMinimal.h\" на CoreTypes.h + только используемые заголовки",
        "opt_scope_duplicates": "Удаление дубликатов",
        "opt_scope_duplicates_desc": "Удалить повторяющиеся #include в одном файле",
        "opt_scope_ppfix": "Исправить инклюды в #if-блоках",
        "opt_scope_ppfix_desc": "Вынести UE_INLINE_GENERATED_CPP_BY_NAME из #if/#ifdef блоков на верхний уровень",
        "opt_scope_backup_desc": "Сохранить оригинал Source/ в Source_backup/",

        # Plugins
        "opt_plugins": "Плагины",
        "opt_include_plugins": "Включить плагины",
        "opt_include_plugins_desc": "Также сканировать и оптимизировать инклюды в плагинах проекта",

        # Preview
        "opt_preview_empty": "Загрузите UE-проект для поиска оптимизаций",
        "opt_preview_clean": "Оптимизации не нужны — исходники уже в порядке",
        "opt_changes_summary": "{count} оптимизаций в {files} файлах",
        "opt_source_project": "Исходники проекта",

        # Execution
        "opt_execute": "Оптимизировать",
        "opt_confirm": "Применить {count} оптимизаций?\n\nФайлы исходников будут изменены на диске.",
        "opt_in_progress": "Идёт оптимизация",
        "opt_cancel_and_exit": "Идёт оптимизация. Отменить и выйти?",
        "opt_complete": "Оптимизация завершена",
        "opt_successful": "Оптимизировано!\nПрименено {count} изменений в {files} файлах за {time:.1f}с",
        "opt_failed": "Ошибка оптимизации",
        "opt_failed_msg": "Оптимизация не удалась:\n\n{error}",

        # Migrated from framekit shared strings
        "scope_backup": "Создать резервную копию",
    },
})
