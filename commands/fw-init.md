---
description: Detect the firmware project's family, MCU, RTOS, toolchain, build command and create .claude/firmware.json (+ optional CLAUDE.md section, handoff notes)
argument-hint: "[optional notes, e.g. 'SAMV71Q21B, FreeRTOS, CMake']"
---

Set up firmware-agent-kit for this project. User notes: $ARGUMENTS

1. **Detect** (read-only, cheap):
   - **Family:** `.ioc`/stm32 headers → stm32; `samv71*.h`/SAMV71 DFP → samv71; other Cortex-M parts → the vendor name (see the `mcu-family` skill).
   - **RTOS:** `FreeRTOSConfig.h` (record its path), `cmsis_os2.h` → api cmsis-rtos2.
   - **Build:** `python <kit>/tools/build_info.py` (generate the compile DB if missing and say how). This gives the toolchain prefix, `-mcpu`, linker script and ELF/map paths.
   - **Tools:** `python <kit>/tools/fw_doctor.py --missing` for installed and missing tools.
   - **Third-party code:** folders with their own LICENSE/README or build files that are not project code (CAN/TCP stacks, vendored libraries, host tools). Propose them for `guard.protected_paths` so they are not edited, style-probed or analysed.
   - **Docs:** datasheets/schematics (`*.pdf`), SVD files.
   - **Style:** existing project → run `style_probe.py` and note its conventions; empty/new project → the kit conventions apply.

   `<kit>` = `${CLAUDE_PLUGIN_ROOT}` or the plugin directory found with Glob.
2. **Ask** once (AskUserQuestion) for anything you could not determine: exact part number, memory sizes.
3. **Write `.claude/firmware.json`** from `<kit>/templates/firmware.json`:
   - fill real values; keep unknown ones as `null`; drop the `_comment` keys;
   - if the file already exists, show a diff and merge.
4. **Verify** the build command once and that the ELF appears. Never flash or touch the target.
5. **Offer** (each optional, ask first):
   - a `.clang-format` (kit template for new projects, or one matching `style_probe.py` output for existing code);
   - a `.gitignore` entry for `.claude/fw-size-history.jsonl`;
   - starting `.claude/fw-notes.md` via `/fw-handoff`;
   - a project conventions skill via `/fw-customize` (existing codebases).
6. Summarise what was detected, what was assumed, which tools are missing (with the free install option), and next steps.
