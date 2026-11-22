---
name: host-unit-test
description: Unit-test firmware on the host with Ceedling (Unity + CMock) - project.yml setup, mocking HAL/ESP-IDF/ASF drivers and FreeRTOS through an OSAL, fake register structs, testing ISR handlers and time-dependent code, sanitizers/leak checks and coverage, plus CMake+Unity alternative and CI. Use when adding tests, making code testable, or before refactoring driver/protocol/state-machine code.
---

# Host unit tests (Ceedling first)

Test logic on the PC: parsers, state machines, ring buffers, CRCs, command handlers, driver logic behind interfaces. Keep the untestable layer (register access, vendor HAL calls) thin. Follow an existing harness if the project has one.

## Ceedling setup
- Install (free, MIT): Ruby + `gem install ceedling`, or use the `arm-dev` container (`python <kit>/tools/fw_container.py run arm-dev -- ceedling test:all`).
- New harness: `ceedling new <name>` or copy `<kit>/templates/ceedling/project.yml` and adapt `:paths:`. The template enables CMock, pretty reports, gcov and an ASan/UBSan option. Its syntax targets Ceedling 1.0; check `ceedling version` and its docs for older 0.31 projects.
- Layout: `test/test_<module>.c`, `test/support/` (fakes, stub headers). `ceedling test:<module>`, `ceedling test:all`, `ceedling gcov:all`.

## Mocking strategy
| Dependency | Approach |
|---|---|
| Your own module interfaces (`spi_bus.h`, `osal.h`) | `#include "mock_spi_bus.h"` - CMock generates expectations from the header |
| FreeRTOS / CMSIS-RTOS2 | Mock your `osal.h` wrapper (recommended). Mocking `queue.h`/`task.h` directly is painful (macros) - if unavoidable, put simplified prototype headers in `test/support/` |
| STM32 HAL / ESP-IDF drivers / ASF4 | Wrap the few calls you use in a thin `bsp_*.h` and mock that; or mock vendor headers via stubs in `test/support/` with only the needed prototypes |
| Registers | Inject a register-block pointer and pass a RAM struct (`USART_TypeDef fake = {0};`), then assert on fields |
| Time | Inject `uint32_t (*now_ms)(void)` / mock `osal_ms()`; test wraparound at 0xFFFFFFFF |
| Core intrinsics | `test/support/cmsis_stub.h` defining `__disable_irq()`, `__DMB()`, `__WFI()` as no-ops or counters |

```c
/* test/test_uart_rx.c */
#include "unity.h"
#include "uart_rx.h"
#include "mock_osal.h"

void setUp(void) { uart_rx_init(); }
void tearDown(void) {}

void test_isr_byte_is_queued_and_task_woken(void)
{
    osal_queue_send_from_isr_ExpectAndReturn(NULL, NULL, NULL, 0);
    osal_queue_send_from_isr_IgnoreArg_q(); osal_queue_send_from_isr_IgnoreArg_item(); osal_queue_send_from_isr_IgnoreArg_woken();
    uart_rx_isr_byte(0x55);                      /* call the ISR-side function directly */
}

void test_frame_with_bad_crc_is_rejected(void)
{
    const uint8_t f[] = {0x7E, 0x01, 0x02, 0xFF, 0x7E};
    TEST_ASSERT_EQUAL(UART_RX_ERR_CRC, uart_rx_parse(f, sizeof f));
}
```

## What to cover
Boundaries (empty/full, max length, zero length, index and tick wraparound), every error path (timeouts, NACK, CRC, NULL from create calls), every state-machine transition including illegal events, and ISR-side functions called directly. Target behaviour, not implementation details.

## Leaks, UB, coverage
- Sanitizers in the test build: `-fsanitize=address,undefined -fno-omit-frame-pointer` (template option). LeakSanitizer reports leaks at exit on Linux; on Windows use the container.
- Valgrind (Linux): `valgrind --leak-check=full --error-exitcode=1 build/test/out/test_x.out`.
- Coverage: `ceedling gcov:all` (+ `gcovr` HTML). Aim for branches in logic modules, not vendor code.
- Host vs target type differences: use fixed-width types, `_Static_assert` sizes; `long` is 64-bit on Linux x86-64 but 32-bit on ARM.

## Alternatives
- CMake + Unity + CTest (FetchContent Unity, separate host build dir), GoogleTest for C++.
- ESP-IDF: Unity test apps + `pytest-embedded`, or the Linux target (`idf.py --preview set-target linux`) with CMock component mocks.
- Integration on the real ELF: `renode-integration` skill.

## Workflow
1. Failing test that captures the bug/feature.
2. Minimal production change.
3. Host tests -> cross build (no new warnings) -> on-target or Renode smoke test if available.
4. Report which layers were verified; never claim hardware behaviour you did not observe.
