---
name: mermaid-diagrams
description: Generate Mermaid diagrams from firmware code and hardware documents - task/ISR interaction sequences, state machines, init and control flowcharts, module dependency graphs, boot sequences, hardware block diagrams and power trees. Use when asked for a flow, diagram, architecture overview or documentation of how code works.
---

# Mermaid diagrams for firmware

## Rules
- Derive diagrams from the code (Grep the real function/state names), never from assumptions; note anything inferred.
- One diagram = one question (e.g. "how does a UART byte reach the parser?"). Keep it under ~25 nodes; split otherwise.
- Use exact identifiers from code in labels; quote labels containing `()`, `[]`, `:` or `/`: `A["HAL_UART_RxCpltCallback()"]`.
- Output a fenced ```mermaid block in the reply. Save to a file (`docs/diagrams/<topic>.md`) only when the user asks.
- Optional render check (free): `npx -y @mermaid-js/mermaid-cli -i x.mmd -o x.svg` (or `mmdc` if installed).

## Pick the diagram type
| Question | Type |
|---|---|
| Who talks to whom over time (ISR -> queue -> task -> driver) | `sequenceDiagram` |
| Protocol / mode / connection logic | `stateDiagram-v2` |
| Init sequence, algorithm, error handling | `flowchart TD` |
| Module/layer dependencies, task map | `flowchart LR` with subgraphs |
| MCU and external parts from a schematic | `flowchart LR` (blocks + buses as edge labels) |

## Templates
```mermaid
sequenceDiagram
    participant ISR as USART2_IRQHandler
    participant Q as rx_stream (stream buffer)
    participant T as comm_task
    participant P as frame_parser
    ISR->>Q: xStreamBufferSendFromISR(byte)
    ISR-->>T: portYIELD_FROM_ISR(woken)
    T->>Q: xStreamBufferReceive(portMAX_DELAY)
    T->>P: parser_feed(buf, n)
    P-->>T: FRAME_OK / FRAME_ERR
```
```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> CONNECTING: link_up
    CONNECTING --> READY: handshake_ok
    CONNECTING --> IDLE: timeout_ms > 2000
    READY --> IDLE: link_down
```
```mermaid
flowchart TD
    A[Reset_Handler] --> B[SystemInit: FPU, clocks]
    B --> C[copy .data, zero .bss]
    C --> D[main]
    D --> E{HAL_Init ok?}
    E -- no --> F[Error_Handler]
    E -- yes --> G[create tasks] --> H[vTaskStartScheduler]
```
For tasks, annotate priority and stack (`comm_task<br/>prio 3, 2 KB`) taken from the `xTaskCreate` calls.
