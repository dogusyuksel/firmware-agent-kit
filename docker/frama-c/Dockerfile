# firmware-agent-kit: Frama-C (LGPL-2.1) formal analysis (EVA value analysis, WP proofs).
# Build:  python tools/fw_container.py build frama-c
# For the newest release use opam instead (opam install frama-c) - see skills/static-analysis.
FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        frama-c-base gcc python3 git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work
CMD ["bash"]
