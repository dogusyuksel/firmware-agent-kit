---
description: Deep embedded/RTOS review of the current diff (firmware-reviewer agent) - RTOS misuse, races, thread safety, registers, timeouts, memory, scope creep, style drift
argument-hint: "[files | git range; default: uncommitted changes]"
---

Review firmware changes. Scope: $ARGUMENTS (default: uncommitted changes, `git diff HEAD`, staged and untracked included).

1. List the changed firmware files (`git diff --stat`). Ignore vendor/generated paths unless the user named them.
2. Delegate to the `firmware-reviewer` agent with:
   - the scope;
   - the family/RTOS from `.claude/firmware.json`;
   - the task the diff was meant to accomplish, if known from the conversation, so it can flag scope creep.
3. Double-check every Critical/Important finding against the code yourself; drop anything you cannot confirm.
4. Present the findings grouped by severity, then "Scope creep / style drift", then "Noticed in untouched code".
5. Ask which fixes to apply. Do not edit before the user agrees. Fixes must be minimal-line changes.
