---
name: build-systems
description: Read, understand and modify firmware build systems - CMake (toolchain files, presets, targets, generator expressions), GNU Make (generated STM32Cube Makefiles, recursive makes), ESP-IDF component CMake, MPLAB/Harmony and CubeIDE projects, compile_commands.json, linker flags and map files. Use when a build fails, flags/defines/include paths must be found or changed, a file must be added to the build, or a new build is set up.
---

# Firmware build systems

## Start cheap
1. `python <kit>/tools/build_info.py` - compiler, arch flags, defines, include dirs, source dirs, linker script from `compile_commands.json` in ~30 lines. `--file src/x.c` gives the exact flags of one TU.
2. No compile DB? Generate one (CMake `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`, ESP-IDF `idf.py reconfigure`, Make `bear -- make`). Do not read whole generated Makefiles/CMake caches.
3. Then read only the relevant `CMakeLists.txt` / Makefile section (Grep for the target or variable).

## CMake for cross builds
```cmake
# cmake/arm-none-eabi.cmake  (toolchain file: -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi.cmake)
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)
set(CMAKE_C_COMPILER arm-none-eabi-gcc)
set(CMAKE_ASM_COMPILER arm-none-eabi-gcc)
set(CMAKE_OBJCOPY arm-none-eabi-objcopy)
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)   # no linking during compiler checks
```
```cmake
add_executable(app ${SOURCES})
target_compile_options(app PRIVATE -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard
                                   -ffunction-sections -fdata-sections -Wall -Wextra)
target_compile_definitions(app PRIVATE STM32F407xx USE_HAL_DRIVER)
target_include_directories(app PRIVATE Core/Inc)
target_link_options(app PRIVATE -T${CMAKE_SOURCE_DIR}/STM32F407VGTX_FLASH.ld -Wl,--gc-sections
                                -Wl,-Map=$<TARGET_FILE_DIR:app>/app.map --specs=nano.specs -mcpu=cortex-m4 -mthumb
                                -mfpu=fpv4-sp-d16 -mfloat-abi=hard)
set_target_properties(app PROPERTIES SUFFIX .elf)
add_custom_command(TARGET app POST_BUILD COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:app> app.bin)
```
- Use target-based commands (`target_*`), not global `add_definitions`/`include_directories`, in new code; follow the existing style in old projects.
- Arch flags must be identical for compile **and** link (float ABI mismatch = link errors or wrong libs).
- Presets (`CMakePresets.json`) for Debug/Release/Test; host unit tests in a separate build dir with the host compiler.

## GNU Make (incl. STM32Cube generated)
- Key variables: `C_SOURCES`, `ASM_SOURCES`, `C_INCLUDES`, `C_DEFS`, `MCU`, `LDSCRIPT`, `OPT`. Add files by appending to these lists in the same style.
- Debug a Makefile: `make -n` (dry run), `make -p | grep VAR` (database), `make V=1`/`VERBOSE=1`.
- Header dependency tracking: `-MMD -MP` and `-include $(DEPS)`; missing it causes stale builds.

## ESP-IDF
- Each component: `idf_component_register(SRCS "a.c" "b.c" INCLUDE_DIRS "include" REQUIRES driver freertos PRIV_REQUIRES esp_timer)`. "Undefined reference" across components is usually a missing `REQUIRES`.
- Global options via Kconfig/sdkconfig, not compiler flags. Extra flags: `target_compile_options(${COMPONENT_LIB} PRIVATE ...)`.

## Microchip SAMV71
- MPLAB X/Harmony: `nbproject/configurations.xml` + generated Makefiles - prefer exporting to CMake or using the DFP headers + startup with your own CMake. Keep `config/default/` generated code untouched.

## Common failures
| Symptom | Usual cause |
|---|---|
| `undefined reference to _sbrk/_write/_close` | newlib syscalls missing: add `syscalls.c` or `--specs=nosys.specs`/`nano.specs` |
| `uses VFP register arguments, x does not` | `-mfloat-abi` mismatch between objects/libraries |
| `region FLASH overflowed` | see `memory-footprint` |
| `multiple definition of` | variable defined in a header, or GCC 10+ `-fno-common` default |
| ISR never called | handler name typo vs startup vector table; startup file not linked; LTO dropped it (`__attribute__((used))`) |
| Works in Debug, fails in Release | missing `volatile`, UB, timing; compare with `-O0` vs `-Os` |
