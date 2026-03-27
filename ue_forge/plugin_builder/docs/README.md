# Plugin Builder

**English | [Русский](README_RU.md)** | [Back to UE Forge](../../../README.md)

Build Unreal Engine plugins from source using UAT (Unreal Automation Tool).

![plugin_builder_en.png](..%2Fscreenshots%2Fplugin_builder_en.png)

## Features

- **Engine auto-discovery** — scans standard install paths and the registry for all UE installations, displays version and path for each
- **`.uplugin` validation** — verifies plugin structure before build (modules, source directories, descriptor integrity)
- **Live build console** — real-time UAT output with color-coded log levels
- **Advanced build flags** — strict includes, unity build, PCH, platform selection, custom UAT arguments
- **Per-engine settings** — save preferred build configurations for each engine version
- **Drag & drop** — drop a plugin folder or `.uplugin` file directly onto the window

## Usage

```bash
# Standalone
python -m ue_forge.plugin_builder

# Inside UE Forge host
python -m ue_forge   # → select "Builder" in sidebar
```

1. Select or drop a `.uplugin` file
2. Pick the target engine version from the dropdown
3. (Optional) Configure advanced options — platforms, build flags
4. Click **Build Plugin**
5. Monitor progress in the live console

## How it works

The core module (`builder.py`) constructs a UAT `BuildPlugin` command line and runs it as a subprocess. Engine discovery (`engine_finder.py`) checks the Windows registry (`HKLM\SOFTWARE\EpicGames\Unreal Engine`), standard install paths, and custom paths stored in settings.

Build output is streamed line-by-line with log-level detection (errors, warnings, successes highlighted in the console widget).
