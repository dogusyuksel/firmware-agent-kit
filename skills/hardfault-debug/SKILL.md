---
name: hardfault-debug
description: Diagnose ARM Cortex-M HardFault, MemManage, BusFault and UsageFault crashes - capture the stacked exception frame, decode CFSR/HFSR/MMFAR/BFAR, map PC/LR to source, and find the root cause (stack overflow, NULL/wild pointer, unaligned access, FPU disabled, bad vector table). Use when firmware crashes, resets unexpectedly, ends up in a fault/Default handler, or the user pastes fault register values.
---

# Cortex-M fault debugging

Work from evidence, not guesses. The goal is: faulting PC -> source line -> why that access was invalid.

## 1. Capture the evidence
### With a debugger attached (preferred)
Halt in the fault handler, then in GDB:
```gdb
info registers                     # note sp, lr (EXC_RETURN), xpsr
p/x *(uint32_t*)0xE000ED28         # CFSR
p/x *(uint32_t*)0xE000ED2C         # HFSR
p/x *(uint32_t*)0xE000ED34         # MMFAR
p/x *(uint32_t*)0xE000ED38         # BFAR
# stacked frame: r0 r1 r2 r3 r12 lr pc xpsr  (use $psp instead of $msp if EXC_RETURN bit2 = 1)
x/8xw $msp
info symbol <stacked_pc>
list *<stacked_pc>
```
OpenOCD/pyOCD/J-Link GDB servers all expose these. Some IDEs have a "Fault Analyzer" view that does the same.

### Without a debugger: a capturing handler
```c
typedef struct { uint32_t r0, r1, r2, r3, r12, lr, pc, xpsr; } fault_frame_t;

typedef struct {
    uint32_t magic, cfsr, hfsr, mmfar, bfar, exc_return;
    fault_frame_t frame;
} fault_log_t;
__attribute__((section(".noinit"))) volatile fault_log_t g_fault_log;   /* survives reset */

void HardFault_Handler_C(fault_frame_t *f, uint32_t exc_return)
{
    g_fault_log.cfsr  = SCB->CFSR;   g_fault_log.hfsr = SCB->HFSR;
    g_fault_log.mmfar = SCB->MMFAR;  g_fault_log.bfar = SCB->BFAR;
    g_fault_log.exc_return = exc_return;
    g_fault_log.frame = *f;
    g_fault_log.magic = 0xFA017EADu;
    __BKPT(0);                 /* halts if a debugger is attached */
    NVIC_SystemReset();        /* report g_fault_log on next boot */
}

__attribute__((naked)) void HardFault_Handler(void)
{
    __asm volatile(
        "tst lr, #4        \n"
        "ite eq            \n"
        "mrseq r0, msp     \n"
        "mrsne r0, psp     \n"
        "mov r1, lr        \n"
        "b HardFault_Handler_C \n");
}
```
On Cortex-M0/M0+ (ARMv6-M) there is no `ite`/CFSR: use `movs r0,#4; mov r1,lr; tst r0,r1; beq 1f; mrs r0,psp; b 2f; 1: mrs r0,msp; 2: ...` and rely on the stacked PC only.
Also enable the separate fault handlers so faults do not all escalate to HardFault: `SCB->SHCSR |= SCB_SHCSR_MEMFAULTENA_Msk | SCB_SHCSR_BUSFAULTENA_Msk | SCB_SHCSR_USGFAULTENA_Msk;` and optionally `SCB->CCR |= SCB_CCR_DIV_0_TRP_Msk;`.

## 2. Decode
Run the bundled decoder (path relative to this skill directory):
```
python scripts/decode_fault.py --cfsr 0x... --hfsr 0x... --bfar 0x... --mmfar 0x... \
       --exc-return 0x... --pc 0x... --lr 0x... --elf build/app.elf
```
It explains each set bit and runs `addr2line` on PC/LR.

## 3. Interpret
| Evidence | Likely cause | Next step |
|---|---|---|
| STKERR / MSTKERR, SP near RAM start or below `_sstack` | Stack overflow | `-fstack-usage`, stack painting, move big locals to static, increase stack in linker script |
| PRECISERR + BFAR small (< 0x1000) | NULL pointer + struct offset | Find which pointer at the faulting PC was NULL |
| PRECISERR + BFAR in a peripheral range | Peripheral clock not enabled / wrong instance | Check RCC enable before access |
| IMPRECISERR | A buffered write some instructions earlier | Disable write buffer (`DISDEFWBUF`) to make it precise, re-run |
| IBUSERR / IACCVIOL, PC = 0 or 0xFFFFFFFx | Called NULL/erased function pointer or corrupted return address | Check callbacks/vtables; stack smashing (buffer overrun of a local array) |
| INVSTATE | Branch to even address | Function pointer built from data, missing Thumb bit, corrupted LR |
| UNDEFINSTR | Wrong `-mcpu`, executing data, flash not programmed | Verify build flags and flash contents |
| NOCP | FPU used before CPACR enable | Enable FPU in `SystemInit` before any float code (including compiler-generated) |
| UNALIGNED | `LDRD`/`LDM` or packed-struct pointer cast | Use `memcpy`, fix alignment |
| FORCED only, CFSR = 0 | Fault inside a fault handler, or vector-table issue | Check VTOR, handler names, stack at reset |
| VECTTBL | VTOR points to garbage | Bootloader/app VTOR setup |
| EXC_RETURN shows Handler mode | Fault occurred inside an ISR | Inspect the ISR named by IPSR in stacked xPSR |

## 4. Root cause, not symptom
- The faulting PC shows *where* it died, the LR shows the caller; the *cause* may be earlier corruption. If the data looks impossible, set a watchpoint (`watch -l ptr->field`) or use the MPU to guard the stack bottom / NULL page.
- Map the call chain manually if GDB cannot unwind: walk the stack for values that look like code addresses (in flash range, odd) and `addr2line` them.
- After fixing, prove it: reproduce the original trigger and confirm no fault, and that stack high-water mark has margin.
