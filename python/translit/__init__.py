"""translit: Fast Unicode transliteration, slugification, and text normalization."""

from __future__ import annotations

import sys as _sys
import types as _stdlib_types
from importlib.metadata import PackageNotFoundError as _PackageNotFoundError
from importlib.metadata import version as _dist_version

# The public transform functions and stateful classes live in translit._api;
# the precompiled pipeline presets live in translit._presets. They are imported
# explicitly (not via ``import *``) so every name in ``__all__`` is an explicit
# re-export under ``mypy --strict`` (no_implicit_reexport).
from translit._api import (
    CachedTransliterator,
    Slugifier,
    TextPipeline,
    UniqueSlugifier,
    casefold,
    clear_replacements,
    collapse_whitespace,
    decode_to_utf8,
    dedup_batch,
    demojize,
    detect_encoding,
    detect_scripts,
    fold_case,
    grapheme_len,
    grapheme_split,
    grapheme_truncate,
    inspect_auto_lang,
    is_ascii,
    is_confusable,
    is_mixed_script,
    is_normalized,
    is_safe_hostname,
    lang_info,
    list_context_langs,
    list_langs,
    list_scripts,
    make_cached_transliterator,
    normalize,
    normalize_confusables,
    register_lang,
    register_replacements,
    registrations_sealed,
    remove_accents,
    remove_replacement,
    reverse_langs,
    sanitize_filename,
    script_info,
    seal_registrations,
    set_emoji_provider,
    slugify,
    strip_accents,
    transliterate,
)

# Enums, type aliases, protocols and the exception are re-exported from their
# source modules explicitly so that, under ``mypy --strict``
# (no_implicit_reexport), every name in ``__all__`` is an explicit re-export.
from translit._enums import (
    LANG_AM,
    LANG_AR,
    LANG_AS,
    LANG_BAN,
    LANG_BAX,
    LANG_BG,
    LANG_BN,
    LANG_BO,
    LANG_BUG,
    LANG_CA,
    LANG_CHR,
    LANG_CJM,
    LANG_COP,
    LANG_CS,
    LANG_CY,
    LANG_DA,
    LANG_DE,
    LANG_DV,
    LANG_EL,
    LANG_ES,
    LANG_ET,
    LANG_FA,
    LANG_FI,
    LANG_FR,
    LANG_GA,
    LANG_GU,
    LANG_HE,
    LANG_HI,
    LANG_HR,
    LANG_HU,
    LANG_HY,
    LANG_IS,
    LANG_IT,
    LANG_JA,
    LANG_JV,
    LANG_KA,
    LANG_KHB,
    LANG_KM,
    LANG_KN,
    LANG_KO,
    LANG_LIS,
    LANG_LO,
    LANG_LT,
    LANG_LV,
    LANG_META,
    LANG_ML,
    LANG_MN,
    LANG_MNI,
    LANG_MR,
    LANG_MT,
    LANG_MY,
    LANG_NE,
    LANG_NL,
    LANG_NO,
    LANG_NOD,
    LANG_NQO,
    LANG_OR,
    LANG_PA,
    LANG_PL,
    LANG_PT,
    LANG_RO,
    LANG_RU,
    LANG_SA,
    LANG_SAT,
    LANG_SI,
    LANG_SK,
    LANG_SL,
    LANG_SQ,
    LANG_SR,
    LANG_SU,
    LANG_SV,
    LANG_SYR,
    LANG_TA,
    LANG_TDD,
    LANG_TE,
    LANG_TH,
    LANG_TL,
    LANG_TR,
    LANG_TZM,
    LANG_UK,
    LANG_VAI,
    LANG_VI,
    LANG_ZH,
    SCRIPT_META,
    LangMeta,
    Script,
    ScriptMeta,
)
from translit._presets import (
    PRESETS,
    catalog_key,
    display_clean,
    get_pipeline,
    is_zalgo,
    list_profiles,
    ml_normalize,
    sanitize_user_input,
    search_key,
    security_clean,
    sort_key,
    strip_bidi,
    strip_obfuscation,
    strip_zalgo,
)
from translit._translit import SafeHostnameDetails, TranslitError
from translit._types import NF, EmojiProvider, ErrorMode

# --- Package version (single source of truth: the installed distribution's metadata,
#     so `translit.__version__` always tracks the wheel the user actually has) ---
try:
    __version__ = _dist_version("translit-rs")
except _PackageNotFoundError:  # pragma: no cover - source checkout without an install
    __version__ = "0.0.0+unknown"

# --- Compatibility aliases ---

from translit._compat import (  # noqa: E402, F401  # noqa: E402, F401
    Slugify,
    UniqueSlugify,
    ascii_fold,
    slugify_de,
    slugify_el,
    slugify_filename,
    slugify_ru,
    slugify_unicode,
    slugify_url,
    unidecode,
)
from translit._text import Text  # noqa: E402

# --- Public API ---

__all__ = [
    # Metadata
    "__version__",
    # Transforms
    "transliterate",
    "dedup_batch",
    "make_cached_transliterator",
    "CachedTransliterator",
    "slugify",
    "normalize",
    "normalize_confusables",
    "sanitize_filename",
    "strip_accents",
    "fold_case",
    "collapse_whitespace",
    "demojize",
    "set_emoji_provider",
    # Precompiled pipelines
    "security_clean",
    "ml_normalize",
    "catalog_key",
    "display_clean",
    "search_key",
    "sort_key",
    "strip_bidi",
    "sanitize_user_input",
    "strip_obfuscation",
    # Zalgo detection and stripping
    "is_zalgo",
    "strip_zalgo",
    # Grapheme clusters
    "grapheme_len",
    "grapheme_split",
    "grapheme_truncate",
    # Hostname safety
    "is_safe_hostname",
    "SafeHostnameDetails",
    # Reverse transliteration
    "reverse_langs",
    # Encoding detection
    "detect_encoding",
    "decode_to_utf8",
    # Predicates
    "detect_scripts",
    "inspect_auto_lang",
    "is_mixed_script",
    "is_confusable",
    "is_ascii",
    "is_normalized",
    # Preset metadata
    "PRESETS",
    # Policy profiles
    "get_pipeline",
    "list_profiles",
    # Stateful / builders
    "Text",
    "Slugifier",
    "UniqueSlugifier",
    "TextPipeline",
    # Language profiles
    "list_langs",
    "list_scripts",
    "list_context_langs",
    "lang_info",
    "script_info",
    "LANG_META",
    "SCRIPT_META",
    "LangMeta",
    "ScriptMeta",
    "register_lang",
    "register_replacements",
    "remove_replacement",
    "clear_replacements",
    "seal_registrations",
    "registrations_sealed",
    # Enums, protocols & constants
    "EmojiProvider",
    "NF",
    "Script",
    "LANG_AM",
    "LANG_AR",
    "LANG_AS",
    "LANG_BAN",
    "LANG_BAX",
    "LANG_BG",
    "LANG_BN",
    "LANG_BO",
    "LANG_BUG",
    "LANG_CA",
    "LANG_CHR",
    "LANG_CJM",
    "LANG_COP",
    "LANG_CS",
    "LANG_CY",
    "LANG_DA",
    "LANG_DE",
    "LANG_DV",
    "LANG_EL",
    "LANG_ES",
    "LANG_ET",
    "LANG_FA",
    "LANG_FI",
    "LANG_FR",
    "LANG_GA",
    "LANG_GU",
    "LANG_HE",
    "LANG_HI",
    "LANG_HR",
    "LANG_HU",
    "LANG_HY",
    "LANG_IS",
    "LANG_IT",
    "LANG_JA",
    "LANG_JV",
    "LANG_KA",
    "LANG_KHB",
    "LANG_KM",
    "LANG_KN",
    "LANG_KO",
    "LANG_LIS",
    "LANG_LO",
    "LANG_LT",
    "LANG_LV",
    "LANG_ML",
    "LANG_MN",
    "LANG_MNI",
    "LANG_MR",
    "LANG_MT",
    "LANG_MY",
    "LANG_NE",
    "LANG_NL",
    "LANG_NO",
    "LANG_NOD",
    "LANG_NQO",
    "LANG_OR",
    "LANG_PA",
    "LANG_PL",
    "LANG_PT",
    "LANG_RO",
    "LANG_RU",
    "LANG_SA",
    "LANG_SAT",
    "LANG_SI",
    "LANG_SK",
    "LANG_SL",
    "LANG_SQ",
    "LANG_SR",
    "LANG_SU",
    "LANG_SV",
    "LANG_SYR",
    "LANG_TA",
    "LANG_TDD",
    "LANG_TE",
    "LANG_TH",
    "LANG_TL",
    "LANG_TR",
    "LANG_TZM",
    "LANG_UK",
    "LANG_VAI",
    "LANG_VI",
    "LANG_ZH",
    # Drop-in compatibility aliases
    "casefold",
    "remove_accents",
    # Compatibility aliases (Unidecode)
    "unidecode",
    "ascii_fold",
    # Compatibility aliases (awesome-slugify)
    "Slugify",
    "UniqueSlugify",
    "slugify_url",
    "slugify_filename",
    "slugify_unicode",
    "slugify_ru",
    "slugify_de",
    "slugify_el",
    # Exception
    "TranslitError",
]

# ---------------------------------------------------------------------------
# Make the module itself callable: import translit; translit("Москва")
# ---------------------------------------------------------------------------


class _CallableModule(_stdlib_types.ModuleType):
    """Make ``import translit; translit(...)`` a shorthand for ``transliterate()``."""

    # #125: explicit parameter list matches transliterate() overloads so that
    # type-checkers can detect unknown kwargs on _CallableModule-typed variables.
    def __call__(
        self,
        text: str | list[str],
        *,
        lang: str | None = None,
        target: str | None = None,
        errors: ErrorMode = "replace",
        replace_with: str = "[?]",
        strict_iso9: bool = False,
        gost7034: bool = False,
        tones: bool = False,
        context: bool = False,
    ) -> str | list[str]:
        return transliterate(
            text,
            lang=lang,
            target=target,
            errors=errors,
            replace_with=replace_with,
            strict_iso9=strict_iso9,
            gost7034=gost7034,
            tones=tones,
            context=context,
        )

    def __repr__(self) -> str:
        return f"<module {self.__name__!r} (callable) from {self.__file__!r}>"


# Mutate the existing module's __class__ in-place so that __dict__ (and
# therefore functions' __globals__) stays identical.  This keeps
# unittest.mock.patch working correctly.
_sys.modules[__name__].__class__ = _CallableModule
