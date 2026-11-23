---
name: <project>-conventions
description: Coding conventions and hardware facts of the <project> firmware - naming, module layout, error handling, locking, ISR rules, forbidden APIs and target facts. Use whenever writing, changing or reviewing code in this repository; it overrides generic firmware-agent-kit defaults where they differ.
---

# <project> conventions

## Target
- Part / family: <part number> (<core>), see the `mcu-family` skill file `<family>.md`.
- RTOS: <FreeRTOS native | CMSIS-RTOS2 | none>, config `<path>`.
- Hardware facts live in: <datasheet / reference manual / schematic paths>.

## Layout and layering
- <folder> - <what lives there>; only <folder> may include vendor headers.
- Generated / vendor code (never edit): <paths>.
- Reference module for new code: `<path/to/module.c>`.

## Naming and style
- Functions `<prefix>_verb_noun`, types `<..._t>`, macros `<UPPER_SNAKE>`, statics `<s_...>`, globals `<g_...>`.
- Formatting: `.clang-format` at <path> | <indent, braces, line length>.
- File header / Doxygen: <format or "none">.

## Errors and logging
- Status type: `<type>`; success `<value>`; errors `<values>`. Every driver function returns it.
- Logging: `<macro>` (never in ISRs). Assert: `<macro>`.

## Concurrency
- Locks: `<API>`; ISR-safe entry points end in `<_from_isr>`.
- IRQ priorities are defined only in `<file>`; RTOS-calling IRQs at <= <value>.
- Shared state rules: <...>.

## Forbidden / required
- Forbidden: <APIs or patterns, e.g. malloc after init, HAL_Delay in tasks>.
- Required: <e.g. timeout on every hardware wait, static allocation>.

## Team rules
- <anything else the team agreed>
