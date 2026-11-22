---
description: Answer a hardware question from datasheets, reference manuals, errata or schematics (PDF) with page citations
argument-hint: "<question, e.g. 'USART2 BRR formula on STM32G474' | 'pin map from schematic.pdf'>"
---

Hardware question: $ARGUMENTS

1. Find the documents in `datasheets` in `.claude/firmware.json`, any paths in the question, or `docs/**/*.pdf` in the repo.
2. For a single fact, run `python <kit>/tools/pdf_search.py <pdf> "<terms>"` and read only the pages it reports.
3. For broader work (full register description, schematic pin map, comparing the firmware pinout with the schematic), delegate to the `datasheet-analyst` agent.
4. Answer with citations (document, section/table, page). Say plainly when something is not in the documents. If the answer contradicts the current code, report the mismatch and do not change the code unless asked.
