# firmware-agent-kit

A [Claude Code](https://claude.com/claude-code) plugin for **bare-metal and FreeRTOS firmware** on **STM32, ESP32 and SAM V71** (and other Cortex-M / RISC-V MCUs). It bundles:

- domain skills;
- specialist agents;
- slash commands;
- RTOS-aware static checks;
- container toolchains;
- safety hooks that stop an AI agent from bricking your board.

Everything it uses is free and open source.

## Install

```
/plugin marketplace add dogusyuksel/firmware-agent-kit
/plugin install firmware-agent-kit@firmware-agent-kit
```

Then, in your firmware project:

```
/fw-init      # detects family, MCU, RTOS, toolchain, build/flash/test commands -> .claude/firmware.json
/fw-doctor    # shows which optional open-source tools are missing and offers to install them
```

**Team setup.** To make the plugin install automatically for everyone who opens the firmware repo, add this to the repo's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "firmware-agent-kit": { "source": { "source": "github", "repo": "dogusyuksel/firmware-agent-kit" } }
  },
  "enabledPlugins": { "firmware-agent-kit@firmware-agent-kit": true }
}
```

**Local development.** Run `claude --plugin-dir /path/to/firmware-agent-kit`.

**Requirements.** Only Python 3.8+ (stdlib only) and git are needed. Everything else is optional; see [REQUIREMENTS.md](REQUIREMENTS.md). On Windows, tools that are only installed inside WSL (cppcheck, clang-format, clang-tidy, Frama-C, Renode, Ceedling, ...) are found and used automatically through `wsl.exe`.

## How it behaves

The session-start hook injects a short set of working rules in firmware repos:

- **Plan first.** For non-trivial changes (several files, ISR/RTOS/clock/linker/bootloader work), Claude shows a short plan (`/fw-plan`) and waits for approval.
- **Minimal diffs.** Claude changes only what was asked, with the fewest lines. Other problems it notices are listed under "Noticed (not changed)" and never fixed unasked.
- **Match the project's style.** It follows the existing code's naming, error handling and formatting, using `style_probe.py` instead of reading dozens of files. New projects use the kit conventions.
- **Thread-safe public APIs.** Every public function documents whether it is ISR-safe.
- **Token economy.** It searches before reading, reads line ranges, uses the compact kit scripts and delegates long PDF work to an agent.
- **No guessing hardware facts.** Registers, pins and priorities are cited from the header, reference manual or schematic.
- **Missing tools.** Claude asks once whether to install a missing free/open-source tool, and otherwise skips that step.
- **Continuity.** `/fw-handoff` writes `.claude/fw-notes.md`, which is loaded into the next session automatically.

## Contents

### Skills (loaded on demand)
| Area | Skills |
|---|---|
| Targets | `stm32`, `esp32`, `samv71` |
| RTOS | `freertos` (FreeRTOS + CMSIS-RTOS2 + ESP-IDF SMP rules) |
| Code | `embedded-c`, `peripheral-driver`, `isr-concurrency`, `portable-architecture`, `linker-startup`, `low-power`, `bootloader` |
| Change management | `restructure` (safe refactoring), `safety-critical` (ECSS/DO-178C-style evidence, traceability, MC/DC, FDIR, SEU) |
| Build & tools | `build-systems`, `static-analysis`, `containers`, `memory-footprint`, `flash-debug` |
| Testing | `host-unit-test` (Ceedling), `renode-integration` (Renode/QEMU) |
| Debug & docs | `hardfault-debug`, `timing-analysis`, `hardware-docs` (datasheets, schematics), `mermaid-diagrams`, `board-bringup` |

### Agents
| Agent | Purpose |
|---|---|
| `firmware-reviewer` | diff review: RTOS misuse, races, thread safety, registers, scope creep, style drift |
| `datasheet-analyst` | facts from datasheets, reference manuals and schematics, with page citations |
| `fault-investigator` | HardFault, ESP panic and RTOS crash root cause |
| `footprint-optimizer` | measured flash/RAM reductions |
| `test-engineer` | Ceedling unit tests and Renode integration tests in the project's style |

### Commands
| Command | Does |
|---|---|
| `/fw-init` | detect project facts, write config, offer templates |
| `/fw-plan` | reviewable plan before any non-trivial change |
| `/fw-restructure` | approved refactor, step by step with tests and size checks |
| `/fw-trace` | requirements traceability matrix (`@req` / `@verifies`) |
| `/fw-doctor` | tool inventory and OSS install offers |
| `/fw-build` | build and triage errors |
| `/fw-flash` | build and flash |
| `/fw-size` | footprint report |
| `/fw-analyze` | lint + RTOS rules + cppcheck (MISRA) + clang-tidy (+ Frama-C) with SARIF output |
| `/fw-format` | clang-format changed lines only |
| `/fw-review` | deep diff review |
| `/fw-test` | Ceedling unit tests |
| `/fw-itest` | Renode / QEMU integration tests |
| `/fw-fault` | crash analysis |
| `/fw-docs` | answer hardware questions from PDFs |
| `/fw-diagram` | Mermaid flows, state machines, task maps |
| `/fw-handoff` | save session notes for the next session |

### Hooks
| Event | Behaviour |
|---|---|
| SessionStart | Project facts, installed tools, working rules and handoff notes (silent in non-firmware repos) |
| PreToolUse Bash: target guard | **Denies** irreversible operations: STM32 RDP level 2, ESP eFuse burns, RP2350 OTP. **Asks** before mass erase, option bytes, SAMV71 GPNVM, AVR fuses, and flashing ESP images whose first boot burns eFuses. Covers OSS and vendor CLIs. |
| PreToolUse Bash: git guard | Denies commits/PRs containing AI attribution (configurable) |
| PreToolUse Edit/Write | Asks before editing vendor code (HAL, CMSIS, managed_components, Harmony) or CubeMX code outside `USER CODE` blocks |
| PostToolUse Edit/Write | Embedded (EMB-xxx) and RTOS (RTOS-xxx) checks on **the lines you edited**. Errors must be fixed; pre-existing findings are reported, not fixed. Optional clang-format of edited lines. |
| PostToolUse Bash | After builds: flash/RAM usage, delta vs the last build and budget enforcement |

### RTOS checks
`tools/rtos_check.py` implements about 60 heuristic rules for FreeRTOS, CMSIS-RTOS2 and ESP-IDF, compiled from the FreeRTOS, ARM and Espressif documentation. Examples:

- ISR context must use FromISR APIs, including propagation into helper functions and HAL callbacks.
- Interrupt priority vs `configMAX_SYSCALL_INTERRUPT_PRIORITY`.
- No blocking before the scheduler starts, in critical sections, while the scheduler is suspended, or in timer callbacks.
- Mutexes are released on every path; recursive and binary semaphores are used correctly.
- Object creation results are checked; static buffer lifetimes are correct; heap schemes are not mixed and nothing is freed twice.
- Task loops never return and always block.
- Event-group reserved bits are not used.
- ESP spinlocks and stack-size units are correct.
- Public functions are thread-safe.

Checks run per file in the edit hook. `--project` mode adds cross-file ISR reachability (a helper in another file called from an ISR is checked as ISR code) plus config, NVIC priority and heap-scheme rules.

The rules are calibrated against official FreeRTOS, ESP-IDF and STM32Cube example code, about 200 files, with zero error-level findings (`tests/calibrate_corpus.py`).

Reviewed false positives are silenced in code with a reason: `/* fwkit-ignore EMB-002: length checked above */`.

The full catalogue, with sources and the review-only checklist, is in [docs/RTOS_RULES.md](docs/RTOS_RULES.md).

### Containers
`docker/` has four images:

- `arm-dev`: arm-none-eabi toolchain, OpenOCD, pyOCD, stlink, cppcheck, clang tools, Ceedling, valgrind;
- `esp-idf`: ESP-IDF plus QEMU;
- `renode`;
- `frama-c`.

`tools/fw_container.py` builds them and runs commands inside them with your project mounted. It works with Podman or Docker Engine.

### Example and evals
- `examples/sensor-node`: a portable ring buffer, frame parser and thread-safe service, with an OSAL over FreeRTOS, Ceedling tests and requirement tags. It demonstrates the recommended patterns and is checked in CI.
- `examples/renode-smoke`: a minimal STM32F4 firmware plus a Robot test, run in Renode in CI. It validates the integration-test templates.
- `evals/`: `claude plugin eval .` scenarios (ISR rules, ESP32 SMP, SAMV71 watchdog, minimal diff, RDP2 safety, plan first). Each scenario runs with and without the plugin to measure what the kit adds.

## Project configuration
`.claude/firmware.json` in your firmware repo. See [templates/firmware.json](templates/firmware.json); every key is optional. The main groups:

- `family`, `mcu`, `rtos`
- `build`, `flash`, `elf`, `compile_commands`
- `test`, `datasheets`
- `lint`, `analysis` (including MISRA), `format.on_edit`
- `guard`, `git.block_ai_attribution`

## Standalone scripts
```sh
python tools/fw_analyze.py --all --misra --sarif analysis.sarif
python tools/rtos_check.py --project
python tools/build_info.py --file src/uart.c
python tools/pdf_search.py RM0440.pdf "USART_BRR"
python tools/style_probe.py src/
python tools/trace_check.py --reqs docs/requirements.csv --matrix trace.csv
python tools/fw_container.py run arm-dev -- ceedling test:all
python skills/hardfault-debug/scripts/decode_fault.py --cfsr 0x8200 --bfar 0x20030000
python skills/memory-footprint/scripts/map_analyzer.py old.map new.map
```

## Development
See [CLAUDE.md](CLAUDE.md). Run `python -m unittest discover -s tests -v` and `claude plugin validate .` before sending changes. Every new rule needs a test.

## License
See [LICENSE](LICENSE).
