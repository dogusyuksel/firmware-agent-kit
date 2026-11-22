---
name: linker-startup
description: GNU ld linker scripts, startup code and memory layout for bare-metal MCUs - vector table, reset handler, .data/.bss init, stack/heap, VMA vs LMA, placing code in RAM, noinit/retained sections, multiple RAM regions, bootloader + application layouts and VTOR relocation. Use when editing *.ld / startup files, adding a bootloader, fixing "region overflowed" or boot-time crashes.
---

# Linker scripts and startup code

## Mental model
- **VMA** (where it runs) vs **LMA** (where it is stored). `.data` has VMA in RAM and LMA in flash; startup copies it. `.bss` has only a VMA and is zeroed.
- The vector table must be at the address the core boots from (usually start of flash), aligned to its size rounded up to a power of two (min 128 B on Cortex-M; `VTOR` alignment rules).
- Entry 0 = initial MSP (top of stack), entry 1 = `Reset_Handler` (with Thumb bit set - the linker does this for Thumb functions).

## Minimal Cortex-M linker script skeleton
```ld
ENTRY(Reset_Handler)

MEMORY
{
  FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 512K   /* from datasheet memory map */
  RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 128K
}

_estack     = ORIGIN(RAM) + LENGTH(RAM);
_stack_size = 0x1000;   /* sized from -fstack-usage / stack painting, not guessed */
_heap_size  = 0x0;      /* 0 if no malloc */

SECTIONS
{
  .isr_vector : { . = ALIGN(4); KEEP(*(.isr_vector)) . = ALIGN(4); } > FLASH

  .text : {
    *(.text*) *(.rodata*)
    KEEP(*(.init)) KEEP(*(.fini))
    . = ALIGN(4);
  } > FLASH

  .ARM.exidx : { *(.ARM.exidx* .gnu.linkonce.armexidx.*) } > FLASH

  .preinit_array : { PROVIDE_HIDDEN(__preinit_array_start = .); KEEP(*(.preinit_array*)) PROVIDE_HIDDEN(__preinit_array_end = .); } > FLASH
  .init_array    : { PROVIDE_HIDDEN(__init_array_start = .); KEEP(*(SORT(.init_array.*))) KEEP(*(.init_array*)) PROVIDE_HIDDEN(__init_array_end = .); } > FLASH

  _sidata = LOADADDR(.data);
  .data : {
    . = ALIGN(4); _sdata = .;
    *(.data*)
    *(.ramfunc*)            /* functions executed from RAM */
    . = ALIGN(4); _edata = .;
  } > RAM AT> FLASH

  .bss (NOLOAD) : {
    . = ALIGN(4); _sbss = .;
    *(.bss*) *(COMMON)
    . = ALIGN(4); _ebss = .;
  } > RAM

  .noinit (NOLOAD) : { *(.noinit*) } > RAM   /* survives soft reset; never initialised */

  ._stack_heap (NOLOAD) : {
    . = ALIGN(8); PROVIDE(end = .); . += _heap_size;
    . = ALIGN(8); . += _stack_size;
  } > RAM      /* reserves space so overflow is a LINK error, not a runtime crash */

  /DISCARD/ : { libc.a(*) libm.a(*) libgcc.a(*) }  /* remove only if you truly do not use them */
}
```
Adapt instead of copying blindly - the `/DISCARD/` line in particular is an example, not a default.

## Minimal startup in C
```c
extern uint32_t _sidata, _sdata, _edata, _sbss, _ebss, _estack;
extern void __libc_init_array(void);
int main(void);

void Reset_Handler(void)
{
    /* SystemInit(): FPU enable (CPACR), clock setup or keep reset clock, VTOR if relocated */
    SystemInit();
    for (uint32_t *s = &_sidata, *d = &_sdata; d < &_edata;) *d++ = *s++;
    for (uint32_t *d = &_sbss; d < &_ebss;) *d++ = 0;
    __libc_init_array();      /* C++ constructors / __attribute__((constructor)) */
    main();
    for (;;) { __BKPT(0); }   /* main must not return */
}

void Default_Handler(void) { for (;;) { __BKPT(0); } }
#define WEAK_ALIAS __attribute__((weak, alias("Default_Handler")))
void NMI_Handler(void) WEAK_ALIAS;
void HardFault_Handler(void) WEAK_ALIAS;
/* ... one per vector, names exactly as in the device's vector table ... */

__attribute__((section(".isr_vector"), used))
void (* const g_vectors[])(void) = {
    (void (*)(void))&_estack, Reset_Handler, NMI_Handler, HardFault_Handler, /* ... */
};
```
Caveats: compile the startup file with `-fno-tree-loop-distribute-patterns` (or the loops may be turned into `memcpy`/`memset` calls, which is fine only if those functions do not depend on `.data`). If SystemInit configures external RAM where `.data` lives, it must run before the copy.

## Common tasks
- **Function in RAM** (flash erase routines, fast ISRs): `__attribute__((section(".ramfunc"), noinline, long_call))`. Everything it calls must also be in RAM.
- **Variable in a specific RAM** (CCM/DTCM/SRAM2): add a MEMORY region and an output section `> CCMRAM`; if initialised, it needs its own copy loop (`AT> FLASH` + symbols). CCM is often not DMA-accessible.
- **Retained/noinit data** for reset reasons or crash logs: `__attribute__((section(".noinit")))` + a magic word + CRC to detect garbage after power-on.
- **Bootloader + app**: split FLASH into two regions in two linker scripts. The app's vector table starts at its own origin; the bootloader jumps with:
  ```c
  uint32_t *app = (uint32_t *)APP_BASE;
  __disable_irq();
  /* deinit peripherals, SysTick->CTRL = 0, clear NVIC enables & pendings */
  SCB->VTOR = APP_BASE;
  __set_MSP(app[0]);
  __DSB(); __ISB();
  ((void (*)(void))app[1])();
  ```
  The app must not reset VTOR back to 0x08000000 in SystemInit (check `VECT_TAB_OFFSET`/`USER_VECT_TAB_ADDRESS`).
- **Firmware header/version/CRC** at a fixed offset: dedicated `KEEP` section right after the vector table; patch CRC post-link with a script (objcopy + python).

## Diagnosing
- `region 'FLASH' overflowed by N bytes` -> see the `memory-footprint` skill.
- Crash before main: step `Reset_Handler` in GDB; check `_sidata`/`_sdata` symbols (`arm-none-eabi-nm -n app.elf | grep -E "_s|_e"`), MSP value in vector[0], and that the vector table address matches VTOR.
- Inspect sections: `arm-none-eabi-objdump -h app.elf` (look at VMA/LMA columns), `readelf -S`, `readelf -l` (program headers).
- Globals with garbage initial values -> `.data` copy loop missing/wrong, or the section is not listed inside `.data`.
- C++ static constructors not running -> `__libc_init_array` not called or `.init_array` not `KEEP`ed.
