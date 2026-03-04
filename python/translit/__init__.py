"""translit: Fast Unicode transliteration, slugification, and text normalization."""

from __future__ import annotations

import unicodedata as _unicodedata
from collections.abc import Iterable

from translit._enums import (
    # Non-European languages
    LANG_AR,
    # European languages
    LANG_BG,
    LANG_CA,
    LANG_CS,
    LANG_CY,
    LANG_DA,
    LANG_DE,
    LANG_EL,
    LANG_ES,
    LANG_ET,
    LANG_FI,
    LANG_FR,
    LANG_GA,
    LANG_HR,
    LANG_HU,
    LANG_IS,
    LANG_IT,
    LANG_JA,
    LANG_KO,
    LANG_LT,
    LANG_LV,
    LANG_MT,
    LANG_NL,
    LANG_NO,
    LANG_PL,
    LANG_PT,
    LANG_RO,
    LANG_RU,
    LANG_SK,
    LANG_SL,
    LANG_SQ,
    LANG_SR,
    LANG_SV,
    LANG_TR,
    LANG_UK,
    LANG_VI,
    LANG_ZH,
    Script,
)
from translit._translit import (
    SafeHostnameDetails,
    # Exception
    TranslitError,
    _catalog_key,
    _clear_replacements,
    _collapse_whitespace,
    _decode_to_utf8,
    _demojize,
    # Encoding detection
    _detect_encoding,
    # Predicates
    _detect_scripts,
    _display_clean,
    _fold_case,
    # Grapheme cluster functions
    _grapheme_len,
    _grapheme_split,
    _grapheme_truncate,
    _is_ascii,
    _is_confusable,
    _is_mixed_script,
    _is_normalized,
    # Hostname safety
    _is_safe_hostname,
    # Language profiles
    _list_langs,
    _ml_normalize,
    _normalize,  # noqa: F401  (used by normalize_batch and internal pipelines)
    _normalize_batch,
    _normalize_confusables,
    _register_lang,
    _register_replacements,
    _remove_replacement,
    _sanitize_filename,
    # Precompiled pipelines
    _security_clean,
    # Emoji provider
    _set_emoji_provider,
    # Stateful
    _Slugifier,
    _slugify,
    _slugify_batch,
    _strip_accents,
    _strip_accents_batch,
    _strip_bidi,
    _TextPipeline,
    # Core transforms (Rust implementations)
    _transliterate,
    # Batch APIs (single PyO3 boundary crossing for N strings)
    _transliterate_batch,
    _UniqueSlugifier,
)
from translit._types import NF, EmojiProvider, ErrorMode, NormalizationForm, Platform

# --- Core transforms ---


def transliterate(
    text: str,
    *,
    lang: str | None = None,
    errors: ErrorMode = "replace",
    replace_with: str = "[?]",
    strict_iso9: bool = False,
) -> str:
    """Unicode → ASCII transliteration.

    Args:
        text: Input Unicode string.
        lang: Language code for language-specific mappings.
              e.g. "de" (ü→ue), "ja" (kanji→romaji), "zh" (hanzi→pinyin).
              None uses best-effort default tables.
        errors: How to handle untransliterable characters.
                "replace" — substitute with replace_with.
                "ignore" — silently drop.
                "preserve" — keep the original character.
        replace_with: Replacement string when errors="replace".
        strict_iso9: Use ISO 9:1995 scholarly transliteration for Cyrillic.
                     When True, overrides both default and lang-specific
                     mappings with the international standard used in
                     linguistics and library science (e.g. й→j, ю→ju, я→ja).

    Returns:
        ASCII transliteration of the input.

    Raises:
        TranslitError: If an internal Rust error occurs (e.g. invalid
            ``errors`` value passed at runtime).

    Examples:
        >>> transliterate("café résumé")
        'cafe resume'
        >>> transliterate("München", lang="de")
        'Muenchen'
        >>> transliterate("Москва", lang="ru")
        'Moskva'
        >>> transliterate("★", errors="ignore")
        ''
        >>> transliterate("★", errors="preserve")
        '★'
    """
    # Fast path: pure ASCII needs no transliteration (~30 ns vs ~4 µs PyO3 call).
    if text.isascii():
        return text
    return _transliterate(
        text,
        lang=lang,
        errors=errors,
        replace_with=replace_with,
        strict_iso9=strict_iso9,
    )


def slugify(
    text: str,
    *,
    separator: str = "-",
    lowercase: bool = True,
    max_length: int = 0,
    word_boundary: bool = False,
    save_order: bool = False,
    stopwords: Iterable[str] = (),
    regex_pattern: str | None = None,
    replacements: Iterable[tuple[str, str]] = (),
    allow_unicode: bool = False,
    lang: str | None = None,
    entities: bool = True,
    decimal: bool = True,
    hexadecimal: bool = True,
) -> str:
    """Generate a URL-safe slug from Unicode text.

    Full pipeline: decode entities → transliterate → lowercase →
    strip non-alphanumeric → collapse separators → apply stopwords/max_length.

    Parameter-compatible with python-slugify.

    Args:
        text: Input Unicode string.
        separator: Character(s) between slug words.
        lowercase: Convert to lowercase.
        max_length: Maximum slug length in bytes (0 = unlimited).
            With ``allow_unicode=True``, multi-byte characters count as
            2–4 bytes each — use :func:`grapheme_truncate` for
            character-aware limiting.
        word_boundary: When truncating via max_length, cut at word boundaries.
        save_order: Preserve original word order when applying stopwords.
        stopwords: Words to remove from the slug.
        regex_pattern: Custom regex for stripping characters.
        replacements: Pre-transliteration (old, new) substitution pairs.
        allow_unicode: Keep non-ASCII letters instead of transliterating.
        lang: Language code for transliteration (e.g. "de", "ru").
        entities: Decode HTML entities before processing.
        decimal: Decode HTML decimal entities (&#123;).
        hexadecimal: Decode HTML hex entities (&#x7B;).

    Returns:
        URL-safe slug string.

    Raises:
        TranslitError: If an internal Rust error occurs.
        NotImplementedError: If ``pretranslate`` is passed as a callable
            (only dict is supported in the compatibility shim).

    Examples:
        >>> slugify("Hello World!")
        'hello-world'
        >>> slugify("Straße nach München", lang="de")
        'strasse-nach-muenchen'
        >>> slugify("My Title", separator="_")
        'my_title'
        >>> slugify("The Big Fox", stopwords=["the"])
        'big-fox'
        >>> slugify("Very Long Title Here", max_length=10, word_boundary=True)
        'very-long'
    """
    return _slugify(
        text,
        separator=separator,
        lowercase=lowercase,
        max_length=max_length,
        word_boundary=word_boundary,
        save_order=save_order,
        stopwords=tuple(stopwords),
        regex_pattern=regex_pattern,
        replacements=tuple(replacements),
        allow_unicode=allow_unicode,
        lang=lang,
        entities=entities,
        decimal=decimal,
        hexadecimal=hexadecimal,
    )


def normalize(
    text: str,
    *,
    form: NormalizationForm = "NFC",
) -> str:
    """Unicode normalization.

    Args:
        text: Input string.
        form: Normalization form — "NFC", "NFD", "NFKC", or "NFKD".

    Returns:
        Normalized string.

    Examples:
        >>> normalize("café")  # NFC is default; already NFC → unchanged
        'café'
        >>> normalize("e\u0301", form="NFC")  # NFD e + combining acute → NFC é
        'é'
        >>> normalize("ﬁ", form="NFKC")  # NFKC decomposes ligature
        'fi'

    Note:
        Standalone calls delegate to CPython's ``unicodedata.normalize()``
        (a C extension that operates directly on Python's internal string
        buffer) which is faster than crossing the PyO3 boundary.  The Rust
        implementation (``_normalize``) is still used by precompiled
        pipelines and batch APIs where it runs inside Rust without
        boundary-crossing overhead.
    """
    # Fast path: ASCII is already in all normalization forms.
    if text.isascii():
        return text
    return _unicodedata.normalize(form, text)


def normalize_confusables(
    text: str,
    *,
    target_script: str = "latin",
) -> str:
    """Replace Unicode confusable homoglyphs with target-script equivalents.

    Uses Unicode TR39 confusables table.

    Args:
        text: Input string potentially containing homoglyphs.
        target_script: Script to normalize toward (default "latin").

    Returns:
        String with confusable characters replaced by target-script equivalents.

    Raises:
        TranslitError: If an internal Rust error occurs.

    Examples:
        >>> normalize_confusables("Ηello")  # Greek Η looks like Latin H
        'Hello'
        >>> normalize_confusables("раypal")  # Cyrillic р/а look like Latin p/a
        'paypal'
    """
    return _normalize_confusables(text, target_script=target_script)


def sanitize_filename(
    text: str,
    *,
    separator: str = "_",
    max_length: int = 255,
    platform: Platform = "universal",
    lang: str | None = None,
    preserve_extension: bool = True,
) -> str:
    """Sanitize a string into a safe filename.

    Transliterate → strip OS-illegal chars → collapse separators →
    handle reserved names (CON, NUL, etc.) → truncate respecting extension.

    Args:
        text: Input string (title, user input, etc.).
        separator: Replacement for spaces and stripped characters.
        max_length: Maximum filename length in bytes (default 255).
        platform: Target platform — "universal", "windows", or "posix".
        lang: Language code for transliteration (e.g. "de", "ja").
        preserve_extension: Keep the file extension within max_length.

    Returns:
        Safe filename string.

    Raises:
        TranslitError: If an internal Rust error occurs.

    Examples:
        >>> sanitize_filename("My Report (final).pdf")
        'My_Report_(final).pdf'
        >>> sanitize_filename("CON.txt")  # reserved on Windows
        '_CON.txt'
        >>> sanitize_filename("résumé.docx", lang="fr")
        'resume.docx'
    """
    return _sanitize_filename(
        text,
        separator=separator,
        max_length=max_length,
        platform=platform,
        lang=lang,
        preserve_extension=preserve_extension,
    )


def strip_accents(text: str) -> str:
    """Remove diacritical marks while preserving base characters.

    NFD decompose → strip combining marks → NFC recompose.
    café → cafe, naïve → naive.

    Args:
        text: Input Unicode string.

    Returns:
        String with diacritical marks removed.

    Examples:
        >>> strip_accents("café résumé naïve")
        'cafe resume naive'
        >>> strip_accents("ÀÁÂÃÄÅ")
        'AAAAAA'
        >>> strip_accents("hello")  # pure ASCII: fast path, no-op
        'hello'
    """
    # Fast path: ASCII has no diacritical marks.
    if text.isascii():
        return text
    return _strip_accents(text)


def fold_case(text: str) -> str:
    """Full Unicode case folding per CaseFolding.txt (Unicode 16.0).

    Unlike ``str.lower()``, this implements the complete Unicode Case Folding
    algorithm with all 1,557 status-C and status-F mappings.  Covers Latin
    (ß→ss, ſ→s, İ→i̇), Greek (ς→σ, variant forms ϐ→β, ϑ→θ, ϕ→φ, ϖ→π,
    ϰ→κ, ϱ→ρ), Cyrillic, Armenian (ligature և→եւ), Georgian Mtavruli,
    Cherokee, Adlam, Deseret, Osage, Warang Citi, fullwidth Latin,
    and all Latin ligature expansions (ﬁ→fi, ﬂ→fl, ﬀ→ff, ﬃ→ffi,
    ﬄ→ffl, ﬅ→st, ﬆ→st).

    Equivalent to ``str.casefold()`` but executed in Rust via a
    compile-time PHF (perfect hash function) table.  Pure-ASCII strings
    take a branchless fast path with no table lookup.

    Args:
        text: Input string.

    Returns:
        Case-folded string.  Characters not in CaseFolding.txt map to
        themselves.  Output satisfies ``fold_case(fold_case(x)) == fold_case(x)``
        (idempotent).

    Examples:
        >>> fold_case("Straße")
        'strasse'
        >>> fold_case("ΣΟΦΙΑ")
        'σοφια'
        >>> fold_case("ﬁnd")
        'find'
    """
    return _fold_case(text)


def collapse_whitespace(
    text: str,
    *,
    strip_control: bool = True,
    strip_zero_width: bool = True,
) -> str:
    """Normalize all Unicode whitespace variants to single ASCII spaces.

    Optionally strip control characters and zero-width characters.

    Args:
        text: Input string.
        strip_control: Remove C0/C1 control characters (U+0000–U+001F,
            U+007F–U+009F) except tab/newline/carriage-return.
        strip_zero_width: Remove zero-width space (U+200B), zero-width
            non-joiner (U+200C), zero-width joiner (U+200D), and
            word joiner (U+2060).

    Returns:
        String with whitespace collapsed and optionally cleaned.

    Examples:
        >>> collapse_whitespace("  hello   world  ")
        'hello world'
        >>> collapse_whitespace("tabs\\there\\ttoo")
        'tabs here too'
        >>> collapse_whitespace("a\\u200Bb\\u200Bc")  # zero-width spaces
        'abc'
    """
    return _collapse_whitespace(
        text, strip_control=strip_control, strip_zero_width=strip_zero_width
    )


def demojize(
    text: str,
    *,
    strip_modifiers: bool = False,
    errors: ErrorMode = "replace",
    replace_with: str = "[?]",
    provider: EmojiProvider | None = None,
) -> str:
    """Expand emoji sequences to their CLDR short-name text descriptions.

    Output is always the bare CLDR short name as plain text.

    Args:
        text: Input string potentially containing emoji.
        strip_modifiers: If True, collapse skin tone and hair style variants
            to their base form (e.g. "woman raising hand" instead of
            "woman raising hand: medium-dark skin tone").
        errors: How to handle emoji not in the provider's data.
                "replace" — substitute with replace_with.
                "ignore" — silently drop.
                "preserve" — keep the original emoji.
        replace_with: Replacement string when errors="replace".
        provider: An object implementing the :class:`EmojiProvider` protocol.
            Overrides the global provider for this call.
            None uses the global provider or the built-in default.

    Returns:
        Text with emoji replaced by their descriptions.

    Raises:
        TranslitError: If an internal Rust error occurs or the provider
            raises an exception.

    Examples:
        >>> demojize("I ❤️ Python 🐍")
        'I red heart Python snake'
    """
    return _demojize(
        text,
        strip_modifiers=strip_modifiers,
        errors=errors,
        replace_with=replace_with,
        provider=provider,
    )


def set_emoji_provider(provider: EmojiProvider | None = None) -> None:
    """Set a global emoji provider for all demojize calls.

    The provider must implement the :class:`EmojiProvider` protocol.

    Pass None to reset to the built-in default (latest English CLDR).

    Args:
        provider: An object implementing the :class:`EmojiProvider` protocol,
            or None to reset to the built-in default.

    Examples:
        >>> set_emoji_provider(None)  # reset to default provider
    """
    _set_emoji_provider(provider)


# --- Batch APIs ---
# These process a list of strings in a single PyO3 boundary crossing,
# amortising the ~4 µs per-call overhead across N strings.


def transliterate_batch(
    texts: list[str],
    *,
    lang: str | None = None,
    errors: ErrorMode = "replace",
    replace_with: str = "[?]",
    strict_iso9: bool = False,
) -> list[str]:
    """Batch Unicode → ASCII transliteration.

    Processes all strings in a single Rust call, amortising the PyO3
    boundary-crossing overhead. For N=1000, overhead drops from ~4 ms
    (1000 × 4 µs) to ~4 µs (one crossing).

    Args:
        texts: List of input Unicode strings.
        lang: Language code for language-specific mappings.
        errors: How to handle untransliterable characters.
        replace_with: Replacement string when errors="replace".
        strict_iso9: Use ISO 9:1995 scholarly transliteration for Cyrillic.

    Returns:
        List of ASCII transliterations, same length as input.

    Raises:
        TranslitError: If an internal Rust error occurs.

    Examples:
        >>> transliterate_batch(["café", "naïve", "résumé"])
        ['cafe', 'naive', 'resume']
        >>> transliterate_batch(["München", "Zürich"], lang="de")
        ['Muenchen', 'Zuerich']
    """
    return _transliterate_batch(
        texts,
        lang=lang,
        errors=errors,
        replace_with=replace_with,
        strict_iso9=strict_iso9,
    )


def slugify_batch(
    texts: list[str],
    *,
    separator: str = "-",
    lowercase: bool = True,
    max_length: int = 0,
    word_boundary: bool = False,
    save_order: bool = False,
    stopwords: Iterable[str] = (),
    regex_pattern: str | None = None,
    replacements: Iterable[tuple[str, str]] = (),
    allow_unicode: bool = False,
    lang: str | None = None,
    entities: bool = True,
    decimal: bool = True,
    hexadecimal: bool = True,
) -> list[str]:
    """Batch URL-safe slug generation.

    Processes all strings in a single Rust call.

    Args:
        texts: List of input strings.
        separator: Separator between words (default ``"-"``).
        lowercase: Lowercase the output (default ``True``).
        max_length: Truncate to this many bytes (0 = unlimited).
        word_boundary: Break only at word boundaries when truncating.
        save_order: Preserve original word order when truncating.
        stopwords: Words to remove before slugifying.
        regex_pattern: Custom regex for allowed characters.
        replacements: Character replacement pairs applied before slugifying.
        allow_unicode: Keep non-ASCII letters in the slug.
        lang: Language code for transliteration (e.g. ``"de"``).
        entities: Decode HTML entities.
        decimal: Decode HTML decimal references.
        hexadecimal: Decode HTML hex references.

    Returns:
        List of slugs, same length as input.

    Raises:
        TranslitError: If an internal Rust error occurs.

    Examples:
        >>> slugify_batch(["Hello World", "Foo Bar"])
        ['hello-world', 'foo-bar']
    """
    return _slugify_batch(
        texts,
        separator=separator,
        lowercase=lowercase,
        max_length=max_length,
        word_boundary=word_boundary,
        save_order=save_order,
        stopwords=list(stopwords),
        regex_pattern=regex_pattern,
        replacements=list(replacements),
        allow_unicode=allow_unicode,
        lang=lang,
        entities=entities,
        decimal=decimal,
        hexadecimal=hexadecimal,
    )


def normalize_batch(
    texts: list[str],
    *,
    form: NormalizationForm = "NFC",
) -> list[str]:
    """Batch Unicode normalization.

    Processes all strings in a single Rust call.

    Args:
        texts: List of input strings.
        form: Normalization form — "NFC", "NFD", "NFKC", or "NFKD".

    Returns:
        List of normalized strings, same length as input.

    Examples:
        >>> normalize_batch(["e\u0301", "n\u0303o"], form="NFC")
        ['é', 'ño']
    """
    return _normalize_batch(texts, form=form)


def strip_accents_batch(texts: list[str]) -> list[str]:
    """Batch accent stripping.

    Processes all strings in a single Rust call.

    Args:
        texts: List of input strings.

    Returns:
        List of accent-stripped strings, same length as input.

    Examples:
        >>> strip_accents_batch(["café", "naïve", "résumé"])
        ['cafe', 'naive', 'resume']
    """
    return _strip_accents_batch(texts)


# --- Precompiled pipelines ---


def security_clean(text: str) -> str:
    """Security-focused text canonicalization.

    Pipeline: NFKC → confusables → collapse_whitespace → strip bidi/format

    Collapses fullwidth bypasses, neutralizes homoglyph spoofing, strips
    zero-width injections and control chars, and removes dangerous bidi
    overrides and soft hyphens that could enable text reordering attacks.

    Args:
        text: Input string (user-submitted, network-received, etc.).

    Returns:
        Canonicalized string safe for security-sensitive comparisons.

    Examples:
        >>> security_clean("Ηello Ꮤorld")  # Greek Η + Cherokee Ꮤ → Latin
        'Hello World'
    """
    return _security_clean(text)


def ml_normalize(
    text: str,
    *,
    lang: str | None = None,
    emoji: str = "cldr",
) -> str:
    """ML/NLP text normalization pipeline.

    Pipeline: NFKC → emoji→text → [transliterate] → strip_accents →
              fold_case → collapse_whitespace

    Produces clean, accent-free, lowercased text suitable for tokenizers,
    embeddings, and feature extraction. Emoji are expanded to their CLDR
    short-name descriptions.

    Args:
        text: Input Unicode string.
        lang: Optional language code for transliteration (e.g. "de", "ja").
        emoji: Emoji handling — "cldr" expands to CLDR short names,
               "none" leaves emoji as-is.

    Returns:
        Clean, accent-free, lowercased text.

    Raises:
        TranslitError: If an internal Rust error occurs.

    Examples:
        >>> ml_normalize("Café RÉSUMÉ")
        'cafe resume'
        >>> ml_normalize("München", lang="de")
        'muenchen'
    """
    return _ml_normalize(text, lang=lang, emoji_style=emoji)


def catalog_key(
    text: str,
    *,
    lang: str | None = None,
    strict_iso9: bool = False,
) -> str:
    """Library catalog key generation pipeline.

    Pipeline: NFKC → confusables → [transliterate] → strip_accents →
              fold_case → collapse_whitespace

    Produces a canonical deduplication key for bibliographic titles.

    Args:
        text: Input title or heading.
        lang: Language code for transliteration (e.g. "ru", "ja").
        strict_iso9: Use ISO 9:1995 scholarly transliteration for Cyrillic.

    Returns:
        Canonical deduplication key string.

    Raises:
        TranslitError: If an internal Rust error occurs.

    Examples:
        >>> catalog_key("  Café  RÉSUMÉ  ")
        'cafe resume'
        >>> catalog_key("ΩMEGA  café")
        'ωmega cafe'
    """
    return _catalog_key(text, lang=lang, strict_iso9=strict_iso9)


def display_clean(text: str) -> str:
    """Display-safe text cleaning pipeline.

    Pipeline: collapse_whitespace (strip control + strip zero-width)

    Lightweight cleanup for user-submitted content destined for rendering.
    Strips control characters and zero-width injections, collapses runs of
    whitespace to single spaces.

    Args:
        text: Input string (user-submitted content).

    Returns:
        Cleaned string safe for display rendering.

    Examples:
        >>> display_clean("hello\\x00world\\u200b!")
        'helloworld!'
        >>> display_clean("  spaced   out  ")
        'spaced out'
    """
    return _display_clean(text)


def strip_bidi(text: str) -> str:
    """Strip bidirectional override and formatting characters (UAX #9).

    Removes: soft hyphen (U+00AD), Arabic Letter Mark (U+061C),
    LRM/RLM (U+200E/F), bidi embeddings/overrides (U+202A–U+202E),
    bidi isolates (U+2066–U+2069).

    Args:
        text: Input string.

    Returns:
        String with bidi override and formatting characters removed.

    Examples:
        >>> strip_bidi("hello\\u200eworld")  # remove LRM
        'helloworld'
        >>> strip_bidi("hello\\u061cworld")  # remove Arabic Letter Mark
        'helloworld'
        >>> strip_bidi("safe text")  # no bidi chars → unchanged
        'safe text'
    """
    return _strip_bidi(text)


# --- Grapheme cluster functions ---


def grapheme_len(text: str) -> int:
    """Count the number of user-perceived characters (extended grapheme clusters).

    This is the correct answer to "how many characters does the user see?"
    A single grapheme cluster may span multiple codepoints (e.g., flag emoji,
    skin-toned emoji, Hangul syllables with combining jamo, Zalgo text).

    Args:
        text: Input string.

    Returns:
        Number of extended grapheme clusters.

    Examples:
        >>> grapheme_len("café")
        4
        >>> grapheme_len("👨‍👩‍👧‍👦")  # family emoji = 1 grapheme cluster
        1
    """
    return _grapheme_len(text)


def grapheme_split(text: str) -> list[str]:
    """Split text into a list of extended grapheme clusters.

    Each element is a user-perceived character.

    Args:
        text: Input string.

    Returns:
        List of grapheme cluster strings.

    Examples:
        >>> grapheme_split("café")
        ['c', 'a', 'f', 'é']
        >>> len(grapheme_split("👨‍👩‍👧‍👦!"))  # family emoji + "!"
        2
    """
    return _grapheme_split(text)


def grapheme_truncate(text: str, max_graphemes: int) -> str:
    """Truncate text to at most max_graphemes user-perceived characters.

    Unlike byte-level or codepoint-level truncation, this never splits
    a grapheme cluster (which could corrupt emoji, combining sequences,
    or Hangul syllables).

    Args:
        text: Input string.
        max_graphemes: Maximum number of grapheme clusters to keep.

    Returns:
        Truncated string containing at most max_graphemes grapheme clusters.

    Examples:
        >>> grapheme_truncate("Hello World", 5)
        'Hello'
        >>> grapheme_truncate("café", 3)
        'caf'
    """
    return _grapheme_truncate(text, max_graphemes)


# --- Hostname safety ---


def is_safe_hostname(hostname: str) -> tuple[bool, SafeHostnameDetails]:
    """Check if a hostname is safe from Unicode homoglyph attacks.

    Returns (is_safe, details) where details is a ``SafeHostnameDetails``
    with attributes:

    - ``safe``: bool — True if no homoglyph spoofing detected.
    - ``scripts``: list[str] — Unicode scripts found across all labels.
    - ``mixed_script``: bool — True if multiple scripts detected.
    - ``has_confusables``: bool — True if confusable homoglyphs found.
    - ``canonical``: str — Latin-normalized form of the hostname.

    A hostname is considered unsafe if it contains mixed high-risk scripts
    (Cyrillic+Latin, Greek+Latin) or confusable homoglyphs.

    Args:
        hostname: Hostname string to check (e.g. "example.com").

    Returns:
        Tuple of (is_safe, details) where details is a SafeHostnameDetails.

    Examples:
        >>> safe, details = is_safe_hostname("google.com")
        >>> safe
        True
        >>> details.canonical
        'google.com'
    """
    return _is_safe_hostname(hostname)


# --- Encoding detection ---


def detect_encoding(data: bytes) -> tuple[str, float]:
    """Detect the encoding of a byte sequence.

    Returns (encoding_name, confidence) where confidence is 0.0–1.0.
    Uses the chardetng algorithm (Firefox's encoding detector).

    Important: automatic encoding detection is inherently probabilistic.
    A high confidence score does NOT guarantee correctness. For critical
    pipelines, always prefer explicit encoding metadata over detection.

    Args:
        data: Raw byte sequence to analyze.

    Returns:
        Tuple of (encoding_name, confidence) where confidence is 0.0–1.0.

    Raises:
        TranslitError: If the byte sequence cannot be analyzed.

    Examples:
        >>> enc, conf = detect_encoding(b"Hello World")
        >>> enc
        'UTF-8'
    """
    return _detect_encoding(data)


def decode_to_utf8(data: bytes, encoding: str | None = None) -> tuple[str, bool]:
    """Decode a byte sequence to UTF-8.

    Returns (decoded_text, had_errors) where had_errors is True if any
    characters were replaced during decoding (lossy conversion).

    If encoding is None, auto-detects the encoding.
    Supports all WHATWG encodings (UTF-8, windows-1252, ISO-8859-1,
    Shift_JIS, EUC-JP, EUC-KR, Big5, GB18030, etc.).

    Args:
        data: Raw byte sequence to decode.
        encoding: Encoding name (e.g. "windows-1252"). None to auto-detect.

    Returns:
        Tuple of (decoded_text, had_errors) where had_errors is True if
        any characters were replaced during lossy conversion.

    Raises:
        TranslitError: If the encoding name is unknown or decoding fails.

    Examples:
        >>> text, had_errors = decode_to_utf8(b"caf\\xe9", "windows-1252")
        >>> text
        'café'
        >>> had_errors
        False
    """
    return _decode_to_utf8(data, encoding=encoding)


# --- Predicates ---


def detect_scripts(text: str) -> list[Script]:
    """Return the set of Unicode scripts present in text, in order of first appearance.

    Args:
        text: Input string.

    Returns:
        List of :class:`Script` enum values, ordered by first appearance.

    Examples:
        >>> detect_scripts("Hello")
        [Script.LATIN]
        >>> detect_scripts("Hello Мир")
        [Script.LATIN, Script.CYRILLIC]
    """
    import warnings

    raw = _detect_scripts(text)
    result = []
    for name in raw:
        try:
            result.append(Script(name))
        except ValueError:
            warnings.warn(
                f"Rust detected script {name!r} which is not in the Script enum; "
                f"upgrade translit or report this as a bug",
                stacklevel=2,
            )
    return result


def is_mixed_script(text: str) -> bool:
    """True if text contains characters from more than one Unicode script.

    Args:
        text: Input string.

    Returns:
        True if multiple scripts detected (excluding Common/Inherited).

    Examples:
        >>> is_mixed_script("Hello")
        False
        >>> is_mixed_script("Hello Мир")  # Latin + Cyrillic
        True
    """
    return _is_mixed_script(text)


def is_confusable(
    text: str,
    *,
    target_script: str = "latin",
) -> bool:
    """True if text contains characters confusable with target-script characters.

    Args:
        text: Input string.
        target_script: Script to check confusability against (default "latin").

    Returns:
        True if any confusable homoglyphs are present.

    Examples:
        >>> is_confusable("pаypal")  # Cyrillic а looks like Latin a
        True
        >>> is_confusable("paypal")  # all genuine Latin
        False
    """
    return _is_confusable(text, target_script=target_script)


def is_ascii(text: str) -> bool:
    """True if all characters are in U+0000–U+007F.

    Args:
        text: Input string.

    Returns:
        True if the string is pure ASCII.

    Examples:
        >>> is_ascii("hello 123")
        True
        >>> is_ascii("café")
        False
    """
    return _is_ascii(text)


def is_normalized(
    text: str,
    *,
    form: NormalizationForm = "NFC",
) -> bool:
    """True if text is already in the specified normalization form.

    Args:
        text: Input string.
        form: Normalization form — "NFC", "NFD", "NFKC", or "NFKD".

    Returns:
        True if the string is already normalized.

    Examples:
        >>> is_normalized("café")  # NFC by default
        True
        >>> is_normalized("e\\u0301", form="NFC")  # NFD decomposed
        False
    """
    return _is_normalized(text, form=form)


# --- Stateful objects ---


class Slugifier:
    """Reusable configured slugifier. Call instance as slugifier(text) -> str.

    Examples:
        >>> s = Slugifier(separator="_", lang="de")
        >>> s("Ärger im Büro")
        'aerger_im_buero'
    """

    def __init__(
        self,
        *,
        separator: str = "-",
        lowercase: bool = True,
        max_length: int = 0,
        word_boundary: bool = False,
        save_order: bool = False,
        stopwords: Iterable[str] = (),
        regex_pattern: str | None = None,
        replacements: Iterable[tuple[str, str]] = (),
        allow_unicode: bool = False,
        lang: str | None = None,
        entities: bool = True,
        decimal: bool = True,
        hexadecimal: bool = True,
    ) -> None:
        self._inner = _Slugifier(
            separator=separator,
            lowercase=lowercase,
            max_length=max_length,
            word_boundary=word_boundary,
            save_order=save_order,
            stopwords=tuple(stopwords),
            regex_pattern=regex_pattern,
            replacements=tuple(replacements),
            allow_unicode=allow_unicode,
            lang=lang,
            entities=entities,
            decimal=decimal,
            hexadecimal=hexadecimal,
        )

    def __call__(self, text: str) -> str:
        return self._inner.slugify(text)

    def __repr__(self) -> str:
        return (
            f"Slugifier(separator={self._inner.separator!r}, lang={self._inner.lang!r})"
        )


class UniqueSlugifier:
    """Stateful slugifier that tracks previously generated slugs.

    Appends incrementing suffixes for uniqueness.
    Optional check callback for external uniqueness (e.g. database lookup).

    Examples:
        >>> u = UniqueSlugifier()
        >>> u("My Post")
        'my-post'
        >>> u("My Post")
        'my-post-1'
    """

    def __init__(
        self,
        *,
        check: object | None = None,
        separator: str = "-",
        lowercase: bool = True,
        max_length: int = 0,
        word_boundary: bool = False,
        save_order: bool = False,
        stopwords: Iterable[str] = (),
        regex_pattern: str | None = None,
        replacements: Iterable[tuple[str, str]] = (),
        allow_unicode: bool = False,
        lang: str | None = None,
        entities: bool = True,
        decimal: bool = True,
        hexadecimal: bool = True,
    ) -> None:
        self._inner = _UniqueSlugifier(
            check=check,
            separator=separator,
            lowercase=lowercase,
            max_length=max_length,
            word_boundary=word_boundary,
            save_order=save_order,
            stopwords=tuple(stopwords),
            regex_pattern=regex_pattern,
            replacements=tuple(replacements),
            allow_unicode=allow_unicode,
            lang=lang,
            entities=entities,
            decimal=decimal,
            hexadecimal=hexadecimal,
        )

    def __call__(self, text: str) -> str:
        return self._inner.slugify(text)

    def reset(self) -> None:
        """Clear the internal set of seen slugs."""
        self._inner.reset()

    def __repr__(self) -> str:
        return "UniqueSlugifier()"


class TextPipeline:
    """Composable, pre-compiled text cleaning pipeline.

    Operations execute in fixed optimal order regardless of construction order.

    Examples:
        >>> pipe = TextPipeline(normalize="NFC", fold_case=True, collapse_whitespace=True)
        >>> pipe("  Héllo  WÖRLD  ")
        'héllo wörld'
    """

    def __init__(
        self,
        *,
        normalize: NormalizationForm | None = None,
        transliterate: bool = False,
        lang: str | None = None,
        strict_iso9: bool = False,
        confusables: bool = False,
        strip_accents: bool = False,
        fold_case: bool = False,
        collapse_whitespace: bool = False,
        strip_control: bool = True,
        strip_zero_width: bool = True,
        demojize: bool = False,
    ) -> None:
        self._inner = _TextPipeline(
            normalize=normalize,
            transliterate=transliterate,
            lang=lang,
            strict_iso9=strict_iso9,
            confusables=confusables,
            strip_accents=strip_accents,
            fold_case=fold_case,
            collapse_whitespace=collapse_whitespace,
            strip_control=strip_control,
            strip_zero_width=strip_zero_width,
            demojize=demojize,
        )

    def __call__(self, text: str) -> str:
        return self._inner.process(text)

    def __repr__(self) -> str:
        return "TextPipeline()"


# --- Language profiles ---


def list_langs() -> list[str]:
    """Return available language codes for transliteration.

    Returns:
        Sorted list of language code strings (e.g. ["ar", "bg", "de", ...]).

    Raises:
        TranslitError: If the language table lock is poisoned.

    Examples:
        >>> "de" in list_langs()
        True
        >>> "ja" in list_langs()
        True
    """
    return _list_langs()


def register_lang(code: str, mappings: dict[str, str]) -> None:
    """Register or override a transliteration mapping for a language code.

    Args:
        code: Language code string (e.g. "xx", "custom").
        mappings: Dict of source→replacement character mappings.

    Raises:
        TranslitError: If the language table lock is poisoned or the
            mapping cannot be stored.

    Examples:
        >>> register_lang("xx", {"Ä": "Ae", "ä": "ae", "Ö": "Oe", "ö": "oe"})
        >>> transliterate("Ärger", lang="xx")
        'Aerger'
    """
    _register_lang(code, mappings)


def register_replacements(replacements: dict[str, str]) -> None:
    """Register global pre-transliteration replacements.

    New entries are merged into the existing table. Existing keys are
    silently overwritten. Use :func:`clear_replacements` to wipe the
    table, or :func:`remove_replacement` to remove a single key.

    Args:
        replacements: Dict of source→replacement string mappings, applied
            before the main transliteration tables.

    Examples:
        >>> register_replacements({"©": "(c)", "®": "(r)"})
    """
    _register_replacements(replacements)


def remove_replacement(key: str) -> bool:
    """Remove a single global pre-transliteration replacement by key.

    Args:
        key: The source string to remove from the replacement table.

    Returns:
        True if the key was present and removed, False otherwise.

    Examples:
        >>> register_replacements({"©": "(c)"})
        >>> remove_replacement("©")
        True
        >>> remove_replacement("©")
        False
    """
    return _remove_replacement(key)


def clear_replacements() -> None:
    """Clear all global pre-transliteration replacements.

    Examples:
        >>> register_replacements({"©": "(c)", "®": "(r)"})
        >>> clear_replacements()
    """
    _clear_replacements()


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
    # Transforms
    "transliterate",
    "slugify",
    "normalize",
    "normalize_confusables",
    "sanitize_filename",
    "strip_accents",
    "fold_case",
    "collapse_whitespace",
    "demojize",
    "set_emoji_provider",
    # Batch APIs
    "transliterate_batch",
    "slugify_batch",
    "normalize_batch",
    "strip_accents_batch",
    # Precompiled pipelines
    "security_clean",
    "ml_normalize",
    "catalog_key",
    "display_clean",
    "strip_bidi",
    # Grapheme clusters
    "grapheme_len",
    "grapheme_split",
    "grapheme_truncate",
    # Hostname safety
    "is_safe_hostname",
    "SafeHostnameDetails",
    # Encoding detection
    "detect_encoding",
    "decode_to_utf8",
    # Predicates
    "detect_scripts",
    "is_mixed_script",
    "is_confusable",
    "is_ascii",
    "is_normalized",
    # Stateful / builders
    "Text",
    "Slugifier",
    "UniqueSlugifier",
    "TextPipeline",
    # Language profiles
    "list_langs",
    "register_lang",
    "register_replacements",
    "remove_replacement",
    "clear_replacements",
    # Enums, protocols & constants
    "EmojiProvider",
    "NF",
    "Script",
    "LANG_BG",
    "LANG_CA",
    "LANG_CS",
    "LANG_CY",
    "LANG_DA",
    "LANG_DE",
    "LANG_EL",
    "LANG_ES",
    "LANG_ET",
    "LANG_FI",
    "LANG_FR",
    "LANG_GA",
    "LANG_HR",
    "LANG_HU",
    "LANG_IS",
    "LANG_IT",
    "LANG_LT",
    "LANG_LV",
    "LANG_MT",
    "LANG_NL",
    "LANG_NO",
    "LANG_PL",
    "LANG_PT",
    "LANG_RO",
    "LANG_SK",
    "LANG_SL",
    "LANG_SQ",
    "LANG_SR",
    "LANG_SV",
    "LANG_TR",
    "LANG_UK",
    "LANG_VI",
    "LANG_AR",
    "LANG_JA",
    "LANG_KO",
    "LANG_RU",
    "LANG_ZH",
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
