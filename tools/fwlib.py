"""Shared helpers for firmware-agent-kit hooks and tools (stdlib only, Python 3.8+)."""

import copy
import json
import os
import re
import shutil
import subprocess
import sys

CONFIG_REL = os.path.join(".claude", "firmware.json")
C_EXTS = (".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".hh")

DEFAULT_CONFIG = {
    "family": None,                      # stm32 | esp32 | samv71 | other
    "mcu": None,
    "core": None,
    "toolchain_prefix": "arm-none-eabi-",
    "build": None,
    "clean": None,
    "flash": None,
    "debug_server": None,
    "elf": None,
    "map": None,
    "compile_commands": None,
    "memory": {"flash_kb": None, "ram_kb": None},
    "size_budget": {"flash_pct_warn": 85, "ram_pct_warn": 85, "flash_pct_max": 98, "ram_pct_max": 95},
    "rtos": {"type": None, "api": None, "config_header": None},   # freertos | none ; native | cmsis-rtos2
    "test": {"unit": None, "integration": None},
    "datasheets": [],
    "lint": {
        "enabled": True,
        "forbid_dynamic_alloc": True,
        "extensions": list(C_EXTS),
        "isr_functions": [],             # extra regexes naming functions that run in interrupt context
        "isr_forbidden_calls": [
            "printf", "sprintf", "snprintf", "puts", "malloc", "calloc", "realloc", "free",
            "HAL_Delay", "delay_ms", "delay_us",
            "ESP_LOGE", "ESP_LOGW", "ESP_LOGI", "ESP_LOGD", "ESP_LOGV",
        ],
    },
    "format": {"on_edit": False},
    "git": {"block_ai_attribution": True},
    "analysis": {
        "tools": ["lint", "cppcheck", "clang-tidy"],
        "misra": False,
        "misra_rules_file": None,
        "clang_tidy_checks": None,
    },
    "guard": {
        "enabled": True,
        "confirm_flash": False,
        "ask_patterns": [],
        "deny_patterns": [],
        "vendor_edits": "ask",
        "protected_paths": [
            "Drivers/CMSIS/", "Drivers/STM32", "_HAL_Driver/", "Middlewares/Third_Party/",
            "managed_components/", "esp-idf/", "hal/sam", "/packs/", "config/default/peripheral/",
            "vendor/", "third_party/", "thirdparty/", "external/",
        ],
    },
}


# ---------------------------------------------------------------- hook I/O

def read_input():
    try:
        data = sys.stdin.read()
        return json.loads(data) if data.strip() else {}
    except Exception:
        return {}


def emit(obj):
    sys.stdout.write(json.dumps(obj))
    sys.stdout.flush()


def pre_tool_decision(decision, reason):
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                 "permissionDecision": decision, "permissionDecisionReason": reason}})


def post_tool_context(text, block=False):
    out = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}
    if block:
        out["decision"] = "block"
        out["reason"] = text
    emit(out)


# ---------------------------------------------------------------- project / config

def project_dir(payload=None):
    d = os.environ.get("CLAUDE_PROJECT_DIR")
    if not d and payload:
        d = payload.get("cwd")
    return d or os.getcwd()


def _merge(base, override):
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(proj):
    """Return (config, path_or_None). Missing keys get defaults."""
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    path = os.path.join(proj, CONFIG_REL)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                _merge(cfg, json.load(f))
            return cfg, path
        except Exception as e:
            cfg["_config_error"] = "{}: {}".format(path, e)
    return cfg, None


def rel(path, proj):
    try:
        return os.path.relpath(path, proj).replace("\\", "/")
    except ValueError:
        return path.replace("\\", "/")


def is_protected(relpath, cfg):
    return any(p and p.replace("\\", "/") in relpath for p in cfg.get("guard", {}).get("protected_paths", []))


def which(name):
    return shutil.which(name)


WIN_TOOL_DIRS = [r"C:\Program Files\Cppcheck", r"C:\Program Files (x86)\Cppcheck", r"C:\Program Files\LLVM\bin",
                 r"C:\Program Files\qemu"]
WSL_PROBE = ["cppcheck", "clang-format", "clang-tidy", "frama-c", "valgrind", "renode", "renode-test", "qemu-system-arm",
             "openocd", "st-flash", "bossac", "edbg", "pyocd", "esptool.py", "idf.py", "arm-none-eabi-gcc", "gcc", "make",
             "ceedling", "gcovr", "podman", "docker", "pdftotext", "cmake", "ninja", "mmdc"]
_WSL_TOOLS = None


def find_native(name):
    """PATH lookup plus standard Windows install folders (installers often skip PATH until a new login)."""
    p = which(name)
    if p:
        return p
    if os.name == "nt":
        for d in WIN_TOOL_DIRS:
            c = os.path.join(d, name + ".exe")
            if os.path.isfile(c):
                return c
    return None


def wsl_tools():
    """Set of WSL_PROBE tools available in the default WSL distro (Windows only; cached for a day per user)."""
    global _WSL_TOOLS
    if _WSL_TOOLS is not None:
        return _WSL_TOOLS
    _WSL_TOOLS = set()
    if os.name != "nt" or not which("wsl"):
        return _WSL_TOOLS
    import time
    cache = os.path.join(os.path.expanduser("~"), ".cache", "fwkit-wsl-tools.json")
    try:
        with open(cache, "r", encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - data.get("t", 0) < 24 * 3600:
            _WSL_TOOLS = set(data.get("tools", []))
            return _WSL_TOOLS
    except (OSError, ValueError):
        pass
    script = "for t in {}; do command -v $t >/dev/null 2>&1 && echo $t; done; exit 0".format(" ".join(WSL_PROBE))
    rc, out, _ = run(["wsl", "-e", "sh", "-c", script], timeout=90)
    if rc == 0:
        _WSL_TOOLS = set(out.replace("\x00", "").split())
        try:
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            with open(cache, "w", encoding="utf-8") as f:
                json.dump({"t": time.time(), "tools": sorted(_WSL_TOOLS)}, f)
        except OSError:
            pass
    return _WSL_TOOLS


def to_wsl_path(p):
    p = os.path.abspath(p)
    m = re.match(r"^([A-Za-z]):[\\/](.*)$", p)
    return "/mnt/{}/{}".format(m.group(1).lower(), m.group(2).replace("\\", "/")) if m else p.replace("\\", "/")


def from_wsl_path(p):
    m = re.match(r"^/mnt/([a-z])/(.*)$", p)
    return "{}:{}{}".format(m.group(1).upper(), os.sep, m.group(2).replace("/", os.sep)) if m else p


def resolve_tool(name):
    """-> (argv prefix, path converter) for a native tool, else the same tool inside WSL, else (None, None)."""
    p = find_native(name)
    if p:
        return [p], (lambda x: x)
    if name in wsl_tools():
        return ["wsl", "-e", name], to_wsl_path
    return None, None


def tool(cfg, name):
    """'size' -> '<toolchain_prefix>size' if installed, else plain 'size' if installed."""
    prefix = cfg.get("toolchain_prefix") or ""
    for cand in (prefix + name, name):
        p = which(cand)
        if p:
            return p
    return None


def run(cmd, cwd=None, timeout=120):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, "", str(e)


# ---------------------------------------------------------------- git helpers

def git_root(path):
    d = path if os.path.isdir(path) else os.path.dirname(os.path.abspath(path))
    rc, out, _ = run(["git", "rev-parse", "--show-toplevel"], cwd=d, timeout=10)
    return out.strip() if rc == 0 and out.strip() else None


def git_changed_files(proj, base="HEAD"):
    """Changed + untracked files vs base (absolute paths). [] if not a git repo."""
    root = git_root(proj)
    if not root:
        return []
    files = set()
    for cmd in (["git", "diff", "--name-only", base], ["git", "diff", "--name-only", "--cached"],
                ["git", "ls-files", "--others", "--exclude-standard"]):
        rc, out, _ = run(cmd, cwd=root, timeout=20)
        if rc == 0:
            files.update(l.strip() for l in out.splitlines() if l.strip())
    return sorted(os.path.join(root, f) for f in files if os.path.isfile(os.path.join(root, f)))


def git_changed_lines(path, base="HEAD"):
    """Set of changed line numbers in the working copy vs base.
    None = whole file counts as new (untracked, or not in git)."""
    root = git_root(path)
    if not root:
        return None
    rc, _, _ = run(["git", "ls-files", "--error-unmatch", path], cwd=root, timeout=10)
    if rc != 0:
        return None
    rc, out, _ = run(["git", "diff", "-U0", "--no-color", base, "--", path], cwd=root, timeout=20)
    if rc != 0:
        return None
    lines = set()
    for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", out, re.M):
        start, count = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
        lines.update(range(start, start + count))
        if count == 0:          # pure deletion: mark the neighbouring line
            lines.add(start)
    return lines


def to_ranges(lines):
    """{1,2,3,7} -> [(1,3),(7,7)]"""
    out = []
    for n in sorted(lines):
        if out and n == out[-1][1] + 1:
            out[-1] = (out[-1][0], n)
        else:
            out.append((n, n))
    return out


def find_compile_commands(proj, cfg=None):
    if cfg and cfg.get("compile_commands"):
        p = os.path.join(proj, cfg["compile_commands"])
        return p if os.path.isfile(p) else None
    cands = [os.path.join(proj, "compile_commands.json")]
    for d in sorted(os.listdir(proj)) if os.path.isdir(proj) else []:
        if d.lower().startswith(("build", "cmake-build", "out", "debug", "release")):
            cands.append(os.path.join(proj, d, "compile_commands.json"))
            sub = os.path.join(proj, d)
            if os.path.isdir(sub):
                cands += [os.path.join(sub, s, "compile_commands.json") for s in os.listdir(sub)]
    found = [c for c in cands if os.path.isfile(c)]
    return max(found, key=os.path.getmtime) if found else None
