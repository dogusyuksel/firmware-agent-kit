---
name: flash-debug
description: Flashing and on-target debugging of STM32, ESP32 and SAMV71 (and other MCUs) with open-source tools - OpenOCD, pyOCD, probe-rs, stlink, esptool/idf.py, bossac, edbg, dfu-util - GDB sessions, semihosting, SWO/ITM, RTT, reading registers/memory, and recovering a target that will not connect. Use when the user wants to program a board, start a debug session, get logs off the target, or the probe cannot connect.
---

# Flashing and debugging

## Rules
1. Use the commands in `.claude/firmware.json` (`flash`, `debug_server`, `elf`) when present. Only fall back to building a command yourself if they are missing - then propose adding it via `/fw-init`.
2. Check which tools are installed (SessionStart context lists them) before suggesting one.
3. Prefer flashing the **ELF** (addresses are embedded) over raw `.bin` (needs a correct base address; wrong address = bricked boot).
4. Always `verify` after programming and `reset` to run.
5. Destructive operations (mass erase, option bytes, fuses, readout protection) are gated by the kit's hooks. Never try to work around a deny; explain to the user what the command would do and let them run it.
6. Long-running servers (OpenOCD, GDB server, RTT viewer) should run in the background; keep commands non-interactive (`-batch`, `-ex`, `exit`).

## Programming one-liners (open-source tools)
```sh
# STM32 - OpenOCD / pyOCD / probe-rs / stlink-org
openocd -f interface/stlink.cfg -f target/stm32f4x.cfg -c "program build/app.elf verify reset exit"
pyocd flash -t stm32f407vg build/app.elf
probe-rs download --chip STM32F407VGTx build/app.elf && probe-rs reset --chip STM32F407VGTx
st-flash --reset write build/app.bin 0x08000000            # .bin needs the base address
dfu-util -a 0 -s 0x08000000:leave -D build/app.bin           # ROM DFU bootloader (BOOT0=1)
# ESP32 family
idf.py -p PORT flash monitor                                 # ESP-IDF projects
esptool.py --chip esp32s3 -p PORT write_flash 0x10000 build/app.bin
# SAM V71 (SAMV71-XULT has an EDBG CMSIS-DAP probe)
openocd -f interface/cmsis-dap.cfg -f target/atsamv.cfg -c "program build/app.elf verify reset exit"
edbg -b -t samv71 -pv -f build/app.bin                        # program + verify
bossac -p PORT -e -w -v -b build/app.bin -R                   # SAM-BA; -e/-b are hook-gated
```
Vendor tools such as J-Link Commander, STM32CubeProgrammer, nrfjprog or MPLAB IPE are proprietary: the kit does not recommend or install them, but its guard hooks still gate their destructive commands if the user runs them.
Target config names, chip names and `-device` strings vary - list them with `openocd -c "help"`/`ls $(openocd-scripts)/target`, `pyocd list --targets`, `probe-rs chip list`.

## GDB session
```sh
# terminal 1 (background): GDB server
openocd -f interface/stlink.cfg -f target/stm32f4x.cfg          # gdb port 3333
#   or: pyocd gdbserver -t <target>   (3333)   |  probe-rs gdb   |  ESP-IDF: idf.py openocd + idf.py gdb
# terminal 2: batch-mode GDB (non-interactive, agent-friendly)
arm-none-eabi-gdb -q -batch build/app.elf \
  -ex "target extended-remote :3333" \
  -ex "monitor reset halt" -ex "load" \
  -ex "break main" -ex "continue" -ex "bt" -ex "info registers"
```
Useful commands: `monitor reset halt`, `x/16xw 0x20000000`, `p/x SCB->CFSR` (needs debug info with the CMSIS header), `info line *0x08001234`, `watch -l var`, `display/i $pc`, `stepi`, `finish`, `monitor mdw 0x40021000 4` (OpenOCD raw read). For peripherals by name, load the SVD (Cortex-Debug in VS Code, `PyCortexMDebug` `svd` command in GDB).
Debug builds: `-Og -g3`. Optimised builds lie about variables ("optimized out") - set breakpoints by address and read registers/memory directly.

## Getting logs off the target
| Method | Pins | Notes |
|---|---|---|
| UART | TX (+GND) | Simplest; buffer + DMA/IRQ, never block in ISRs |
| RTT | SWD only | Fast, non-blocking ring buffer in RAM (SEGGER RTT protocol, target code is BSD-licensed); read with probe-rs (`rtt`), OpenOCD (`rtt setup/start`, `rtt server start 9090 0`) or pyOCD |
| SWO/ITM | SWO pin | `ITM_SendChar`; needs correct trace clock (`tpiu config`/`swo` in OpenOCD); not on M0/M0+ |
| Semihosting | SWD | Very slow, halts core per call; HardFaults (BKPT) when no debugger attached - disable in release (`--specs=rdimon.specs` only in debug) |

## Probe cannot connect - recovery ladder
1. Check wiring: SWDIO, SWCLK, GND, VTref (target voltage sense), NRST. Lower speed (`adapter speed 100`).
2. Target powered? Measure VDD. Is the debugger supplying or sensing power?
3. Firmware disables SWD pins / enters deep sleep / reconfigures clocks immediately -> **connect under reset**: OpenOCD `reset_config srst_only srst_nogate connect_assert_srst`; probe-rs `--connect-under-reset`; pyOCD `-O connect_mode=under-reset`.
4. Boot into the ROM bootloader (STM32 BOOT0=1) to stop user code running, then erase/reflash.
5. Readout protection / APPROTECT enabled -> recovery requires mass erase (STM32 RDP 1->0 via OpenOCD `stm32xx unlock`, SAMV71 ERASE pin, nRF `pyocd erase --chip`). These are destructive and hook-gated: explain and ask the user.
6. RDP level 2 / JTAG fuses / eFuse lock = permanent. No recovery.
