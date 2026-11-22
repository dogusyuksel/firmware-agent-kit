---
name: esp32
description: ESP32-family (ESP32, S2, S3, C3, C6, H2, P4) firmware with ESP-IDF - components and idf.py, sdkconfig/Kconfig, SMP FreeRTOS differences, IRAM_ATTR ISRs and flash-cache rules, spinlock critical sections, task watchdog, heap_caps/PSRAM, partitions/NVS/OTA, panic and core-dump decoding, eFuse/secure boot/flash encryption dangers, QEMU and host tests. Use when working on ESP32 projects.
---

# ESP32 / ESP-IDF notes

## Project and build
- `idf.py set-target esp32s3`, `idf.py build`, `idf.py -p PORT flash monitor`, `idf.py size` / `size-components` / `size-files` (accurate IRAM/DRAM/flash split - prefer over `size`).
- Components: `idf_component_register(SRCS ... INCLUDE_DIRS ... REQUIRES ... PRIV_REQUIRES ...)`; dependencies in `idf_component.yml` (managed_components/ is generated - do not edit).
- Configuration: `sdkconfig` (generated, commit `sdkconfig.defaults` instead), Kconfig options in code as `CONFIG_*`.
- Compile DB: `build/compile_commands.json` - summarise with `tools/build_info.py`.
- Toolchains: Xtensa (`xtensa-esp32-elf-`, `xtensa-esp32s3-elf-`) for ESP32/S2/S3, RISC-V (`riscv32-esp-elf-`) for C3/C6/H2/P4. Use the `esp-idf` container for reproducible builds.

## FreeRTOS in ESP-IDF (SMP)
- `app_main()` runs in a task after the scheduler started - never call `vTaskStartScheduler()`; returning from `app_main` is allowed.
- **Stack sizes are in bytes** (`xTaskCreate(fn, "n", 4096, ...)`). printf/ESP_LOG need >= 2-3 KB.
- `xTaskCreatePinnedToCore(..., core)`; `tskNO_AFFINITY` lets the scheduler choose. Wi-Fi/BT run on core 0 by default.
- Critical sections take a spinlock: `static portMUX_TYPE s_mux = portMUX_INITIALIZER_UNLOCKED; portENTER_CRITICAL(&s_mux)`; in ISRs `portENTER_CRITICAL_ISR(&s_mux)`. They also disable interrupts on the calling core - keep them tiny.
- `vTaskSuspendAll()` only affects the calling core - not a lock.
- Task watchdog (TWDT) fires when a task (or idle) does not run for `CONFIG_ESP_TASK_WDT_TIMEOUT_S` - every task loop must block.

## Interrupts and flash cache
- Register with `gpio_isr_handler_add` / `esp_intr_alloc` or driver callbacks (`.on_alarm`, `.on_trans_done`...) - all run in ISR context.
- With `ESP_INTR_FLAG_IRAM` the handler and everything it touches must be in IRAM/DRAM (`IRAM_ATTR`, `DRAM_ATTR`) because flash cache is disabled during flash writes; otherwise "Cache disabled but cached memory region accessed".
- No FPU use in ISRs; no `ESP_LOGx` in ISRs (use `ESP_DRAM_LOGx` / `ESP_EARLY_LOGx` sparingly); only `...FromISR` RTOS APIs + `portYIELD_FROM_ISR()`.

## Memory
- `heap_caps_malloc(size, MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL)` for DMA buffers; PSRAM (`MALLOC_CAP_SPIRAM`) is not DMA-capable on all chips and is slower.
- Monitor: `heap_caps_get_free_size`, `heap_caps_get_minimum_free_size`, `heap_caps_check_integrity_all`; heap tracing (`CONFIG_HEAP_TRACING`) for leaks.
- `ESP_ERROR_CHECK(x)` aborts on error - fine for init, not for recoverable runtime errors (handle `esp_err_t`).

## Storage, partitions, OTA
- `partitions.csv`: nvs, phy_init, factory/ota_0/ota_1, otadata, spiffs/fat. Changing offsets breaks OTA of deployed devices.
- NVS: commit after writes, handle `ESP_ERR_NVS_NO_FREE_PAGES`/`NEW_VERSION_FOUND` by erase+init only with user consent (data loss).
- OTA: validate image, mark valid after self-test (`esp_ota_mark_app_valid_cancel_rollback`), enable rollback.

## Security - irreversible
- eFuses (secure boot keys, flash encryption, JTAG disable) are one-time programmable. With `CONFIG_SECURE_BOOT`/`CONFIG_SECURE_FLASH_ENC_ENABLED` the **first boot burns eFuses automatically**. The kit denies `espefuse burn*` and asks before flashing such images.
- Development: use "Development" flash-encryption mode; never on boards that must stay reflashable.

## Debugging
- Panic output: `idf.py monitor` decodes backtraces automatically (addr2line); core dumps to flash/UART: `idf.py coredump-info` / `coredump-debug`.
- JTAG: built-in USB-JTAG (S3/C3/C6) with OpenOCD from ESP-IDF (`idf.py openocd`, `idf.py gdb`).
- Strapping pins (ESP32: GPIO0, 2, 5, 12, 15; others differ - check the datasheet) must be at the right level at reset; GPIO12 (MTDI) at 1 on ESP32 selects 1.8 V flash and can prevent boot.

## Testing
- Unit tests: Unity is built into ESP-IDF (`test_apps`, `pytest-embedded`); host-side tests with the Linux target (`idf.py --preview set-target linux`) and CMock for component mocks; or Ceedling on pure logic.
- Emulation: Espressif QEMU (`idf.py qemu monitor`) for ESP32/S3/C3 - limited peripherals. Renode support for ESP32 is limited; prefer QEMU + host tests.
