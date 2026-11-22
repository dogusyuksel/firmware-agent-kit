---
max_turns: 6
allowed_tools: [Read, Glob, Grep, Skill]
---

My bare-metal SAMV71Q21 board (CMSIS DFP startup, my own main) resets by itself roughly every 16 seconds, even with an empty main loop. No HardFault handler is hit. What is the most likely cause and how do I fix it?
