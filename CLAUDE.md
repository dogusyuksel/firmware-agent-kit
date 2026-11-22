# firmware-agent-kit - contributor guide

Claude Code plugin + marketplace for bare-metal / FreeRTOS firmware (STM32, ESP32, SAMV71). The repo root is both the marketplace (`.claude-plugin/marketplace.json`) and the plugin (`.claude-plugin/plugin.json`).

## Layout
- `skills/<name>/SKILL.md` - domain knowledge, loaded on demand. Keep each focused and short (token cost); frontmatter `description` says when to use it.
- `agents/*.md` - sub-agents (reviewer, datasheet analyst, fault investigator, footprint optimizer, test engineer). Read-only unless their job is writing tests.
- `commands/*.md` - slash commands (`/fw-*`). They call scripts via `${CLAUDE_PLUGIN_ROOT}` with a Glob fallback.
- `hooks/hooks.json` + `hooks/run-hook.sh` (finds a working Python, skips the Windows Store stub) + `hooks/scripts/*.py`.
- `tools/` - stdlib-only Python shared by hooks and commands: `fwlib` (config, git, hook I/O), `cparse` (C model, contexts, call graph), `fw_lint` (EMB-xxx), `rtos_check` (RTOS-xxx), `fw_analyze` (+SARIF), `fwfmt`/`fw_format`, `build_info`, `pdf_search`, `style_probe`, `trace_check`, `fw_doctor`, `fw_container`.
- `docs/RTOS_RULES.md` - the RTOS rule catalogue; every RTOS-xxx ID in code must appear there (and vice versa for Auto rules).
- `docker/<image>/Dockerfile` - arm-dev, esp-idf, renode, frama-c.
- `templates/` - files `/fw-init` copies into user projects.
- `tests/test_hooks.py` - unittest suite; hooks are run as subprocesses with real JSON payloads.
- `tests/calibrate_corpus.py` - false-positive calibration on official FreeRTOS/ESP-IDF/STM32Cube examples (network).
- `examples/sensor-node` - reference project (Ceedling, OSAL, traceability); must stay finding-free.
- `evals/` - `claude plugin eval .` scenarios (prompt.md + graders/*.md).

## Rules for changes
- English only, everywhere in the repo.
- Python: stdlib only, 3.8 compatible, no machine-specific paths, cross-platform (Windows Git Bash, Linux, macOS).
- Only free/open-source tools may be required, recommended or installed. Proprietary tools may appear only in guard patterns.
- Hooks must fail open (never break a session) and keep output short (it costs the user tokens).
- New lint/RTOS rule: add the check, a positive test, a no-false-positive case in `RTOS_GOOD` (or similar), a row in `docs/RTOS_RULES.md`, and run `tests/calibrate_corpus.py` (must stay at zero errors).
- New tool in `fw_doctor.TOOLS`: verified install command per OS + license; regenerate the REQUIREMENTS.md table.
- Bump the version in `plugin.json`, `marketplace.json` and `tools/fw_container.py` together; add a CHANGELOG entry.
- No AI attribution in commits or PRs (the kit's own guard enforces it for users too).

## Verify before committing
```sh
python -m unittest discover -s tests -v
python tests/calibrate_corpus.py          # after rule changes
claude plugin validate .
claude plugin eval . --runs 1 --no-publish  # after skill/command changes (costs tokens)
```
