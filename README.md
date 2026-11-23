# firmware-agent-kit

A [Claude Code](https://claude.com/claude-code) plugin for writing and changing **bare-metal and FreeRTOS firmware on Cortex-M microcontrollers**. It ships reference notes for **STM32** and **SAM V71**, and you can add your own family in one file.

It helps Claude write code that fits your project:
- it follows your existing style and conventions;
- it keeps diffs minimal;
- it respects ISR and RTOS rules;
- it keeps public APIs thread-safe;
- it never touches the hardware.

Everything it uses is free and open source.

## Quick start

### 1. Requirements
- **Linux only.** On Windows, install WSL (Ubuntu), then install and run Claude Code *inside* WSL and open your project from there. Outside Linux the kit's hooks are disabled and print a one-line note.
- **Python 3.8+** and **git**. Nothing else is required.
- **Optional tools** add features: cppcheck, clang-tidy, clang-format, the Arm GNU toolchain, poppler. Claude tells you when one would help and shows the install command. See [REQUIREMENTS.md](REQUIREMENTS.md).

### 2. Install the plugin
In Claude Code:
```
/plugin marketplace add dogusyuksel/firmware-agent-kit
/plugin install firmware-agent-kit@firmware-agent-kit
```

### 3. Set up your firmware project (once)
Open Claude Code in the project folder and run:
```
/fw-init        # detects family, MCU, RTOS, toolchain and build command; writes .claude/firmware.json
/fw-doctor      # lists optional tools that are missing, with install commands (you run them)
/fw-customize   # existing codebase: writes .claude/skills/<project>-conventions/SKILL.md
```
Commit `.claude/firmware.json` and the conventions skill so your teammates get the same behaviour.

Two settings matter most in `.claude/firmware.json`:
- **`compile_commands`:** point it at `compile_commands.json` (CMake: `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`; Make: `bear -- make`). Analysis then uses the real include paths and defines.
- **`guard.protected_paths`:** list vendor and third-party folders (for example `Drivers/`, `Middlewares/`, `lib/somestack/`). Claude asks before editing them, and they are left out of style detection and analysis.

## A typical session

The example project is an STM32L4 board running FreeRTOS (CMSIS-RTOS2), with a CubeMX-generated tree and a CAN stack.

**1. Claude starts with the project facts.** When the session opens, the kit injects a compact summary and the working rules:
```
[firmware-agent-kit] firmware project.
family=stm32 (mcu-family skill, stm32.md), rtos=freertos/cmsis-rtos2 (freertos skill)
build: cd build && make -j8   elf: build/app.elf   cc: arm-none-eabi-gcc 13.3.1
tools: cppcheck, clang-format, clang-tidy, cmake, make
Working rules: plan first, minimal diff, match the project style, thread-safe public APIs, ...
```

**2. You ask for a change.**
> Add a function that returns the number of CAN frames received since the last call. The CAN RX interrupt should count them.

**3. Claude plans first.** The change touches an ISR, so Claude shows a short plan and waits for your OK. The plan lists the files, the steps, the risks (ISR context, critical section, IRQ priority) and how the change will be checked.

**4. Claude writes code in your style.** It follows `.claude/skills/<project>-conventions` (or `style_probe.py`) for naming, error codes and formatting. A new module comes from `/fw-module`.

**5. Every edit is checked.** After each edit the kit lints the lines Claude just changed. A mistake is reported back immediately and Claude fixes it before going on:
```
firmware-agent-kit lint Dev/can_stats.c:
  ERROR L42: [RTOS-011] xSemaphoreTake() in interrupt handler 'CAN1_RX0_IRQHandler' - use xSemaphoreTakeFromISR.
```
Problems in code nobody touched are listed, not fixed:
```
Noticed (not changed):
- Dev/csp_can.c:136 - 'task_woken' starts at 1 instead of pdFALSE: an extra context switch after every TX interrupt.
```

**6. Build and size.** Claude builds once. The kit then reports flash and RAM use and how they changed against the last build:
```
firmware-agent-kit size [build/app.elf]: FLASH 95320 B = 18.2% of 512 KB | RAM 38072 B = 29.0% of 128 KB  (flash +212 B)
```

**7. Review and hand off.**
- **`/fw-review`:** the reviewer agent checks the whole diff for RTOS misuse, races, thread safety, scope creep and style drift.
- **`/fw-analyze`:** adds cppcheck and clang-tidy on the changed lines.
- **`/fw-handoff`:** saves where you stopped; the next session starts from those notes.

**Guards that are always on:**
- edits to vendor code, or to CubeMX code outside `USER CODE` blocks, ask first;
- irreversible target commands (STM32 RDP level 2) are blocked;
- erase and option-byte commands ask first;
- commits that carry AI attribution are refused.

## How it behaves

At session start, the kit gives Claude these working rules in firmware repos:

- **Plan first.** For non-trivial changes (several files, ISR/RTOS/clock/linker work), Claude shows a short plan (`/fw-plan`) and waits for approval.
- **Minimal diffs.** Claude changes only what was asked, with the fewest lines. It lists other problems under "Noticed (not changed)" and never fixes them unasked.
- **Match the project's style.** Claude follows the existing naming, error handling and formatting. New projects use the kit conventions. A project conventions skill from `/fw-customize` overrides the kit defaults.
- **Thread-safe public APIs.** Every public function documents whether it is ISR-safe.
- **Token economy.** Claude searches before reading, reads line ranges, uses the compact kit scripts and hands long PDF work to an agent.
- **No guessing hardware facts.** Claude takes registers, pins and priorities from the header, reference manual or schematic, and cites the source.
- **Missing tools.** Claude shows the install command and asks. You install the tool yourself, or the step is skipped.
- **Build stays green.** After code changes, Claude builds once (if a build command is configured) and reports new warnings or errors.
- **Hands off the hardware.** Claude never runs flash, erase or debug commands; it shows them for you to run.
- **Continuity.** `/fw-handoff` writes `.claude/fw-notes.md`, and the next session loads it automatically.

## Contents

### Skills (loaded on demand)
| Area | Skills |
|---|---|
| Targets | `mcu-family` (reference files: STM32, SAM V71; add `<family>.md` for others) |
| RTOS | `freertos` (FreeRTOS + CMSIS-RTOS2 rules) |
| Code | `embedded-c`, `peripheral-driver`, `isr-concurrency`, `state-machines`, `portable-architecture`, `linker-startup` |
| Change management | `restructure` (safe refactoring), `safety-critical` (ECSS/DO-178C-style evidence, traceability, MC/DC, FDIR, SEU) |
| Build & tools | `build-systems`, `static-analysis`, `memory-footprint` |
| Docs | `hardware-docs` (datasheets, schematics), `mermaid-diagrams` |

Skills are generic. Each one that has project-dependent choices ends with a **Project customization** section that says where your project's overrides belong.

### Agents
| Agent | Purpose |
|---|---|
| `firmware-reviewer` | diff review: RTOS misuse, races, thread safety, registers, scope creep, style drift |
| `datasheet-analyst` | facts from datasheets, reference manuals and schematics, with page citations |
| `footprint-optimizer` | measured flash/RAM reductions |

### Commands
| Command | Does |
|---|---|
| `/fw-init` | detect project facts and write `.claude/firmware.json` |
| `/fw-customize` | write a project conventions skill so the generic kit follows this codebase |
| `/fw-module` | new module (.h/.c) in the project's style with a thread-safe API, added to the build |
| `/fw-plan` | reviewable plan before any non-trivial change |
| `/fw-build` | build and triage errors |
| `/fw-analyze` | kit lint + RTOS rules + cppcheck (MISRA) + clang-tidy, one compact report |
| `/fw-format` | clang-format on changed lines only |
| `/fw-review` | deep diff review |
| `/fw-size` | flash/RAM report and diff between builds |
| `/fw-restructure` | approved refactor, step by step with build, analysis and size checks |
| `/fw-diagram` | Mermaid flows, state machines, task maps from the code |
| `/fw-docs` | answer hardware questions from datasheets and schematics |
| `/fw-trace` | requirements traceability (`@req` tags) |
| `/fw-doctor` | tool inventory with install commands |
| `/fw-handoff` | save session notes for the next session |

### Hooks
| Event | Behaviour |
|---|---|
| SessionStart | Project facts, installed tools, working rules and handoff notes (silent in non-firmware repos) |
| Before Bash: target guard | Safety net for the project's own flash commands. **Denies** irreversible operations (STM32 RDP level 2, security bits) and **asks** before mass erase, option bytes, SAMV71 GPNVM and write protection. |
| Before Bash: git guard | Denies commits/PRs containing AI attribution (configurable) |
| Before Edit/Write | Asks before editing vendor code or CubeMX code outside `USER CODE` blocks |
| After Edit/Write | Embedded (EMB-xxx) and RTOS (RTOS-xxx) checks on **the lines just edited**. Errors must be fixed; pre-existing findings are listed, not fixed. Optional clang-format of edited lines. |
| After Bash (builds) | Flash/RAM usage, delta against the last build, budget warnings |

### RTOS checks
`tools/rtos_check.py` implements about 60 heuristic rules for FreeRTOS and CMSIS-RTOS2 on Cortex-M, compiled from the FreeRTOS and ARM documentation:

- ISR context uses only FromISR APIs. This is checked through helper functions and HAL callbacks too.
- IRQ priority vs `configMAX_SYSCALL_INTERRUPT_PRIORITY`, and the NVIC priority grouping.
- No blocking before the scheduler starts, in critical sections, while the scheduler is suspended, or in timer callbacks.
- Mutexes are released on every path. Recursive and binary semaphores are used correctly.
- Creation results are checked and static buffers live long enough. Heap schemes are not mixed and nothing is freed twice.
- Task loops never return and always block. Event-group reserved bits stay unused. Public functions are thread-safe.

The edit hook checks one file at a time. `--project` mode adds:
- cross-file ISR reachability;
- FreeRTOSConfig.h checks;
- NVIC priority checks;
- heap-scheme checks.

The rules are calibrated on official FreeRTOS and STM32Cube example code, with zero error-level findings (`tests/calibrate_corpus.py`). Findings are heuristics, so Claude confirms each one against the code. The full catalogue, with sources and the review-only checklist, is in [docs/RTOS_RULES.md](docs/RTOS_RULES.md).

## Project configuration
`.claude/firmware.json` in your firmware repo. `/fw-init` writes it; see [templates/firmware.json](templates/firmware.json). Every key is optional:

- `family`, `mcu`, `core`, `rtos`
- `build`, `elf`, `map`, `compile_commands`, `memory`, `size_budget`
- `datasheets`, `notes`
- `lint` (`forbid_dynamic_alloc`, `isr_functions`, `isr_forbidden_calls`), `analysis` (tools, MISRA), `format.on_edit`
- `guard` (`protected_paths`, `vendor_edits`, `confirm_flash`, extra patterns), `git.block_ai_attribution`

## Standalone scripts
The scripts also work without Claude:
```sh
python3 tools/fw_analyze.py                 # changed lines; --all for the whole project; --misra
python3 tools/rtos_check.py --project
python3 tools/build_info.py --file src/uart.c
python3 tools/style_probe.py src/
python3 tools/pdf_search.py RM0394.pdf "USART_BRR"
python3 tools/trace_check.py --reqs docs/requirements.csv --matrix trace.csv
python3 skills/memory-footprint/scripts/map_analyzer.py old.map new.map
```

## Repository layout
- `skills/`, `agents/`, `commands/`, `hooks/`: the plugin.
- `tools/`: stdlib-only Python used by hooks and commands.
- `templates/`: config, conventions skill, module skeleton, `.clang-format`, `.clang-tidy`.
- `examples/sensor-node`: a portable ring buffer, frame parser and thread-safe service with an OSAL over FreeRTOS. It shows the recommended patterns and must stay finding-free.
- `evals/`: `claude plugin eval .` scenarios (ISR rules, thread-safe API, minimal diff, RDP2 safety, plan first).
- `tests/`: unit tests and the calibration script.
- `.github/workflows/test.yml`: CI, triggered manually.

## Development
See [CLAUDE.md](CLAUDE.md). Before sending changes, run:
```sh
python3 -m unittest discover -s tests -v
claude plugin validate .
```
Every new rule needs a test.

## License
MIT, see [LICENSE](LICENSE).
