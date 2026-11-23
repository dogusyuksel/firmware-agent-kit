# sensor-node example

A small, portable firmware module set that shows the patterns the kit recommends and serves as a finding-free corpus for the kit's checks:

- `src/` - hardware-independent code:
  - `ring_buffer.c`: lock-free SPSC buffer, ISR producer to task consumer.
  - `frame_parser.c`: framed protocol with CRC-16.
  - `comm_service.c`: thread-safe public API, with ISR-safe `_from_isr` entry points.
- `src/osal.h` - the only dependency on the RTOS. `port/freertos/osal_freertos.c` implements it for the target.

Run from this directory:

```sh
python ../../tools/fw_analyze.py --all --tools lint              # expected: no findings
```
