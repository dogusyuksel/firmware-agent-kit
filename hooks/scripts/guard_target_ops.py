"""PreToolUse(Bash): stop irreversible or destructive operations on real hardware.

deny -> permanently bricks / locks silicon (RDP level 2, eFuse, OTP). The user
        must run these themselves, outside the agent.
ask  -> destructive but recoverable (mass erase, option bytes, GPNVM, fuses, recover),
        or flashing an ESP-IDF image whose first boot burns eFuses (secure boot /
        flash encryption enabled in sdkconfig).
Patterns also cover common proprietary vendor CLIs so they are guarded if installed;
the kit itself only recommends open-source tools.
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
    (r"\bespefuse(\.py)?\b.*\bburn", "Burns ESP eFuses - permanent and irreversible."),
    (r"\besptool(\.py)?\b.*\bburn[_-]efuse", "Burns ESP eFuses - permanent and irreversible."),
    (r"\bidf\.py\b.*\befuse[-_]burn", "Burns ESP eFuses - permanent and irreversible."),
    (r"\bpicotool\b.*\botp\s+(set|load|write|permission)", "Writes RP2350 OTP - permanent."),
    (r"\bblhost\b.*\befuse[-_]program", "Programs NXP eFuses - permanent."),
    (r"\b(set_?security_?bit|security_?bit\s+set)\b", "Sets a security bit that may permanently lock the device."),
]

ASK = [
    # Mass/chip erase
    (r"\bst-flash\b.*\berase\b", "Mass-erases the target flash."),
    (r"(stm32_programmer_cli|cubeprog).*(\s-e\s+all|--erase\s+all|\s-e\s*$)", "Mass-erases the target flash."),
    (r"\bmass_erase\b", "Mass-erases the target flash."),
    (r"\bnrfjprog\b.*(--eraseall|--recover|-e\b)", "Erases the nRF device (all flash + UICR)."),
    (r"\bnrfutil\b.*\b(recover|erase)\b", "Erases the nRF device."),
    (r"\bpyocd\b\s+erase", "Erases target flash via pyOCD."),
    (r"\bprobe-rs\b\s+erase", "Erases target flash via probe-rs."),
    (r"\besptool(\.py)?\b.*\berase[_-](flash|region)", "Erases ESP flash (NVS, calibration data, keys included)."),
    (r"\bidf\.py\b.*\berase[-_](flash|otadata)", "Erases ESP flash / OTA data."),
    (r"\bparttool(\.py)?\b.*\berase", "Erases an ESP partition."),
    (r"\bavrdude\b.*\s-e(\s|$)", "Performs an AVR chip erase."),
    (r"\bjlink(exe)?\b.*\berase\b", "Erases the target via J-Link."),
    (r"\bbossac\b.*(\s-e\b|--erase)", "Erases SAM flash via bossac."),
    (r"\bedbg\b.*\s-e\b", "Erases the target via edbg."),
    (r"\bipecmd\b.*\s-e\b", "Erases the target via MPLAB IPE."),
    (r"\b(atsamv|at91samd|atsame5)\w*\s+chip[-_]erase\b", "Chip-erases the SAM device."),
    # Option bytes / protection / fuses / boot config
    (r"(stm32_programmer_cli|cubeprog).*\s-ob\b", "Writes STM32 option bytes (RDP, WRP, BOR, boot config). A wrong value can lock or brick the chip."),
    (r"\bstm32\w*\s+(lock|unlock|option_write|options_write|option_load)\b", "Changes STM32 protection/option bytes via OpenOCD (unlock triggers mass erase)."),
    (r"\bflash\s+protect\b", "Changes flash write protection."),
    (r"\batsamv\w*\s+gpnvm\s+(set|clr|clear)\b", "Changes SAMV7x GPNVM bits (bit0 = security: locks debug until a full ERASE-pin erase; bit1 = boot from ROM/flash; bits 7-8 = TCM size)."),
    (r"\bbossac\b.*(\s-s\b|--security|\s-b\b|--boot)", "Changes SAM security/boot GPNVM bits via bossac."),
    (r"\bavrdude\b.*-u\s*(l|h|e)?fuse\d?:w", "Writes AVR fuses (wrong clock/RSTDISBL/SPIEN can make ISP impossible)."),
    (r"\bavrdude\b.*-u\s*lock:w", "Writes AVR lock bits."),
    (r"\bnrfjprog\b.*--memwr\s+0x1000120[0-9a-f]", "Writes nRF UICR (APPROTECT / REGOUT0)."),
    (r"\bnrfjprog\b.*--rbp\b", "Enables nRF readback protection."),
    (r"\bpicotool\b.*\botp\b", "Accesses RP2350 OTP."),
    (r"\bdd\b.*\bof=/dev/(sd|mmcblk|disk|nvme)", "Raw write to a block device."),
]

FLASH_HINTS = [
    r"\bst-flash\b.*\bwrite\b", r"\bopenocd\b.*\bprogram\b", r"\bpyocd\b\s+(flash|load)",
    r"\bprobe-rs\b\s+(download|run)", r"\bnrfjprog\b.*--program", r"\besptool(\.py)?\b.*write[_-]flash",
    r"\bidf\.py\b.*\b(flash|app-flash|encrypted-flash)\b", r"\bavrdude\b.*-u\s*flash:w",
    r"(stm32_programmer_cli|cubeprog).*(\s-w\s|\s-d\s|--download)", r"\bjlink(exe)?\b", r"\bdfu-util\b.*\s-d\b",
    r"\bpicotool\b\s+load", r"\bbossac\b.*(\s-w\b|--write)", r"\bedbg\b.*\s-p\b",
]
ESP_FLASH_RE = re.compile(r"\bidf\.py\b.*\b(flash|encrypted-flash|bootloader-flash)\b|\besptool(\.py)?\b.*write[_-]flash")
ESP_SECURE_RE = re.compile(r"^CONFIG_(SECURE_FLASH_ENC_ENABLED|SECURE_BOOT|SECURE_BOOT_V[12]_ENABLED)=y", re.M)


def esp_secure_config(proj):
    p = os.path.join(proj, "sdkconfig")
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            hits = ESP_SECURE_RE.findall(f.read())
        return sorted(set(hits))
    except OSError:
        return []


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

    if ESP_FLASH_RE.search(norm):
        secure = esp_secure_config(proj)
        if secure:
            pre_tool_decision("ask", "sdkconfig enables {} - the first boot of this image PERMANENTLY burns eFuses "
                              "(keys / security bits). Only continue if this board is meant to be locked.".format(
                                  ", ".join("CONFIG_" + s for s in secure)))
            return 0

    if guard.get("confirm_flash"):
        for pat in FLASH_HINTS:
            if re.search(pat, norm, re.I):
                pre_tool_decision("ask", "Flashing hardware (guard.confirm_flash is enabled for this project).")
                return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
