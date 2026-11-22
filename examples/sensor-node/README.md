# sensor-node example

A small, portable firmware module set that shows the patterns the kit recommends and serves as its test corpus:

- `src/` - hardware-independent code:
  - `ring_buffer.c`: lock-free SPSC buffer, ISR producer to task consumer.
  - `frame_parser.c`: framed protocol with CRC-16.
  - `comm_service.c`: thread-safe public API, with ISR-safe `_from_isr` entry points.
- `src/osal.h` - the only dependency on the RTOS. `port/freertos/osal_freertos.c` implements it for the target; host tests mock it with CMock.
- `test/` - Ceedling unit tests, tagged with `@verifies` requirement IDs.
- `docs/requirements.csv` - requirement list used by `trace_check.py`.

Run from this directory:

```sh
ceedling test:all                                             # needs Ruby + Ceedling + a host gcc
python ../../tools/fw_container.py run arm-dev -- ceedling test:all   # or in the container
python ../../tools/trace_check.py --reqs docs/requirements.csv
python ../../tools/fw_analyze.py --all --tools lint              # expected: no findings
```

CI runs all of these on every push.
