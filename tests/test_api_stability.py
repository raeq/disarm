"""API surface stability tests.

These tests verify that the public API of translit has not changed.
They check function existence, parameter names, and type annotations —
NOT behavior or output. Any failure means a breaking API change was
introduced and must be intentional.

To update after an intentional API change, modify the expected values
in this file to match the new signatures.
"""

from __future__ import annotations

import inspect
from typing import get_type_hints

import pytest

import translit
from translit import (
    LANG_META,
    NF,
    SCRIPT_META,
    EmojiProvider,
    LangMeta,
    Script,
    ScriptMeta,
)

# ---------------------------------------------------------------------------
# __all__ completeness
# ---------------------------------------------------------------------------

EXPECTED_ALL = {
    # Metadata
    "__version__",
    # Core transforms
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
    # Zalgo
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
    # Encoding
    "detect_encoding",
    "decode_to_utf8",
    # Predicates
    "detect_scripts",
    "inspect_auto_lang",
    "is_mixed_script",
    "is_confusable",
    "is_ascii",
    "is_normalized",
    # Pipeline management
    "PRESETS",
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
    # Compatibility aliases
    "casefold",
    "remove_accents",
    "unidecode",
    "ascii_fold",
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
}

# LANG_* constants: generated from the canonical set
EXPECTED_LANG_CONSTANTS = {
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
}


class TestAllExports:
    """__all__ must contain exactly the expected public names."""

    def test_all_contains_expected(self):
        actual = set(translit.__all__)
        expected = EXPECTED_ALL | EXPECTED_LANG_CONSTANTS
        missing = expected - actual
        assert not missing, f"Missing from __all__: {sorted(missing)}"

    def test_no_unexpected_exports(self):
        actual = set(translit.__all__)
        expected = EXPECTED_ALL | EXPECTED_LANG_CONSTANTS
        extra = actual - expected
        assert not extra, f"Unexpected in __all__: {sorted(extra)}"


# ---------------------------------------------------------------------------
# Function signature stability
# ---------------------------------------------------------------------------


def _param_names(fn) -> list[str]:
    """Extract parameter names from a callable (excluding 'self')."""
    sig = inspect.signature(fn)
    return [p for p in sig.parameters if p != "self"]


def _param_kinds(fn) -> dict[str, str]:
    """Extract parameter kinds (POSITIONAL_OR_KEYWORD, KEYWORD_ONLY, etc.)."""
    sig = inspect.signature(fn)
    return {name: p.kind.name for name, p in sig.parameters.items() if name != "self"}


# Core transforms: (function_name, expected_params)
CORE_FUNCTION_PARAMS = {
    "transliterate": [
        "text",
        "lang",
        "target",
        "errors",
        "replace_with",
        "strict_iso9",
        "gost7034",
        "tones",
        "context",
    ],
    "dedup_batch": [
        "texts",
        "lang",
        "target",
        "errors",
        "replace_with",
        "strict_iso9",
        "gost7034",
        "tones",
        "context",
    ],
    "make_cached_transliterator": [
        "maxsize",
        "lang",
        "target",
        "errors",
        "replace_with",
        "strict_iso9",
        "gost7034",
        "tones",
        "context",
    ],
    "slugify": [
        "text",
        "separator",
        "lowercase",
        "max_length",
        "word_boundary",
        "save_order",
        "stopwords",
        "regex_pattern",
        "replacements",
        "allow_unicode",
        "lang",
        "entities",
        "decimal",
        "hexadecimal",
    ],
    "normalize": ["text", "form"],
    "normalize_confusables": ["text", "target_script"],
    "sanitize_filename": [
        "text",
        "separator",
        "max_length",
        "platform",
        "lang",
        "preserve_extension",
        "replacement_text",
        "max_len",
    ],
    "strip_accents": ["text"],
    "fold_case": ["text"],
    "collapse_whitespace": ["text", "strip_control", "strip_zero_width"],
    "demojize": [
        "text",
        "strip_modifiers",
        "errors",
        "replace_with",
        "provider",
        "delimiters",
    ],
    "set_emoji_provider": ["provider"],
    # Precompiled pipelines
    "security_clean": ["text"],
    "ml_normalize": ["text", "lang", "emoji"],
    "catalog_key": ["text", "lang", "strict_iso9"],
    "display_clean": ["text"],
    "search_key": ["text", "lang"],
    "sort_key": ["text", "lang"],
    "strip_bidi": ["text"],
    "sanitize_user_input": ["text"],
    "strip_obfuscation": ["text"],
    # Zalgo
    "is_zalgo": ["text", "threshold"],
    "strip_zalgo": ["text", "max_marks"],
    # Grapheme
    "grapheme_len": ["text"],
    "grapheme_split": ["text"],
    "grapheme_truncate": ["text", "max_graphemes"],
    # Hostname
    "is_safe_hostname": ["hostname"],
    # Reverse
    "reverse_langs": [],
    # Encoding
    "detect_encoding": ["data"],
    "decode_to_utf8": ["data", "encoding", "min_confidence"],
    # Predicates
    "detect_scripts": ["text"],
    "inspect_auto_lang": ["text"],
    "is_mixed_script": ["text"],
    "is_confusable": ["text", "target_script", "greedy", "preferred_aliases"],
    "is_ascii": ["text"],
    "is_normalized": ["text", "form"],
    # Pipeline management
    "get_pipeline": ["profile"],
    "list_profiles": [],
    "list_langs": [],
    "list_scripts": [],
    "list_context_langs": [],
    "lang_info": ["code"],
    "script_info": ["script"],
    # Registration
    "register_lang": ["code", "mappings"],
    "register_replacements": ["replacements"],
    "remove_replacement": ["key"],
    "clear_replacements": [],
}


class TestFunctionSignatures:
    """Every public function must have the exact expected parameter list."""

    @pytest.mark.parametrize(
        "name,expected_params",
        [
            pytest.param(name, params, id=name)
            for name, params in sorted(CORE_FUNCTION_PARAMS.items())
        ],
    )
    def test_function_params(self, name: str, expected_params: list[str]):
        fn = getattr(translit, name)
        assert callable(fn), f"{name} is not callable"
        actual = _param_names(fn)
        assert actual == expected_params, (
            f"{name}() params changed:\n  expected: {expected_params}\n  actual:   {actual}"
        )

    @pytest.mark.parametrize(
        "name",
        [
            pytest.param(name, id=name)
            for name in sorted(CORE_FUNCTION_PARAMS)
            if CORE_FUNCTION_PARAMS[name]
            and CORE_FUNCTION_PARAMS[name][0] in ("text", "texts", "data", "hostname")
        ],
    )
    def test_first_param_is_positional(self, name: str):
        """The first param (text/texts/data/hostname) must be positional."""
        fn = getattr(translit, name)
        kinds = _param_kinds(fn)
        first = list(kinds.keys())[0]
        assert kinds[first] in (
            "POSITIONAL_OR_KEYWORD",
            "POSITIONAL_ONLY",
        ), f"{name}() first param {first!r} should be positional, got {kinds[first]}"


# ---------------------------------------------------------------------------
# Class API stability
# ---------------------------------------------------------------------------


CLASS_METHODS = {
    "Text": {
        "__init__": ["text"],
        "normalize": ["form"],
        "normalize_confusables": ["target_script"],
        "strip_accents": [],
        "transliterate": [
            "lang",
            "target",
            "errors",
            "replace_with",
            "strict_iso9",
            "gost7034",
            "tones",
            "context",
        ],
        "fold_case": [],
        "collapse_whitespace": ["strip_control", "strip_zero_width"],
        "slugify": [
            "separator",
            "lowercase",
            "max_length",
            "word_boundary",
            "save_order",
            "stopwords",
            "regex_pattern",
            "replacements",
            "allow_unicode",
            "lang",
            "entities",
            "decimal",
            "hexadecimal",
        ],
        "sanitize_filename": [
            "separator",
            "max_length",
            "platform",
            "lang",
            "preserve_extension",
        ],
        "demojize": ["strip_modifiers", "errors", "replace_with", "provider"],
        "strip_bidi": [],
        "security_clean": [],
        "ml_normalize": ["lang", "emoji"],
        "display_clean": [],
        "grapheme_truncate": ["max_graphemes"],
        "catalog_key": ["lang", "strict_iso9"],
        "is_ascii": [],
        "is_normalized": ["form"],
        "is_confusable": ["target_script"],
        "is_mixed_script": [],
        "detect_scripts": [],
        "grapheme_len": [],
        "grapheme_split": [],
    },
    "TextPipeline": {
        "__init__": [
            "normalize",
            "transliterate",
            "lang",
            "strict_iso9",
            "gost7034",
            "confusables",
            "strip_accents",
            "fold_case",
            "collapse_whitespace",
            "strip_control",
            "strip_zero_width",
            "demojize",
        ],
        "__call__": ["text"],
        "explain": [],
    },
    "Slugifier": {
        "__init__": [
            "separator",
            "lowercase",
            "max_length",
            "word_boundary",
            "save_order",
            "stopwords",
            "regex_pattern",
            "replacements",
            "allow_unicode",
            "lang",
            "entities",
            "decimal",
            "hexadecimal",
        ],
        "__call__": ["text"],
    },
    "UniqueSlugifier": {
        "__init__": [
            "check",
            "separator",
            "lowercase",
            "max_length",
            "word_boundary",
            "save_order",
            "stopwords",
            "regex_pattern",
            "replacements",
            "allow_unicode",
            "lang",
            "entities",
            "decimal",
            "hexadecimal",
        ],
        "__call__": ["text"],
        "reset": [],
    },
}


class TestClassAPIs:
    """Public classes must have the exact expected method signatures."""

    @pytest.mark.parametrize(
        "cls_name,method_name,expected_params",
        [
            pytest.param(cls, method, params, id=f"{cls}.{method}")
            for cls, methods in sorted(CLASS_METHODS.items())
            for method, params in sorted(methods.items())
        ],
    )
    def test_class_method_params(self, cls_name: str, method_name: str, expected_params: list[str]):
        cls = getattr(translit, cls_name)
        method = getattr(cls, method_name)
        actual = _param_names(method)
        assert actual == expected_params, (
            f"{cls_name}.{method_name}() params changed:\n"
            f"  expected: {expected_params}\n"
            f"  actual:   {actual}"
        )

    def test_text_has_value_property(self):
        assert isinstance(inspect.getattr_static(translit.Text, "value"), property), (
            "Text.value must be a property"
        )

    def test_text_pipeline_has_steps_property(self):
        assert isinstance(inspect.getattr_static(translit.TextPipeline, "steps"), property), (
            "TextPipeline.steps must be a property"
        )


# ---------------------------------------------------------------------------
# Enum stability
# ---------------------------------------------------------------------------

EXPECTED_SCRIPT_MEMBERS = {
    "LATIN",
    "CYRILLIC",
    "GREEK",
    "ARABIC",
    "HEBREW",
    "DEVANAGARI",
    "BENGALI",
    "GURMUKHI",
    "GUJARATI",
    "ORIYA",
    "TAMIL",
    "TELUGU",
    "KANNADA",
    "MALAYALAM",
    "MEETEI_MAYEK",
    "OL_CHIKI",
    "SINHALA",
    "HAN",
    "HIRAGANA",
    "KATAKANA",
    "HANGUL",
    "LISU",
    "THAI",
    "LAO",
    "MYANMAR",
    "KHMER",
    "BALINESE",
    "BUGINESE",
    "CHAM",
    "JAVANESE",
    "SUNDANESE",
    "TAGALOG",
    "TAI_LE",
    "TAI_THAM",
    "NEW_TAI_LUE",
    "TIBETAN",
    "MONGOLIAN",
    "GEORGIAN",
    "ARMENIAN",
    "ETHIOPIC",
    "NKO",
    "BAMUM",
    "TIFINAGH",
    "VAI",
    "SYRIAC",
    "THAANA",
    "COPTIC",
    "CHEROKEE",
    "CANADIAN_ABORIGINAL",
    "RUNIC",
    "OGHAM",
    "GOTHIC",
    "OLD_PERSIAN",
    "CUNEIFORM",
    "LINEAR_B",
    "COMMON",
    "INHERITED",
}

EXPECTED_NF_MEMBERS = {"C", "D", "KC", "KD"}


class TestEnumStability:
    """Enum members must not be added or removed without updating these tests."""

    def test_script_members(self):
        actual = {m.name for m in Script}
        missing = EXPECTED_SCRIPT_MEMBERS - actual
        extra = actual - EXPECTED_SCRIPT_MEMBERS
        assert not missing, f"Script enum lost members: {sorted(missing)}"
        assert not extra, f"Script enum gained members: {sorted(extra)}"

    def test_script_member_count(self):
        assert len(Script) == len(EXPECTED_SCRIPT_MEMBERS)

    def test_nf_members(self):
        actual = {m.name for m in NF}
        assert actual == EXPECTED_NF_MEMBERS

    def test_script_is_enum(self):
        import enum

        assert issubclass(Script, enum.Enum)

    def test_nf_is_enum(self):
        import enum

        assert issubclass(NF, enum.Enum)


# ---------------------------------------------------------------------------
# TypedDict stability
# ---------------------------------------------------------------------------


class TestTypedDictStability:
    """TypedDict field names must not change."""

    def test_lang_meta_fields(self):
        hints = get_type_hints(LangMeta)
        assert set(hints.keys()) == {"name", "script", "region", "context"}

    def test_script_meta_fields(self):
        hints = get_type_hints(ScriptMeta)
        assert set(hints.keys()) == {"name", "default_lang", "example", "context_aware"}

    def test_every_script_meta_entry_has_all_required_keys(self):
        # Guard against an entry omitting a required key (regression: the
        # CanadianAboriginal entry was missing "context_aware", which made
        # script_info(...)["context_aware"] raise KeyError). Uses the public
        # SCRIPT_META (imported at module level), not the private _enums one.
        required = set(get_type_hints(ScriptMeta).keys())
        for name, meta in SCRIPT_META.items():
            assert set(meta.keys()) == required, (
                f"SCRIPT_META[{name!r}] keys {set(meta.keys())} != required {required}"
            )


# ---------------------------------------------------------------------------
# Protocol stability
# ---------------------------------------------------------------------------


class TestProtocolStability:
    """EmojiProvider protocol must have the expected interface."""

    def test_emoji_provider_has_lookup(self):
        assert hasattr(EmojiProvider, "lookup")

    def test_emoji_provider_is_runtime_checkable(self):

        # If it's runtime checkable, isinstance checks work
        class FakeProvider:
            def lookup(self, sequence):
                return None

        assert isinstance(FakeProvider(), EmojiProvider)


# ---------------------------------------------------------------------------
# Metadata dict stability
# ---------------------------------------------------------------------------


class TestMetadataStability:
    """LANG_META and SCRIPT_META must have entries for all registered items."""

    def test_lang_meta_is_dict(self):
        assert isinstance(LANG_META, dict)

    def test_script_meta_is_dict(self):
        assert isinstance(SCRIPT_META, dict)

    def test_lang_meta_values_are_typed_dicts(self):
        for code, meta in LANG_META.items():
            assert "name" in meta, f"LANG_META[{code!r}] missing 'name'"
            assert "script" in meta, f"LANG_META[{code!r}] missing 'script'"
            assert "region" in meta, f"LANG_META[{code!r}] missing 'region'"

    def test_script_meta_values_are_typed_dicts(self):
        for name, meta in SCRIPT_META.items():
            assert "name" in meta, f"SCRIPT_META[{name!r}] missing 'name'"
            assert "default_lang" in meta, f"SCRIPT_META[{name!r}] missing 'default_lang'"
            assert "example" in meta, f"SCRIPT_META[{name!r}] missing 'example'"


# ---------------------------------------------------------------------------
# Exception stability
# ---------------------------------------------------------------------------


class TestExceptionStability:
    def test_translit_error_exists(self):
        assert hasattr(translit, "TranslitError")

    def test_translit_error_is_exception(self):
        assert issubclass(translit.TranslitError, Exception)


# ---------------------------------------------------------------------------
# Module callable
# ---------------------------------------------------------------------------


class TestModuleCallable:
    """The translit module itself must be callable (transliterate shorthand)."""

    def test_module_is_callable(self):
        assert callable(translit)
