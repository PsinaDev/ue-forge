"""Renamer translations — registered at import time."""

from framekit.localization import register_translations

register_translations({
    "en": {
        # Sidebar label
        "renamer": "Renamer",

        # Page
        "rename_plugin": "Rename Plugin",
        "rename_project": "Rename Project",
        "renamer_title": "Rename",
        "current_name": "Current Name",
        "new_name": "New Name",
        "enter_new_name": "Enter new name...",
        "rename_scope": "Rename Scope",

        # Scope items
        "scope_modules": "Module directories & files",
        "scope_modules_desc": "Rename Source/ModuleName/ folders and .Build.cs files",
        "scope_api_macros": "API export macros",
        "scope_api_macros_desc": "OLDNAME_API -> NEWNAME_API in all headers",
        "scope_includes": "Include paths",
        "scope_includes_desc": 'Update #include "OldName/..." references',
        "scope_build_cs": "Build.cs class names",
        "scope_build_cs_desc": "class OldName : ModuleRules -> class NewName : ModuleRules",
        "scope_module_macros": "Module macros & IMPLEMENT_MODULE",
        "scope_module_macros_desc": "FOldNameModule -> FNewNameModule",
        "scope_comments": "Comments & docstrings",
        "scope_comments_desc": "Replace old name references in comments",
        "scope_backup_desc": "Save original to PluginName_backup/",

        # Preview
        "preview_empty": "Load a plugin or project to see rename preview",
        "preview_enter_name": "Enter a valid new name to preview changes",
        "changes_summary": "{count} changes across {cats} categories",

        # Mode
        "rename_mode": "What to rename?",
        "mode_plugin": "Plugin (.uplugin)",
        "mode_project": "Project (.uproject)",
        "select_uplugin_or_uproject": "Select .uplugin or .uproject file",
        "drag_drop_rename_hint": "Or drag & drop plugin/project folder",

        # Validation
        "name_validation_same": "New name must be different from current name",
        "name_validation_format": "Must start with a letter, alphanumeric only",

        # Execution
        "rename_started": "Renaming: {old} -> {new}",
        "rename_complete": "Rename Complete",
        "rename_successful": "Renamed successfully!\\nApplied {count} changes in {time:.1f}s",
        "rename_failed": "Rename Failed",
        "rename_failed_msg": "Rename failed:\\n\\n{error}",
        "rename_in_progress": "Rename in Progress",
        "rename_cancel_and_exit": "Rename is in progress. Cancel and exit?",
        "refresh_preview": "Refresh",

        # Migrated from framekit shared strings
        "scope_backup": "Create backup before changes",
        "invalid_drop_file": "Invalid file or folder doesn't contain .uplugin",
        "path_to_plugin_file": "Path to plugin file...",
    },

    "ru": {
        # Sidebar label
        "renamer": "Переименование",

        # Page
        "rename_plugin": "Переименовать",
        "rename_project": "Переименовать проект",
        "renamer_title": "Переименование",
        "current_name": "Текущее имя",
        "new_name": "Новое имя",
        "enter_new_name": "Введите новое имя...",
        "rename_scope": "Область переименования",

        # Scope items
        "scope_modules": "Директории и файлы модулей",
        "scope_modules_desc": "Переименование Source/ModuleName/ и .Build.cs",
        "scope_api_macros": "API-макросы экспорта",
        "scope_api_macros_desc": "OLDNAME_API -> NEWNAME_API во всех заголовках",
        "scope_includes": "Пути #include",
        "scope_includes_desc": 'Обновить #include "OldName/..." ссылки',
        "scope_build_cs": "Классы в Build.cs",
        "scope_build_cs_desc": "class OldName : ModuleRules -> class NewName : ModuleRules",
        "scope_module_macros": "Макросы модулей и IMPLEMENT_MODULE",
        "scope_module_macros_desc": "FOldNameModule -> FNewNameModule",
        "scope_comments": "Комментарии и docstrings",
        "scope_comments_desc": "Замена старого имени в комментариях",
        "scope_backup_desc": "Сохранить оригинал в PluginName_backup/",

        # Preview
        "preview_empty": "Загрузите плагин или проект для просмотра изменений",
        "preview_enter_name": "Введите валидное новое имя для просмотра изменений",
        "changes_summary": "{count} изменений в {cats} категориях",

        # Mode
        "rename_mode": "Что переименовать?",
        "mode_plugin": "Плагин (.uplugin)",
        "mode_project": "Проект (.uproject)",
        "select_uplugin_or_uproject": "Выберите .uplugin или .uproject файл",
        "drag_drop_rename_hint": "Или перетащите папку плагина/проекта",

        # Validation
        "name_validation_same": "Новое имя должно отличаться от текущего",
        "name_validation_format": "Должно начинаться с буквы, только буквы и цифры",

        # Execution
        "rename_started": "Переименование: {old} -> {new}",
        "rename_complete": "Переименование завершено",
        "rename_successful": "Успешно переименовано!\\nПрименено {count} изменений за {time:.1f}с",
        "rename_failed": "Ошибка переименования",
        "rename_failed_msg": "Переименование не удалось:\\n\\n{error}",
        "rename_in_progress": "Идёт переименование",
        "rename_cancel_and_exit": "Идёт переименование. Отменить и выйти?",
        "refresh_preview": "Обновить",

        # Migrated from framekit shared strings
        "scope_backup": "Создать резервную копию",
        "invalid_drop_file": "Неверный файл или папка не содержит .uplugin",
        "path_to_plugin_file": "Путь к файлу плагина...",
    },
})
