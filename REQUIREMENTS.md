# Requirements

Everything the kit uses is **free and open source**. Only **Python 3.8+** (stdlib only) and **git** are required; every other tool is optional and unlocks a feature. Missing tools are detected at runtime: the kit asks once whether to install them and otherwise skips that step.

Check a machine with:

```sh
python tools/fw_doctor.py            # full table with install commands for this OS
python tools/fw_doctor.py --missing  # only what is missing
```

Or run everything in the kit's containers (`docker/`, see `tools/fw_container.py`) and install only Podman.

| Tool | Area | License | Used for | Windows | Linux (apt) | macOS |
|---|---|---|---|---|---|---|
| python | Required | PSF-2.0 | runs all kit hooks and scripts | `winget install -e --id Python.Python.3.12` | `sudo apt install -y python3` | `brew install python` |
| git | Required | GPL-2.0 | changed-line detection, diffs for review | `winget install -e --id Git.Git` | `sudo apt install -y git` | `brew install git` |
| arm-none-eabi-gcc | Build | GPL-3.0 | cross compiler for STM32 / SAMV71 (Cortex-M) | `winget install -e --id Arm.GnuArmEmbeddedToolchain` | `sudo apt install -y gcc-arm-none-eabi libnewlib-arm-none-eabi` | `brew install --cask gcc-arm-embedded` |
| cmake | Build | BSD-3-Clause | build system | `winget install -e --id Kitware.CMake` | `sudo apt install -y cmake` | `brew install cmake` |
| ninja | Build | Apache-2.0 | fast CMake generator | `winget install -e --id Ninja-build.Ninja` | `sudo apt install -y ninja-build` | `brew install ninja` |
| make | Build | GPL-3.0 | Makefile projects | `winget install -e --id ezwinports.make` | `sudo apt install -y make` | `xcode-select --install` |
| idf.py | ESP32 | Apache-2.0 | ESP-IDF build/flash/monitor (or use the esp-idf container) | `see https://docs.espressif.com/projects/esp-idf/en/stable/esp32/get-started/ (or: python tools/fw_container.py build esp-idf)` | `see https://docs.espressif.com/projects/esp-idf/en/stable/esp32/get-started/ (or: python tools/fw_container.py build esp-idf)` | `see https://docs.espressif.com/projects/esp-idf/en/stable/esp32/get-started/ (or: python tools/fw_container.py build esp-idf)` |
| openocd | Flash / debug | GPL-2.0 | flash/debug STM32 & SAMV71 (atsamv driver) | `download xPack OpenOCD: https://github.com/xpack-dev-tools/openocd-xpack/releases` | `sudo apt install -y openocd` | `brew install open-ocd` |
| pyocd | Flash / debug | Apache-2.0 | flash/debug via CMSIS-DAP/ST-LINK | `python -m pip install --user pyocd` | `python -m pip install --user pyocd` | `python -m pip install --user pyocd` |
| st-flash | Flash / debug | BSD-3-Clause | ST-LINK flashing (stlink-org) | `download: https://github.com/stlink-org/stlink/releases` | `sudo apt install -y stlink-tools` | `brew install stlink` |
| esptool | Flash / debug, ESP32 | GPL-2.0 | ESP32 flashing | `python -m pip install --user esptool` | `python -m pip install --user esptool` | `python -m pip install --user esptool` |
| bossac | Flash / debug | BSD-3-Clause | SAM flashing over SAM-BA | `download: https://github.com/shumatech/BOSSA/releases` | `sudo apt install -y bossa-cli` | `brew install --cask bossa` |
| gdb | Flash / debug | GPL-3.0 | on-target debugging | `included with the Arm GNU toolchain` | `sudo apt install -y gdb-multiarch` | `included with gcc-arm-embedded` |
| cppcheck | Static analysis | GPL-3.0 | static analysis + MISRA C:2012 addon | `winget install -e --id Cppcheck.Cppcheck` | `sudo apt install -y cppcheck` | `brew install cppcheck` |
| clang-tidy | Static analysis | Apache-2.0 WITH LLVM-exception | static analysis (clang-analyzer, bugprone, cert) | `winget install -e --id LLVM.LLVM` | `sudo apt install -y clang-tidy` | `brew install llvm` |
| clang-format | Formatting | Apache-2.0 WITH LLVM-exception | C formatter (changed lines only) | `winget install -e --id LLVM.LLVM` | `sudo apt install -y clang-format` | `brew install clang-format` |
| frama-c | Static analysis | LGPL-2.1 | formal analysis (EVA: runtime errors, WP: proofs) | `use WSL or the frama-c container: python tools/fw_container.py build frama-c` | `sudo apt install -y frama-c-base  (or: opam install frama-c)` | `opam install frama-c` |
| ceedling | Unit tests | MIT | unit tests with Unity + CMock | `winget install -e --id RubyInstallerTeam.RubyWithDevKit.3.3 ; gem install ceedling` | `sudo apt install -y ruby && sudo gem install ceedling` | `brew install ruby && gem install ceedling` |
| gcovr | Unit tests | BSD-3-Clause | coverage reports for host tests | `python -m pip install --user gcovr` | `python -m pip install --user gcovr` | `python -m pip install --user gcovr` |
| valgrind | Unit tests | GPL-2.0 | leak/memory checks of host tests (Linux; use ASan elsewhere) | `not available - use -fsanitize=address in host tests or the arm-dev container` | `sudo apt install -y valgrind` | `not available on Apple Silicon - use -fsanitize=address` |
| renode | Integration tests | MIT | simulation / integration tests (Robot Framework via renode-test) | `download the .msi/.zip: https://github.com/renode/renode/releases (or the renode container)` | `download the .deb: https://github.com/renode/renode/releases` | `brew install --cask renode` |
| qemu-system-arm | Integration tests | GPL-2.0 | Cortex-M emulation (limited board set) | `winget install -e --id SoftwareFreedomConservancy.QEMU` | `sudo apt install -y qemu-system-arm` | `brew install qemu` |
| pdftotext | Documents & diagrams | GPL-2.0 | fast datasheet/schematic page search (poppler) | `winget install -e --id oschwartz10612.Poppler` | `sudo apt install -y poppler-utils` | `brew install poppler` |
| pypdf | Documents & diagrams | BSD-3-Clause | pure-Python fallback for PDF search | `python -m pip install --user pypdf` | `python -m pip install --user pypdf` | `python -m pip install --user pypdf` |
| mmdc | Documents & diagrams | MIT | render Mermaid diagrams to SVG/PNG (optional) | `npm install -g @mermaid-js/mermaid-cli   (needs Node.js: winget install -e --id OpenJS.NodeJS.LTS)` | `npm install -g @mermaid-js/mermaid-cli   (needs Node.js: winget install -e --id OpenJS.NodeJS.LTS)` | `npm install -g @mermaid-js/mermaid-cli   (needs Node.js: winget install -e --id OpenJS.NodeJS.LTS)` |
| podman | Containers | Apache-2.0 | run builds/tests/analysis in containers (Podman, or Docker Engine) | `winget install -e --id RedHat.Podman ; podman machine init ; podman machine start` | `sudo apt install -y podman` | `brew install podman && podman machine init && podman machine start` |

## Notes
- Windows + WSL: when a tool is not installed natively, the kit looks for it in the default WSL distro and runs it through `wsl.exe` (paths are translated). `fw_doctor.py` reports such tools as "available in WSL".
- Windows: Claude Code already requires Git Bash, which the hooks use. The hook runner skips the Microsoft Store `python3` stub automatically; set `FWKIT_PYTHON` to force an interpreter.
- MISRA C:2012: the cppcheck addon is open source; the official rule *texts* are sold by MISRA. Without them findings show rule numbers only (`analysis.misra_rules_file` points to your licensed copy).
- Container engine: Podman or Docker Engine (both Apache-2.0). Docker Desktop is not open source and is never required.
- Proprietary vendor tools (J-Link software, STM32CubeProgrammer, nrfjprog, MPLAB) are neither required nor installed. If you use them anyway, the guard hooks still gate their destructive commands.
- Vendor SDKs your project already uses (STM32Cube HAL/LL: BSD-3-Clause; ESP-IDF: Apache-2.0; CMSIS: Apache-2.0; FreeRTOS: MIT; Microchip DFP/Harmony: Microchip license) are project dependencies, not kit requirements.
