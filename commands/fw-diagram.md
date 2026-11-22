---
description: Generate a Mermaid diagram (sequence, state machine, flowchart, task map, hardware block diagram) from firmware code or a schematic
argument-hint: "<what to draw, e.g. 'UART RX path ISR->task' | 'state machine in modem.c' | 'task map' | 'schematic blocks'>"
---

Draw: $ARGUMENTS

1. Follow the `mermaid-diagrams` skill. Choose the diagram type from the question.
2. Gather facts cheaply. Grep for the real function, state, task and queue names, and read only the relevant ranges. For a task map, collect `xTaskCreate*`/`osThreadNew` calls with their priority and stack. For schematics, use the `hardware-docs` skill and `pdf_search.py`.
3. Output one fenced ```mermaid block of at most ~25 nodes, using exact code identifiers. Add a short legend for anything inferred.
4. Save to `docs/diagrams/<topic>.md` only if the user asks.
