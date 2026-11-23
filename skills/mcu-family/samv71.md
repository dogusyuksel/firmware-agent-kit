# SAM V71 / V70 / E70 / S70 (Cortex-M7) reference

Verify every register name and value against the SAM E70/S70/V70/V71 datasheet and the DFP device header (`samv71q21b.h` etc.) - this family shares one datasheet.

## Reset-time traps
- **The watchdog (WDT) is enabled after reset** with a ~16 s timeout. Disable it early (`WDT->WDT_MR = WDT_MR_WDDIS_Msk;` - WDT_MR is write-once) or configure and kick it. RSWDT likewise.
- `CCFG_SYSIO` routes PB4/PB5 (TDI/TDO), PB6/PB7 (SWDIO/SWCLK) and PB12 (ERASE) to system functions by default. Repurposing PB6/PB7 kills SWD; PB12 as ERASE: holding it high at reset **erases the whole flash and clears GPNVM** (recovery path, also destructive).

## Clocks and flash
- PMC: main crystal or RC -> PLLA -> MCK. CPU up to 300 MHz, **MCK (bus) max 150 MHz** -> `PMC_MCKR` MDIV = 2 at 300 MHz.
- Set EEFC flash wait states (`EFC->EEFC_FMR FWS`) for the target frequency **before** switching to the faster clock.
- Peripheral clocks by peripheral ID: `PMC->PMC_PCER0` (IDs < 32), `PMC->PMC_PCER1` (>= 32). The ID table is in the datasheet "Peripheral Identifiers".
- Every PMC status wait (MOSCXTS, LOCKA, MCKRDY) needs a timeout.

## Pins
- PIO controller per port: disable PIO control (`PIO_PDR`) and select peripheral A-D via `PIO_ABCDSR[0..1]`. Writes to protected registers need `PIO_WPMR` unlocked if write protection is on.
- Use the datasheet pin-multiplexing table, not memory; package (LQFP64/100/144, BGA) changes what exists.

## Cortex-M7: cache, TCM, MPU
- Enable I/D cache early (`SCB_EnableICache(); SCB_EnableDCache();`) and handle coherency for **XDMAC**, GMAC, HSMCI, USBHS: clean before TX, invalidate after RX, 32-byte aligned buffers, or a non-cacheable MPU region for DMA buffers.
- TCM size is selected by GPNVM bits 7-8 and enabled in `SCB->ITCMCR/DTCMCR`; DTCM is not reachable by every DMA master - check the bus matrix.
- GPNVM bit 1 selects boot from flash vs ROM (SAM-BA). If a board "does nothing" after flashing, check that GPNVM1 is set. GPNVM0 is the security bit (locks debug; clearing needs a full ERASE). The kit asks before any GPNVM change.
- Use the MPU to guard the stack bottom and NULL page; mark peripheral space as device memory (default map does).

## Frameworks
- CMSIS DFP (`SAMV71_DFP`) headers + startup: bare-metal register style (`PIOA->PIO_SODR`).
- ASF4 (Atmel START) / MPLAB Harmony v3: generated `config/default/peripheral/*` code - treat as vendor/generated, wrap rather than edit (the kit protects `config/default/peripheral/` and `/packs/`).

## FreeRTOS on Cortex-M7
- Port: `portable/GCC/ARM_CM7/r0p1` is required for Cortex-M7 **r0p0/r0p1** cores (errata 837070); read `SCB->CPUID` (variant/revision) to confirm which applies to your silicon revision, else `ARM_CM4F` works for M7.
- `configPRIO_BITS 3` (__NVIC_PRIO_BITS = 3 on SAM V7x) - priorities 0..7; ISRs calling FromISR APIs need priority >= `configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY`.
- Lazy FPU stacking (FPv5 double precision) increases ISR stack usage.
