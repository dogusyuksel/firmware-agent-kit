#!/usr/bin/env python3
"""RTOS API usage checker for FreeRTOS (vanilla, ESP-IDF SMP) and CMSIS-RTOS2.

Rule IDs (RTOS-xxx) and their rationale are catalogued in docs/RTOS_RULES.md.
Heuristic and intra-file (with an intra-file call graph); project mode adds
FreeRTOSConfig.h, NVIC priority and heap-scheme checks.

  python rtos_check.py src/*.c                 # per-file rules (changed lines only, vs git)
  python rtos_check.py --all-lines src/app.c
  python rtos_check.py --project               # project-level rules (+ per-file on all sources)
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cparse import CFile, Finding, call_args, calls, match_close  # noqa: E402
from fwlib import C_EXTS, git_changed_lines, is_protected, load_config, rel  # noqa: E402

# ------------------------------------------------------------------ API tables
ISR_VARIANT = {n: n + "FromISR" for n in (
    "xQueueSend", "xQueueSendToBack", "xQueueSendToFront", "xQueueReceive", "xQueueOverwrite", "xQueuePeek",
    "xQueueReset", "uxQueueMessagesWaiting", "xQueueIsQueueEmpty", "xQueueIsQueueFull",
    "xSemaphoreGive", "xSemaphoreTake", "xTaskNotify", "xTaskNotifyAndQuery", "xTaskNotifyIndexed",
    "xEventGroupSetBits", "xEventGroupClearBits", "xEventGroupGetBits",
    "xTimerStart", "xTimerStop", "xTimerReset", "xTimerChangePeriod", "xTimerPendFunctionCall",
    "xStreamBufferSend", "xStreamBufferReceive", "xMessageBufferSend", "xMessageBufferReceive",
    "xTaskGetTickCount", "xTaskResume", "uxTaskPriorityGet",
)}
ISR_VARIANT.update({
    "xTaskNotifyGive": "vTaskNotifyGiveFromISR", "vTaskNotifyGive": "vTaskNotifyGiveFromISR",
    "taskENTER_CRITICAL": "taskENTER_CRITICAL_FROM_ISR", "taskEXIT_CRITICAL": "taskEXIT_CRITICAL_FROM_ISR",
})
NEVER_IN_ISR = (
    "vTaskDelay", "vTaskDelayUntil", "xTaskDelayUntil", "vTaskSuspend", "vTaskSuspendAll", "xTaskResumeAll",
    "ulTaskNotifyTake", "xTaskNotifyWait", "xEventGroupWaitBits", "xEventGroupSync", "xSemaphoreTakeRecursive",
    "xSemaphoreGiveRecursive", "vTaskDelete", "xTaskCreate", "xTaskCreatePinnedToCore", "vTaskPrioritySet",
    "pvPortMalloc", "vPortFree", "taskYIELD", "portYIELD", "vQueueDelete", "vSemaphoreDelete",
    "osDelay", "osDelayUntil", "osMutexAcquire", "osMutexRelease", "osThreadFlagsWait", "osEventFlagsWait",
    "osThreadYield", "osThreadNew", "osThreadTerminate", "osKernelLock", "osKernelUnlock", "osThreadSuspend",
)
# (api, index of timeout argument)
TIMEOUT_ARG = {
    "xQueueSend": 2, "xQueueSendToBack": 2, "xQueueSendToFront": 2, "xQueueReceive": 2, "xQueuePeek": 2,
    "xSemaphoreTake": 1, "xSemaphoreTakeRecursive": 1, "ulTaskNotifyTake": 1, "xTaskNotifyWait": 3,
    "xEventGroupWaitBits": 4, "xStreamBufferSend": 3, "xStreamBufferReceive": 3, "xMessageBufferSend": 3,
    "xMessageBufferReceive": 3, "xTimerStart": 1, "xTimerStop": 1, "xTimerReset": 1, "xTimerChangePeriod": 2,
    "xTimerDelete": 1, "osSemaphoreAcquire": 1, "osMutexAcquire": 1, "osMessageQueuePut": 3, "osMessageQueueGet": 3,
    "osMemoryPoolAlloc": 1, "osThreadFlagsWait": 2, "osEventFlagsWait": 3,
}
ALWAYS_BLOCKING = ("vTaskDelay", "vTaskDelayUntil", "xTaskDelayUntil", "osDelay", "osDelayUntil", "taskYIELD", "osThreadYield")
CONTEXT_SWITCHING = tuple(TIMEOUT_ARG) + ALWAYS_BLOCKING + (
    "xSemaphoreGive", "xSemaphoreGiveRecursive", "xTaskNotify", "xTaskNotifyGive", "xEventGroupSetBits",
    "vTaskPrioritySet", "vTaskResume", "vTaskSuspend", "xTaskCreate", "vTaskDelete")
CREATE_KIND = {
    "xSemaphoreCreateMutex": "mutex", "xSemaphoreCreateMutexStatic": "mutex",
    "xSemaphoreCreateRecursiveMutex": "recursive", "xSemaphoreCreateRecursiveMutexStatic": "recursive",
    "xSemaphoreCreateBinary": "binary", "xSemaphoreCreateBinaryStatic": "binary",
    "xSemaphoreCreateCounting": "counting", "xSemaphoreCreateCountingStatic": "counting",
    "xQueueCreate": "queue", "xQueueCreateStatic": "queue", "xTimerCreate": "timer", "xTimerCreateStatic": "timer",
    "xEventGroupCreate": "eventgroup", "xEventGroupCreateStatic": "eventgroup",
    "xStreamBufferCreate": "stream", "xMessageBufferCreate": "message",
    "osMutexNew": "osmutex", "osSemaphoreNew": "ossem", "osMessageQueueNew": "queue", "osTimerNew": "timer",
    "osEventFlagsNew": "eventgroup", "pvPortMalloc": "heap", "malloc": "libc_heap", "calloc": "libc_heap",
}
DYNAMIC_CREATE = [k for k in CREATE_KIND if not k.endswith("Static")]
STATIC_TYPES = ("StaticTask_t", "StaticQueue_t", "StaticSemaphore_t", "StaticTimer_t", "StaticEventGroup_t",
                "StaticStreamBuffer_t", "StaticMessageBuffer_t", "StackType_t")
UNCHECKED_RET = ("xTaskCreate", "xTaskCreatePinnedToCore", "xQueueSend", "xQueueSendToBack", "xQueueSendToFront",
                 "xQueueReceive", "xSemaphoreTake", "xTimerStart", "xTimerStop", "xTimerReset", "xTimerChangePeriod",
                 "xQueueSendFromISR", "xQueueSendToBackFromISR", "xTimerStartFromISR", "xTimerPendFunctionCallFromISR",
                 "xEventGroupSetBitsFromISR", "osMessageQueuePut", "osSemaphoreAcquire", "osMutexAcquire")
WDT_FEED = re.compile(r"\b(HAL_IWDG_Refresh|HAL_WWDG_Refresh|LL_IWDG_ReloadCounter|IWDG->KR\s*=|WDT_Restart|wdt_reset|"
                      r"esp_task_wdt_reset|WDT->WDT_CR\s*=)")
DEPRECATED = {"xTaskHandle": "TaskHandle_t", "xQueueHandle": "QueueHandle_t", "xSemaphoreHandle": "SemaphoreHandle_t",
              "xTimerHandle": "TimerHandle_t", "portTICK_RATE_MS": "portTICK_PERIOD_MS / pdMS_TO_TICKS()",
              "vSemaphoreCreateBinary": "xSemaphoreCreateBinary (starts EMPTY - give once if needed)",
              "portBASE_TYPE": "BaseType_t", "xTimeOutType": "TimeOut_t", "xMemoryRegion": "MemoryRegion_t"}
FOREVER_RE = re.compile(r"\bfor\s*\(\s*;\s*;\s*\)|\bwhile\s*\(\s*(?:1|1U|true|TRUE|pdTRUE)\s*\)")
TASK_END_RE = re.compile(r"\bvTaskDelete\s*\(|\bosThreadExit\s*\(")
BLOCKING_ANY = tuple(TIMEOUT_ARG) + ALWAYS_BLOCKING + ("vTaskSuspend",)


def is_zero(arg):
    return arg.strip().rstrip("uUlL") in ("0", "0x0", "(TickType_t)0", "( TickType_t ) 0", "NULL")


def is_forever(arg):
    return "portMAX_DELAY" in arg or "osWaitForever" in arg


def statement_start(code, idx):
    """True if the call at idx is a whole expression statement (return value discarded)."""
    j = idx - 1
    while j >= 0 and code[j] in " \t\r\n":
        j -= 1
    return j < 0 or code[j] in ";{}:" or code[max(0, j - 5):j + 1] == "(void)" and False


def discarded(code, idx):
    j = idx - 1
    while j >= 0 and code[j] in " \t\r\n":
        j -= 1
    if j >= 0 and code[j] == ")" and re.search(r"\(\s*void\s*\)$", code[max(0, j - 10):j + 1]):
        return False  # explicit (void) cast: intentional
    return j < 0 or code[j] in ";{}" or (code[j] == ":" and code[j - 1] != ":")


# ------------------------------------------------------------------ per-file rules
def check_source(src, cfg, rtos_cfg=None):
    cf = CFile(src, (cfg.get("lint") or {}).get("isr_functions", []))
    code = cf.code
    out = []
    rtos_cfg = rtos_cfg or {}

    def add(rule, sev, idx, msg, end_idx=None):
        out.append(Finding(rule, sev, cf.line(idx), cf.line(end_idx) if end_idx is not None else cf.line(idx), msg))

    if not re.search(r"\b(xTask\w+|vTask\w+|xQueue\w+|xSemaphore\w+|xTimer\w+|xEventGroup\w+|os(Delay|Thread|Mutex|"
                     r"Semaphore|MessageQueue|Kernel|Timer|EventFlags)\w*|portENTER_CRITICAL|taskENTER_CRITICAL|"
                     r"pvPortMalloc|FreeRTOS)\b", code + src[:3000]):
        return out  # not an RTOS file

    # handle kinds: name -> (kind, creating function name)
    kinds = {}
    for m in re.finditer(r"([\w\.\->\[\]]+)\s*=\s*(?:\(\s*\w+\s*\*?\s*\)\s*)?(" + "|".join(CREATE_KIND) + r")\s*\(", code):
        f = cf.func_at(m.start())
        kinds[m.group(1)] = (CREATE_KIND[m.group(2)], f.name if f else None, m)

    def kind(arg):
        a = arg.strip().lstrip("&").strip()
        return kinds.get(a, (None,))[0]

    # ---------- ISR context
    for name, why in cf.isr.items():
        f = cf.funcs[name]
        b0, body = f.body_start, cf.body(f)
        for api, at, paren in calls(body, list(ISR_VARIANT)):
            add("RTOS-011", "error", b0 + at, "{}() in {} '{}' - use {}.".format(api, why, name, ISR_VARIANT[api]))
        for api, at, paren in calls(body, list(NEVER_IN_ISR)):
            add("RTOS-015", "error", b0 + at, "{}() must never be called from {} '{}' (blocks or not ISR-safe). "
                "Defer to a task (notification/queue).".format(api, why, name))
        if cf.is_esp:
            for api, at, _ in calls(body, ["portENTER_CRITICAL", "portEXIT_CRITICAL"]):
                add("RTOS-045", "error", b0 + at, "{}() in ISR '{}' - use {}_ISR() on ESP-IDF.".format(api, name, api))
        for api, at, paren in calls(body, ["xSemaphoreGiveFromISR", "xSemaphoreTakeFromISR", "xSemaphoreGive",
                                           "xSemaphoreTake", "osMutexAcquire", "osMutexRelease"]):
            args, _ = call_args(body, paren)
            if api.startswith("osMutex") or (args and kind(args[0]) in ("mutex", "recursive")):
                add("RTOS-014", "error", b0 + at, "Mutex used in {} '{}' - mutexes (priority inheritance) are task-only. "
                    "Use a binary semaphore or task notification from ISRs.".format(why, name))
        for api, at, paren in calls(body, ["osMessageQueuePut", "osMessageQueueGet", "osSemaphoreAcquire", "osMemoryPoolAlloc"]):
            args, _ = call_args(body, paren)
            i = TIMEOUT_ARG[api]
            if len(args) > i and not is_zero(args[i]):
                add("RTOS-108", "error", b0 + at, "{}() from ISR '{}' needs timeout 0 (CMSIS-RTOS2 returns osErrorParameter "
                    "otherwise).".format(api, name))
        woken = re.search(r"FromISR\s*\([^;]*&\s*(\w+)", body)
        if woken:
            var = woken.group(1)
            if "ISR-reachable" not in why and not re.search(r"\b(portYIELD_FROM_ISR|portEND_SWITCHING_ISR)\s*\(", body):
                add("RTOS-016", "warn", b0, "'{}' collects xHigherPriorityTaskWoken but never calls portYIELD_FROM_ISR() - "
                    "the woken task runs only at the next tick.".format(name), f.body_end)
            decl = re.search(r"\bBaseType_t\s+" + re.escape(var) + r"\s*(=\s*([^;]+))?;", body)
            if decl and (not decl.group(1) or "pdFALSE" not in decl.group(2) and decl.group(2).strip() != "0"):
                add("RTOS-017", "error", b0 + decl.start(), "'{}' must be initialised to pdFALSE before FromISR calls.".format(var))
        for m in WDT_FEED.finditer(body):
            add("RTOS-073", "warn", b0 + m.start(), "Watchdog fed from {} '{}' - it keeps running even if tasks are dead. "
                "Feed it from a supervisor task that checks task health.".format(why, name))
        for h, (k, creator, cm) in kinds.items():
            if creator in cf.tasks and re.search(r"(?<![\w.>])" + re.escape(h) + r"\b", body):
                add("RTOS-087", "warn", b0, "ISR '{}' uses '{}' which is created inside task '{}' - the IRQ can fire "
                    "before creation (NULL handle). Create it before enabling the IRQ.".format(name, h, creator), f.body_end)
                break

    # ---------- timer callbacks (run in the timer service task)
    for name in cf.timer_cbs:
        if name not in cf.funcs:
            continue
        f = cf.funcs[name]
        b0, body = f.body_start, cf.body(f)
        for api, at, paren in calls(body, list(TIMEOUT_ARG) + list(ALWAYS_BLOCKING)):
            args, _ = call_args(body, paren)
            i = TIMEOUT_ARG.get(api)
            if api in ALWAYS_BLOCKING or (i is not None and len(args) > i and not is_zero(args[i])):
                rule = "RTOS-043" if api.startswith("xTimer") else "RTOS-037"
                add(rule, "error", b0 + at, "{}() may block in timer callback '{}' - it stalls the timer service task "
                    "(all timers, and FromISR deferrals). Use timeout 0 or defer to a task.".format(api, name))
        for m in WDT_FEED.finditer(body):
            add("RTOS-073", "warn", b0 + m.start(), "Watchdog fed from timer callback '{}' - not a proof that tasks are alive.".format(name))
    for m in re.finditer(r"\bxTimerCreate(?:Static)?\s*\(", code):
        args, _ = call_args(code, m.end() - 1)
        if len(args) > 1 and is_zero(args[1]):
            add("RTOS-041", "error", m.start(), "Timer period 0 is invalid (xTimerCreate fails/asserts).")

    # ---------- per-function state scan: critical sections, scheduler suspension, mutex holding
    tok_rx = re.compile(r"(?<![\w.>])(taskENTER_CRITICAL(?:_FROM_ISR)?|taskEXIT_CRITICAL(?:_FROM_ISR)?|portENTER_CRITICAL(?:_ISR)?|"
                        r"portEXIT_CRITICAL(?:_ISR)?|vTaskSuspendAll|xTaskResumeAll|__disable_irq|__enable_irq|"
                        r"xSemaphoreTake(?:Recursive)?|xSemaphoreGive(?:Recursive)?|osMutexAcquire|osMutexRelease|return|"
                        r"for|while|" + "|".join(re.escape(a) for a in CONTEXT_SWITCHING) + r")\b\s*(\()?")
    for f in cf.funcs.values():
        b0, body = f.body_start, cf.body(f)
        crit = susp = irq = 0
        held = {}       # handle -> take idx
        pending = []    # (activate_after_idx, handle, idx)
        for m in tok_rx.finditer(body):
            t, at = m.group(1), m.start()
            for p in list(pending):
                if at > p[0]:
                    held[p[1]] = p[2]
                    pending.remove(p)
            if t.startswith(("taskENTER_CRITICAL", "portENTER_CRITICAL")):
                crit += 1
            elif t.startswith(("taskEXIT_CRITICAL", "portEXIT_CRITICAL")):
                crit = max(0, crit - 1)
            elif t == "__disable_irq":
                irq += 1
            elif t == "__enable_irq":
                irq = max(0, irq - 1)
            elif t == "vTaskSuspendAll":
                if cf.is_esp:
                    add("RTOS-112", "warn", b0 + at, "vTaskSuspendAll() on ESP-IDF (SMP) does not stop the other core and "
                        "does not mask ISRs - use a mutex or portENTER_CRITICAL(&spinlock) for mutual exclusion.")
                susp += 1
            elif t == "xTaskResumeAll":
                susp = max(0, susp - 1)
            elif t == "return":
                if crit or irq:
                    add("RTOS-044", "error", b0 + at, "return inside a critical section in '{}' - interrupts stay masked.".format(f.name))
                if susp:
                    add("RTOS-049", "error", b0 + at, "return while the scheduler is suspended in '{}' (missing xTaskResumeAll).".format(f.name))
                for h, ti in held.items():
                    add("RTOS-029", "error", b0 + at, "return in '{}' while still holding '{}' (taken at L{}) - "
                        "the mutex is never released on this path.".format(f.name, h, cf.line(b0 + ti)))
            elif t in ("for", "while"):
                if crit or irq:
                    add("RTOS-047", "warn", b0 + at, "Loop inside a critical section in '{}' - keep critical sections "
                        "to a few instructions (interrupt latency).".format(f.name))
            elif m.group(2):
                args, close = call_args(body, m.end() - 1)
                if t in ("xSemaphoreTake", "xSemaphoreTakeRecursive", "osMutexAcquire") and args:
                    h = args[0].lstrip("&").strip()
                    k = kind(h)
                    if t == "xSemaphoreTake" and k == "recursive":
                        add("RTOS-030", "error", b0 + at, "'{}' is a recursive mutex - use xSemaphoreTakeRecursive().".format(h))
                    if t == "xSemaphoreTakeRecursive" and k in ("mutex", "binary", "counting"):
                        add("RTOS-030", "error", b0 + at, "'{}' is not a recursive mutex - use xSemaphoreTake().".format(h))
                    lockish = k in ("mutex", "recursive", "osmutex") or (k is None and re.search(r"mutex|mtx|lock", h, re.I))
                    if lockish:
                        if h in held and t == "xSemaphoreTake" and k != "recursive":
                            add("RTOS-055", "error", b0 + at, "'{}' taken twice in '{}' without a give - a non-recursive mutex "
                                "self-deadlocks.".format(h, f.name))
                        pre = body[max(0, at - 40):at]
                        neg = re.search(r"if\s*\(\s*(!\s*)?$", pre)
                        post = body[close + 1:close + 30]
                        negative = neg and (neg.group(1) or re.match(r"\s*(!=\s*pdTRUE|==\s*pdFALSE|!=\s*pdPASS|==\s*pdFAIL|"
                                                                      r"!=\s*osOK)", post))
                        if negative:
                            # "if (take != pdTRUE) { ... return; }" - hold starts after the if-statement
                            j = body.find(")", close + 1)
                            k2 = j + 1
                            while k2 < len(body) and body[k2] in " \t\r\n":
                                k2 += 1
                            end = match_close(body, k2) if k2 < len(body) and body[k2] == "{" else body.find(";", k2)
                            pending.append((end, h, at))
                        elif not neg and not re.search(r"if\s*\(\s*$", pre) or neg:
                            held[h] = at
                    if k == "binary" and re.search(r"(?<![\w.>])xSemaphoreGive\s*\(\s*&?" + re.escape(h) + r"\b", body[close:]):
                        add("RTOS-027", "warn", b0 + at, "Binary semaphore '{}' is used as a lock (take..give in '{}') - "
                            "use a mutex for priority inheritance.".format(h, f.name))
                elif t in ("xSemaphoreGive", "xSemaphoreGiveRecursive", "osMutexRelease") and args:
                    h = args[0].lstrip("&").strip()
                    if t == "xSemaphoreGive" and kind(h) == "recursive":
                        add("RTOS-030", "error", b0 + at, "'{}' is a recursive mutex - use xSemaphoreGiveRecursive().".format(h))
                    held.pop(h, None)
                    pending[:] = [p for p in pending if p[1] != h]
                if t in CONTEXT_SWITCHING:
                    i = TIMEOUT_ARG.get(t)
                    blocking = t in ALWAYS_BLOCKING or (i is not None and len(args) > i and not is_zero(args[i]))
                    if (crit or irq) and (blocking or t in ("xSemaphoreGive", "xTaskNotify", "xTaskNotifyGive")):
                        add("RTOS-046", "error", b0 + at, "{}() inside a critical section in '{}' - blocking/context-switching "
                            "API with interrupts masked.".format(t, f.name))
                    elif susp and (blocking or t in ALWAYS_BLOCKING):
                        add("RTOS-050", "error", b0 + at, "{}() while the scheduler is suspended in '{}' - API that can "
                            "block/switch context must not be called between vTaskSuspendAll/xTaskResumeAll.".format(t, f.name))
        if crit:
            add("RTOS-044", "error", f.start, "Critical section entered but not exited in '{}'.".format(f.name), f.body_end)
        if susp:
            add("RTOS-049", "error", f.start, "vTaskSuspendAll() without matching xTaskResumeAll() in '{}'.".format(f.name), f.body_end)
        if held and not re.search(r"lock|acquire|take|enter|begin", f.name, re.I):
            for h, ti in held.items():
                add("RTOS-029", "warn", b0 + ti, "'{}' taken in '{}' but never given in this function.".format(h, f.name))

    # ---------- tasks
    for name, creator in cf.tasks.items():
        if name not in cf.funcs:
            continue
        f = cf.funcs[name]
        body = cf.body(f)
        loop = FOREVER_RE.search(body)
        if not loop and not TASK_END_RE.search(body):
            add("RTOS-071", "warn", f.start, "Task '{}' can return - tasks must loop forever or end with vTaskDelete(NULL) "
                "(osThreadExit()).".format(name), f.body_end)
        if loop:
            lb = body.find("{", loop.end())
            lbody = body[lb:match_close(body, lb) + 1] if lb >= 0 else ""
            reach = set([name])
            stack = [name]
            while stack:
                for c in cf.callees.get(stack.pop(), ()):
                    if c not in reach:
                        reach.add(c)
                        stack.append(c)
            texts = [lbody] + [cf.body(cf.funcs[c]) for c in reach if c != name]
            if not any(any(True for _ in calls(t, list(BLOCKING_ANY))) for t in texts):
                add("RTOS-070", "warn", f.body_start + max(lb, 0), "Task '{}' loop never blocks (no delay/wait/take/receive) - "
                    "it starves lower-priority tasks and the idle task (which frees deleted-task memory; ESP-IDF task "
                    "watchdog fires). Ignore if it blocks inside another module.".format(name))
        if TASK_END_RE.search(body) and re.search(r"\bxSemaphoreTake\s*\(", body) and \
                len(re.findall(r"\bxSemaphoreTake\s*\(", body)) > len(re.findall(r"\bxSemaphoreGive\s*\(", body)):
            add("RTOS-063", "warn", f.start, "Task '{}' deletes itself with more takes than gives - a held mutex is never "
                "released (and its priority inheritance never undone).".format(name), f.body_end)

    # ---------- creation calls: arguments & return values
    for m in re.finditer(r"\b(xTaskCreate|xTaskCreatePinnedToCore|xTaskCreateStatic|osThreadNew)\s*\(", code):
        api = m.group(1)
        args, close = call_args(code, m.end() - 1)
        caller = cf.func_at(m.start())
        p_idx, s_idx, pr_idx = (1, None, None) if api == "osThreadNew" else (3, 2, 4)
        if s_idx is not None and len(args) > s_idx and re.match(r"^\d+$", args[s_idx]):
            n = int(args[s_idx])
            if cf.is_esp and n < 1536:
                add("RTOS-009", "warn", m.start(), "Stack {} for '{}': ESP-IDF stack depth is in BYTES - {} B is very small "
                    "(typical >= 2048; printf/ESP_LOG need more).".format(n, args[0], n))
            elif not cf.is_esp and n < 64:
                add("RTOS-009", "warn", m.start(), "Stack depth {} words for '{}' is below a safe minimum (configMINIMAL_STACK_SIZE).".format(n, args[0]))
            elif not cf.is_esp and n >= 4096:
                add("RTOS-009", "info", m.start(), "Stack depth is in WORDS on vanilla FreeRTOS: {} = {} KB for '{}' - "
                    "intended?".format(n, n * 4 // 1024, args[0]))
        maxp = rtos_cfg.get("configMAX_PRIORITIES")
        if pr_idx is not None and maxp and len(args) > pr_idx:
            pm = re.match(r"^(?:tskIDLE_PRIORITY\s*\+\s*)?\(?\s*(\d+)\s*\)?$", args[pr_idx])
            if pm and int(pm.group(1)) >= maxp:
                add("RTOS-010", "error", m.start(), "Priority {} >= configMAX_PRIORITIES ({}) for '{}'.".format(pm.group(1), maxp, args[0]))
        if caller and len(args) > p_idx:
            pa = args[p_idx].strip()
            vm = re.match(r"^\(?\s*(?:\(\s*void\s*\*\s*\)\s*)?&?\s*(\w+)\s*\)?$", pa)
            if vm and pa.lstrip("( void*)").startswith("&") or (vm and re.search(r"\b\w+\s+" + re.escape(vm.group(1)) + r"\s*\[", cf.body(caller))):
                v = vm.group(1)
                decl = re.search(r"(^|[;{]\s*)([^;{}()]*?)\b" + re.escape(v) + r"\s*(\[[^\]]*\])?\s*(=[^;]*)?;", cf.body(caller))
                if decl and "static" not in decl.group(2) and decl.group(2).strip():
                    sev = "error" if caller.name == "main" else "warn"
                    add("RTOS-062", sev, m.start(), "Task parameter points to local '{}' of '{}'{} - it is gone when the "
                        "task reads it. Use static/global storage or a heap copy.".format(
                            v, caller.name, " (on Cortex-M ports main()'s stack is reused after vTaskStartScheduler)"
                            if caller.name == "main" else ""))

    for m in calls(code, list(UNCHECKED_RET)):
        api, at, paren = m
        if not discarded(code, at):
            continue
        args, _ = call_args(code, paren)
        i = TIMEOUT_ARG.get(api)
        if i is not None and len(args) > i and is_forever(args[i]) and api not in ("xTimerStart", "xTimerStop", "xTimerReset", "xTimerChangePeriod"):
            continue
        rule = "RTOS-008" if api.startswith(("xTaskCreate", "osThreadNew")) else "RTOS-040" if api.startswith("xTimer") else "RTOS-024"
        add(rule, "warn", at, "Return value of {}() ignored - handle failure (queue full / timeout / out of heap) or "
            "cast to (void) if intentional.".format(api))

    for h, (k, creator, cm) in kinds.items():
        if creator is None or k in ("libc_heap",) or cm.group(2).endswith("Static"):
            continue
        f = cf.funcs[creator]
        after = code[cm.end():f.body_end]
        hv = re.escape(h)
        if not re.search(r"(\b|^)" + hv + r"\s*[!=]=\s*NULL|NULL\s*[!=]=\s*" + hv + r"|!\s*\(?\s*" + hv + r"\b|if\s*\(\s*" + hv +
                         r"\s*\)|(configASSERT|assert|ASSERT|ESP_ERROR_CHECK|FW_ASSERT)\w*\s*\(\s*" + hv, after):
            rule = "RTOS-058" if k == "heap" else "RTOS-022"
            add(rule, "warn", cm.start(), "Result of {}() stored in '{}' is never checked for NULL (out of FreeRTOS heap).".format(cm.group(2), h))

    # ---------- memory
    for m in re.finditer(r"(?<![\w.>])(vPortFree|free)\s*\(\s*([\w\.\->]+)\s*\)", code):
        api, ptr = m.group(1), m.group(2)
        k = kind(ptr)
        if api == "vPortFree" and k == "libc_heap" or api == "free" and k == "heap":
            add("RTOS-059", "error", m.start(), "'{}' allocated by {} but freed with {}() - heaps must match "
                "(pvPortMalloc/vPortFree, malloc/free).".format(ptr, kinds[ptr][2].group(2), api))
        f = cf.func_at(m.start())
        if f:
            rest = code[m.end():f.body_end]
            again = re.search(r"(?<![\w.>])" + api + r"\s*\(\s*" + re.escape(ptr) + r"\s*\)", rest)
            if again and not re.search(re.escape(ptr) + r"\s*=(?!=)", rest[:again.start()]):
                add("RTOS-059", "error", m.end() + again.start(), "'{}' freed twice in '{}' without reassignment (double free).".format(ptr, f.name))
    for m in re.finditer(r"^[ \t]*(?!static\b)((?:const\s+)?(" + "|".join(STATIC_TYPES) + r"))\s+(\w+)", code, re.M):
        f = cf.func_at(m.start())
        if f:
            add("RTOS-113", "error", m.start(), "{} '{}' is a local in '{}' - static-allocation buffers must outlive the "
                "object: make it static or global.".format(m.group(2), m.group(3), f.name))

    # ---------- scheduler start ordering (main)
    if "main" in cf.funcs:
        f = cf.funcs["main"]
        body = cf.body(f)
        s = re.search(r"\b(vTaskStartScheduler|osKernelStart)\s*\(", body)
        if s:
            pre = body[:s.start()]
            for api, at, paren in calls(pre, list(BLOCKING_ANY) + ["taskYIELD"]):
                args, _ = call_args(pre, paren)
                i = TIMEOUT_ARG.get(api)
                if api in ALWAYS_BLOCKING or api == "vTaskSuspend" or i is None or (len(args) > i and not is_zero(args[i])):
                    add("RTOS-001", "error", f.body_start + at, "{}() before {}() - the scheduler is not running: it blocks "
                        "forever or asserts. Move it into a task.".format(api, s.group(1)))
            for api, at, paren in calls(pre, ["vTaskDelete", "vTaskSuspend"]):
                args, _ = call_args(pre, paren)
                if args and args[0].strip() in ("NULL", "0"):
                    add("RTOS-003", "error", f.body_start + at, "{}(NULL) in main() before the scheduler - there is no current task.".format(api))
            for callee in cf.callees.get("main", ()):
                cm = re.search(r"(?<![\w.>])" + callee + r"\s*\(", pre)
                if cm and any(a in ALWAYS_BLOCKING for a, _, _ in calls(cf.body(cf.funcs[callee]), list(ALWAYS_BLOCKING))):
                    add("RTOS-001", "error", f.body_start + cm.start(), "{}() is called before {}() but contains a blocking "
                        "RTOS delay.".format(callee, s.group(1)))
        ki = re.search(r"\bosKernelInitialize\s*\(", body)
        for m in re.finditer(r"\bos(Thread|Mutex|Semaphore|MessageQueue|Timer|EventFlags|MemoryPool)New\s*\(", body):
            if not ki or m.start() < ki.start():
                add("RTOS-109", "error", f.body_start + m.start(), "CMSIS-RTOS2 object created before osKernelInitialize().")
                break

    # ---------- public functions must be thread-safe
    file_vars = set()
    depth, start = 0, 0
    for i, ch in enumerate(code):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            start = i + 1
        elif ch == ";" and depth == 0:
            stmt = "\n".join(l for l in code[start:i].splitlines() if not l.lstrip().startswith("#")).strip()
            start = i + 1
            if stmt and "(" not in stmt.split("=")[0] and not re.search(r"\b(const|typedef|extern|enum)\b", stmt):
                vm = re.search(r"\b([A-Za-z_]\w*)\s*(\[[^\]]*\])*\s*(=.*)?$", stmt, re.S)
                if vm and len(stmt.split()) >= 2:
                    file_vars.add(vm.group(1))
    lock_rx = re.compile(r"\b(xSemaphoreTake\w*|osMutexAcquire|taskENTER_CRITICAL\w*|portENTER_CRITICAL\w*|__disable_irq|"
                         r"vTaskSuspendAll|atomic_\w+|__atomic_\w+|__sync_\w+|\w*[Ll]ock\w*|\w*CRITICAL\w*|\w*[Mm]utex\w*)\s*\(")
    special = set(cf.isr) | set(cf.tasks) | set(cf.timer_cbs) | {"main", "app_main"}
    for f in cf.funcs.values():
        if "static" in f.prefix.split() or f.name in special or re.search(r"init|setup|deinit|create|test|reset", f.name, re.I):
            continue
        body = cf.body(f)
        if lock_rx.search(body):
            continue
        for v in file_vars:
            w = re.search(r"(?<![\w.>])" + re.escape(v) + r"\s*(\[[^\]]*\]|\.\w+|->\w+)*\s*(\+\+|--|[-+*/|&^]?=(?!=))|(\+\+|--)\s*"
                          + re.escape(v) + r"\b", body)
            if w:
                add("RTOS-120", "warn", f.body_start + w.start(), "Public function '{}' modifies shared state '{}' without "
                    "a mutex/critical section - public APIs must be thread-safe (or document a single owner task).".format(f.name, v))
                break

    # ---------- literature-derived extras
    for name, why in cf.isr.items():
        body = cf.body(cf.funcs[name])
        n = len(re.findall(r"\b(xEventGroupSetBitsFromISR|osEventFlagsSet)\s*\(", body))
        if n > 1:
            add("RTOS-126", "warn", cf.funcs[name].body_start, "{} event-flag sets in '{}' - each posts to the timer command "
                "queue and can fail; combine the bits into one call.".format(n, name), cf.funcs[name].body_end)
    if "vApplicationIdleHook" in cf.funcs:
        f = cf.funcs["vApplicationIdleHook"]
        for api, at, paren in calls(cf.body(f), list(BLOCKING_ANY)):
            add("RTOS-127", "error", f.body_start + at, "{}() in vApplicationIdleHook - the idle task must never block.".format(api))
    for f in cf.funcs.values():
        if f.name in cf.isr:
            continue
        for m in re.finditer(r"\b(__disable_irq|__enable_irq|__set_PRIMASK|__set_BASEPRI)\s*\(", cf.body(f)):
            add("RTOS-121", "warn", f.body_start + m.start(), "{}() in RTOS code ('{}') bypasses the kernel's critical-section "
                "nesting - use taskENTER_CRITICAL()/taskEXIT_CRITICAL().".format(m.group(1), f.name))
            break
    qlen = {}
    for h, (k, creator, cm) in kinds.items():
        if k == "queue" and cm.group(2).startswith("xQueueCreate"):
            args, _ = call_args(code, cm.end() - 1)
            if args and re.match(r"^\d+$", args[0]):
                qlen[h] = int(args[0])
    for api, at, paren in calls(code, ["xQueueOverwrite", "xQueueOverwriteFromISR"]):
        args, _ = call_args(code, paren)
        if args and qlen.get(args[0].strip(), 1) != 1:
            add("RTOS-118", "error", at, "{}() is only valid on queues of length 1 ('{}' has length {}).".format(api, args[0], qlen[args[0].strip()]))
    writers = {}
    for api, at, paren in calls(code, ["xStreamBufferSend", "xStreamBufferSendFromISR", "xMessageBufferSend", "xMessageBufferSendFromISR"]):
        args, _ = call_args(code, paren)
        f = cf.func_at(at)
        if args and f:
            writers.setdefault(args[0].strip(), set()).add(f.name)
    for h, fns in writers.items():
        if len(fns) > 1:
            add("RTOS-119", "warn", code.find(h), "Stream/message buffer '{}' has several writers ({}) - they allow ONE writer "
                "and ONE reader unless serialised.".format(h, ", ".join(sorted(fns))))
    for f in cf.funcs.values():
        body = cf.body(f)
        if re.search(r"\bxRingbufferReceive\w*\s*\(", body) and not re.search(r"\bvRingbufferReturnItem\w*\s*\(", body):
            add("RTOS-122", "warn", f.body_start, "xRingbufferReceive() in '{}' without vRingbufferReturnItem() - the item's "
                "space is never released.".format(f.name), f.body_end)
    for m in re.finditer(r"\bosMutexNew\s*\(\s*NULL\s*\)", code):
        add("RTOS-123", "warn", m.start(), "osMutexNew(NULL): default attributes are non-recursive without priority inheritance "
            "by the CMSIS spec - pass attr_bits = osMutexPrioInherit explicitly.")
    for m in re.finditer(r"\bosMutexRobust\b", code):
        add("RTOS-123", "error", m.start(), "osMutexRobust is not supported by CMSIS-FreeRTOS - osMutexNew() returns NULL.")
    for m in re.finditer(r"\bosDelayUntil\s*\(\s*\d+\s*\)", code):
        add("RTOS-123", "warn", m.start(), "osDelayUntil() takes an ABSOLUTE tick count - use osKernelGetTickCount() + period.")
    for m in re.finditer(r"\bvTaskDelete\s*\(\s*(?!NULL\b|0\b)([^)\s]+)\s*\)", code):
        add("RTOS-124", "info" if not cf.is_esp else "warn", m.start(), "vTaskDelete({}) deletes ANOTHER task - its held mutexes and "
            "heap are not released{}; prefer signalling it to clean up and self-delete.".format(
                m.group(1), " and on SMP it may be running on the other core" if cf.is_esp else ""))
    if cf.is_esp:
        for m in re.finditer(r"\bvTaskStartScheduler\s*\(", code):
            add("RTOS-125", "error", m.start(), "vTaskStartScheduler() in an ESP-IDF project - the scheduler is already running "
                "when app_main() is called.")
        for m in re.finditer(r"\b(portDISABLE_INTERRUPTS|taskDISABLE_INTERRUPTS)\s*\(", code):
            add("RTOS-112", "warn", m.start(), "{}() only affects the current core on ESP-IDF SMP - not mutual exclusion; use "
                "portENTER_CRITICAL(&spinlock).".format(m.group(1)))
    for m in re.finditer(r"/\s*portTICK_(PERIOD|RATE)_MS\b", code):
        add("RTOS-102", "info", m.start(), "Division by portTICK_PERIOD_MS truncates (and is 0 above 1 kHz) - use pdMS_TO_TICKS().")

    # ---------- misc
    for m in re.finditer(r"\b(vTaskDelay|osDelay)\s*\(\s*(\d+)\s*\)", code):
        if int(m.group(2)) > 1:
            add("RTOS-102", "warn", m.start(), "{}({}) uses raw ticks - write pdMS_TO_TICKS(ms) so it survives "
                "configTICK_RATE_HZ changes.".format(m.group(1), m.group(2)))
    for m in calls(code, ["xEventGroupSetBits", "xEventGroupClearBits", "xEventGroupWaitBits", "xEventGroupSetBitsFromISR",
                          "xEventGroupSync"]):
        args, _ = call_args(code, m[2])
        if len(args) > 1:
            for v in re.findall(r"0x([0-9a-fA-F]+)", args[1]):
                if int(v, 16) >= 0x01000000:
                    add("RTOS-103", "error", m[1], "Event group bits 24-31 are reserved by the kernel (32-bit ticks).")
            if re.search(r"<<\s*(2[4-9]|3[01])\b", args[1]):
                add("RTOS-103", "error", m[1], "Event group bits 24-31 are reserved by the kernel (32-bit ticks).")
    for m in calls(code, ["xQueueSend", "xQueueSendToBack", "xQueueSendToFront", "xQueueSendFromISR", "xQueueOverwrite",
                          "xQueueReceive", "xQueuePeek"]):
        args, _ = call_args(code, m[2])
        if len(args) > 1 and re.match(r"^-?\d+[uUlL]*$|^'.'$", args[1]):
            add("RTOS-117", "error", m[1], "{}() takes a POINTER to the item (copied by value), not the value itself.".format(m[0]))
    for old, new in DEPRECATED.items():
        for m in re.finditer(r"\b" + old + r"\b", code):
            add("RTOS-101", "info", m.start(), "{} is deprecated - use {}.".format(old, new))
            break
    if cf.is_esp:
        for m in re.finditer(r"\bportMUX_TYPE\s+(\w+)\s*;", code):
            add("RTOS-110", "error", m.start(), "portMUX_TYPE '{}' not initialised - use = portMUX_INITIALIZER_UNLOCKED.".format(m.group(1)))
        for m in re.finditer(r"^[ \t]*(?!static\b)portMUX_TYPE\s+(\w+)", code, re.M):
            if cf.func_at(m.start()):
                add("RTOS-110", "error", m.start(), "portMUX_TYPE '{}' is a local - spinlocks must be static/global "
                    "(shared by all users).".format(m.group(1)))
        for m in re.finditer(r"\bportENTER_CRITICAL\s*\(\s*\)", code):
            add("RTOS-110", "error", m.start(), "ESP-IDF portENTER_CRITICAL() needs a spinlock argument: portENTER_CRITICAL(&mux).")
    return out


# ------------------------------------------------------------------ project-level rules
CFG_DEF_RE = re.compile(r"^\s*#\s*define\s+(config\w+|INCLUDE_\w+)\s+(.+?)\s*(?://.*|/\*.*)?$", re.M)


def find_files(proj, names=None, exts=None, limit_depth=8):
    skip = {".git", "build", "node_modules", ".venv", "venv", "managed_components", ".pio", "out"}
    base = proj.rstrip("\\/").count(os.sep)
    for root, dirs, files in os.walk(proj):
        dirs[:] = [d for d in dirs if d not in skip and not d.startswith("build")]
        if root.count(os.sep) - base >= limit_depth:
            dirs[:] = []
        for f in files:
            if (names and f in names) or (exts and f.lower().endswith(exts)):
                yield os.path.join(root, f)


def eval_int(expr, defs, depth=0):
    expr = re.sub(r"\b(\d+)[uUlL]+\b", r"\1", expr.strip())
    expr = re.sub(r"\(\s*(uint\w*|int\w*|unsigned\s*\w*|UBaseType_t|BaseType_t|TickType_t)\s*\)", "", expr)
    if depth < 5:
        expr = re.sub(r"\b([A-Za-z_]\w*)\b", lambda m: "(" + defs[m.group(1)] + ")" if m.group(1) in defs else m.group(1), expr)
    if not re.match(r"^[\s\d()+\-*/<>|&x a-fA-F]+$", expr) or re.search(r"[a-wyzA-WYZ]", re.sub(r"0x[0-9a-fA-F]+", "", expr)):
        return eval_int(expr, defs, depth + 1) if depth < 5 and re.search(r"[A-Za-z_]", expr) else None
    try:
        return int(eval(expr, {"__builtins__": {}}))  # noqa: S307 - digits/operators only (checked above)
    except Exception:
        return None


def load_rtos_config(proj, cfg):
    path = (cfg.get("rtos") or {}).get("config_header")
    path = os.path.join(proj, path) if path else next(find_files(proj, names={"FreeRTOSConfig.h"}), None)
    if not path or not os.path.isfile(path):
        return {}, None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    defs = {m.group(1): m.group(2) for m in CFG_DEF_RE.finditer(text)}
    for m in re.finditer(r"^\s*#\s*define\s+(__NVIC_PRIO_BITS)\s+(\d+)", text, re.M):
        defs[m.group(1)] = m.group(2)
    vals = {k: eval_int(v, defs) for k, v in defs.items()}
    vals["_raw"] = defs
    vals["_text"] = text
    return vals, path


def check_project(proj, cfg, sources):
    out = []   # (relpath, Finding)
    rc, cfg_path = load_rtos_config(proj, cfg)
    srcs = {}
    for p in sources:
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                srcs[p] = f.read()
        except OSError:
            pass
    is_esp = os.path.isfile(os.path.join(proj, "sdkconfig")) or (cfg.get("family") == "esp32")
    uses_rtos = any(re.search(r"\b(xTaskCreate|osThreadNew|vTaskStartScheduler|osKernelStart|xTaskCreatePinnedToCore)\b", s)
                    for s in srcs.values())
    if not uses_rtos:
        return out, rc

    def add(path, rule, sev, line, msg):
        out.append((rel(path, proj) if path else "(project)", Finding(rule, sev, line, line, msg)))

    if cfg_path and not is_esp:
        text, raw = rc["_text"], rc["_raw"]
        ln = lambda key: next((i + 1 for i, l in enumerate(text.splitlines()) if re.search(r"#\s*define\s+" + key + r"\b", l)), 1)  # noqa: E731
        if "configASSERT" not in text:
            add(cfg_path, "RTOS-104", "warn", 1, "configASSERT() is not defined - kernel misuse (wrong ISR priority, "
                "NULL handles) goes undetected. Define it to trap (e.g. disable IRQs + BKPT/loop).")
        if not rc.get("configCHECK_FOR_STACK_OVERFLOW"):
            add(cfg_path, "RTOS-057", "warn", ln("configCHECK_FOR_STACK_OVERFLOW"), "configCHECK_FOR_STACK_OVERFLOW is 0/undefined - "
                "set 2 in development and implement vApplicationStackOverflowHook().")
        if not rc.get("configUSE_MALLOC_FAILED_HOOK") and any(re.search(r"\b(" + "|".join(DYNAMIC_CREATE[:20]) + r")\s*\(", s) for s in srcs.values()):
            add(cfg_path, "RTOS-114", "info", ln("configUSE_MALLOC_FAILED_HOOK"), "configUSE_MALLOC_FAILED_HOOK is 0 while objects "
                "are created dynamically - enable it to catch heap exhaustion.")
        msp = rc.get("configMAX_SYSCALL_INTERRUPT_PRIORITY")
        if msp == 0:
            add(cfg_path, "RTOS-105", "error", ln("configMAX_SYSCALL_INTERRUPT_PRIORITY"), "configMAX_SYSCALL_INTERRUPT_PRIORITY must "
                "not be 0 on Cortex-M (BASEPRI=0 masks nothing).")
        lib = rc.get("configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY")
        bits = rc.get("configPRIO_BITS") or rc.get("__NVIC_PRIO_BITS")
        if lib is None and msp is not None and bits:
            lib = msp >> (8 - bits)
        kern = rc.get("configKERNEL_INTERRUPT_PRIORITY")
        if kern is not None and bits and kern != ((1 << bits) - 1) << (8 - bits) and kern != 255:
            add(cfg_path, "RTOS-105", "warn", ln("configKERNEL_INTERRUPT_PRIORITY"), "configKERNEL_INTERRUPT_PRIORITY should be the "
                "LOWEST priority (SysTick/PendSV).")
        tick = rc.get("configTICK_RATE_HZ")
        if tick and tick < 1000:
            for p, s in srcs.items():
                for m in re.finditer(r"\bpdMS_TO_TICKS\s*\(\s*(\d+)\s*\)", s):
                    if int(m.group(1)) * tick // 1000 == 0:
                        add(p, "RTOS-115", "warn", s.count("\n", 0, m.start()) + 1, "pdMS_TO_TICKS({}) is 0 ticks at "
                            "configTICK_RATE_HZ={} - the delay/timeout becomes 0 (busy loop / no wait).".format(m.group(1), tick))
        maxp = rc.get("configMAX_PRIORITIES")
        if maxp and maxp > 32 and not rc.get("configUSE_PORT_OPTIMISED_TASK_SELECTION") == 0:
            add(cfg_path, "RTOS-105", "warn", ln("configMAX_PRIORITIES"), "configMAX_PRIORITIES > 32 is not allowed with optimised "
                "task selection.")
        # NVIC priorities vs ISRs that call FromISR APIs
        if lib is not None:
            prio = {}
            for p, s in srcs.items():
                for m in re.finditer(r"\b(?:HAL_)?NVIC_SetPriority\s*\(\s*(\w+?)_IRQn\s*,\s*([^,\)]+)", s):
                    v = eval_int(m.group(2), rc.get("_raw", {}))
                    if v is not None:
                        prio[m.group(1)] = (v, p, s.count("\n", 0, m.start()) + 1)
            for p, s in srcs.items():
                for m in re.finditer(r"\bvoid\s+(\w+?)_(IRQHandler|Handler)\s*\(\s*(?:void)?\s*\)\s*\{", s):
                    irq = m.group(1)
                    body = s[m.end() - 1:match_close(s, m.end() - 1)]
                    if irq in ("SysTick", "PendSV", "SVC", "HardFault", "NMI", "MemManage", "BusFault", "UsageFault", "Error", "Default"):
                        continue
                    if not re.search(r"\w+FromISR\s*\(|\bosSemaphoreRelease|\bosMessageQueuePut|\bosThreadFlagsSet|\bosEventFlagsSet", body):
                        continue
                    line = s.count("\n", 0, m.start()) + 1
                    if irq in prio:
                        v, pp, pl = prio[irq]
                        if v < lib:
                            add(pp, "RTOS-018", "error", pl, "{}_IRQn priority {} is above (numerically below) "
                                "configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY={} but its handler calls RTOS FromISR APIs - "
                                "kernel corruption / configASSERT.".format(irq, v, lib))
                    else:
                        add(p, "RTOS-018", "warn", line, "{}_IRQHandler calls RTOS FromISR APIs but no NVIC priority is set for "
                            "{}_IRQn in the scanned sources - the reset default 0 is the HIGHEST priority and not allowed "
                            "(must be >= {}).".format(irq, irq, lib))
        # priority grouping / value encoding / IRQs enabled before the scheduler
        hal_groups = {"NVIC_PRIORITYGROUP_0": 7, "NVIC_PRIORITYGROUP_1": 6, "NVIC_PRIORITYGROUP_2": 5,
                      "NVIC_PRIORITYGROUP_3": 4, "NVIC_PRIORITYGROUP_4": 3}
        for p, s in srcs.items():
            for m in re.finditer(r"\b(?:HAL_)?NVIC_SetPriorityGrouping\s*\(\s*([^)]+?)\s*\)", s):
                arg = m.group(1).strip()
                raw = hal_groups.get(arg, eval_int(arg, rc.get("_raw", {})))
                if raw is not None and bits and raw > 7 - bits:
                    add(p, "RTOS-020", "error", s.count("\n", 0, m.start()) + 1, "Priority grouping {} leaves sub-priority bits - "
                        "FreeRTOS requires all bits as preemption (NVIC_PRIORITYGROUP_4 on STM32).".format(arg))
            for m in re.finditer(r"\b(?:HAL_)?NVIC_SetPriority\s*\(\s*\w+\s*,\s*([^,\)]+)", s):
                arg = m.group(1)
                line = s.count("\n", 0, m.start()) + 1
                if re.search(r"config(MAX_SYSCALL|KERNEL)_INTERRUPT_PRIORITY", arg):
                    add(p, "RTOS-021", "error", line, "NVIC_SetPriority() takes the UNSHIFTED priority; {} is already shifted "
                        "- use configLIBRARY_* values.".format(arg.strip()))
                v = eval_int(arg, rc.get("_raw", {}))
                if v is not None and bits and v > (1 << bits) - 1:
                    add(p, "RTOS-021", "error", line, "Priority {} exceeds the {} implemented bits (max {}) - shifted value "
                        "passed to NVIC_SetPriority?".format(v, bits, (1 << bits) - 1))
        fromisr_irqs = set()
        for s in srcs.values():
            for m in re.finditer(r"\bvoid\s+(\w+?)_IRQHandler\s*\(\s*(?:void)?\s*\)\s*\{", s):
                body = s[m.end() - 1:match_close(s, m.end() - 1)]
                if re.search(r"\w+FromISR\s*\(", body):
                    fromisr_irqs.add(m.group(1))
        for p, s in srcs.items():
            mm = re.search(r"\bint\s+main\s*\([^)]*\)\s*\{", s)
            st = mm and re.search(r"\b(vTaskStartScheduler|osKernelStart)\s*\(", s[mm.end():])
            if not st:
                continue
            pre = s[mm.end():mm.end() + st.start()]
            for m in re.finditer(r"\b(?:HAL_)?NVIC_EnableIRQ\s*\(\s*(\w+?)_IRQn", pre):
                if m.group(1) in fromisr_irqs:
                    add(p, "RTOS-019", "warn", s.count("\n", 0, mm.end() + m.start()) + 1, "{}_IRQn is enabled before the "
                        "scheduler starts and its handler calls RTOS APIs - make sure every handle it uses exists and the "
                        "priority is valid before enabling.".format(m.group(1)))
        # Cortex-M7 port selection (SAMV71, STM32F7/H7)
        core = (cfg.get("core") or "") + " " + (cfg.get("family") or "") + " " + (cfg.get("mcu") or "")
        if re.search(r"m7|samv7|same7|sams7|stm32f7|stm32h7", core, re.I):
            for p in find_files(proj, exts=("port.c",)):
                if re.search(r"ARM_CM4F", p.replace("\\", "/")):
                    add(p, "RTOS-116", "info", 1, "Cortex-M7 target built with the ARM_CM4F port: confirm the core revision "
                        "(SCB->CPUID). r0p0/r0p1 cores need portable/GCC/ARM_CM7/r0p1 (errata 837070).")
                    break
        if not rc.get("configUSE_NEWLIB_REENTRANT"):
            users = [p for p, s in srcs.items() if re.search(r"\b(printf|sprintf|snprintf|malloc|strtok|rand)\s*\(", s)]
            if len(users) > 0 and cfg.get("family") in ("stm32", "samv71", None):
                add(cfg_path, "RTOS-107", "warn", 1, "newlib functions (printf/malloc/strtok...) are used from tasks but "
                    "configUSE_NEWLIB_REENTRANT is not 1 - not thread-safe (or provide newlib lock hooks).")
    # ESP-IDF: default 100 Hz tick turns small pdMS_TO_TICKS() into 0
    if is_esp:
        hz = None
        try:
            with open(os.path.join(proj, "sdkconfig"), "r", encoding="utf-8", errors="replace") as f:
                m = re.search(r"^CONFIG_FREERTOS_HZ=(\d+)", f.read(), re.M)
                hz = int(m.group(1)) if m else None
        except OSError:
            pass
        if hz and hz < 1000:
            for p, s in srcs.items():
                for m in re.finditer(r"\bpdMS_TO_TICKS\s*\(\s*(\d+)\s*\)", s):
                    if int(m.group(1)) * hz // 1000 == 0:
                        add(p, "RTOS-115", "warn", s.count("\n", 0, m.start()) + 1, "pdMS_TO_TICKS({}) is 0 ticks at "
                            "CONFIG_FREERTOS_HZ={} - no delay/timeout.".format(m.group(1), hz))
    # heap_1 never frees
    heap1 = [p for p in find_files(proj, names={"heap_1.c"})]
    if heap1:
        for p, s in srcs.items():
            m = re.search(r"\b(vTaskDelete|vQueueDelete|vSemaphoreDelete|vPortFree|xTimerDelete|vEventGroupDelete|osThreadTerminate)\s*\(", s)
            if m:
                add(p, "RTOS-100", "error", s.count("\n", 0, m.start()) + 1, "{}() with heap_1 (found {}) - heap_1 never frees "
                    "memory; use heap_4 or static allocation.".format(m.group(1), rel(heap1[0], proj)))
                break
    # STM32 HAL timebase must not be SysTick under FreeRTOS
    stm32 = cfg.get("family") == "stm32" or any(re.search(r"\bHAL_Init\s*\(", s) for s in srcs.values())
    if stm32 and not is_esp and not any(find_files(proj, names=None, exts=("hal_timebase_tim.c",))):
        if any(re.search(r"\bHAL_IncTick\s*\(", s) and re.search(r"\bSysTick_Handler\b", s) for s in srcs.values()):
            add(None, "RTOS-106", "warn", 1, "STM32 HAL timebase appears to be SysTick while FreeRTOS uses SysTick - select a TIMx "
                "timebase in CubeMX (SYS > Timebase Source) so HAL_Delay/timeouts work and the kernel tick is not disturbed.")
    return out, rc


# ------------------------------------------------------------------ CLI
def check_file(path, cfg, changed="git", rtos_cfg=None):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        findings = check_source(f.read(), cfg, rtos_cfg)
    if changed == "git":
        changed = git_changed_lines(path)
    return [x for x in findings if x.touches(changed)], [x for x in findings if not x.touches(changed)]


def project_sources(proj, cfg):
    return [p for p in find_files(proj, exts=(".c", ".cpp", ".cc")) if not is_protected(rel(p, proj), cfg)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*")
    ap.add_argument("--all-lines", action="store_true")
    ap.add_argument("--project", action="store_true", help="project-level rules + all sources")
    ap.add_argument("--info", action="store_true", help="include info-level findings")
    args = ap.parse_args()
    proj = os.getcwd()
    cfg, _ = load_config(proj)
    rc, _ = load_rtos_config(proj, cfg)
    files = args.files or (project_sources(proj, cfg) if args.project else [])
    rcode = 0
    for p in files:
        if not p.lower().endswith(C_EXTS):
            continue
        new, old = check_file(p, cfg, None if (args.all_lines or args.project) else "git", rc)
        for f in new:
            if f.sev == "info" and not args.info:
                continue
            print("{}:{}: {}: [{}] {}".format(rel(p, proj), f.line, f.sev, f.rule, f.msg))
            rcode |= f.sev == "error"
        if old:
            print("{}: {} pre-existing finding(s) on unchanged lines (--all-lines)".format(rel(p, proj), len(old)))
    if args.project:
        findings, _ = check_project(proj, cfg, project_sources(proj, cfg))
        for path, f in findings:
            if f.sev == "info" and not args.info:
                continue
            print("{}:{}: {}: [{}] {}".format(path, f.line, f.sev, f.rule, f.msg))
            rcode |= f.sev == "error"
    return 1 if rcode else 0


if __name__ == "__main__":
    sys.exit(main())
