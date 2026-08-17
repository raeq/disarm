# Adversarial-text robustness — bitabuse

_disarm 0.12.0; `strip_obfuscation`. Numbers reflect the current version and may differ from the historical baseline in the README as coverage grows._

- rows evaluated: **325580**
- perturbation-bearing rows (contain non-ASCII): **99.9%** (325361/325580)
- non-ASCII codepoints folded by `strip_obfuscation`: **81.7%** (3932758/4811752)

## Recovery (clean ground truth available)

- XMR (exact-match recovery, `P(perturbed) == P(clean)`): **6.1%**
- line-exact recovery (`P(perturbed) == clean`): **5.8%**
- word-level recovery: **65.3%**

## Miss-mining (non-ASCII codepoints surviving the defense)

- **principled** (in UTS#39, addressable — feed to #40): **54** distinct, 133535 occurrences
- **novel** (not in UTS#39, out of scope): **294** distinct, 745459 occurrences

Top principled (addressable) misses:

| codepoint | char | occurrences |
|---|---|---|
| U+03C4 | `τ` | 37084 |
| U+0437 | `з` | 26373 |
| U+050D | `ԍ` | 26040 |
| U+0499 | `ҙ` | 12763 |
| U+00E6 | `æ` | 6334 |
| U+1D28 | `ᴨ` | 4957 |
| U+1D0D | `ᴍ` | 3404 |
| U+04A3 | `ң` | 2074 |
| U+0375 | `͵` | 1962 |
| U+0223 | `ȣ` | 1917 |
| U+01BB | `ƻ` | 1011 |
| U+01A7 | `Ƨ` | 830 |
| U+066C | `٬` | 819 |
| U+0241 | `Ɂ` | 704 |
| U+02BF | `ʿ` | 697 |

> Guardrail: these are **observations**, not optimization targets. Principled misses are candidates to verify and upstream via #40 — never silent table edits.
