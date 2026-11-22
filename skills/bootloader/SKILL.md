---
name: bootloader
description: Bootloaders and field firmware updates for STM32, ESP32 and SAMV71 - flash layout, image header and CRC/signature, A/B slots with rollback, jump to application (VTOR, MSP, peripheral deinit), update transport (UART/CAN/USB DFU/OTA), power-fail safety, vendor ROM bootloaders and ESP-IDF OTA. Use when designing or debugging a bootloader, OTA/DFU, dual-image updates, or a device that does not start after an update.
---

# Bootloaders and firmware update

Changes here can brick devices in the field. Always plan first (`/fw-plan`), and test power loss at every step on real hardware or in Renode before shipping.

## Design checklist
1. **Flash layout** (document it in one header + the linker scripts): bootloader | (config/keys) | slot A | slot B / download area | persistent data. Align slots to erase-sector boundaries (STM32F4 sectors differ in size; SAMV71 erases in pages/sectors via EEFC; ESP32 uses the partition table).
2. **Image header** at a fixed offset of each slot: magic, header version, image size, load/entry address, firmware version, CRC32 (or SHA-256) and optional signature (ECDSA/Ed25519 - e.g. MCUboot does this; open source).
3. **Validation before jump**: header magic, size bounds, CRC/signature over the whole image, vector table sanity (initial SP inside RAM, reset vector inside the slot and odd/Thumb).
4. **A/B with rollback**: new image boots in "trial" state; the application confirms itself after a self-test (and successful communication); otherwise the bootloader reverts after N attempts. Keep the state in a power-fail-safe record (two copies with sequence counter + CRC).
5. **Power-fail safety**: never erase the only valid image; write the download slot, verify, then switch the boot flag atomically.
6. **Anti-rollback / security** (if required): monotonic version counter, signed images, debug lock - irreversible steps (RDP2, eFuses) are gated by the kit's hooks and are the user's decision.
7. **Recovery path**: vendor ROM bootloader (STM32 system memory via BOOT0, SAMV71 SAM-BA via GPNVM1/ERASE, ESP32 ROM download mode via GPIO0) must stay reachable; document how.

## Jumping to the application (Cortex-M: STM32, SAMV71)
```c
static void jump_to_app(uint32_t app_base)
{
    const uint32_t *vt = (const uint32_t *)app_base;
    __disable_irq();
    SysTick->CTRL = 0;                                   /* stop SysTick */
    for (uint32_t i = 0; i < 8; i++) { NVIC->ICER[i] = 0xFFFFFFFFu; NVIC->ICPR[i] = 0xFFFFFFFFu; }
    /* deinit every peripheral/clock the bootloader used (or return clocks to reset state) */
    SCB->VTOR = app_base;                                /* table alignment per VTOR rules */
    __DSB(); __ISB();
    __set_MSP(vt[0]);
    __enable_irq();                                      /* the app's startup will configure IRQs */
    ((void (*)(void))vt[1])();
}
```
- On Cortex-M7 (SAMV71, STM32F7/H7): clean and disable D-cache (and disable I-cache or invalidate) before jumping if the bootloader enabled them; the app re-enables.
- With FreeRTOS in the bootloader: never jump from a task; jump before starting the scheduler, or reset into the app via a "boot app" flag in noinit RAM (cleanest).
- The application's linker script origin and `SystemInit` VTOR setting must match the slot address.

## ESP32
- Use ESP-IDF OTA: `esp_ota_begin/write/end`, `esp_ota_set_boot_partition`, rollback (`CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE` + `esp_ota_mark_app_valid_cancel_rollback()` after self-test), `esp_https_ota` for HTTPS. Partition table must contain `otadata` + two `ota_x` slots.
- Secure boot / flash encryption burn eFuses (irreversible) - development mode first, user decision.

## Transports
- UART/RS-485 with framed packets (length, sequence number, CRC16/32, ACK/NACK, timeouts, resume); CAN with ISO-TP; USB DFU (dfu-util, open source); OTA over network.
- Keep the protocol stateless enough to resume after a link drop; never trust lengths from the wire.

## Debugging "does not start after update"
Read the header and CRC of the active slot (GDB `x/16xw <slot>`), check VTOR and MSP after the jump, verify the app was linked for that slot (`arm-none-eabi-objdump -h app.elf`), confirm interrupts pending from the bootloader were cleared, and check the boot-state record. Use the `hardfault-debug` skill if it faults.
