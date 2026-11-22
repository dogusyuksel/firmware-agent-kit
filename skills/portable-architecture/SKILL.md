---
name: portable-architecture
description: Hardware-independent, testable firmware architecture across STM32, ESP32 and SAMV71 - layering (app / services / drivers / BSP / HAL port), interfaces in C, OSAL over FreeRTOS/CMSIS-RTOS2, dependency injection, thread-safe public APIs, ISR-safe contracts, error handling and module conventions. Use when designing new modules, porting code between MCUs, or making code unit-testable.
---

# Portable firmware architecture

## Layers (dependencies point downwards only)
```
app/          business logic, state machines         -> services, osal
services/     protocols, storage, logging, sensors    -> drivers (interfaces), osal
drivers/      device drivers (external chips)         -> hal interfaces (spi_bus_t, i2c_bus_t, gpio_pin_t)
hal/          interfaces only (*.h)                   -> nothing
port/<mcu>/   HAL implementations: stm32/, esp32/, samv71/ (registers, vendor HAL/ESP-IDF/ASF4)
osal/         osal.h + osal_freertos.c / osal_cmsis_rtos2.c / osal_host.c (tests)
bsp/<board>/  pin map, clock config, which port instance backs which interface
```
Only `port/` and `bsp/` include vendor headers. Everything above compiles on the host -> unit tests with Ceedling (see `host-unit-test`).

## Interfaces in C
```c
/* hal/spi_bus.h */
typedef struct spi_bus spi_bus_t;               /* opaque */
typedef struct {
    int (*transfer)(spi_bus_t *bus, const uint8_t *tx, uint8_t *rx, size_t len, uint32_t timeout_ms);
    int (*lock)(spi_bus_t *bus, uint32_t timeout_ms);
    void (*unlock)(spi_bus_t *bus);
} spi_bus_ops_t;
struct spi_bus { const spi_bus_ops_t *ops; void *ctx; };

/* drivers/bme280.c depends only on spi_bus_t */
int bme280_init(bme280_t *dev, spi_bus_t *bus, gpio_pin_t cs);
```
- Inject dependencies through init functions (no hidden globals). Tests pass fakes/mocks.
- Use link-time substitution (one implementation per build) when runtime polymorphism is not needed - zero overhead.
- Keep interfaces small and stable; put MCU-specific options in a `void *port_cfg` or BSP tables.

## OSAL
Wrap the RTOS so logic is portable and mockable:
```c
typedef struct osal_mutex *osal_mutex_t;
int  osal_mutex_create(osal_mutex_t *m);                 /* static-allocation variant for safety builds */
int  osal_mutex_lock(osal_mutex_t m, uint32_t timeout_ms);
void osal_mutex_unlock(osal_mutex_t m);
int  osal_queue_send(osal_queue_t q, const void *item, uint32_t timeout_ms);
int  osal_queue_send_from_isr(osal_queue_t q, const void *item, bool *woken);
uint32_t osal_ms(void);
```
Implementations: FreeRTOS native (STM32/SAMV71), ESP-IDF FreeRTOS (stack bytes, pinned tasks), CMSIS-RTOS2 (Cube), host (pthreads or single-threaded fakes for tests). ISR variants are separate functions - never "detect ISR context" at runtime in portable code.

## Public API rules (every module)
1. **Thread-safe**: public (non-static) functions may be called from any task. Protect shared state with a mutex (blocking OK), a short critical section (tiny updates), or route all access through one owner task via a queue. State the choice in the header.
2. **ISR contract** in the header: `/* ISR-safe: no */` by default; ISR-callable functions are named `..._from_isr` and never block.
3. Return a status (`int` 0/negative errno-style, or a module `_status_t` enum - follow the project's existing convention). Validate arguments at the boundary.
4. No dynamic allocation after init; caller provides storage (`bme280_t dev;`) or static pools.
5. Timeouts in ms at the API boundary; convert to ticks inside the OSAL.
6. Units in names (`_ms`, `_hz`, `_mv`), fixed-width types, `const` correctness.
7. Re-entrancy: no static locals or shared scratch buffers in public functions unless protected.

## Matching an existing codebase
When the project already exists, its conventions win over this skill: run `python <kit>/tools/style_probe.py` and mirror the naming, error type, comment style and file layout of neighbouring modules. Only introduce layers/OSAL when the user asks for a refactor.

## Porting checklist (e.g. STM32 -> SAMV71 or ESP32)
- New `port/<mcu>/` implementing the same `hal/` interfaces; BSP pin/clock tables.
- Differences that leak: DMA/cache coherency (M7, ESP32 PSRAM), interrupt priority model (NVIC vs ESP interrupt allocator), stack units (ESP bytes), critical sections (ESP spinlocks), endianness (all little-endian here), alignment.
- Run the same host unit tests; add a Renode/QEMU smoke test per port where possible.
