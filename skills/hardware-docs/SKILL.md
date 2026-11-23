---
name: hardware-docs
description: Read datasheets, reference manuals, errata sheets and board schematics (PDF) efficiently and accurately - find the right pages first, extract register facts, pin/net maps, power rails, strapping/boot pins, crystals and connector pinouts, with citations. Use when firmware needs hardware facts or the user shares a datasheet or schematic.
---

# Reading hardware documents

## Token-efficient procedure
1. Locate pages, do not read the whole PDF:
   `python <kit>/tools/pdf_search.py doc.pdf "USART_BRR" "Baud rate"` -> pages + snippets.
   Schematics: `pdf_search.py sch.pdf --regex "PA\d+|PB\d+|BOOT0|NRST|SWDIO|GPIO0"` and `--page N` for one sheet's text (refdes, nets).
2. Read only those pages with the Read tool (`pages: "41-43"`). Schematic sheets are vector drawings: read the page visually when text extraction loses the wiring.
3. For large jobs (many registers, full pin map), delegate to the `datasheet-analyst` agent so only the distilled answer enters the conversation.
4. Cite every fact: document, revision, section/table, page.

## Datasheet vs reference manual vs errata
- Datasheet: pinout per package, alternate-function table, electrical limits, memory sizes, ordering codes.
- Reference manual: registers, bit fields, reset values, peripheral behaviour, init sequences.
- Errata: silicon bugs and workarounds for a given revision - check before blaming the driver.
- Device header / SVD in the repo is authoritative for names and addresses; the manual explains behaviour.

## Schematic extraction checklist
Produce these tables (Markdown) when asked to "read the schematic":
1. **MCU pin map**: pin | port/GPIO | net name | connected to (refdes.pin) | function (peripheral/AF) | pull-up/down | notes.
2. **Power**: rails, regulators (part, max current), sequencing, ADC reference, battery/backup domain.
3. **Clocks**: crystals/oscillators with frequency and load caps (-> HSE/XTAL config).
4. **Boot/strapping/debug**: STM32 BOOT0/BOOT1, NRST; SAMV71 ERASE (PB12), JTAG/SWD, TCM/boot via GPNVM; debug connector pinout.
5. **External devices**: bus (I2C address with A0..A2 straps, SPI CS pin, UART), interrupt/reset lines, level shifters.
6. **Risks found**: floating inputs, missing pull-ups on I2C/open-drain, strapping pins with loads, LEDs on boot pins, 5 V on non-tolerant pins.
Then compare with the firmware's pin configuration and report mismatches (without changing code unless asked).

## Diagrams
Turn extracted structure into Mermaid when it helps (block diagram of MCU <-> peripherals, power tree) - see the `mermaid-diagrams` skill.
