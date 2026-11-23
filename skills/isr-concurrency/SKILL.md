---
name: isr-concurrency
description: Interrupt and concurrency design for bare-metal firmware - ISR structure, NVIC priorities and grouping, BASEPRI/PRIMASK, deferring work from ISRs, lock-free ring buffers, ISR/main data races, DMA double buffering and reentrancy. Use when adding or changing interrupt handlers, chasing intermittent bugs, lost data, or "works in debug, fails in release".
---

# Interrupts and concurrency on bare metal

## Architecture pattern: superloop + events
```c
static volatile uint32_t g_events;            /* one bit per event source */

void TIM2_IRQHandler(void) {
    if (TIM2->SR & TIM_SR_UIF) {
        TIM2->SR = ~TIM_SR_UIF;               /* clear first (rc_w0) */
        g_events |= EVT_TICK;                 /* single-word RMW: safe ONLY if no higher-prio ISR writes g_events */
    }
}

int main(void) {
    init();
    for (;;) {
        uint32_t ev;
        __disable_irq(); ev = g_events; g_events = 0; __enable_irq();   /* atomic fetch-and-clear */
        if (ev & EVT_TICK)  on_tick();
        if (ev & EVT_UART)  on_uart();
        if (!ev) __WFI();                     /* sleep until next interrupt */
    }
}
```
If several ISRs at *different* priorities set bits in the same word, each `|=` needs protection (or use per-source `volatile bool` flags, or `LDREX/STREX` / C11 `atomic_fetch_or` on M3+).
The race-free sleep idiom: disable IRQs, check for work, `__WFI()` with IRQs disabled (pending IRQ still wakes the core), then re-enable.

## ISR rules
1. Identify and clear the source; check the flag *and* its enable bit if several sources share a vector.
2. Move data (to a ring buffer / DMA descriptor), set a flag, return. Target: microseconds.
3. No blocking, no printf, no malloc, no long loops, avoid floating point.
4. Clearing a flag as the last instruction can cause re-entry due to write buffering: clear early, or add `__DSB()` before return.
5. Never call non-reentrant functions (strtok, shared static buffers, most of libc with global state) from both ISR and main.
6. A peripheral error flag that is never cleared (UART ORE!) will make the IRQ fire forever and starve the main loop.

## NVIC priorities (Cortex-M)
- Lower number = higher urgency. Only the top `__NVIC_PRIO_BITS` bits are implemented (4 on STM32 -> 0..15). Use `NVIC_SetPriority(IRQn, prio)` which handles shifting.
- Choose a priority grouping once (`NVIC_SetPriorityGrouping`) - mixing HAL and CMSIS defaults is a common bug.
- Assign deliberately and document in one table (e.g. `irq_prio.h`): fast/hard-real-time (motor PWM, comms with tiny FIFOs) highest; housekeeping lowest. SysTick and PendSV positions matter if an RTOS is used.
- `BASEPRI` masks only interrupts at or below a level: `__set_BASEPRI(prio << (8 - __NVIC_PRIO_BITS));` - keeps critical high-priority ISRs alive during critical sections. Not available on Cortex-M0/M0+ (use PRIMASK there).
- Same-priority ISRs do not preempt each other; nested preemption requires a strictly higher priority.

## Lock-free SPSC ring buffer (ISR producer, main consumer or vice versa)
```c
#define RB_SIZE 256u                     /* power of two */
typedef struct {
    uint8_t buf[RB_SIZE];
    volatile uint32_t head;              /* written only by producer */
    volatile uint32_t tail;              /* written only by consumer */
} ringbuf_t;

static inline bool rb_put(ringbuf_t *rb, uint8_t b) {      /* producer */
    uint32_t h = rb->head;
    if ((uint32_t)(h - rb->tail) >= RB_SIZE) return false;  /* full: count overflows! */
    rb->buf[h & (RB_SIZE - 1u)] = b;
    __DMB();                                                /* data before index */
    rb->head = h + 1u;
    return true;
}

static inline bool rb_get(ringbuf_t *rb, uint8_t *b) {      /* consumer */
    uint32_t t = rb->tail;
    if (t == rb->head) return false;
    *b = rb->buf[t & (RB_SIZE - 1u)];
    __DMB();
    rb->tail = t + 1u;
    return true;
}
```
Free-running 32-bit indices + mask: no "one slot wasted", correct across wraparound. Only valid for exactly one producer and one consumer context.

## Race checklist (use when reviewing)
- [ ] Every variable touched by an ISR and other code: `volatile`?
- [ ] Multi-word or RMW access to it from the lower-priority side: inside a critical section?
- [ ] 64-bit timestamps/counters read from main: read-retry loop (`do { hi = H; lo = L; } while (hi != H);`) or critical section.
- [ ] Struct/state machine updated by main and read by ISR: could the ISR observe a half-updated state?
- [ ] Flags cleared by main *after* processing (lost-event window) instead of fetch-and-clear *before*?
- [ ] DMA buffer being written by CPU while DMA reads it? Use double buffering (half/complete callbacks) and cache maintenance on M7.
- [ ] Peripheral registers configured from both ISR and main (RMW on shared CR registers)?
- [ ] Release build (`-O2/-Os`) behaviour differs from `-O0`? -> almost always a missing `volatile` or barrier, or UB.
