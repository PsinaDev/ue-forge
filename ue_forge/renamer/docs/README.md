# Renamer

**English | [Русский](README_RU.md)** | [Back to UE Forge](../../../README.md)

Rename Unreal Engine plugins and projects with full source-code awareness.

![renamer_en.png](..%2Fscreenshots%2Frenamer_en.png)

## Features

- **`.uplugin` / `.uproject` JSON** — updates `FriendlyName`, `Modules[].Name`, plugin references
- **`.Build.cs`** — renames class names, constructors, and `ReadOnlyTargetRules` parameters across all `.cs` files (avoids `CS1520` build errors)
- **API macros** — `MYMODULE_API` export macros updated globally
- **Include paths** — `#include "OldName/..."` references in C++ source
- **Module macros** — `IMPLEMENT_MODULE`, `IMPLEMENT_PRIMARY_GAME_MODULE`
- **Config files** — `DefaultEngine.ini`, `DefaultGame.ini` section references
- **Comments** — mentions of the old name in `//` and `/* */` comments
- **Diff preview** — collapsible category-based diff view before any files are touched
- **Backup** — original source saved to `Source_backup/` before modifications
- **Auto-refresh** — preview updates automatically on any input change, no refresh button

## Usage

```bash
python -m ue_forge.renamer
# or inside the host:
python -m ue_forge   # → "Renamer" in sidebar
```

1. Select a `.uplugin` or `.uproject` file (or drag & drop)
2. Enter the new name
3. Review changes in the diff preview — each category is collapsible
4. Click **Rename**

## What gets renamed

| Category | Files affected | Example |
|---|---|---|
| JSON descriptors | `.uplugin`, `.uproject` | `"Name": "OldPlugin"` → `"Name": "NewPlugin"` |
| Build scripts | `*.Build.cs` | `class OldPlugin : ModuleRules` → `class NewPlugin : ModuleRules` |
| API macros | `*.h`, `*.cpp` | `OLDPLUGIN_API` → `NEWPLUGIN_API` |
| Include paths | `*.h`, `*.cpp` | `#include "OldPlugin/Public/..."` → `#include "NewPlugin/Public/..."` |
| Module macros | `*.cpp` | `IMPLEMENT_MODULE(FOldPluginModule, OldPlugin)` |
| Config files | `*.ini` | `[/Script/OldPlugin.SomeSettings]` |
| Source comments | `*.h`, `*.cpp`, `*.cs` | `// OldPlugin initialization` |

## Caveats

The renamer operates on text patterns, not a C++ AST. It handles standard UE naming conventions well but may miss non-standard patterns. Always review the diff preview before applying.
