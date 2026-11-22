---
name: renode-integration
description: Integration and system tests of firmware binaries in simulation with Renode (Robot Framework, .resc/.repl platforms, UART/GPIO assertions, peripheral stubs) and QEMU (Cortex-M boards, Espressif QEMU for ESP32), run locally or in the renode container and CI. Use when writing integration tests, running the real ELF without hardware, or setting up HIL-free CI.
---

# Integration tests with Renode / QEMU

Unit tests (Ceedling) prove logic on the host; integration tests run the **real ELF** on a simulated MCU and assert on its observable behaviour (UART output, GPIO, timing).

## Support matrix (verify against your Renode version: `ls $(renode-dir)/platforms/cpus`)
| Target | Option |
|---|---|
| STM32F0/F4/F7/G0/H7/L0/L1/WBA... | Renode platforms exist for many parts/boards (e.g. `stm32f4_discovery-kit.repl`) |
| SAM V71 / E70 | no official platform known - write a `.repl` with the CPU (`CPU.CortexM`, `cpuType: "cortex-m7"`), memories and the peripherals you need, or stub peripherals with Python peripherals |
| ESP32 (Xtensa) | Renode support is limited -> Espressif QEMU (`idf.py qemu`, esp-idf container); ESP32-C3 has partial RISC-V support in both |
| Generic Cortex-M logic | QEMU `-M mps2-an385/an500` or `lm3s6965evb` with semihosting for pure-logic integration |

## Layout
```
tests/integration/
  app.resc          # machine setup: platform, ELF, UART analyzer
  app.robot         # Robot Framework test cases
  stubs/            # optional Python peripherals / .repl overlays
```
Templates: `templates/renode/app.resc` and `templates/renode/app.robot` from the kit.

## Minimal Robot test
```robot
*** Settings ***
Suite Setup       Setup
Suite Teardown    Teardown
Test Teardown     Test Teardown
Resource          ${RENODEKEYWORDS}

*** Variables ***
${ELF}            ${CURDIR}/../../build/app.elf
${UART}           sysbus.usart2

*** Test Cases ***
Boots And Prints Banner
    Execute Command           mach create
    Execute Command           machine LoadPlatformDescription @platforms/boards/stm32f4_discovery-kit.repl
    Execute Command           sysbus LoadELF @${ELF}
    Create Terminal Tester    ${UART}    timeout=5
    Start Emulation
    Wait For Line On Uart     fw: boot ok
    Write Line To Uart        version    waitForEcho=false
    Wait For Line On Uart     v\\d+\\.\\d+    treatAsRegex=true
```
Run: `renode-test tests/integration/app.robot` (or `python tools/fw_container.py run renode -- renode-test tests/integration/app.robot`). Results in `robot_output.xml`/`log.html`.

## Practices
- `Write Line To Uart` waits for the firmware to echo the line by default in current Renode versions. Pass `waitForEcho=false` unless your firmware echoes, or the test hangs until the timeout.
- Reference: `examples/renode-smoke` (minimal STM32F4 firmware + robot test, run in CI).
- Build a dedicated test configuration if needed (`-DSIMULATION=1` only for things the simulator cannot model, e.g. skip waiting for an external PHY) - keep differences minimal and documented.
- Assert on behaviour (UART protocol, GPIO toggles via `sysbus.gpioPortA.led`, register values with `sysbus ReadDoubleWord`) rather than internal variables.
- Use virtual time: Renode is deterministic; timeouts in tests are virtual-time based - avoid flaky wall-clock waits.
- Missing peripheral -> model just enough: Python peripheral in the `.repl`, or `sysbus Tag <0xaddr 4> "PERIPH" 0x0` to return fixed values, and log unimplemented accesses (`logLevel 0`) to see what the firmware touches.
- FreeRTOS works in Renode (SysTick/NVIC modelled); check stack/heap issues the same way as on hardware.
- CI: run in the `renode` container; publish Robot logs as artifacts.

## QEMU quick reference
```sh
qemu-system-arm -M mps2-an385 -nographic -semihosting-config enable=on,target=native -kernel build/test.elf
idf.py qemu monitor        # ESP32 with Espressif QEMU (esp-idf container)
```
