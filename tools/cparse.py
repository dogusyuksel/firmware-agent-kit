"""Tiny heuristic C model for the kit's checkers: functions, calls, call graph, execution contexts.

Regex-level by design (fast, no compiler needed, works on code that does not build yet).
"""

import re

KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof", "else", "do", "case", "defined", "_Static_assert"}
FUNC_DEF_RE = re.compile(r"^[ \t]*((?:[A-Za-z_]\w*[ \t\*]+)+)(\w+)[ \t]*\(([^;{}]*?)\)\s*\{", re.M)
ISR_NAME_RE = re.compile(r"^(?:\w+_IRQHandler|\w+_Handler|\w+_(?:isr|ISR|irq|IRQ)(?:_handler|_callback|_cb)?|(?:isr|ISR)_\w+|HAL_\w+Callback)$")
NOT_ISR = {"Error_Handler", "Default_Handler", "Reset_Handler", "vApplicationStackOverflowHook",
           "vApplicationMallocFailedHook", "vApplicationIdleHook", "vApplicationDaemonTaskStartupHook"}
TASK_CREATE_RE = re.compile(r"\b(xTaskCreate|xTaskCreateStatic|osThreadNew)\s*\(")
TIMER_CREATE_RE = re.compile(r"\b(xTimerCreate|xTimerCreateStatic|osTimerNew)\s*\(")


class Finding(object):
    __slots__ = ("rule", "sev", "line", "end", "msg")

    def __init__(self, rule, sev, line, end, msg):
        self.rule, self.sev, self.line, self.end, self.msg = rule, sev, line, end, msg

    def touches(self, changed):
        return changed is None or any(l in changed for l in range(self.line, self.end + 1))

    def __str__(self):
        return "L{}: [{}] {}".format(self.line, self.rule, self.msg)


def strip_comments_and_strings(src):
    """Blank out comments and string/char literals, keeping offsets and newlines."""
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        c, nxt = src[i], src[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            out[i:j] = " " * (j - i)
            i = j
        elif c == "/" and nxt == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        elif c in "\"'":
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            for k in range(i + 1, min(j, n)):
                out[k] = " "
            i = j + 1
        else:
            i += 1
    return "".join(out)


def match_close(text, open_idx, open_ch="{", close_ch="}"):
    depth = 0
    for i in range(open_idx, len(text)):
        ch = text[i]
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
    return len(text) - 1


def call_args(text, open_paren):
    """Split the top-level comma-separated arguments of a call whose '(' is at open_paren."""
    close = match_close(text, open_paren, "(", ")")
    inner = text[open_paren + 1:close]
    args, depth, cur = [], 0, []
    for ch in inner:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            args.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        args.append("".join(cur).strip())
    return args, close


def calls(text, names):
    """Yield (name, match_start, open_paren_idx) for calls to any of names."""
    if not names:
        return
    rx = re.compile(r"(?<![\w.>])(" + "|".join(re.escape(n) for n in names) + r")\s*\(")
    for m in rx.finditer(text):
        yield m.group(1), m.start(), m.end() - 1


class Func(object):
    __slots__ = ("name", "start", "body_start", "body_end", "prefix", "params")

    def __init__(self, name, start, body_start, body_end, prefix, params):
        self.name, self.start, self.body_start, self.body_end = name, start, body_start, body_end
        self.prefix, self.params = prefix, params


class CFile(object):
    def __init__(self, src, isr_patterns=(), extra_isr=None):
        self.src = src
        self.extra_isr = extra_isr or {}
        self.code = strip_comments_and_strings(src)
        self._nl = [0] + [i + 1 for i, ch in enumerate(self.code) if ch == "\n"]
        self.funcs = {}
        for m in FUNC_DEF_RE.finditer(self.code):
            name = m.group(2)
            if name in KEYWORDS or "else" in m.group(1).split():
                continue
            b = m.end() - 1
            self.funcs[name] = Func(name, m.start(), b, match_close(self.code, b), m.group(1), m.group(3))
        self.callees = {}
        self.calls_all = {}
        ident = re.compile(r"(?<![\w.>])(\w+)\s*\(")
        for f in self.funcs.values():
            names = set(ident.findall(self.body(f))) - KEYWORDS
            self.calls_all[f.name] = names
            self.callees[f.name] = set(n for n in names if n in self.funcs and n != f.name)
        self.isr = self._isr_contexts(isr_patterns)
        self.tasks = self._created(TASK_CREATE_RE, 0)
        self.timer_cbs = self._created(TIMER_CREATE_RE, None)

    # ---- positions
    def line(self, idx):
        lo, hi = 0, len(self._nl) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self._nl[mid] <= idx:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    def body(self, f):
        return self.code[f.body_start:f.body_end + 1]

    def func_at(self, idx):
        for f in self.funcs.values():
            if f.body_start <= idx <= f.body_end:
                return f
        return None

    # ---- contexts
    def _isr_contexts(self, extra_patterns):
        extra = [re.compile(p + r"$") for p in extra_patterns]
        roots = {}
        for name, f in self.funcs.items():
            if name in NOT_ISR:
                continue
            if name == "vApplicationTickHook":
                roots[name] = "tick hook (runs in the SysTick ISR)"
            elif name == "ISR" or (ISR_NAME_RE.match(name) and "FromISR" not in name):
                roots[name] = ("HAL callback (ISR context with _IT/_DMA APIs)" if name.startswith("HAL_")
                               else "interrupt handler")
            elif any(r.match(name) for r in extra):
                roots[name] = "configured ISR function"
            elif name in self.extra_isr and "static" not in f.prefix.split():
                roots[name] = self.extra_isr[name]
        return self._propagate(roots, "ISR-reachable function (via")

    def _propagate(self, roots, label):
        ctx = dict(roots)
        stack = list(roots)
        while stack:
            cur = stack.pop()
            for callee in self.callees.get(cur, ()):
                if callee not in ctx and callee not in NOT_ISR:
                    ctx[callee] = "{} '{}')".format(label, cur)
                    stack.append(callee)
        return ctx

    def _created(self, rx, arg_index):
        """Functions passed to task/timer creation calls -> name."""
        out = {}
        for m in rx.finditer(self.code):
            args, _ = call_args(self.code, m.end() - 1)
            if m.group(1) in ("osThreadNew", "osTimerNew"):
                idx = 0
            elif arg_index is not None:
                idx = arg_index
            else:
                idx = 4  # xTimerCreate(name, period, autoreload, id, callback)
            if len(args) > idx:
                name = re.sub(r"^\(\s*\w+\s*\)\s*|&", "", args[idx]).strip()
                if re.match(r"^\w+$", name):
                    out[name] = m.group(1)
        return out
