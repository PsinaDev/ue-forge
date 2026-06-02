# UE Forge

**English | [Русский](README_RU.md)**

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
![plugin_builder_en.png](ue_forge%2Fplugin_builder%2Fscreenshots%2Fplugin_builder_en.png)
Build UE plugins from source via UAT. Auto-discovers engine installations, validates `.uplugin` structure, shows live build console. Supports advanced build flags, platform selection, per-engine settings.

### [Renamer](ue_forge/renamer/docs/README.md)
![renamer_en.png](ue_forge%2Frenamer%2Fscreenshots%2Frenamer_en.png)
Rename UE plugins and projects end-to-end. Handles `.uplugin` / `.uproject` JSON, `.Build.cs` class names and constructors, API macros, include guards, `IMPLEMENT_MODULE`, config files, comments. Diff-style preview before execution, backup on apply.

### [Include Optimizer](ue_forge/include_optimizer/docs/README.md)
![include_optimizer_en.png](ue_forge%2Finclude_optimizer%2Fscreenshots%2Finclude_optimizer_en.png)
Optimize C++ `#include` directives across a UE project. Adds missing `UE_INLINE_GENERATED_CPP_BY_NAME`, replaces `CoreMinimal.h` with only the specific headers actually used, removes duplicates, fixes includes trapped inside preprocessor blocks. Recursive plugin scanning with per-plugin exclusion.

### [Commandlet Runner](ue_forge/commandlet_runner/docs/README.md)
![comandlet_runner_en.png](ue_forge%2Fcommandlet_runner%2Fscreenshots%2Fcomandlet_runner_en.png)
Discover and execute UE commandlets. Scans engine and project source for `UCommandlet` subclasses, extracts descriptions from code comments and `HelpDescription`, auto-generates usage from `FParse::Param` patterns. Favorites, notes, live console output.

---

## Architecture

```
framekit/                  # Reusable UI chassis — no Unreal-specific code
├── styles.py              # Colors, fonts, radii (zinc + cyan theme)
├── icons.py               # Lucide SVG icon renderer
├── localization.py        # i18n (EN/RU), per-module registration
├── config.py              # Persistent settings (JSON)
├── platform.py            # Per-OS config dirs + process control
├── app.py                 # run_host() / run_standalone() bootstrap
├── widgets/               # PathInput, ConsoleWidget, StatusBadge, ScrollingLabel
├── dialogs/               # MessageDialog, SettingsDialog
└── shell/                 # HostWindow (sidebar), SinglePageShell, ToolPage protocol

ue_forge/
├── config.py              # UE settings — engines, build options, favorites, notes
├── platform.py            # UE platform — engine discovery, UAT/editor naming
├── assets.py              # Resource path resolution (dev + frozen)
├── resources/             # App icon
├── plugin_builder/        # Plugin Builder module
├── renamer/               # Renamer module
├── include_optimizer/     # Include Optimizer module
├── commandlet_runner/     # Commandlet Runner module
└── __main__.py            # Combined entry point

pyside_frameless/          # Git submodule → github.com/PsinaDev/pyside-frameless
├── frameless_window.py    # FramelessWindow with Aero Snap
└── drop_overlay.py        # Animated drag-and-drop overlay
```

UE Forge is built on **framekit** — a self-contained UI chassis (themed widgets, dialogs, sidebar and standalone shells, JSON config, localization and a one-call bootstrap) with no Unreal-specific code. `ue_forge` layers the UE specifics on top: engine discovery, build automation and the tool pages. Every tool page implements the same `ToolPage` contract, so it drops into either the combined host window or its own standalone shell.

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

Individual tool builds: `specs/plugin_builder.spec`, `specs/renamer.spec`, `specs/include_optimizer.spec`, `specs/commandlet_runner.spec`.

## Dependencies

- **Python** ≥ 3.10
- **PySide6** ≥ 6.5
- **Pillow** ≥ 12.0
- **[pyside-frameless](https://github.com/PsinaDev/pyside-frameless)** — frameless window with Aero Snap (git submodule)

## License

MIT
