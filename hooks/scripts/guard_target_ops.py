"""PreToolUse(Bash): stop irreversible or destructive operations on real hardware (Cortex-M).

The kit never flashes or debugs by itself; this is a safety net for commands the user's
project runs (make flash, vendor CLIs).
deny -> permanently locks silicon (STM32 RDP level 2, security bits). The user must run
        these themselves, outside the agent.
ask  -> destructive but recoverable (mass erase, option bytes, GPNVM, write protection).
Patterns also cover common vendor CLIs so they are guarded if installed.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
from fwlib import load_config, pre_tool_decision, project_dir, read_input  # noqa: E402

DENY = [
    (r"(stm32_programmer_cli|stm32cubeprogrammer|cubeprog).*\brdp\s*=\s*(0xcc|2)\b",
     "Sets STM32 readout protection to Level 2, which is PERMANENT (debug port disabled forever)."),
    (r"\brdp[_ ]?level\s*[=: ]\s*2\b", "Readout protection Level 2 is permanent on most MCUs."),
    (r"\b(set_?security_?bit|security_?bit\s+set)\b", "Sets a security bit that may permanently lock the device."),
]

ASK = [
    # Mass/chip erase
    (r"\bst-flash\b.*\berase\b", "Mass-erases the target flash."),
    (r"(stm32_programmer_cli|cubeprog).*(\s-e\s+all|--erase\s+all|\s-e\s*$)", "Mass-erases the target flash."),
    (r"\bmass_erase\b", "Mass-erases the target flash."),
    (r"\bpyocd\b\s+erase", "Erases target flash via pyOCD."),
    (r"\bprobe-rs\b\s+erase", "Erases target flash via probe-rs."),
    (r"\bjlink(exe)?\b.*\berase\b", "Erases the target via J-Link."),
    (r"\bbossac\b.*(\s-e\b|--erase)", "Erases SAM flash via bossac."),
    (r"\bedbg\b.*\s-e\b", "Erases the target via edbg."),
    (r"\bipecmd\b.*\s-e\b", "Erases the target via MPLAB IPE."),
    (r"\b(atsamv|at91samd|atsame5)\w*\s+chip[-_]erase\b", "Chip-erases the SAM device."),
    # Option bytes / protection / boot config
    (r"(stm32_programmer_cli|cubeprog).*\s-ob\b", "Writes STM32 option bytes (RDP, WRP, BOR, boot config). A wrong value can lock or brick the chip."),
    (r"\bstm32\w*\s+(lock|unlock|option_write|options_write|option_load)\b", "Changes STM32 protection/option bytes via OpenOCD (unlock triggers mass erase)."),
    (r"\bflash\s+protect\b", "Changes flash write protection."),
    (r"\batsamv\w*\s+gpnvm\s+(set|clr|clear)\b", "Changes SAMV7x GPNVM bits (bit0 = security: locks debug until a full ERASE-pin erase; bit1 = boot from ROM/flash; bits 7-8 = TCM size)."),
    (r"\bbossac\b.*(\s-s\b|--security|\s-b\b|--boot)", "Changes SAM security/boot GPNVM bits via bossac."),
    (r"\bdd\b.*\bof=/dev/(sd|mmcblk|disk|nvme)", "Raw write to a block device."),
]

FLASH_HINTS = [
    r"\bst-flash\b.*\bwrite\b", r"\bopenocd\b.*\bprogram\b", r"\bpyocd\b\s+(flash|load)",
    r"\bprobe-rs\b\s+(download|run)", r"(stm32_programmer_cli|cubeprog).*(\s-w\s|\s-d\s|--download)",
    r"\bjlink(exe)?\b", r"\bdfu-util\b.*\s-d\b", r"\bbossac\b.*(\s-w\b|--write)", r"\bedbg\b.*\s-p\b",
    r"\bmake\b.*\bflash\b",
]


def main():
    payload = read_input()
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command.strip():
        return 0
    proj = project_dir(payload)
    cfg, _ = load_config(proj)
    guard = cfg.get("guard", {})
    if not guard.get("enabled", True):
        return 0

    norm = re.sub(r"\\\r?\n", " ", command)
    norm = re.sub(r"\s+", " ", norm).lower()

    for pat, why in DENY + [(p, "Matches project deny pattern: " + p) for p in guard.get("deny_patterns", [])]:
        if re.search(pat, norm, re.I):
            pre_tool_decision("deny", "firmware-agent-kit blocked an IRREVERSIBLE target operation: {} If this is "
                              "truly intended, the user must run it manually outside the agent.".format(why))
            return 0

    for pat, why in ASK + [(p, "Matches project ask pattern: " + p) for p in guard.get("ask_patterns", [])]:
        if re.search(pat, norm, re.I):
            pre_tool_decision("ask", "Destructive target operation: {} Confirm the correct board is connected.".format(why))
            return 0

    if guard.get("confirm_flash"):
        for pat in FLASH_HINTS:
            if re.search(pat, norm, re.I):
                pre_tool_decision("ask", "Flashing hardware (guard.confirm_flash is enabled for this project).")
                return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
