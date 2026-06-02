"""Commandlet Runner translations — registered at import time."""

from framekit.localization import register_translations

register_translations({
    "en": {
        # Sidebar label
        "commandlet_launcher": "Commandlet",

        # Page
        "cmd_title": "Commandlet Runner",
        "cmd_description": "Discover and run Unreal Engine commandlets. Scans engine and project sources for available commandlets, extracts parameters and descriptions from code.",
        "cmd_select_project": "Select .uproject file",
        "cmd_path_placeholder": "Path to UE project...",
        "cmd_drag_drop_hint": "Or drag & drop a project folder here",
        "cmd_invalid_drop": "Not a valid UE project (.uproject)",

        # Commandlet list
        "cmd_commandlets": "Commandlets",
        "cmd_search_placeholder": "Search commandlets...",
        "cmd_filter_engine": "Engine",
        "cmd_filter_project": "Project",
        "cmd_filter_favorites": "Show favorites only",
        "cmd_count": "{total} commandlets ({engine} engine, {project} project)",
        "cmd_engine_detected": "Engine: UE {version} — {path}",
        "cmd_engine_not_found": "Could not detect engine for this project",
        "cmd_editor_not_found": "Editor executable not found in engine installation",

        # Detail panel
        "cmd_details": "Commandlet Details",
        "cmd_source_engine": "Engine",
        "cmd_source_project": "Project",
        "cmd_parameters": "Parameters",
        "cmd_custom_params": "Additional parameters",
        "cmd_custom_params_hint": "-Param1=Value1 -Flag\n-Param2=\"Value with spaces\"",
        "cmd_dry_run": "Dry Run (-WhatIf)",
        "cmd_dry_run_desc": "Add -WhatIf flag to preview changes without applying them",
        "cmd_empty": "Select a project and commandlet to see details",

        # Execution
        "cmd_run": "Run Commandlet",
        "cmd_confirm": "Run commandlet {name}?",
        "cmd_in_progress": "Commandlet Running",
        "cmd_complete": "Commandlet Complete",
        "cmd_successful": "Commandlet completed successfully in {time:.1f}s",
        "cmd_failed_title": "Commandlet Failed",
        "cmd_failed_msg": "Commandlet failed:\n\n{error}",
        "cmd_scan_done": "Found {count} commandlets",
        "cmd_no_params": "No parameters discovered from source code",
        "cmd_examples": "Usage examples:",
        "cmd_open_source": "Open source file",
        "cmd_cancel_and_exit": "A commandlet is running. Cancel and exit?",
        "cmd_notes": "Notes",
        "cmd_notes_placeholder": "Your notes about this commandlet...",
        "cmd_back_to_console": "Back to Console",
    },

    "ru": {
        # Sidebar label
        "commandlet_launcher": "Командлеты",

        # Page
        "cmd_title": "Запуск командлетов",
        "cmd_description": "Обнаружение и запуск командлетов Unreal Engine. Сканирует исходники движка и проекта, извлекает параметры и описания из кода.",
        "cmd_select_project": "Выберите файл .uproject",
        "cmd_path_placeholder": "Путь к UE-проекту...",
        "cmd_drag_drop_hint": "Или перетащите папку проекта сюда",
        "cmd_invalid_drop": "Не является UE-проектом (.uproject)",

        # Commandlet list
        "cmd_commandlets": "Командлеты",
        "cmd_search_placeholder": "Поиск командлетов...",
        "cmd_filter_engine": "Движок",
        "cmd_filter_project": "Проект",
        "cmd_filter_favorites": "Только избранные",
        "cmd_count": "{total} командлетов ({engine} движок, {project} проект)",
        "cmd_engine_detected": "Движок: UE {version} — {path}",
        "cmd_engine_not_found": "Не удалось определить движок для проекта",
        "cmd_editor_not_found": "Исполняемый файл редактора не найден",

        # Detail panel
        "cmd_details": "Детали командлета",
        "cmd_source_engine": "Движок",
        "cmd_source_project": "Проект",
        "cmd_parameters": "Параметры",
        "cmd_custom_params": "Дополнительные параметры",
        "cmd_custom_params_hint": "-Param1=Value1 -Flag\n-Param2=\"Значение с пробелами\"",
        "cmd_dry_run": "Тестовый запуск (-WhatIf)",
        "cmd_dry_run_desc": "Добавить флаг -WhatIf для предпросмотра без применения",
        "cmd_empty": "Выберите проект и командлет для просмотра деталей",

        # Execution
        "cmd_run": "Запустить",
        "cmd_confirm": "Запустить командлет {name}?",
        "cmd_in_progress": "Выполнение командлета",
        "cmd_complete": "Командлет завершён",
        "cmd_successful": "Командлет выполнен успешно за {time:.1f}с",
        "cmd_failed_title": "Ошибка командлета",
        "cmd_failed_msg": "Командлет завершился с ошибкой:\n\n{error}",
        "cmd_scan_done": "Найдено {count} командлетов",
        "cmd_no_params": "Параметры не обнаружены в исходном коде",
        "cmd_examples": "Примеры использования:",
        "cmd_open_source": "Открыть исходный файл",
        "cmd_cancel_and_exit": "Командлет выполняется. Отменить и выйти?",
        "cmd_notes": "Заметки",
        "cmd_notes_placeholder": "Ваши заметки об этом командлете...",
        "cmd_back_to_console": "Вернуться к консоли",
    },
})