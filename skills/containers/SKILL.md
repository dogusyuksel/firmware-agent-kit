---
name: containers
description: Reproducible firmware builds, tests and analysis inside containers (Podman or Docker Engine) using the kit's images - arm-dev (STM32/SAMV71 toolchain, OpenOCD, cppcheck, clang tools, Ceedling), esp-idf (ESP-IDF + QEMU), renode, frama-c - and writing project Dockerfiles/devcontainers and CI jobs. Use when the user wants to build or run code in a container, a tool is missing locally, or CI needs a pinned toolchain.
---

# Containers

## Kit images (all free/open source)
| Image | Contents | Typical use |
|---|---|---|
| `arm-dev` | arm-none-eabi-gcc, CMake/Ninja/Make, gdb-multiarch, OpenOCD, stlink, pyOCD, cppcheck, clang-format/tidy, Ceedling, gcovr, valgrind, bear, poppler | STM32/SAMV71 builds, unit tests, analysis |
| `esp-idf` | Espressif ESP-IDF (pinned version) + QEMU + analyzers + Ceedling | ESP32 builds/tests |
| `renode` | Renode + Robot Framework deps + arm toolchain | integration tests |
| `frama-c` | Frama-C | formal analysis (esp. on Windows) |

```sh
python <kit>/tools/fw_container.py build arm-dev
python <kit>/tools/fw_container.py run arm-dev -- "cmake -B build -G Ninja && cmake --build build"
python <kit>/tools/fw_container.py run arm-dev -- ceedling test:all
python <kit>/tools/fw_container.py run arm-dev -- python3 /kit/tools/fw_analyze.py --all   # see note on /kit
python <kit>/tools/fw_container.py run esp-idf -- idf.py build
python <kit>/tools/fw_container.py run renode -- renode-test tests/integration/app.robot
```
The project directory is mounted at `/work`. To use kit scripts inside a container, run them on the host (they work on the build outputs) or copy `tools/` into the project's `.fwkit/` (do not commit if the user prefers).

## Engine
- Podman (Apache-2.0) is the default; Docker Engine (Apache-2.0) works too. Docker Desktop is not open source - the kit never requires it.
- Windows/macOS: Podman runs a Linux VM (`podman machine init && podman machine start`).
- Bind-mount performance on Windows: keep large builds inside the container volume or WSL filesystem if slow.

## Hardware access
Flashing/debugging from containers needs USB passthrough: Linux `--device /dev/ttyACM0` (or `--privileged` for probes); on Windows use usbipd-win (GPL-3.0) into WSL/Podman machine, or simply flash from the host with the host's OpenOCD/pyOCD. Build in the container, flash on the host is the simple default.

## Project Dockerfile / devcontainer
When the user wants the toolchain pinned in their repo:
1. Start `FROM` a kit image or copy the relevant `docker/<image>/Dockerfile` into the project (`.devcontainer/Dockerfile` for VS Code Dev Containers, which is open source).
2. Pin versions (base image tag, toolchain, ESP-IDF tag, Ceedling).
3. Add a CI job that runs the same container: build, `ceedling test:all`, `fw_analyze.py --all --sarif`, Renode tests.
Ask before creating these files; they change the project.
