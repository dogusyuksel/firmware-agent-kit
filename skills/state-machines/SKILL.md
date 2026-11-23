---
name: state-machines
description: Design and implement event-driven firmware logic as finite state machines - switch-based and table-driven FSMs, hierarchical states, event queues, the active-object pattern (one task + one queue per component) on FreeRTOS, timeouts as events, ISR-to-FSM event posting, and documenting the machine as a Mermaid state diagram. Use when writing protocol handlers, device/connection lifecycles, UI or mode logic, or replacing flag-and-if spaghetti.
---

# State machines in firmware

## Pick the form
| Form | Use when |
|---|---|
| `switch (state)` with a nested `switch (event)` | < ~8 states, readable top-down; the default |
| Transition table `{state, event, guard, action, next}` | many states/events, transitions reviewed as data |
| Hierarchical (parent handles common events) | many states share handling (errors, power-down) |
Match what the project already uses before introducing a new form.

## Rules
- States and events are `enum`s with an explicit `_COUNT`; never encode state in several booleans.
- One function `fsm_dispatch(fsm, event)` is the only place state changes; entry/exit actions run there, once per transition.
- Every state handles every event explicitly or falls to one `default` that logs/ignores by design; unexpected events are counted, never silently dropped.
- Actions are short and non-blocking; long work becomes a new event when done.
- Timeouts are events: start a software timer or record a deadline on entry, post `EV_TIMEOUT` on expiry, cancel on exit.
- Keep the FSM free of hardware calls where possible (actions call driver APIs) so the logic stays portable.

## Event sources and concurrency
- **Active object:** one task owns the FSM and blocks on its queue; everyone else posts events. No locks needed around FSM state.
- ISRs post with the FromISR queue API (or a ring buffer + task notification) and never call `fsm_dispatch` directly.
- Event struct: `{ uint8_t id; uint8_t len; union payload }` sized for the largest payload; copy, do not pass pointers to ISR buffers.
- Queue full = design error: count it, size the queue from worst-case burst analysis.

## Skeleton (switch form)
```c
typedef enum { ST_IDLE, ST_CONNECTING, ST_ONLINE, ST_COUNT } state_t;
typedef enum { EV_START, EV_CONNECTED, EV_TIMEOUT, EV_ERROR, EV_COUNT } event_id_t;

static void enter(fsm_t *f, state_t s) { f->state = s; /* entry actions per state */ }

void fsm_dispatch(fsm_t *f, const event_t *e)
{
    switch (f->state)
    {
    case ST_IDLE:
        if (e->id == EV_START) { start_connect(); enter(f, ST_CONNECTING); }
        break;
    case ST_CONNECTING:
        if (e->id == EV_CONNECTED) { enter(f, ST_ONLINE); }
        else if (e->id == EV_TIMEOUT || e->id == EV_ERROR) { enter(f, ST_IDLE); }
        break;
    case ST_ONLINE:
        if (e->id == EV_ERROR) { enter(f, ST_IDLE); }
        break;
    default:
        f->bad_state++;
        enter(f, ST_IDLE);
        break;
    }
}
```

## Document it
Generate a Mermaid `stateDiagram-v2` from the code (see `mermaid-diagrams`) and keep it next to the module; update it in the same change as the transitions.

## Project customization
State naming, event struct layout, the queue/timer API and whether table or switch form is preferred belong in the project's conventions skill (`/fw-customize`).
