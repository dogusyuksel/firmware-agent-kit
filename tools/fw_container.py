#!/usr/bin/env python3
"""Build the kit's container images and run commands inside them with the project mounted.

Works with Podman or Docker Engine (both open source). Images are defined in docker/<name>/Dockerfile.

  python fw_container.py list
  python fw_container.py build arm-dev                 # or: esp-idf, renode, frama-c
  python fw_container.py run arm-dev -- cmake --build build
  python fw_container.py run arm-dev -- ceedling test:all
  python fw_container.py run esp-idf -- idf.py build
  python fw_container.py run renode -- renode-test tests/integration/app.robot
  python fw_container.py shell arm-dev                 # interactive shell (user runs this)
Options: --engine podman|docker, --tag, --device /dev/ttyACM0 (USB probes: Linux hosts only;
on Windows/macOS flash from the host or pass USB through to the VM), --privileged.
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys

KIT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCKER_DIR = os.path.join(KIT_ROOT, "docker")
VERSION = "0.3.1"


def images():
    if not os.path.isdir(DOCKER_DIR):
        return []
    return sorted(d for d in os.listdir(DOCKER_DIR) if os.path.isfile(os.path.join(DOCKER_DIR, d, "Dockerfile")))


def engine(pref=None):
    for e in ([pref] if pref else []) + ["podman", "docker"]:
        if e and shutil.which(e):
            return e
    return None


def tag_for(name, tag=None):
    return tag or "fwkit/{}:{}".format(name, VERSION)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["list", "build", "run", "shell"])
    ap.add_argument("image", nargs="?")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    ap.add_argument("--engine")
    ap.add_argument("--tag")
    ap.add_argument("--device", action="append", default=[])
    ap.add_argument("--privileged", action="store_true")
    ap.add_argument("--build-arg", action="append", default=[])
    args = ap.parse_args()

    if args.action == "list":
        for n in images():
            print("{:<10} {}".format(n, os.path.join("docker", n, "Dockerfile")))
        return 0
    if args.image not in images():
        print("unknown image '{}'. Available: {}".format(args.image, ", ".join(images())))
        return 2
    eng = engine(args.engine)
    if not eng:
        print("No container engine found. Install Podman (Apache-2.0): see `python tools/fw_doctor.py --for container`.")
        return 2
    tag = tag_for(args.image, args.tag)

    if args.action == "build":
        cmd = [eng, "build", "-t", tag, "-f", os.path.join(DOCKER_DIR, args.image, "Dockerfile")]
        for b in args.build_arg:
            cmd += ["--build-arg", b]
        cmd.append(os.path.join(DOCKER_DIR, args.image))
        print("+ " + " ".join(cmd))
        return subprocess.call(cmd)

    proj = os.getcwd()
    cmd = [eng, "run", "--rm", "-v", "{}:/work".format(proj), "-w", "/work", "-e", "HOME=/tmp"]
    if eng == "docker" and platform.system() == "Linux" and hasattr(os, "getuid"):
        cmd += ["--user", "{}:{}".format(os.getuid(), os.getgid())]   # files stay owned by you
    if eng == "podman" and platform.system() == "Linux":
        cmd += ["--userns=keep-id"]
    for d in args.device:
        cmd += ["--device", d]
    if args.privileged:
        cmd.append("--privileged")
    if args.action == "shell":
        cmd += ["-it", tag, "bash"]
    else:
        rest = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
        if not rest:
            print("nothing to run: python fw_container.py run {} -- <command>".format(args.image))
            return 2
        cmd += [tag, "bash", "-lc", " ".join(rest)]
    print("+ " + " ".join(cmd))
    r = subprocess.call(cmd)
    if r == 125:
        print("Hint: build the image first: python tools/fw_container.py build " + args.image)
    return r


if __name__ == "__main__":
    sys.exit(main())
