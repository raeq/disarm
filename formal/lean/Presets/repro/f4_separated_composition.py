"""Finding 4: a character removed after the last normalization separates two that compose.

Model: `Findings.obf_jamo`, `ml_jamo`, `web_bs`, `web_pua`.
"""

from __future__ import annotations

from common import profile, show, w

import disarm

L, V = 0x1100, 0x1161  # Hangul choseong kiyeok, jungseong a: L + V composes to U+AC00

show("strip_obfuscation L NUL V", w(L, 0x0, V), disarm.strip_obfuscation)
show("ml_normalize L ZWSP V", w(L, 0x200B, V), disarm.ml_normalize)
show("ml_normalize L NUL V", w(L, 0x0, V), disarm.ml_normalize)
show("ml_corpus_normalize L NUL V", w(L, 0x0, V), profile("ml_corpus_normalize"))
show("ml_corpus_normalize L BS V", w(L, 0x8, V), profile("ml_corpus_normalize"))
show("llm_guardrail L ZWSP V", w(L, 0x200B, V), profile("llm_guardrail"))
show("normalize_web_input L ZWSP V", w(L, 0x200B, V), profile("normalize_web_input"))
show("normalize_web_input e BS acute", w(0x65, 0x8, 0x301), profile("normalize_web_input"))
show("normalize_web_input c NUL cedilla", w(0x63, 0x0, 0x327), profile("normalize_web_input"))
show("normalize_web_input I PUA acute", w(0x49, 0xE000, 0x301), profile("normalize_web_input"))

print()
print("the presets that recompose after their strips are fixed points on the same words:")
for name in ("canonicalize", "canonicalize_strict", "sort_key", "search_key", "catalog_key"):
    show(f"{name} L NUL V", w(L, 0x0, V), getattr(disarm, name))
