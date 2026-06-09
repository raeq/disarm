"""Adversarial-text robustness evaluation harness (#49).

A reusable, out-of-CI benchmark that measures how translit's defense transforms
(``strip_obfuscation``) behave on real-world spam/phishing corpora. It pulls
large external datasets over the network, so it is **not** part of the test gate
— run it on demand (see ``README.md``).

Guardrail (carried from #39/#40): these corpora are **measuring instruments,
never optimization targets.** Do not add confusable mappings to improve a
benchmark number; coverage grows only from authoritative sources (UTS#39 +
transitive closure; real attacker confusables verified and upstreamed per #40).
Report results as observations; feed misses into #40, not into silent table edits.
"""

from .corpora import ADAPTERS, CorpusAdapter, Record
from .metrics import EvalResult, evaluate, load_uts39_sources

__all__ = [
    "ADAPTERS",
    "CorpusAdapter",
    "Record",
    "EvalResult",
    "evaluate",
    "load_uts39_sources",
]
