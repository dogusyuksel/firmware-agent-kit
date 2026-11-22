# firmware-agent-kit: Renode (MIT) simulation + Robot Framework integration tests + arm toolchain.
# Build:  python tools/fw_container.py build renode  [--build-arg RENODE_VERSION=1.16.0]
# Ubuntu 22.04 on purpose: the Renode .deb depends on packages that Ubuntu 24.04 renamed or removed
# (policykit-1, t64 library renames), so apt cannot resolve it there.
FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG RENODE_VERSION=1.16.0

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl python3 python3-pip python3-venv git \
        gcc-arm-none-eabi libnewlib-arm-none-eabi cmake ninja-build make \
    && curl -fsSL -o /tmp/renode.deb \
        "https://github.com/renode/renode/releases/download/v${RENODE_VERSION}/renode_${RENODE_VERSION}_amd64.deb" \
    && apt-get install -y --no-install-recommends /tmp/renode.deb \
    && rm -f /tmp/renode.deb && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir -r /opt/renode/tests/requirements.txt

WORKDIR /work
CMD ["bash"]
