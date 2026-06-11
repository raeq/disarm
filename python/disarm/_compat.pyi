"""Type stubs for disarm._compat (awesome-slugify compatibility layer)."""

from __future__ import annotations

from typing import Any

from disarm._types import ErrorMode as ErrorMode

def unidecode(text: str) -> str: ...

# Elasticsearch/Solr alias for strip_accents
def ascii_fold(text: str) -> str: ...

class Slugify:
    """awesome-slugify-compatible Slugify class."""

    to_lower: bool
    stop_words: tuple[str, ...]
    max_length: int | None
    separator: str
    safe_chars: str
    pretranslate: tuple[tuple[str, str], ...] | None

    def __init__(self, **kwargs: Any) -> None: ...
    def __call__(self, text: str, **kwargs: Any) -> str: ...
    def __repr__(self) -> str: ...

class UniqueSlugify(Slugify):
    """awesome-slugify-compatible UniqueSlugify class."""

    def __init__(self, **kwargs: Any) -> None: ...
    def __call__(self, text: str, **kwargs: Any) -> str: ...
    def reset(self) -> None: ...
    def __repr__(self) -> str: ...

slugify_url: Slugify
slugify_filename: Slugify
slugify_unicode: Slugify
slugify_ru: Slugify
slugify_de: Slugify
slugify_el: Slugify
