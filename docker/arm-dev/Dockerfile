# firmware-agent-kit: Cortex-M development image (STM32, SAMV71, any arm-none-eabi target).
# Everything here is free/open source. Build:  python tools/fw_container.py build arm-dev
FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG CEEDLING_VERSION=1.0.1

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc-arm-none-eabi libnewlib-arm-none-eabi libstdc++-arm-none-eabi-newlib binutils-arm-none-eabi \
        gdb-multiarch cmake ninja-build make git ca-certificates \
        python3 python3-pip python3-venv \
        gcc g++ ruby gcovr lcov valgrind \
        cppcheck clang clang-format clang-tidy \
        openocd stlink-tools \
        poppler-utils bear \
    && rm -rf /var/lib/apt/lists/*

RUN gem install --no-document ceedling -v "${CEEDLING_VERSION}"
RUN python3 -m pip install --no-cache-dir --break-system-packages pyocd pypdf

WORKDIR /work
CMD ["bash"]
