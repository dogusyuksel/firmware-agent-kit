---
name: memory-footprint
description: Measure and reduce flash and RAM usage of MCU firmware - size/nm/objdump/map-file analysis, finding what pulled in a big library function, stack usage analysis and stack painting, compiler/linker flags (-Os, LTO, gc-sections, newlib-nano, printf float). Use on "region FLASH/RAM overflowed", when the size hook reports growth, or when asked to optimise footprint.
---

# Flash / RAM footprint

Measure first, change second, measure again. Report numbers before/after for every change.

## Measure
```sh
arm-none-eabi-size -B -d build/app.elf          # text/data/bss.  flash = text+data, RAM = data+bss
arm-none-eabi-size -A -d build/app.elf          # per output section
arm-none-eabi-nm -S --size-sort -r -C build/app.elf | head -40   # biggest symbols (t/T=code, r/R=const, d/D=data, b/B=bss)
python <skill-dir>/scripts/map_analyzer.py build/app.map             # biggest objects & symbols by flash/RAM
python <skill-dir>/scripts/map_analyzer.py old.map new.map           # what changed between two builds
```
For F/O lists to make sense the build needs `-ffunction-sections -fdata-sections` and `-Wl,-Map=app.map` (+ `-Wl,--cref` to see who references a symbol).
The `size_tracker` hook already logs every build to `.claude/fw-size-history.jsonl`.

## Who pulled this in?
- `-Wl,--trace-symbol=_printf_float` or `-Wl,-y,sym` prints which object references a symbol.
- In the map file "Cross Reference Table" (`--cref`), the first file listed defines the symbol, the rest reference it.
- "Archive member included to satisfy reference by file (symbol)" at the top of the map explains every library object pulled in.

## Typical big wins (check each with numbers)
| Culprit | Typical cost | Fix |
|---|---|---|
| `printf`/`sprintf` family | 10-25 KB | `--specs=nano.specs`; avoid `%f` (`-u _printf_float` adds ~10 KB); use a tiny printf (e.g. mpaland/eyalroz printf) or custom formatters |
| Floating point on a core without FPU | 2-10 KB of soft-float | Fixed-point; check `__aeabi_*` / `__adddf3` in nm output |
| `double` math on single-precision FPU | soft-float double routines | `f` suffix, `sinf`, `-Wdouble-promotion`, `-fsingle-precision-constant` |
| C++ exceptions/RTTI/iostream | 50+ KB | `-fno-exceptions -fno-rtti`, no `<iostream>` |
| `malloc` pulled by libc (printf, strdup) | 1-3 KB + heap | nano specs, avoid offending calls |
| Vendor HAL | large | `-ffunction-sections` + `--gc-sections`; LL drivers or register code for hot/small paths |
| Big `const` tables in RAM | RAM = table size | Ensure `const` (and `static const`); check they are in `.rodata`, not `.data` |
| Zero-initialised large buffers | RAM | Share buffers between non-concurrent modules (union), size them from real requirements |
| Inlining/unrolling at -O2/-O3 | code size | `-Os` (or `-Oz` with clang/GCC 12+); `__attribute__((noinline))` on rarely used big helpers |
| Debug strings / asserts with file names | flash | `__FILE__` -> numeric IDs; strip logs in release |

Global flags worth having: `-Os -ffunction-sections -fdata-sections -Wl,--gc-sections`; consider `-flto` (verify ISRs/vector table still `KEEP`/`used`; debugging gets harder). Measure LTO, do not assume.

## RAM: stack and heap
- Static stack analysis: compile with `-fstack-usage` (emits `.su` files per function) and `-Wstack-usage=256` to warn on large frames. Combine with call graph (`-fcallgraph-info=su` on GCC 10+, or tools like `puncover`, `avstack.pl`) for worst-case depth. Add ISR worst-case frames (+ FPU context 104 B if lazy stacking).
- Dynamic measurement - stack painting:
  ```c
  extern uint32_t _sstack, _estack;           /* define in linker script */
  void stack_paint(void) { for (uint32_t *p = &_sstack; p < (uint32_t *)__get_MSP() - 16; ) *p++ = 0xDEADBEEF; }
  size_t stack_unused(void) { uint32_t *p = &_sstack; while (*p == 0xDEADBEEF) p++; return (size_t)((uint8_t *)p - (uint8_t *)&_sstack); }
  ```
  Paint early in startup, exercise worst-case paths, read the high-water mark. Keep >= 20-25 % margin.
- Overflow detection: MPU guard region at the stack bottom (M3+), `MSPLIM` on ARMv8-M, or a canary word checked in the main loop.
- Heap: if unused, set heap size to 0 and make `_sbrk` fail loudly so nothing silently uses it.

## When the build overflows
1. Read the overflow amount from the linker error.
2. Run the map analyzer; take the top offenders.
3. Apply the cheapest fixes from the table, rebuild, compare with the diff mode.
4. If still over: discuss trade-offs with the user (features, logging level, bigger part) - do not silently remove functionality.
