---
description: Requirements traceability report - requirement IDs -> code (@req) -> tests (@verifies), with gaps and an optional CSV matrix
argument-hint: "[--reqs docs/requirements.csv] [--matrix trace.csv]"
---

Run `python "${CLAUDE_PLUGIN_ROOT}/tools/trace_check.py" $ARGUMENTS` (locate `trace_check.py` with Glob if the variable is not expanded).

- No requirements file given: look for one (`docs/*req*`, `*SRS*`, `.claude/firmware.json` notes) and ask before assuming.
- Present the counts and the three gap lists:
  - requirements not implemented;
  - requirements not verified;
  - unknown IDs referenced in tags.

  Explain what is needed to close each gap.
- When adding code or tests for a requirement, add the matching `@req` / `@verifies` tag in the project's comment style. Never invent requirement IDs; ask for them.
- See the `safety-critical` skill for the wider evidence checklist.
