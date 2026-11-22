---
max_turns: 8
allowed_tools: [Read, Glob, Grep, Skill]
---

ESP-IDF v5 on an ESP32-S3. I need a GPIO interrupt on GPIO4 (falling edge) that increments a shared counter, and a task that prints the counter every second. The ISR is registered with `ESP_INTR_FLAG_IRAM`. Write the code (ISR, the shared counter handling, task creation in app_main) and point out ESP-IDF specific pitfalls I must respect.
