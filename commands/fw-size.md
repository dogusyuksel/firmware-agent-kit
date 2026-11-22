---
description: Report flash/RAM usage, top consumers from the map file and the trend across recent builds
argument-hint: "[old.map new.map] | [--top N]"
---

Analyse firmware footprint. Arguments: $ARGUMENTS

1. Find the ELF and map file (`.claude/firmware.json` `elf`/`map`, else newest `*.elf` / `*.map` under build directories). If they are older than the sources, say so and offer to build first.
2. Run `arm-none-eabi-size -B -d <elf>` (use the configured `toolchain_prefix`) and compute flash = text+data, RAM = data+bss, plus % of the part's memory (`memory` in config or the map's Memory Configuration).
3. Run the map analyzer from the plugin: `python "${CLAUDE_PLUGIN_ROOT}/skills/memory-footprint/scripts/map_analyzer.py" <map> --top 15` (if the variable is not expanded, locate `map_analyzer.py` in the firmware-agent-kit plugin). If two map files were given as arguments, run it in diff mode instead.
4. Show the last ~10 entries of `.claude/fw-size-history.jsonl` as a small trend table if it exists.
5. Summarise: headroom, top 5 consumers with one-line explanations, and 1-3 cheapest reduction ideas (details in the `memory-footprint` skill). For deep work, suggest the `footprint-optimizer` agent.
