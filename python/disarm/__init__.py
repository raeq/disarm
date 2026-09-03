"""disarm: Fast Unicode transliteration, slugification, and text normalization."""

from __future__ import annotations

import sys as _sys
import types as _stdlib_types
from importlib.metadata import PackageNotFoundError as _PackageNotFoundError
from importlib.metadata import version as _dist_version

# The public transform functions and stateful classes live in disarm._api;
# the precompiled pipeline presets live in disarm._presets. They are imported
# explicitly (not via ``import *``) so every name in ``__all__`` is an explicit
# re-export under ``mypy --strict`` (no_implicit_reexport).
from disarm._api import (
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
    edit_distance,
    escape_html,
    find_confusables,
    find_key_collisions,
    find_unmapped_confusables,
    find_untranslatable,
    fold_case,
    grapheme_len,
    grapheme_split,
    grapheme_truncate,
    grapheme_width,
    has_anomalies,
    has_bidi_conflict,
    has_bidi_control,
    inspect_anomalies,
    inspect_auto_lang,
    is_ascii,
    is_canonical,
    is_case_fold_stable,
    is_confusable,
    is_mixed_script,
    is_normalized,
    is_normalized_stream_safe,
    is_suspicious_hostname,
    lang_info,
    list_context_langs,
    list_langs,
    list_scripts,
    make_cached_transliterator,
    nearest_match,
    normalize,
    normalize_confusables,
    percent_encode,
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
    stream_safe,
    strip_accents,
    strip_control_chars,
    strip_log_injection,
    strip_zero_width_chars,
    terminal_width,
    transliterate,
    unmapped_confusables,
)
from disarm._boundary import (
    _CONFUSABLES_VERSION,
    _KEY_SCHEMA_VERSION,
    _UNICODE_VERSION,
    AnomalyReport,
    DisarmError,
    Finding,
    HostnameAnalysis,
    InvalidArgumentError,
    KeyCollision,
    Lexicon,
    NearestMatch,
    ResourceLimitError,
    UnsupportedError,
)

# Enums, type aliases, protocols and the exception are re-exported from their
# source modules explicitly so that, under ``mypy --strict``
# (no_implicit_reexport), every name in ``__all__`` is an explicit re-export.
from disarm._enums import (
    LANG_AM,
    LANG_AR,
    LANG_AS,
    LANG_AUTO,
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
    Component,
    LangMeta,
    Script,
    ScriptMeta,
)
from disarm._presets import (
    PRESETS,
    canonicalize,
    canonicalize_strict,
    catalog_key,
    display_clean,
    get_pipeline,
    is_zalgo,
    list_profiles,
    ml_normalize,
    normalize_user_input,
    search_key,
    security_clean,
    sort_key,
    strip_bidi,
    strip_format,
    strip_noncharacters,
    strip_obfuscation,
    strip_pua,
    strip_tags,
    strip_variation_selectors,
    strip_zalgo,
)
from disarm._types import NF, EmojiProvider, TransliterateErrorMode

# --- Package version (single source of truth: the installed distribution's metadata,
#     so `disarm.__version__` always tracks the wheel the user actually has) ---
try:
    __version__ = _dist_version("disarm")
except _PackageNotFoundError:  # pragma: no cover - source checkout without an install
    __version__ = "0.0.0+unknown"

# --- Bundled data version (#560) ---
#
# The Unicode `confusables.txt` release the bundled confusable tables were folded from.
# This constant answers one question only: how current is the confusables fold? It is not
# a library-wide Unicode version, and there deliberately is none — disarm's tables track
# different releases (case folding 16.0, East Asian width 15.1.0), so a single number
# would be wrong for most of them. `docs/provenance.md` is the census.
#
# Read from the compiled core, which in turn reads it from the TSV header at build time,
# so the number is never typed twice.
CONFUSABLES_VERSION: str = _CONFUSABLES_VERSION

# The UCD release disarm's NORMALIZER implements — not a library-wide version, for the
# reason above. An earlier comment here argued against this name on exactly that ground,
# and the objection is right about the risk: a reader can take `UNICODE_VERSION` to cover
# the whole artifact. It is kept because the question it answers is the one integrators
# actually ask — *will my keys agree with `unicodedata`?* — and that question is about the
# normalizer alone. Every NFC/NFKC step in the library, including the ones inside presets,
# runs through `unicode-normalization`, and it carries its own UCD independent of both the
# bundled tables and disarm's semver. Usually the answer is no: disarm tracks a newer UCD
# than most shipped CPythons, which is what makes a pipeline that canonicalizes with one
# and validates with the other a problem (docs/security/cve-validation.md).
#
# Emitted by build.rs from the crate's own constant, so it cannot drift from the tables it
# names.
UNICODE_VERSION: str = _UNICODE_VERSION

# Whether a key stored under an earlier release still compares equal. NOT a Unicode
# version and not disarm's version: a monotonic counter, bumped whenever key-producing
# output moves. Two artifacts reporting the same value produce the same key for the same
# input; different values mean reindex. The value is meaningless alone — the question a
# key consumer has is a comparison — and pre-0.15 releases expose nothing, so "unknown"
# and "different" are the same answer there.
#
# It covers all eight functions the key-stability fixture tracks, not only the three named
# "key builders": a stored `canonicalize` value is as much a key as a stored `search_key`
# one. The counter is kept honest by that fixture, which records the version it was
# generated under; regenerating it without bumping this is a test failure (#644, #645).
KEY_SCHEMA_VERSION: int = _KEY_SCHEMA_VERSION

# --- Compatibility aliases ---

from disarm._compat import (  # noqa: E402, F401
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
from disarm._text import Text  # noqa: E402

# --- Public API ---

__all__ = [
    # Metadata
    "__version__",
    "CONFUSABLES_VERSION",
    "KEY_SCHEMA_VERSION",
    "UNICODE_VERSION",
    # Transforms
    "transliterate",
    "find_untranslatable",
    "find_confusables",
    "find_unmapped_confusables",
    "dedup_batch",
    "make_cached_transliterator",
    "CachedTransliterator",
    "slugify",
    "normalize",
    "normalize_confusables",
    "sanitize_filename",
    "stream_safe",
    "strip_accents",
    "strip_control_chars",
    "fold_case",
    "collapse_whitespace",
    "demojize",
    "set_emoji_provider",
    # Precompiled pipelines
    "canonicalize",
    "ml_normalize",
    "catalog_key",
    "strip_format",
    "search_key",
    "sort_key",
    "strip_bidi",
    "strip_tags",
    "strip_variation_selectors",
    "strip_noncharacters",
    "strip_pua",
    "canonicalize_strict",
    "strip_obfuscation",
    # Deprecated preset aliases (#430) — removed in 1.0
    "security_clean",
    "display_clean",
    "normalize_user_input",
    # Zalgo detection and stripping
    "is_zalgo",
    "strip_zalgo",
    # Grapheme clusters
    "grapheme_len",
    "grapheme_split",
    "grapheme_truncate",
    "grapheme_width",
    "terminal_width",
    # Hostname safety
    "is_suspicious_hostname",
    # Anomaly detection (#389)
    "has_anomalies",
    "inspect_anomalies",
    "AnomalyReport",
    "Finding",
    # Reusable anomaly lexicon handle (HAI-SDLC 6.1)
    "Lexicon",
    "escape_html",
    "percent_encode",
    "strip_log_injection",
    "strip_zero_width_chars",
    "HostnameAnalysis",
    # Reverse transliteration
    "reverse_langs",
    # Encoding detection
    "detect_encoding",
    "decode_to_utf8",
    # Predicates
    "detect_scripts",
    "inspect_auto_lang",
    "is_mixed_script",
    "has_bidi_conflict",
    "has_bidi_control",
    "is_confusable",
    "unmapped_confusables",
    "edit_distance",
    "find_key_collisions",
    "NearestMatch",
    "nearest_match",
    "KeyCollision",
    "is_ascii",
    "is_case_fold_stable",
    "is_canonical",
    "is_normalized",
    "is_normalized_stream_safe",
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
    "Component",
    "Script",
    "LANG_AM",
    "LANG_AR",
    "LANG_AS",
    "LANG_AUTO",
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
    "DisarmError",
    "InvalidArgumentError",
    "ResourceLimitError",
    "UnsupportedError",
]

# ---------------------------------------------------------------------------
# Make the module itself callable: import disarm; disarm("Москва")
# ---------------------------------------------------------------------------


#: Names a reader reaches for when they want an outcome rather than an operation, and
#: what to point them at instead (#654).
#:
#: CONTRIBUTING.md's naming rule says a public name may describe the operation and never
#: the outcome, so none of these will ever exist. That leaves a reader who searches for
#: one with a bare ``AttributeError`` at exactly the moment they are asking the question
#: the threat model answers. The hook below refuses and explains in the same breath —
#: which is compatible with the rule, because it promises nothing.
_OUTCOME_NAMES = frozenset(
    {"clean", "sanitize", "sanitise", "safe", "secure", "escape", "is_safe", "make_safe"}
)

_OUTCOME_GUIDANCE = """disarm has no {name!r}, and will not: a public name here describes the operation, \
never the outcome. Nothing in this library makes text safe to emit.

  comparison / canonical form   canonicalize()
  display-safe cleanup          strip_format()
  untrusted LLM input           get_pipeline("llm_guardrail")
  output safety                 encode at the sink — see THREAT_MODEL.md

For filenames see sanitize_filename(); it is named for what it does to a filename, not \
for a guarantee about one."""


class _CallableModule(_stdlib_types.ModuleType):
    """Make ``import disarm; disarm(...)`` a shorthand for ``transliterate()``."""

    # #125: explicit parameter list matches transliterate() overloads so that
    # type-checkers can detect unknown kwargs on _CallableModule-typed variables.
    def __call__(
        self,
        text: str | list[str],
        *,
        lang: str | None = None,
        target: str | None = None,
        errors: TransliterateErrorMode = "replace",
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

    def __getattr__(self, name: str) -> object:
        """Teach the naming rule at the moment someone runs into it (#654).

        Only reached when normal lookup has already failed, so it cannot shadow a real
        attribute. It re-raises the ordinary message for every name outside
        `_OUTCOME_NAMES`, which keeps `hasattr`, `getattr(..., default)` and the import
        machinery behaving exactly as before — including for any `AttributeError` raised
        from inside a submodule import, which this must not swallow.
        """
        if name in _OUTCOME_NAMES:
            raise AttributeError(_OUTCOME_GUIDANCE.format(name=name), name=name, obj=self)
        raise AttributeError(
            f"module {self.__name__!r} has no attribute {name!r}", name=name, obj=self
        )

    def __repr__(self) -> str:
        return f"<module {self.__name__!r} (callable) from {self.__file__!r}>"


# Mutate the existing module's __class__ in-place so that __dict__ (and
# therefore functions' __globals__) stays identical.  This keeps
# unittest.mock.patch working correctly.
_sys.modules[__name__].__class__ = _CallableModule
