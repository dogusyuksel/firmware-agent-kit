---
type: llm
weight: 1
---

A successful response identifies that the SAMV71 watchdog (WDT) is enabled after reset (~16 s timeout) as the most likely cause, and explains the fix: disable it early (write WDT_MR with WDDIS - noting WDT_MR is write-once) or configure it and kick it periodically (preferably from a health-checked context). Mentioning the reinforced/secondary watchdog (RSWDT) or checking the reset cause in RSTC is a plus. Fail if the watchdog is not named as the primary suspect.
