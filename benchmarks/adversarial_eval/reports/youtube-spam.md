# Adversarial-text robustness — youtube-spam

_disarm 0.6.3; `strip_obfuscation`. Numbers reflect the current version and may differ from the historical baseline in the README as coverage grows._

- rows evaluated: **1956**
- perturbation-bearing rows (contain non-ASCII): **80.8%** (1580/1956)
- non-ASCII codepoints folded by `strip_obfuscation`: **81.9%** (2541/3104)

## Miss-mining (non-ASCII codepoints surviving the defense)

- **principled** (in UTS#39, addressable — feed to #40): **6** distinct, 121 occurrences
- **novel** (not in UTS#39, out of scope): **22** distinct, 442 occurrences

Top principled (addressable) misses:

| codepoint | char | occurrences |
|---|---|---|
| U+2503 | `┃` | 42 |
| U+2501 | `━` | 26 |
| U+2588 | `█` | 19 |
| U+250F | `┏` | 16 |
| U+2590 | `▐` | 10 |
| U+0B9C | `ஜ` | 8 |

> Guardrail: these are **observations**, not optimization targets. Principled misses are candidates to verify and upstream via #40 — never silent table edits.
