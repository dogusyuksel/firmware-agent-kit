# Requirements

The kit supports **Linux only** (commands below are for Debian/Ubuntu). On Windows, run Claude Code inside WSL and install the tools there.

Everything the kit uses is **free and open source**. Only **Python 3.8+** (stdlib only) and **git** are required; every other tool is optional and unlocks a feature. Missing tools are detected when a feature needs them: Claude shows the install command and asks; you install it yourself and the feature runs, or you decline and the step is skipped. Claude never installs anything itself.

Check a machine with:

```sh
python3 tools/fw_doctor.py            # full table with install commands
python3 tools/fw_doctor.py --missing  # only what is missing
```

| Tool | Area | License | Used for | Install (Debian/Ubuntu) |
|---|---|---|---|---|
| python | Required | PSF-2.0 | runs all kit hooks and scripts | `sudo apt install -y python3` |
| git | Required | GPL-2.0 | changed-line detection, diffs for review | `sudo apt install -y git` |
| arm-none-eabi-gcc | Build | GPL-3.0 | Cortex-M cross compiler | `sudo apt install -y gcc-arm-none-eabi libnewlib-arm-none-eabi` |
| cmake | Build | BSD-3-Clause | build system | `sudo apt install -y cmake` |
| ninja | Build | Apache-2.0 | fast CMake generator | `sudo apt install -y ninja-build` |
| make | Build | GPL-3.0 | Makefile projects | `sudo apt install -y make` |
| bear | Build | GPL-3.0 | compile_commands.json for Make projects | `sudo apt install -y bear` |
| cppcheck | Static analysis | GPL-3.0 | static analysis + MISRA C:2012 addon | `sudo apt install -y cppcheck` |
| clang-tidy | Static analysis | Apache-2.0 WITH LLVM-exception | static analysis (clang-analyzer, bugprone, cert) | `sudo apt install -y clang-tidy` |
| clang-format | Formatting | Apache-2.0 WITH LLVM-exception | C formatter (changed lines only) | `sudo apt install -y clang-format` |
| pdftotext | Documents & diagrams | GPL-2.0 | fast datasheet/schematic page search (poppler) | `sudo apt install -y poppler-utils` |
| pypdf | Documents & diagrams | BSD-3-Clause | pure-Python fallback for PDF search | `python3 -m pip install --user pypdf` |
| mmdc | Documents & diagrams | MIT | render Mermaid diagrams to SVG/PNG (optional) | `npm install -g @mermaid-js/mermaid-cli   (needs Node.js: sudo apt install -y nodejs npm)` |

## Notes
- MISRA C:2012: the cppcheck addon is open source; the official rule *texts* are sold by MISRA. Without them findings show rule numbers only (`analysis.misra_rules_file` points to your licensed copy).
- Proprietary vendor tools (STM32CubeProgrammer, J-Link software, MPLAB) are neither required nor installed. If you use them anyway, the guard hooks still gate their destructive commands.
- Vendor SDKs your project already uses (STM32Cube HAL/LL: BSD-3-Clause; CMSIS: Apache-2.0; FreeRTOS: MIT; Microchip DFP/Harmony: Microchip license) are project dependencies, not kit requirements.
