"""Type stub for ``disarm._boundary``.

At runtime this module re-exports every ``_core`` callable wrapped with the #469
surrogate boundary guard (signature-transparent via ``functools.wraps``), plus the
guard helpers. Statically it IS ``_core``'s surface, re-exported with precise types
(explicit ``as`` aliases so the wrappers' return types are not widened to ``Any``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from disarm._core import (
    _MAX_BATCH_SIZE as _MAX_BATCH_SIZE,
)
from disarm._core import (
    AnomalyReport as AnomalyReport,
)
from disarm._core import (
    DisarmError as DisarmError,
)
from disarm._core import (
    Finding as Finding,
)
from disarm._core import (
    HostnameAnalysis as HostnameAnalysis,
)
from disarm._core import (
    InvalidArgumentError as InvalidArgumentError,
)
from disarm._core import (
    Lexicon as Lexicon,
)
from disarm._core import (
    ResourceLimitError as ResourceLimitError,
)
from disarm._core import (
    UnsupportedError as UnsupportedError,
)
from disarm._core import (
    _canonicalize as _canonicalize,
)
from disarm._core import (
    _canonicalize_strict as _canonicalize_strict,
)
from disarm._core import (
    _catalog_key as _catalog_key,
)
from disarm._core import (
    _clear_replacements as _clear_replacements,
)
from disarm._core import (
    _collapse_whitespace as _collapse_whitespace,
)
from disarm._core import (
    _decode_to_utf8 as _decode_to_utf8,
)
from disarm._core import (
    _demojize as _demojize,
)
from disarm._core import (
    _detect_encoding as _detect_encoding,
)
from disarm._core import (
    _detect_scripts as _detect_scripts,
)
from disarm._core import (
    _escape_html as _escape_html,
)
from disarm._core import (
    _find_untranslatable as _find_untranslatable,
)
from disarm._core import (
    _fold_case as _fold_case,
)
from disarm._core import (
    _get_pipeline as _get_pipeline,
)
from disarm._core import (
    _grapheme_len as _grapheme_len,
)
from disarm._core import (
    _grapheme_split as _grapheme_split,
)
from disarm._core import (
    _grapheme_truncate as _grapheme_truncate,
)
from disarm._core import (
    _grapheme_width as _grapheme_width,
)
from disarm._core import (
    _has_anomalies as _has_anomalies,
)
from disarm._core import (
    _has_anomalies_lex as _has_anomalies_lex,
)
from disarm._core import (
    _has_bidi_conflict as _has_bidi_conflict,
)
from disarm._core import (
    _inspect_anomalies as _inspect_anomalies,
)
from disarm._core import (
    _inspect_anomalies_lex as _inspect_anomalies_lex,
)
from disarm._core import (
    _inspect_auto_lang as _inspect_auto_lang,
)
from disarm._core import (
    _is_ascii as _is_ascii,
)
from disarm._core import (
    _is_confusable as _is_confusable,
)
from disarm._core import (
    _is_mixed_script as _is_mixed_script,
)
from disarm._core import (
    _is_normalized as _is_normalized,
)
from disarm._core import (
    _is_suspicious_hostname as _is_suspicious_hostname,
)
from disarm._core import (
    _is_zalgo as _is_zalgo,
)
from disarm._core import (
    _list_langs as _list_langs,
)
from disarm._core import (
    _list_profiles as _list_profiles,
)
from disarm._core import (
    _ml_normalize as _ml_normalize,
)
from disarm._core import (
    _normalize as _normalize,
)
from disarm._core import (
    _normalize_batch as _normalize_batch,
)
from disarm._core import (
    _normalize_confusables as _normalize_confusables,
)
from disarm._core import (
    _percent_encode as _percent_encode,
)
from disarm._core import (
    _register_lang as _register_lang,
)
from disarm._core import (
    _register_replacements as _register_replacements,
)
from disarm._core import (
    _registrations_sealed as _registrations_sealed,
)
from disarm._core import (
    _remove_replacement as _remove_replacement,
)
from disarm._core import (
    _reverse_langs as _reverse_langs,
)
from disarm._core import (
    _reverse_transliterate as _reverse_transliterate,
)
from disarm._core import (
    _sanitize_filename as _sanitize_filename,
)
from disarm._core import (
    _seal_registrations as _seal_registrations,
)
from disarm._core import (
    _search_key as _search_key,
)
from disarm._core import (
    _set_emoji_provider as _set_emoji_provider,
)
from disarm._core import (
    _set_transliterate_fallback as _set_transliterate_fallback,
)
from disarm._core import (
    _Slugifier as _Slugifier,
)
from disarm._core import (
    _slugify as _slugify,
)
from disarm._core import (
    _slugify_batch as _slugify_batch,
)
from disarm._core import (
    _sort_key as _sort_key,
)
from disarm._core import (
    _strip_accents as _strip_accents,
)
from disarm._core import (
    _strip_accents_batch as _strip_accents_batch,
)
from disarm._core import (
    _strip_bidi as _strip_bidi,
)
from disarm._core import (
    _strip_format as _strip_format,
)
from disarm._core import (
    _strip_log_injection as _strip_log_injection,
)
from disarm._core import (
    _strip_noncharacters as _strip_noncharacters,
)
from disarm._core import (
    _strip_obfuscation as _strip_obfuscation,
)
from disarm._core import (
    _strip_pua as _strip_pua,
)
from disarm._core import (
    _strip_tags as _strip_tags,
)
from disarm._core import (
    _strip_variation_selectors as _strip_variation_selectors,
)
from disarm._core import (
    _strip_zalgo as _strip_zalgo,
)
from disarm._core import (
    _terminal_width as _terminal_width,
)
from disarm._core import (
    _TextPipeline as _TextPipeline,
)
from disarm._core import (
    _transliterate as _transliterate,
)
from disarm._core import (
    _transliterate_batch as _transliterate_batch,
)
from disarm._core import (
    _transliterate_context as _transliterate_context,
)
from disarm._core import (
    _transliterate_entry as _transliterate_entry,
)
from disarm._core import (
    _UniqueSlugifier as _UniqueSlugifier,
)
from disarm._core import (
    _validate_transliterate_args as _validate_transliterate_args,
)

_F = TypeVar("_F", bound=Callable[..., Any])

def _wtf8(s: str) -> str: ...
def _scrub(value: Any) -> Any: ...
def _surrogate_safe(fn: _F) -> _F: ...
