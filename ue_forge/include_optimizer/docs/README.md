# Include Optimizer

**[Русская версия](README_RU.md)** · [← Back to UE Forge](../../../README.md)

Optimize C++ `#include` directives across an Unreal Engine project.

## Features

- **`UE_INLINE_GENERATED_CPP_BY_NAME`** — adds missing inline macros to `.cpp` files whose paired `.h` has `GENERATED_BODY()`. Engine version check (requires UE 5.1+). Insertion point is preprocessor-aware — always placed at top-level scope, never inside `#if` blocks
- **`CoreMinimal.h` replacement** — analyzes actual type usage (100+ patterns: containers, math, delegates, UObject macros, smart pointers, engine types) and replaces the catch-all `CoreMinimal.h` with only the specific headers needed, plus `CoreTypes.h` as baseline
- **Duplicate `#include` removal** — detects and removes repeated includes within the same file
- **Preprocessor block fix** — detects `UE_INLINE_GENERATED_CPP_BY_NAME` macros incorrectly placed inside `#if` / `#ifdef` / `#ifndef` blocks and moves them outside the enclosing `#endif`
- **Plugin scanning** — when a `.uproject` is selected, optionally scans `Plugins/` recursively for `.uplugin` files. Plugins grouped by category with individual checkboxes for exclusion
- **Diff preview** — categorized changes with collapsible groups. When plugins are included, changes are grouped by source (Project / each plugin), then by optimization category within each source
- **Backup** — `Source/` → `Source_backup/` before modifications, including per-plugin backups

## Usage

```bash
python -m ue_forge.include_optimizer
# or inside the host:
python -m ue_forge   # → "Includes" in sidebar
```

1. Select a `.uproject`, `.uplugin`, or `Source/` directory
2. Toggle optimization categories on/off
3. (For `.uproject`) Enable "Include Plugins" and uncheck any plugins to exclude
4. Review changes in the diff preview
5. Click **Optimize Includes**

## CoreMinimal.h replacement logic

The optimizer strips comments and `#include` lines from the file content, then scans for 100+ regex patterns mapped to specific headers:

| Usage pattern | Resolved header |
|---|---|
| `TArray<>` | `Containers/Array.h` |
| `FString` | `Containers/UnrealString.h` |
| `FVector` | `Math/Vector.h` |
| `UE_LOG` | `Logging/LogMacros.h` |
| `TSharedPtr<>` | `Templates/SharedPointer.h` |
| `UCLASS()` | `UObject/ObjectMacros.h` |
| `AActor` | `GameFramework/Actor.h` |
| ... | (100+ total mappings) |

`CoreTypes.h` is always included as a safe baseline (provides `int32`, `uint8`, `TEXT()`, `TCHAR`, `FORCEINLINE`, `check`/`ensure`, platform macros).

Headers already explicitly present in the file are not duplicated.

## Preprocessor awareness

The optimizer tracks `#if` / `#ifdef` / `#ifndef` / `#endif` nesting depth per line. This prevents two classes of bugs:

1. **Insertion** — `UE_INLINE_GENERATED_CPP_BY_NAME` is inserted after the last `#include` at depth 0 (top-level), not after an `#include` inside a `#if WITH_EDITOR` block
2. **Detection** — the "Preprocessor Block Fix" category catches existing `UE_INLINE_GENERATED_CPP_BY_NAME` macros that ended up inside conditional blocks and proposes moving them after the enclosing `#endif`
