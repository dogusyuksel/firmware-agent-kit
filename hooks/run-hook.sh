#!/usr/bin/env bash
# Runs a firmware-agent-kit hook script with the first *working* Python 3.8+.
#
# Probing matters: on Windows `python3` is often the Microsoft Store stub that
# exists on PATH but cannot run anything. Set FWKIT_PYTHON to force a specific
# interpreter. Hooks fail open: if no Python is found the hook is skipped.

script="$1"
shift

root="${CLAUDE_PLUGIN_ROOT:-}"
if [ -z "$root" ]; then
  root="$(cd "$(dirname "$0")/.." && pwd)"
fi

for py in "${FWKIT_PYTHON:-}" python3 python py; do
  [ -z "$py" ] && continue
  command -v "$py" >/dev/null 2>&1 || continue
  if "$py" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" </dev/null >/dev/null 2>&1; then
    exec "$py" "$root/hooks/scripts/$script" "$@"
  fi
done

echo "firmware-agent-kit: no working Python 3.8+ found; hook '$script' skipped (set FWKIT_PYTHON)." >&2
exit 0
