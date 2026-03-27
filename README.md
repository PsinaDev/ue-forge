# UE Forge

**[Русская версия](README_RU.md)**

Desktop toolkit for Unreal Engine automation. Frameless dark UI, modular page architecture, runs standalone or as a combined app.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![PySide6](https://img.shields.io/badge/PySide6-6.5%2B-green)
![License: MIT](https://img.shields.io/badge/license-MIT-brightgreen)
![Platform: Windows](https://img.shields.io/badge/platform-Windows-blue)

> **Note**: This project supersedes [Unreal-Engine-Plugin-Builder](https://github.com/PsinaDev/Unreal-Engine-Plugin-Builder), which is now archived.

---

## Tools

UE Forge is a host window with a sidebar that loads tool pages. Each tool can also run standalone.

### [Plugin Builder](ue_forge/plugin_builder/docs/README.md)

Build UE plugins from source via UAT. Auto-discovers engine installations, validates `.uplugin` structure, shows live build console. Supports advanced build flags, platform selection, per-engine settings.

### [Renamer](ue_forge/renamer/docs/README.md)

Rename UE plugins and projects end-to-end. Handles `.uplugin` / `.uproject` JSON, `.Build.cs` class names and constructors, API macros, include guards, `IMPLEMENT_MODULE`, config files, comments. Diff-style preview before execution, backup on apply.

### [Include Optimizer](ue_forge/include_optimizer/docs/README.md)

Optimize C++ `#include` directives across a UE project. Adds missing `UE_INLINE_GENERATED_CPP_BY_NAME`, replaces `CoreMinimal.h` with only the specific headers actually used, removes duplicates, fixes includes trapped inside preprocessor blocks. Recursive plugin scanning with per-plugin exclusion.

### [Commandlet Runner](ue_forge/commandlet_runner/docs/README.md)

Discover and execute UE commandlets. Scans engine and project source for `UCommandlet` subclasses, extracts descriptions from code comments and `HelpDescription`, auto-generates usage from `FParse::Param` patterns. Favorites, notes, live console output.

---

## Architecture

```
ue_forge/
├── host/                  # Host window — sidebar, page switching, title bar
│   ├── host_window.py     # HostWindow (FramelessWindow subclass)
│   ├── single_page_shell.py
│   └── page_protocol.py   # Page interface contract
├── shared/                # Cross-module infrastructure
│   ├── styles.py          # Colors, fonts, radii (zinc + cyan theme)
│   ├── icons.py           # Lucide SVG icon renderer
│   ├── localization.py    # i18n (EN/RU), per-module registration
│   ├── config.py          # Persistent settings (JSON)
│   ├── widgets/           # PathInput, ConsoleWidget, StatusBadge
│   └── dialogs/           # MessageDialog, SettingsDialog
├── plugin_builder/        # Plugin Builder module
├── renamer/               # Renamer module
├── include_optimizer/     # Include Optimizer module
├── commandlet_runner/     # Commandlet Runner module
└── __main__.py            # Combined entry point

pyside_frameless/          # Git submodule → github.com/PsinaDev/pyside-frameless
├── frameless_window.py    # FramelessWindow with Aero Snap
└── drop_overlay.py        # Animated drag-and-drop overlay
```

Each tool module follows the same structure: `core.py` (pure Python, no Qt), `page.py` (PySide6 UI), `strings.py` (translations), `__main__.py` (standalone entry point).

## Setup

```bash
git clone --recurse-submodules https://github.com/PsinaDev/ue-forge.git
cd ue-forge
pip install -r requirements.txt
```

### Run

```bash
# Combined app (all tools in one window)
python -m ue_forge

# Individual tools
python -m ue_forge.plugin_builder
python -m ue_forge.renamer
python -m ue_forge.include_optimizer
python -m ue_forge.commandlet_runner
```

### Build standalone exe

```bash
pip install pyinstaller
pyinstaller specs/ue_forge.spec
```

Individual tool builds: `specs/plugin_builder.spec`, `specs/renamer.spec`, `specs/include_optimizer.spec`.

## Dependencies

- **Python** ≥ 3.10
- **PySide6** ≥ 6.5
- **Pillow** ≥ 12.0
- **[pyside-frameless](https://github.com/PsinaDev/pyside-frameless)** — frameless window with Aero Snap (git submodule)

## License

MIT
