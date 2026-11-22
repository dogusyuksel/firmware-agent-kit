"""Tests for firmware-agent-kit hooks and tools.  Run:  python -m unittest discover -s tests -v

Hooks run as subprocesses with a JSON payload on stdin, exactly as Claude Code runs them.
Tests needing optional tools (arm-none-eabi-gcc, a PDF backend) skip when those are absent.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "hooks", "scripts")
TOOLS = os.path.join(ROOT, "tools")
DECODER = os.path.join(ROOT, "skills", "hardfault-debug", "scripts", "decode_fault.py")
MAPPER = os.path.join(ROOT, "skills", "memory-footprint", "scripts", "map_analyzer.py")
HAVE_GCC = shutil.which("arm-none-eabi-gcc") is not None
sys.path.insert(0, TOOLS)


def run_hook(script, payload, proj):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=proj, CLAUDE_PLUGIN_ROOT=ROOT)
    r = subprocess.run([sys.executable, os.path.join(HOOKS, script)], input=json.dumps(payload),
                       capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout) if r.stdout.strip() else None


def run_tool(script, args, cwd):
    return subprocess.run([sys.executable, os.path.join(TOOLS, script)] + args, capture_output=True, text=True,
                          cwd=cwd, timeout=120)


def decision(out):
    return out and out["hookSpecificOutput"]["permissionDecision"]


class Base(unittest.TestCase):
    def setUp(self):
        self.proj = tempfile.mkdtemp(prefix="fwkit-")

    def tearDown(self):
        shutil.rmtree(self.proj, ignore_errors=True)

    def write(self, rel, text):
        p = os.path.join(self.proj, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(textwrap.dedent(text))
        return p

    def bash(self, script, cmd):
        return run_hook(script, {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": self.proj}, self.proj)


# ------------------------------------------------------------------ guards
class GuardTargetOps(Base):
    def g(self, cmd):
        return decision(self.bash("guard_target_ops.py", cmd))

    def test_deny_irreversible(self):
        for cmd in ["STM32_Programmer_CLI -c port=SWD -ob RDP=0xCC", "espefuse.py --port COM3 burn_efuse JTAG_DISABLE",
                    "esptool.py burn_efuse FLASH_CRYPT_CNT", "picotool otp set 0x10 0x1", "idf.py efuse-burn --do-not-confirm"]:
            self.assertEqual(self.g(cmd), "deny", cmd)

    def test_ask_destructive(self):
        for cmd in ["st-flash erase", "nrfjprog -f nrf52 --recover", "openocd -c 'init; stm32f4x unlock 0; exit'",
                    "openocd -c 'init; stm32f1x mass_erase 0'", "STM32_Programmer_CLI -c port=SWD -ob RDP=0xAA",
                    "avrdude -c usbasp -p m328p -U lfuse:w:0xFF:m", "esptool.py --chip esp32 erase_flash",
                    "pyocd erase --chip -t stm32f407vg", "idf.py -p COM3 erase-flash",
                    "openocd -f target/atsamv.cfg -c 'init; atsamv gpnvm set 1; exit'", "bossac -p COM4 -e -w app.bin"]:
            self.assertEqual(self.g(cmd), "ask", cmd)

    def test_allow_normal(self):
        for cmd in ["openocd -f interface/stlink.cfg -f target/stm32f4x.cfg -c \"program build/app.elf verify reset exit\"",
                    "cmake --build build", "idf.py build", "idf.py -p COM3 flash monitor", "git status", "espefuse.py summary",
                    "openocd -f target/atsamv.cfg -c 'init; atsamv gpnvm show; exit'"]:
            self.assertIsNone(self.g(cmd), cmd)

    def test_esp_secure_boot_flash_asks(self):
        self.write("sdkconfig", "CONFIG_SECURE_BOOT=y\nCONFIG_SECURE_BOOT_V2_ENABLED=y\n")
        self.assertEqual(self.g("idf.py -p COM3 flash"), "ask")

    def test_project_patterns_and_confirm_flash(self):
        self.write(".claude/firmware.json", json.dumps({"guard": {"deny_patterns": [r"\bmy_lock_tool\b"], "confirm_flash": True}}))
        self.assertEqual(self.g("my_lock_tool --go"), "deny")
        self.assertEqual(self.g("pyocd flash -t nrf52840 app.hex"), "ask")

    def test_disabled(self):
        self.write(".claude/firmware.json", json.dumps({"guard": {"enabled": False}}))
        self.assertIsNone(self.g("st-flash erase"))


class GuardGit(Base):
    def g(self, cmd):
        return decision(self.bash("guard_git.py", cmd))

    def test_blocks_attribution(self):
        self.assertEqual(self.g('git commit -m "fix uart\n\nCo-Authored-By: Claude <noreply@anthropic.com>"'), "deny")
        self.assertEqual(self.g('gh pr create --title x --body "Generated with [Claude Code](https://claude.com/claude-code)"'), "deny")
        self.write("msg.txt", "fix\n\nCo-Authored-By: Claude Opus <noreply@anthropic.com>\n")
        self.assertEqual(self.g("git commit -F msg.txt"), "deny")

    def test_allows_clean(self):
        self.assertIsNone(self.g('git commit -m "uart: add DMA RX timeout"'))
        self.assertIsNone(self.g("git push origin main"))

    def test_can_disable(self):
        self.write(".claude/firmware.json", json.dumps({"git": {"block_ai_attribution": False}}))
        self.assertIsNone(self.g('git commit -m "x\n\nCo-Authored-By: Claude <noreply@anthropic.com>"'))


class GuardEdits(Base):
    CUBE = """\
        #include "main.h"
        /* USER CODE BEGIN Includes */
        #include "app.h"
        /* USER CODE END Includes */
        int main(void)
        {
          /* USER CODE BEGIN 1 */
          app_init();
          /* USER CODE END 1 */
          HAL_Init();
        }
        """

    def edit(self, path, old):
        return run_hook("guard_edits.py", {"tool_name": "Edit", "tool_input": {"file_path": path, "old_string": old,
                                                                               "new_string": "x"}}, self.proj)

    def test_user_code(self):
        p = self.write("Core/Src/main.c", self.CUBE)
        self.assertIsNone(self.edit(p, "app_init();"))
        self.assertEqual(decision(self.edit(p, "HAL_Init();")), "ask")

    def test_vendor_paths(self):
        for rel in ("Drivers/STM32F4xx_HAL_Driver/Src/x.c", "managed_components/espressif__led/x.c", "config/default/peripheral/usart/x.c"):
            p = self.write(rel, "int x;\n")
            self.assertEqual(decision(self.edit(p, "int x;")), "ask", rel)
        self.assertIsNone(self.edit(self.write("src/app.c", "int x;\n"), "int x;"))


# ------------------------------------------------------------------ lint hook
class CLintHook(Base):
    def lint(self, path, name="Write", **ti):
        ti["file_path"] = path
        return run_hook("c_lint.py", {"tool_name": name, "tool_input": ti}, self.proj)

    def test_bare_metal_findings(self):
        p = self.write("src/bad.c", """\
            #include <stdint.h>
            #include <stdlib.h>
            static uint32_t rx_count;
            static volatile uint32_t ok_flag;
            void USART1_IRQHandler(void)
            {
                rx_count++;
                ok_flag = 1;
                printf("irq\\n");
            }
            void f(void)
            {
                uint8_t big[1024];
                char *p = malloc(10);
                *(uint32_t *)0x40021000 = 1;
                while (!(USART1->SR & USART_SR_TXE));
                if (HAL_GetTick() > 1000) { }
                (void)big; (void)p;
            }
            """)
        out = self.lint(p)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(out.get("decision"), "block")
        for needle in ["[EMB-011] printf()", "[EMB-003] malloc()", "[EMB-004]", "'rx_count' is modified", "[EMB-005]",
                       "[EMB-006]", "1024-byte local array"]:
            self.assertIn(needle, ctx)
        self.assertNotIn("'ok_flag'", ctx)

    def test_clean_file_silent(self):
        p = self.write("src/good.c", """\
            #include <stdint.h>
            static volatile uint32_t g_events;
            /* printf in a comment, malloc( too */
            void TIM2_IRQHandler(void) { TIM2->SR = ~TIM_SR_UIF; g_events |= 1u; }
            uint32_t elapsed(uint32_t start) { return (uint32_t)(HAL_GetTick() - start); }
            const char *s = "malloc(";
            """)
        self.assertIsNone(self.lint(p))

    def test_preexisting_not_blocking(self):
        p = self.write("src/old.c", """\
            #include <stdlib.h>
            void legacy(void) { char *p = malloc(4); (void)p; }
            int added(int a) { return a + 1; }
            """)
        out = self.lint(p, name="Edit", old_string="return a;", new_string="int added(int a) { return a + 1; }")
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertNotEqual(out.get("decision"), "block")
        self.assertIn("pre-existing", ctx)
        self.assertIn("Noticed (not changed)", ctx)

    def test_non_c_ignored(self):
        self.assertIsNone(self.lint(self.write("README.md", "malloc(\n")))


# ------------------------------------------------------------------ RTOS rules
RTOS_BAD = """\
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"
#include "timers.h"
static SemaphoreHandle_t g_mtx;
static SemaphoreHandle_t g_bin;
static SemaphoreHandle_t g_rec;
static QueueHandle_t g_q;
static TimerHandle_t g_tmr;
static uint32_t g_count;

static void helper(void) { xQueueSend(g_q, &g_q, 0); }

void USART1_IRQHandler(void)
{
    BaseType_t woken;
    uint8_t b = 1;
    xQueueSendFromISR(g_q, &b, &woken);
    xSemaphoreGiveFromISR(g_mtx, &woken);
    helper();
}

static void tmr_cb(TimerHandle_t t) { vTaskDelay(10); xTimerStart(g_tmr, 100); }

static int do_io(void)
{
    xSemaphoreTake(g_mtx, portMAX_DELAY);
    if (err()) return -1;
    xSemaphoreGive(g_mtx);
    taskENTER_CRITICAL();
    vTaskDelay(pdMS_TO_TICKS(5));
    taskEXIT_CRITICAL();
    if (xSemaphoreTake(g_bin, 10) == pdTRUE) { work(); xSemaphoreGive(g_bin); }
    xSemaphoreTake(g_rec, 10);
    return 0;
}

void counter_add(uint32_t n) { g_count += n; }

static void worker(void *p) { for (;;) { compute(); } }
static void once(void *p) { compute(); }

int main(void)
{
    StaticTask_t tcb;
    int local = 5;
    g_mtx = xSemaphoreCreateMutex();
    g_bin = xSemaphoreCreateBinary();
    g_rec = xSemaphoreCreateRecursiveMutex();
    g_q = xQueueCreate(4, 1);
    g_tmr = xTimerCreate("t", 0, pdTRUE, NULL, tmr_cb);
    vTaskDelay(100);
    xTaskCreate(worker, "w", 32, &local, 2, NULL);
    xTaskCreate(once, "o", 256, NULL, 1, NULL);
    xEventGroupSetBits(eg, 0x01000000);
    xQueueSend(g_q, 5, 0);
    xQueueOverwrite(g_q, &local);
    vTaskStartScheduler();
}
"""

RTOS_GOOD = """\
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"
static SemaphoreHandle_t s_lock;
static QueueHandle_t s_rx;
static uint32_t s_total;

void USART2_IRQHandler(void)
{
    BaseType_t woken = pdFALSE;
    uint8_t b = 0x55;
    if (xQueueSendFromISR(s_rx, &b, &woken) != pdPASS) { overrun(); }
    portYIELD_FROM_ISR(woken);
}

int total_add(uint32_t n)
{
    if (xSemaphoreTake(s_lock, pdMS_TO_TICKS(10)) != pdTRUE) { return -1; }
    s_total += n;
    xSemaphoreGive(s_lock);
    return 0;
}

static void rx_task(void *arg)
{
    uint8_t b;
    (void)arg;
    for (;;)
    {
        if (xQueueReceive(s_rx, &b, portMAX_DELAY) == pdPASS) { handle(b); }
    }
}

int main(void)
{
    static StaticTask_t tcb;
    s_lock = xSemaphoreCreateMutex();
    s_rx = xQueueCreate(16, sizeof(uint8_t));
    configASSERT(s_lock != NULL && s_rx != NULL);
    if (xTaskCreate(rx_task, "rx", 256, NULL, 3, NULL) != pdPASS) { for (;;) {} }
    vTaskStartScheduler();
    for (;;) {}
}
"""


class RtosRules(Base):
    def rules(self, src, cfg=None):
        import rtos_check
        from fwlib import DEFAULT_CONFIG
        return rtos_check.check_source(src, cfg or DEFAULT_CONFIG, {"configMAX_PRIORITIES": 5})

    def test_bad_code_hits_expected_rules(self):
        found = {f.rule for f in self.rules(RTOS_BAD)}
        expected = {"RTOS-001", "RTOS-008", "RTOS-009", "RTOS-011", "RTOS-014", "RTOS-016", "RTOS-017", "RTOS-022",
                    "RTOS-024", "RTOS-027", "RTOS-029", "RTOS-030", "RTOS-037", "RTOS-040", "RTOS-041", "RTOS-043",
                    "RTOS-046", "RTOS-062", "RTOS-070", "RTOS-071", "RTOS-102", "RTOS-103", "RTOS-113", "RTOS-117",
                    "RTOS-118", "RTOS-120"}
        self.assertEqual(expected - found, set(), "missing rules")

    def test_good_code_has_no_findings(self):
        bad = [str(f) for f in self.rules(RTOS_GOOD) if f.sev != "info"]
        self.assertEqual(bad, [])

    def test_esp_rules(self):
        src = """\
            #include "freertos/FreeRTOS.h"
            #include "esp_log.h"
            static portMUX_TYPE s_mux;
            static void IRAM_ATTR gpio_isr(void *arg) { portENTER_CRITICAL(&s_mux); ESP_LOGI("x", "y"); portEXIT_CRITICAL(&s_mux); }
            void app_main(void)
            {
                gpio_isr_handler_add(4, gpio_isr, NULL);
                xTaskCreate(task_a, "a", 512, NULL, 5, NULL);
                vTaskStartScheduler();
            }
            """
        import rtos_check
        import fw_lint
        from fwlib import DEFAULT_CONFIG
        found = {f.rule for f in rtos_check.check_source(textwrap.dedent(src), DEFAULT_CONFIG)}
        self.assertTrue({"RTOS-045", "RTOS-110", "RTOS-009", "RTOS-125"} <= found, found)
        emb = {f.rule for f in fw_lint.lint_source(textwrap.dedent(src), DEFAULT_CONFIG)}
        self.assertIn("EMB-011", emb)   # ESP_LOGI in ISR

    def test_cmsis_rules(self):
        src = """\
            #include "cmsis_os2.h"
            osMessageQueueId_t q;
            void TIM3_IRQHandler(void) { uint8_t b = 1; osMessageQueuePut(q, &b, 0, osWaitForever); osDelay(1); }
            int main(void)
            {
                q = osMessageQueueNew(8, 1, NULL);
                osKernelInitialize();
                osMutexNew(NULL);
                osKernelStart();
            }
            """
        import rtos_check
        from fwlib import DEFAULT_CONFIG
        found = {f.rule for f in rtos_check.check_source(textwrap.dedent(src), DEFAULT_CONFIG)}
        self.assertTrue({"RTOS-108", "RTOS-015", "RTOS-109", "RTOS-123"} <= found, found)

    def test_project_rules(self):
        self.write("Core/Inc/FreeRTOSConfig.h", """\
            #define configPRIO_BITS 4
            #define configMAX_PRIORITIES 7
            #define configTICK_RATE_HZ 100
            #define configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY 5
            #define configMAX_SYSCALL_INTERRUPT_PRIORITY (configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY << (8 - configPRIO_BITS))
            #define configKERNEL_INTERRUPT_PRIORITY (15 << 4)
            #define configCHECK_FOR_STACK_OVERFLOW 0
            """)
        self.write("Core/Src/main.c", """\
            #include "FreeRTOS.h"
            void USART1_IRQHandler(void) { BaseType_t w = pdFALSE; xSemaphoreGiveFromISR(s, &w); portYIELD_FROM_ISR(w); }
            void SPI1_IRQHandler(void) { BaseType_t w = pdFALSE; vTaskNotifyGiveFromISR(t, &w); portYIELD_FROM_ISR(w); }
            int main(void)
            {
                HAL_NVIC_SetPriorityGrouping(NVIC_PRIORITYGROUP_2);
                HAL_NVIC_SetPriority(USART1_IRQn, 2, 0);
                HAL_NVIC_EnableIRQ(USART1_IRQn);
                xTaskCreate(t1, "t", 128, NULL, 1, NULL);
                vTaskDelay(pdMS_TO_TICKS(5));
                vTaskStartScheduler();
            }
            """)
        self.write("Middlewares/FreeRTOS/portable/MemMang/heap_1.c", "/* heap */\n")
        self.write("Core/Src/other.c", "void stop(void) { vTaskDelete(h); }\n")
        r = run_tool("rtos_check.py", ["--project"], self.proj)
        for rule in ("RTOS-018", "RTOS-019", "RTOS-020", "RTOS-057", "RTOS-104", "RTOS-100", "RTOS-115"):
            self.assertIn(rule, r.stdout, rule)


# ------------------------------------------------------------------ session context / handoff
class SessionContext(Base):
    def test_silent_for_non_firmware(self):
        self.write("index.js", "console.log(1)\n")
        self.assertIsNone(run_hook("session_context.py", {"hook_event_name": "SessionStart"}, self.proj))

    def test_reports_firmware_rules_and_notes(self):
        self.write("STM32G474RETX_FLASH.ld", "MEMORY {}\n")
        self.write("Core/Inc/FreeRTOSConfig.h", "#define configUSE_PREEMPTION 1\n")
        self.write(".claude/firmware.json", json.dumps({"mcu": "STM32G474RE", "build": "make -j"}))
        self.write(".claude/fw-notes.md", "# Firmware handoff notes\n- In progress: UART DMA timeout\n")
        ctx = run_hook("session_context.py", {"hook_event_name": "SessionStart"}, self.proj)["hookSpecificOutput"]["additionalContext"]
        for needle in ("STM32G474RE", "make -j", "rtos=freertos", "Working rules", "thread-safe", "UART DMA timeout"):
            self.assertIn(needle, ctx)

    def test_esp_family_detected(self):
        self.write("sdkconfig", "CONFIG_IDF_TARGET=\"esp32s3\"\n")
        ctx = run_hook("session_context.py", {"hook_event_name": "SessionStart"}, self.proj)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("family=esp32", ctx)


# ------------------------------------------------------------------ tools
class Tools(Base):
    def test_decoder(self):
        out = subprocess.run([sys.executable, DECODER, "--cfsr", "0x00009200", "--bfar", "0x10", "--hfsr", "0x40000000",
                              "--exc-return", "0xFFFFFFFD"], capture_output=True, text=True).stdout
        for needle in ("STKERR", "PRECISERR", "NULL pointer", "FORCED", "PSP", "Thread"):
            self.assertIn(needle, out)

    def test_build_info(self):
        os.makedirs(os.path.join(self.proj, "build"))
        db = [{"directory": os.path.join(self.proj, "build"), "file": "../src/%s.c" % n,
               "command": ("arm-none-eabi-gcc -mcpu=cortex-m7 -mthumb -mfpu=fpv5-d16 -mfloat-abi=hard -DSAMV71Q21B -DNDEBUG "
                           "-I../inc -I../freertos/include -Os -std=gnu11 -Wall -ffunction-sections -c ../src/%s.c" % n)}
              for n in ("main", "uart")]
        with open(os.path.join(self.proj, "build", "compile_commands.json"), "w") as f:
            json.dump(db, f)
        r = run_tool("build_info.py", [], self.proj)
        for needle in ("2 TUs", "-mcpu=cortex-m7", "SAMV71Q21B", "inc", "-Os"):
            self.assertIn(needle, r.stdout)
        r = run_tool("build_info.py", ["--file", "src/uart.c"], self.proj)
        self.assertIn("fpv5-d16", r.stdout)

    def test_fw_analyze_lint_and_sarif(self):
        self.write("src/a.c", RTOS_BAD)
        r = run_tool("fw_analyze.py", ["--all", "--tools", "lint", "--sarif", "out.sarif"], self.proj)
        self.assertIn("RTOS-014", r.stdout)
        with open(os.path.join(self.proj, "out.sarif")) as f:
            sarif = json.load(f)
        self.assertEqual(sarif["version"], "2.1.0")
        self.assertTrue(sarif["runs"][0]["results"])

    def test_style_probe(self):
        self.write("src/uart_drv.c", """\
            #include "uart_drv.h"
            static int s_ready;
            int uart_drv_init(void)
            {
                s_ready = 1;
                return 0;
            }
            int uart_drv_send(const uint8_t *buf, size_t len)
            {
                if (!s_ready)
                {
                    return -1;
                }
                return 0;
            }
            """)
        r = run_tool("style_probe.py", [], self.proj)
        self.assertIn("lower_snake", r.stdout)
        self.assertIn("uart_", r.stdout)
        self.assertIn("4 spaces", r.stdout)

    def test_doctor_json(self):
        r = run_tool("fw_doctor.py", ["--json", "--for", "analysis"], self.proj)
        rows = json.loads(r.stdout)
        self.assertTrue(any(x["tool"] == "cppcheck" for x in rows))
        self.assertTrue(all(x["license"] for x in rows))

    def test_pdf_search(self):
        sys.path.insert(0, TOOLS)
        import pdf_search
        pdf = os.path.join(self.proj, "doc.pdf")
        make_pdf(pdf, ["Overview of the device", "USART_BRR register: baud rate divider", "BOOT0 pin selects boot"])
        pages, backend = pdf_search.load_pages(pdf)
        if pages is None:
            self.skipTest("no PDF text backend installed")
        r = run_tool("pdf_search.py", [pdf, "USART_BRR", "--regex", "BOOT\\d"], self.proj)
        self.assertIn("pages: 2", r.stdout)
        self.assertIn("pages: 3", r.stdout)


def make_pdf(path, page_texts):
    """Minimal valid multi-page PDF with Helvetica text (no dependencies)."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for t in page_texts:
        stream = "BT /F1 12 Tf 72 720 Td ({}) Tj ET".format(t)
        objs.append("<< /Length {} >>\nstream\n{}\nendstream".format(len(stream), stream))
        objs.append("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> "
                    "/Contents {} 0 R >>".format(len(objs)))
        kids.append("{} 0 R".format(len(objs)))
    objs[1] = "<< /Type /Pages /Kids [{}] /Count {} >>".format(" ".join(kids), len(kids))
    out, offs = "%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out.encode("latin-1")))
        out += "{} 0 obj\n{}\nendobj\n".format(i, o)
    xref = len(out.encode("latin-1"))
    out += "xref\n0 {}\n0000000000 65535 f \n".format(len(objs) + 1) + "".join("{:010d} 00000 n \n".format(x) for x in offs)
    out += "trailer\n<< /Size {} /Root 1 0 R >>\nstartxref\n{}\n%%EOF\n".format(len(objs) + 1, xref)
    with open(path, "wb") as f:
        f.write(out.encode("latin-1"))


# ------------------------------------------------------------------ toolchain-based
@unittest.skipUnless(HAVE_GCC, "arm-none-eabi-gcc not installed")
class WithToolchain(Base):
    def build(self, extra_array=16):
        src = self.write("main.c", """\
            #include <stdint.h>
            #define N %d
            volatile uint8_t big_buffer[N];
            const uint32_t table[64] = {1, 2, 3};
            volatile uint32_t counter = 5;
            void Reset_Handler(void) { for (;;) { big_buffer[counter %% N] = (uint8_t)table[counter & 63]; counter++; } }
            __attribute__((section(".isr_vector"), used)) void (*const vectors[])(void) = { (void (*)(void))0x20001000, Reset_Handler };
            """ % extra_array)
        ld = self.write("app.ld", """\
            MEMORY { FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 64K
                     RAM (rwx)  : ORIGIN = 0x20000000, LENGTH = 16K }
            ENTRY(Reset_Handler)
            SECTIONS {
              .isr_vector : { KEEP(*(.isr_vector)) } > FLASH
              .text : { *(.text*) *(.rodata*) } > FLASH
              .data : { *(.data*) } > RAM AT> FLASH
              .bss (NOLOAD) : { *(.bss*) *(COMMON) } > RAM
            }
            """)
        os.makedirs(os.path.join(self.proj, "build"), exist_ok=True)
        elf = os.path.join(self.proj, "build", "app.elf")
        obj = os.path.join(self.proj, "build", "main.o")
        flags = ["-mcpu=cortex-m4", "-mthumb", "-Os", "-ffunction-sections", "-fdata-sections"]
        r = subprocess.run(["arm-none-eabi-gcc"] + flags + ["-c", src, "-o", obj], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = subprocess.run(["arm-none-eabi-gcc"] + flags + ["-nostartfiles", "--specs=nano.specs", "-T", ld, obj, "-o", elf,
                            "-Wl,--gc-sections", "-Wl,-Map=" + os.path.join(self.proj, "build", "app.map")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return elf

    def size_hook(self):
        return run_hook("size_tracker.py", {"tool_name": "Bash", "tool_input": {"command": "make -C build"}}, self.proj)

    def test_size_tracker_baseline_and_delta(self):
        self.build(16)
        ctx = self.size_hook()["hookSpecificOutput"]["additionalContext"]
        self.assertIn("of 64 KB", ctx)
        self.assertIsNone(self.size_hook())
        time.sleep(1.1)
        self.build(4096)
        self.assertRegex(self.size_hook()["hookSpecificOutput"]["additionalContext"], r"RAM \d+ B \(\+40[0-9]{2} B\)")

    def test_size_budget_blocks(self):
        self.write(".claude/firmware.json", json.dumps({"memory": {"flash_kb": 64, "ram_kb": 4}}))
        self.build(4000)
        self.assertEqual(self.size_hook().get("decision"), "block")

    def test_map_analyzer_and_diff(self):
        self.build(16)
        old = os.path.join(self.proj, "old.map")
        shutil.copy(os.path.join(self.proj, "build", "app.map"), old)
        self.build(1016)
        new = os.path.join(self.proj, "build", "app.map")
        out = subprocess.run([sys.executable, MAPPER, new, "--top", "10"], capture_output=True, text=True).stdout
        self.assertIn("big_buffer", out)
        out = subprocess.run([sys.executable, MAPPER, old, new], capture_output=True, text=True).stdout
        self.assertRegex(out, r"\+0\s+\+1000\s+big_buffer")


if __name__ == "__main__":
    unittest.main()
