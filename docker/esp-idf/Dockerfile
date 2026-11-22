# firmware-agent-kit: ESP32 family image (ESP-IDF is Apache-2.0) + QEMU + analyzers.
# Build:  python tools/fw_container.py build esp-idf  [--build-arg IDF_VERSION=v5.x.y]
ARG IDF_VERSION=v5.4.1
FROM espressif/idf:${IDF_VERSION}

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        cppcheck clang-format clang-tidy ruby gcovr poppler-utils \
        libgcrypt20 libglib2.0-0 libpixman-1-0 libsdl2-2.0-0 libslirp0 \
    && rm -rf /var/lib/apt/lists/*

# Espressif QEMU forks (Xtensa ESP32/S3 and RISC-V C3/C6): `idf.py qemu` / `idf.py qemu monitor`
RUN bash -c "source \$IDF_PATH/export.sh >/dev/null && python \$IDF_PATH/tools/idf_tools.py install qemu-xtensa qemu-riscv32"
RUN gem install --no-document ceedling

WORKDIR /work
