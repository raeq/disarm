"""Unicode normalization, accent stripping, case folding, and whitespace handling.

Usage::

    from translit.normalization import normalize, strip_accents, fold_case

    normalize("cafe\u0301", form="NFC")  # 'cafe'  (composed form)
    strip_accents("cafe\u0301")           # 'cafe'
    fold_case("Strasse")                 # 'strasse'
"""

from translit import (
    collapse_whitespace,
    fold_case,
    is_normalized,
    normalize,
    normalize_batch,
    strip_accents,
    strip_accents_batch,
)

__all__ = [
    "collapse_whitespace",
    "fold_case",
    "is_normalized",
    "normalize",
    "normalize_batch",
    "strip_accents",
    "strip_accents_batch",
]
