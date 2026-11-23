#!/usr/bin/env bash
# Runs a firmware-agent-kit hook script with the first working Python 3.8+.
# The kit supports Linux only (on Windows, run Claude Code inside WSL). Elsewhere every
# hook is a no-op except a one-line note at session start. Hooks always fail open.
# Set FWKIT_PYTHON to force a specific interpreter.

script="$1"
shift

if [ "$(uname -s 2>/dev/null)" != "Linux" ]; then
  if [ "$script" = "session_context.py" ]; then
    echo "firmware-agent-kit supports Linux only; its hooks are disabled here. On Windows, run Claude Code inside WSL."
  fi
  exit 0
fi

root="${CLAUDE_PLUGIN_ROOT:-}"
if [ -z "$root" ]; then
  root="$(cd "$(dirname "$0")/.." && pwd)"
fi

for py in "${FWKIT_PYTHON:-}" python3 python; do
  [ -z "$py" ] && continue
  command -v "$py" >/dev/null 2>&1 || continue
  if "$py" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" </dev/null >/dev/null 2>&1; then
    exec "$py" "$root/hooks/scripts/$script" "$@"
  fi
done

echo "firmware-agent-kit: no working Python 3.8+ found; hook '$script' skipped (set FWKIT_PYTHON)." >&2
exit 0
