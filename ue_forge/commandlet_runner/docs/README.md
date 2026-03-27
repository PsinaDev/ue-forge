# Commandlet Runner

**[Русская версия](README_RU.md)** · [← Back to UE Forge](../../../README.md)

Discover and execute Unreal Engine commandlets with auto-generated usage info.

## Features

- **Source scanning** — scans engine and project `Source/` for `UCommandlet` subclasses, finds them by class inheritance patterns in `.h` / `.cpp` files
- **Description extraction** — pulls descriptions from code comments above the class declaration, `HelpDescription` property in constructors, and `HelpUsage` strings
- **Parameter detection** — auto-generates usage hints from `FParse::Param`, `FParse::Value`, and `FParse::Bool` patterns found in the commandlet source
- **Favorites** — star commandlets for quick access, persisted to `commandlet_favorites.json`
- **Notes** — attach per-commandlet notes with debounced auto-save to `commandlet_notes.json`
- **Live console** — real-time output from commandlet execution with log-level highlighting
- **Engine integration** — uses the same engine discovery as Plugin Builder, runs commandlets via the engine's `UE4Editor-Cmd.exe` / `UnrealEditor-Cmd.exe`

## Usage

```bash
python -m ue_forge.commandlet_runner
# or inside the host:
python -m ue_forge   # → "Commandlets" in sidebar
```

1. Select a `.uproject` file (or drag & drop)
2. Pick the engine version
3. Browse the discovered commandlet list — use search to filter, star to favorite
4. Select a commandlet to see its description, parameters, and usage
5. Configure arguments and click **Run**
6. Monitor output in the live console

## How discovery works

The scanner walks `Source/` directories in both the engine installation and the selected project, looking for files containing `UCommandlet` subclass declarations. For each found commandlet:

1. Class name is extracted from the inheritance pattern (`class XCommandlet : public UCommandlet`)
2. The `.h` and `.cpp` files are searched for comment blocks immediately above the class declaration
3. Constructor bodies are scanned for `HelpDescription`, `HelpUsage`, `HelpWebLink`, `IsServer`, `IsClient`, `IsEditor`, `LogToConsole` assignments
4. The full `.cpp` is scanned for `FParse::Param("ParamName")`, `FParse::Value("Key", ...)`, `FParse::Bool("Flag")` calls to build the parameter list

## File structure

| File | Location | Description |
|---|---|---|
| `commandlet_favorites.json` | App config dir | List of starred commandlet names |
| `commandlet_notes.json` | App config dir | Map of commandlet name → user note text |
