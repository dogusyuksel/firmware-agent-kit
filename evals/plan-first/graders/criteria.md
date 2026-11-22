---
type: llm
weight: 1
---

A successful response presents a short implementation plan before writing code. The plan should cover:
- which files and functions are affected;
- the steps;
- the risks;
- how the change will be verified.

It must also address at least two of these H7/RTOS concerns:
- the DMA buffer must not be in DTCM, or must be placed in DMA-reachable RAM;
- D-cache coherency: invalidate after DMA, use a non-cacheable MPU region, or align buffers to 32 bytes;
- IRQ priority versus configMAX_SYSCALL_INTERRUPT_PRIORITY for an ISR that calls stream-buffer FromISR APIs;
- the stream buffer allows a single writer and a single reader, and is written via xStreamBufferSendFromISR.

The response should end by asking for approval or the missing project details. It should not dump a full implementation as if the plan were already approved.

Fail if it goes straight to a full implementation with no plan, or ignores DMA placement and cache coherency entirely.
