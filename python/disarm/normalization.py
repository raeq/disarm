"""Unicode normalization, accent stripping, case folding, and whitespace handling.

Usage::

    from disarm.normalization import normalize, strip_accents, fold_case

    normalize("cafe\u0301", form="NFC")  # 'caf\u00e9'  (composed form)
    strip_accents("cafe\u0301")           # 'cafe'
    fold_case("Strasse")                 # 'strasse'
"""

from disarm import (
    collapse_whitespace,
    fold_case,
    is_normalized,
    normalize,
    strip_accents,
)

__all__ = [
    "collapse_whitespace",
    "fold_case",
    "is_normalized",
    "normalize",
    "strip_accents",
]
