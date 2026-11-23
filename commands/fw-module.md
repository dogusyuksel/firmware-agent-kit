---
description: Create a new firmware module (.h/.c) that matches the project's style and the kit's rules - thread-safe public API, optional ISR-safe entry points, status codes, init/deinit - and add it to the build
argument-hint: "<name> [purpose] [--isr] [--layer drivers|services|app]"
---

Create a module. Request: $ARGUMENTS

1. **Conventions first:** if a `*-conventions` project skill exists, follow it. Otherwise run `python3 <kit>/tools/style_probe.py` (`<kit>` = `${CLAUDE_PLUGIN_ROOT}` or found with Glob) and read one similar existing module. Only an empty project uses the kit skeleton as-is.
2. **Decide and state in 3-5 lines:** folder/layer, file names, public functions, which ones are ISR-safe (`--isr` or obvious from the purpose), locking (project lock API / OSAL), error type, what is static vs. caller-provided memory. Ask only if a choice changes the API.
3. **Write** the files starting from `<kit>/templates/module/module.h` and `module.c`, renamed and restyled to the project's conventions:
   - every public function is thread-safe or documents why not; ISR entry points end in the project's ISR suffix and never block;
   - no dynamic allocation after init, every hardware wait has a timeout, every public function validates its arguments;
   - keep only what the request needs - no placeholder functions.
4. **Build integration:** add the source to CMake/Make/IDE build the way neighbouring files are added (minimal diff); show the change.
5. **Verify:** build once and run `/fw-analyze` on the new files; report findings. Do not touch other modules.
