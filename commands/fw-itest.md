---
description: Run (or create) integration tests of the real firmware ELF in Renode (Robot Framework) or QEMU, locally or in the renode/esp-idf container
argument-hint: "[robot file] [--container] [--write <scenario>]"
---

Integration tests. Arguments: $ARGUMENTS

1. Use `test.integration` from `.claude/firmware.json` if set, else look for `tests/integration/*.robot` / `*.resc`.
2. With `--write <scenario>` or no tests yet: delegate to the `test-engineer` agent. Point it to the `renode-integration` skill and the templates in `<kit>/templates/renode/`. Check the platform support matrix for the target first (STM32: Renode; SAMV71: custom `.repl`; ESP32: Espressif QEMU).
3. Build the ELF if it is stale, then run `renode-test <robot>`. Use `python <kit>/tools/fw_container.py run renode -- renode-test <robot>` when Renode is not installed or `--container` is given. For ESP32, run `python <kit>/tools/fw_container.py run esp-idf -- idf.py qemu`.
4. Report the results per test case and the failing step with the UART log excerpt. Keep the logs (`log.html`) for the user.
