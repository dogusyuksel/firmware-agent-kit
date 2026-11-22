---
name: embedded-c
description: Coding rules for bare-metal C/C++ firmware on microcontrollers (no OS or a tiny RTOS). Use whenever writing, modifying or reviewing MCU firmware code - volatile, ISR-shared data, atomicity, critical sections, fixed-width types, bit manipulation, static allocation, timeouts, undefined behaviour and portability between compilers.
---

# Embedded C rules

Apply these to every line of firmware you write or change. When existing code violates them, point it out but do not mass-refactor unrelated code.

## Types and arithmetic
- Use `<stdint.h>` fixed-width types (`uint32_t`, `int16_t`) for anything that touches hardware, protocols or storage. `int` is fine for loop counters only.
- Use `<stdbool.h>` `bool`. Use `size_t` for sizes/indexes into memory.
- Beware integer promotion: `uint8_t a = 200, b = 100; if (a + b > 255)` is true because of promotion to `int`. `~u8` is a negative `int`. Cast explicitly.
- Shifts: `1 << 31` is UB on 32-bit `int`. Write `1UL << 31` or `(uint32_t)1U << n`. Never shift by >= width.
- Signed overflow is UB. Counters that wrap must be unsigned.
- Wraparound-safe time comparisons: `if ((uint32_t)(now - start) >= timeout_ticks)`; never `if (now > deadline)`.
- Division/modulo on cores without hardware divide (Cortex-M0/M0+) are slow library calls; prefer powers of two and masks in hot paths.
- Avoid `float`/`double` unless the core has an FPU and it is enabled (`-mfloat-abi=hard -mfpu=...` + CPACR set in startup). `double` is always soft-float on single-precision FPUs (M4F/M33). Use `f` suffix on literals (`0.5f`) and `-Wdouble-promotion`.

## volatile and memory ordering
- Every memory-mapped register access must go through a `volatile`-qualified pointer (CMSIS device headers already do this with `__IO`/`__IOM`).
- Variables shared between an ISR and main context (or between DMA and CPU) must be `volatile`.
- `volatile` does NOT make access atomic and does NOT order non-volatile accesses. Use `__DMB()`/`__DSB()` (or `atomic_signal_fence`) where ordering vs. a peripheral or DMA matters, e.g. fill buffer -> `__DMB()` -> start DMA.
- After writing a register that disables an interrupt source or clears a flag at the end of an ISR, add `__DSB()` if the write may still be in a bus buffer (avoids spurious re-entry on Cortex-M with write buffers).

## Atomicity and critical sections
- Natural-width aligned loads/stores (32-bit on Cortex-M) are atomic. 64-bit values, bitfields, structs and read-modify-write (`x++`, `x |= m`) are NOT.
- Protect shared RMW with a short critical section that restores the previous state:
  ```c
  uint32_t primask = __get_PRIMASK();
  __disable_irq();
  shared_counter++;
  __set_PRIMASK(primask);
  ```
  Or mask only lower-priority IRQs with `BASEPRI` (Cortex-M3+). Keep critical sections to a few instructions; never call blocking code inside.
- Lock-free single-producer/single-consumer ring buffers avoid most critical sections (see `isr-concurrency` skill).
- Use GPIO BSRR-style set/reset registers instead of RMW on ODR when ISRs also touch the port.

## Memory
- No dynamic allocation after init (`malloc`/`free`/`new`). Use static buffers, fixed-size pools or allocate-once-at-startup.
- No recursion. No VLAs. No large local arrays (stack is often 1-8 KB); make them `static` or global and document ownership.
- `const` data stays in flash: `static const uint8_t table[] = {...};`. Check the map file that big tables did not land in `.data` (that costs flash AND RAM).
- Do not cast byte buffers to struct pointers on cores that fault on unaligned access (Cortex-M0, or LDRD/LDM on M3+). Use `memcpy` - compilers optimise it to the right loads.
- `__attribute__((packed))` structs generate slow byte accesses and unaligned pointer UB when you take a member's address; use them only for wire formats and copy in/out.
- Endianness: Cortex-M is little-endian. Serialize protocol fields explicitly with shifts; never `memcpy` a struct onto the wire.
- Use `_Static_assert(sizeof(struct x) == 12, "layout")` for layouts that must match hardware or protocols.

## Control flow and robustness
- Every wait on hardware has a timeout and an error path. `while (!(USART1->SR & USART_SR_TXE));` is a latent hang.
- Functions that can fail return a status (`enum`/`int` error code); callers check it.
- Validate inputs at module boundaries; `assert`-style checks (`configASSERT`, custom `FW_ASSERT`) in debug builds that halt with a breakpoint (`__BKPT(0)`) and record file/line.
- `switch` on enums: handle every value, add `default` that reports an error.
- Watchdog: kick it from the main loop only after verifying all tasks made progress, never from a timer ISR.
- Initialise all variables. Do not rely on `.bss` zeroing for things that need re-init after a soft reset or wake-up.

## ISRs (summary - see `isr-concurrency`)
- ISRs are short: acknowledge/clear the source, move data, set a flag, return.
- No `printf`, `malloc`, delays, blocking waits, or floating point in ISRs.
- Clear the interrupt flag early enough (and with `__DSB()` if needed) to avoid double entry.
- Handler names must exactly match the vector table (`USART1_IRQHandler`); a typo silently routes to `Default_Handler`.

## Style that helps the compiler and the reviewer
- `static` for every function/variable not used outside the file.
- One module = `module.c` + `module.h`; headers have include guards, include what they use, and contain no definitions (except `static inline`).
- Bit manipulation: use the device header's `_Pos`/`_Msk` macros: `REG = (REG & ~X_MSK) | ((val << X_POS) & X_MSK);`. Avoid C bitfields for registers (layout is implementation-defined).
- Name units: `timeout_ms`, `freq_hz`, `len_bytes`.
- Compile with `-Wall -Wextra -Wshadow -Wdouble-promotion -Wformat=2 -Wundef -Wconversion` (where feasible) and `-ffunction-sections -fdata-sections -Wl,--gc-sections`.

## Public APIs and project style
- Public (non-static) functions are thread-safe: protect shared state with a mutex, a short critical section, or a single owner task; document ISR-safety in the header (`_from_isr` suffix for ISR-callable ones).
- Existing project: match its conventions (naming, error type, formatting, comments) - `tools/style_probe.py` summarises them. These rules apply to new projects and to correctness everywhere, never as a reason to restyle existing code.

## Before you finish a change
1. Does it build with zero new warnings?
2. Any new shared data between ISR and main? -> volatile + atomic access review.
3. Any new wait loop? -> timeout.
4. Flash/RAM delta reasonable? (the size hook reports it after builds).
5. If you touched clocks, power or pins: re-check against the reference manual, not memory.
