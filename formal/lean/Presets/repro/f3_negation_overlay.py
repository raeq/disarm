"""Finding 3: `llm_guardrail` and `ml_corpus_normalize` keep a negation overlay, then orphan it.

Model: `Findings.guard_cent`, `guard_cent2`, `corpus_pua`, `corpus_pua2`.
"""

from __future__ import annotations

from common import profile, show, w

import disarm

guard = profile("llm_guardrail")
corpus = profile("ml_corpus_normalize")

show("llm_guardrail cent + U+0338", w(0xA2, 0x338), guard)
show("llm_guardrail union + U+0338", w(0x222A, 0x338), guard)
show("llm_guardrail for-all + U+20D2", w(0x2200, 0x20D2), guard)
show("llm_guardrail PUA + U+0338", w(0xE000, 0x338), guard)
show(
    "llm_guardrail[tr39] cent + U+0338",
    w(0xA2, 0x338),
    profile("llm_guardrail", digit_policy="tr39"),
)
show("ml_corpus_normalize PUA + U+0338", w(0xE000, 0x338), corpus)
show("ml_corpus_normalize plane-15 PUA + U+20D2", w(0xF0000, 0x20D2), corpus)

print()
print(
    "the same inputs through the presets, which order the strip after the fold or strip PUA first:"
)
for name in ("canonicalize", "strip_obfuscation", "ml_normalize", "search_key"):
    f = getattr(disarm, name)
    show(f"{name} cent + U+0338", w(0xA2, 0x338), f)
