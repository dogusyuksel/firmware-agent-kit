---
description: Produce a reviewable implementation plan for a firmware change before touching any file (files, steps, RTOS/memory/timing risks, verification)
argument-hint: "<the change, e.g. 'UART2 RX via DMA + idle line into the comm task'>"
---

Plan this change without editing anything: $ARGUMENTS

1. Gather only the facts you need (Grep/Glob first; `build_info.py`, `style_probe.py`, `.claude/firmware.json`, `.claude/fw-notes.md`). Read the involved functions, not whole files.
2. Output the plan in this format (concise; English or the user's language in chat):
   ```
   ## Plan: <title>
   Goal: <one sentence>   Scope: <what is explicitly NOT changed>
   ### Files
   - path/file.c - <what changes, ~lines>
   ### Steps
   1. ...  (each step leaves the build green)
   ### Risks & rules
   - RTOS: <contexts touched (ISR/task/timer), priorities vs configMAX_SYSCALL_INTERRUPT_PRIORITY, new objects + where created>
   - Memory/timing: <stack/heap/flash/RAM impact, DMA/cache, ISR latency>
   - Hardware facts needing a source: <register/pin/priority + document to check>
   ### Verification
   - build + /fw-analyze on changed files; unit tests (which); Renode/target test (which); size delta expectation
   ### Open questions
   - ...
   ```
3. Add a Mermaid sequence/flow diagram only if it clarifies interactions (ISR -> queue -> task).
4. Stop and ask for approval. Implement only after the user agrees, then follow the plan step by step and report deviations.
