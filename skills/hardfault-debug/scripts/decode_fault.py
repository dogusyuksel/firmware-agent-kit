#!/usr/bin/env python3
"""Decode ARM Cortex-M fault status registers and optionally map PC/LR to source.

Examples:
  python decode_fault.py --cfsr 0x00008200 --bfar 0x20030000
  python decode_fault.py --cfsr 0x01000000 --hfsr 0x40000000 --pc 0x08001234 --lr 0x08000F01 --elf build/app.elf
  python decode_fault.py --exc-return 0xFFFFFFFD
Values can be hex (0x...) or decimal. Stdlib only.
"""

import argparse
import shutil
import subprocess
import sys

MMFSR = {
    0: ("IACCVIOL", "Instruction fetch from an MPU-protected / XN region (executed from data or invalid address)."),
    1: ("DACCVIOL", "Data access violated MPU rules (often NULL / stack guard region)."),
    3: ("MUNSTKERR", "MPU fault while unstacking on exception return (corrupted SP/stack)."),
    4: ("MSTKERR", "MPU fault while stacking on exception entry (stack overflow into guard region)."),
    5: ("MLSPERR", "MPU fault during lazy FPU state preservation."),
    7: ("MMARVALID", "MMFAR holds the faulting address."),
}
BFSR = {
    8: ("IBUSERR", "Bus error on instruction fetch (jump to invalid/erased flash, bad function pointer)."),
    9: ("PRECISERR", "Precise data bus error - BFAR holds the address; stacked PC is the faulting instruction."),
    10: ("IMPRECISERR", "Imprecise data bus error (buffered write) - stacked PC is AFTER the culprit. "
         "Temporarily set SCnSCB->ACTLR |= DISDEFWBUF (M3/M4) to make it precise."),
    11: ("UNSTKERR", "Bus fault on exception return unstacking (corrupted stack)."),
    12: ("STKERR", "Bus fault on exception entry stacking - classic STACK OVERFLOW off the end of RAM."),
    13: ("LSPERR", "Bus fault during lazy FPU state preservation."),
    15: ("BFARVALID", "BFAR holds the faulting address."),
}
UFSR = {
    16: ("UNDEFINSTR", "Undefined instruction (corrupted code, jumped into data, wrong -mcpu)."),
    17: ("INVSTATE", "Invalid EPSR state - usually branch to an address with bit0=0 (missing Thumb bit): "
         "bad function pointer or corrupted LR."),
    18: ("INVPC", "Invalid EXC_RETURN on exception return (stack corruption in ISR)."),
    19: ("NOCP", "Coprocessor access with FPU disabled - enable CP10/CP11 in SCB->CPACR before any float code."),
    20: ("STKOF", "Stack limit (MSPLIM/PSPLIM) violation - ARMv8-M stack overflow."),
    24: ("UNALIGNED", "Unaligned access trapped (UNALIGN_TRP set, or LDM/LDRD/STRD on unaligned address)."),
    25: ("DIVBYZERO", "Integer division by zero (DIV_0_TRP enabled)."),
}
HFSR = {
    1: ("VECTTBL", "Bus fault reading the vector table (VTOR wrong or vector table missing)."),
    30: ("FORCED", "Escalated configurable fault - look at CFSR for the real cause "
         "(or enable MemManage/BusFault/UsageFault handlers in SCB->SHCSR)."),
    31: ("DEBUGEVT", "Debug event (BKPT executed with no debugger attached)."),
}


def num(s):
    return int(s, 0) if s is not None else None


def decode_bits(value, table):
    return [(name, desc) for bit, (name, desc) in sorted(table.items()) if value & (1 << bit)]


def addr2line(elf, addr):
    tool = next((t for t in ("arm-none-eabi-addr2line", "addr2line") if shutil.which(t)), None)
    if not tool:
        return "(addr2line not found)"
    r = subprocess.run([tool, "-e", elf, "-f", "-C", "-i", "-p", hex(addr)], capture_output=True, text=True)
    return r.stdout.strip() or r.stderr.strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for a in ("cfsr", "hfsr", "mmfar", "bfar", "afsr", "exc-return", "pc", "lr", "psr", "sp"):
        ap.add_argument("--" + a)
    ap.add_argument("--elf", help="ELF with debug info for addr2line")
    args = ap.parse_args()

    cfsr, hfsr = num(args.cfsr), num(args.hfsr)
    if cfsr is None and hfsr is None and args.exc_return is None and args.pc is None:
        ap.print_help()
        return 2

    if hfsr is not None:
        print("HFSR = 0x{:08X}".format(hfsr))
        for name, desc in decode_bits(hfsr, HFSR):
            print("  {:<11} {}".format(name, desc))
    if cfsr is not None:
        print("CFSR = 0x{:08X}  (MMFSR=0x{:02X} BFSR=0x{:02X} UFSR=0x{:04X})".format(
            cfsr, cfsr & 0xFF, (cfsr >> 8) & 0xFF, (cfsr >> 16) & 0xFFFF))
        hits = decode_bits(cfsr, MMFSR) + decode_bits(cfsr, BFSR) + decode_bits(cfsr, UFSR)
        for name, desc in hits:
            print("  {:<11} {}".format(name, desc))
        if not hits:
            print("  (no configurable fault bits set)")
        if cfsr & (1 << 7) and args.mmfar:
            print("  MMFAR = 0x{:08X}  <- faulting data address".format(num(args.mmfar)))
        if cfsr & (1 << 15) and args.bfar:
            b = num(args.bfar)
            print("  BFAR  = 0x{:08X}  <- faulting data address{}".format(
                b, "  (near 0: NULL pointer + offset)" if b < 0x1000 else ""))
        elif args.bfar and not cfsr & (1 << 15):
            print("  BFAR given but BFARVALID=0 -> ignore its value.")

    if args.exc_return:
        er = num(args.exc_return)
        print("EXC_RETURN = 0x{:08X}".format(er))
        print("  stack used : {}".format("PSP (thread/RTOS task)" if er & 0x4 else "MSP"))
        print("  mode       : {}".format("Thread" if er & 0x8 else "Handler (fault inside an ISR)"))
        print("  frame      : {}".format("basic (8 words)" if er & 0x10 else "extended with FPU (26 words)"))

    if args.psr:
        psr = num(args.psr)
        print("xPSR = 0x{:08X}  IPSR(exception #)={}  T-bit={}".format(psr, psr & 0x1FF, (psr >> 24) & 1))
        if not (psr >> 24) & 1:
            print("  T-bit is 0 -> branch to an even address (INVSTATE).")

    for label, val in (("PC", args.pc), ("LR", args.lr)):
        if val is None:
            continue
        a = num(val)
        print("{} = 0x{:08X}".format(label, a))
        if args.elf:
            print("  -> " + addr2line(args.elf, a & ~1))
    if args.pc and args.elf:
        print("Tip: arm-none-eabi-objdump -d -S --start-address=<PC-0x20> --stop-address=<PC+0x10> " + args.elf)
    return 0


if __name__ == "__main__":
    sys.exit(main())
