---
description: Detect the firmware project's family, MCU, RTOS, toolchain, build/flash/test commands and create .claude/firmware.json (+ optional CLAUDE.md section, handoff notes)
argument-hint: "[optional notes, e.g. 'SAMV71Q21B, FreeRTOS, CMake, EDBG']"
---

Set up firmware-agent-kit for this project. User notes: $ARGUMENTS

1. **Detect** (read-only, cheap):
   - **Family:** `.ioc`/stm32 headers → stm32; `sdkconfig`/`idf_component_register` → esp32; `samv71*.h`/SAMV71 DFP → samv71.
   - **RTOS:** `FreeRTOSConfig.h` (record its path), `cmsis_os2.h` → api cmsis-rtos2.
   - **Build:** `python <kit>/tools/build_info.py` (generate the compile DB if missing and say how). This gives the toolchain prefix, `-mcpu`, linker script and ELF/map paths.
   - **Tests:** Ceedling `project.yml`, CMake tests, `tests/integration/*.robot`.
   - **Tools:** `python <kit>/tools/fw_doctor.py --missing` for installed and missing tools, plus OpenOCD cfgs and launch.json in the repo.
   - **Docs:** datasheets/schematics (`*.pdf`), SVD files.
   - **Style:** existing project → run `style_probe.py` and note its conventions; empty/new project → the kit conventions apply.

   `<kit>` = `${CLAUDE_PLUGIN_ROOT}` or the plugin directory found with Glob.
2. **Ask** once (AskUserQuestion) for anything you could not determine: exact part number, probe, memory sizes.
3. **Write `.claude/firmware.json`** from `<kit>/templates/firmware.json`:
   - fill real values; keep unknown ones as `null`; drop the `_comment` keys;
   - flash commands must use open-source tools (OpenOCD, pyOCD, probe-rs, stlink, esptool/idf.py, bossac, edbg);
   - if the file already exists, show a diff and merge.
4. **Verify** the build command once and that the ELF appears. Do **not** flash; show the flash command and let the user confirm it.
5. **Offer** (each optional, ask first):
   - a firmware section in CLAUDE.md from `<kit>/templates/CLAUDE.firmware.md`;
   - a `.clang-format` (kit template for new projects, or one matching `style_probe.py` output for existing code);
   - a Ceedling harness / Renode test skeleton if none exists;
   - a `.gitignore` entry for `.claude/fw-size-history.jsonl`;
   - starting `.claude/fw-notes.md` via `/fw-handoff`.
6. Summarise what was detected, what was assumed, which tools are missing (with the free install option), and next steps.
