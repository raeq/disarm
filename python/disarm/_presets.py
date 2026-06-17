"""Precompiled pipeline presets and named policy profiles.

These compose the public transforms in :mod:`disarm._api` (and the Rust
backend) into ready-made canonicalization pipelines.  Re-exported from the
``disarm`` package root.
"""

from __future__ import annotations

from disarm._api import TextPipeline
from disarm._core import (
    _catalog_key,
    _display_clean,
    _get_pipeline,
    _is_zalgo,
    _list_profiles,
    _ml_normalize,
    _normalize_user_input,
    _search_key,
    _security_clean,
    _sort_key,
    _strip_bidi,
    _strip_noncharacters,
    _strip_obfuscation,
    _strip_pua,
    _strip_tags,
    _strip_variation_selectors,
    _strip_zalgo,
)

# --- Precompiled pipelines ---


def security_clean(text: str) -> str:
    """Security-focused text canonicalization.

    Pipeline: NFKC → strip bidi/format → collapse_whitespace → NFC → confusables → NFC → (path-separator neutralization)

    Collapses fullwidth bypasses, neutralizes homoglyph spoofing, strips
    dangerous bidi overrides and soft hyphens, then normalizes whitespace
    (collapsing runs, stripping control chars and zero-width injections).

    .. warning::
       Canonicalizes Unicode for *comparison*; it is **not** an output
       sanitizer and provides no XSS/HTML/SQL/injection protection. The NFKC
       step maps fullwidth lookalikes to live ASCII metacharacters by design
       (``＜`` → ``<``), so the output may be *more* important to context-encode
       on the way out, not less. Encode at the sink; never emit this result
       into markup or a query unescaped.

    Args:
        text: Input string (user-submitted, network-received, etc.).

    Returns:
        A canonicalized string suitable for security-sensitive *comparison*
        (e.g. against a denylist). **Not** safe to emit unescaped into any
        execution or markup context — see warning above.

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
        emoji: Emoji handling mode.
               ``"cldr"`` — expand emoji to CLDR short names (default).
               ``"none"`` — leave emoji characters unchanged.

    Returns:
        Clean, accent-free, lowercased text.

    Raises:
        InvalidArgumentError: If *emoji* is not ``"cldr"`` or ``"none"``.
        DisarmError: If an internal Rust error occurs (base of the above).

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

    Pipeline: NFKC → transliterate → confusables → strip_accents →
              fold_case → collapse_whitespace

    Produces a canonical deduplication key for bibliographic titles.

    Args:
        text: Input title or heading.
        lang: Language code for transliteration (e.g. "ru", "ja").
        strict_iso9: Use ISO 9:1995 scholarly transliteration for Cyrillic.

    Returns:
        Canonical deduplication key string.

    Raises:
        DisarmError: If an internal Rust error occurs.

    Examples:
        >>> catalog_key("  Café  RÉSUMÉ  ")
        'cafe resume'
        >>> catalog_key("ΩMEGA  café")
        'omega cafe'
    """
    return _catalog_key(text, lang=lang, strict_iso9=strict_iso9)


def display_clean(text: str) -> str:
    """Display-safe text cleaning pipeline.

    Pipeline: strip bidi/format → collapse_whitespace (strip control + strip zero-width)

    Lightweight cleanup for user-submitted content destined for rendering.
    Strips bidirectional overrides (which can visually reorder text to hide
    malicious content), soft hyphens, control characters, and zero-width
    injections, then collapses runs of whitespace to single spaces.

    .. warning::
       "Display-safe" means *visual* hygiene (no bidi reordering, no invisible
       injections) — **not** markup-safe. This does no HTML escaping and does
       not strip ``<``, ``>``, ``&``. When rendering into HTML, still escape at
       the template/output layer; disarm is not an XSS defense.

    Args:
        text: Input string (user-submitted content).

    Returns:
        A visually cleaned string. **Escape it at the output layer** before
        rendering into HTML or any other markup context (see warning above).

    Examples:
        >>> display_clean("hello\\x00world\\u200b!")
        'helloworld!'
        >>> display_clean("  spaced   out  ")
        'spaced out'
    """
    return _display_clean(text)


def search_key(
    text: str,
    *,
    lang: str | None = None,
) -> str:
    """Search index key generation pipeline.

    Pipeline: NFKC → transliterate → strip_accents → fold_case →
              collapse_whitespace

    Produces a case-insensitive, accent-insensitive, script-insensitive
    lookup key.  Like :func:`catalog_key` but without confusable
    normalization — lighter and faster for search indexes.

    Args:
        text: Input text to generate a search key from.
        lang: Language code for transliteration (e.g. "ru", "de").

    Returns:
        Normalized search key string.

    Examples:
        >>> search_key("  Café  RÉSUMÉ  ")
        'cafe resume'
        >>> search_key("Москва")
        'moskva'
        >>> search_key("Über allen Gipfeln")
        'uber allen gipfeln'
    """
    return _search_key(text, lang=lang)


def sort_key(
    text: str,
    *,
    lang: str | None = None,
) -> str:
    """Sort key generation pipeline.

    Pipeline: NFKC → strip_bidi → transliterate-non-Latin → fold_case →
    collapse_whitespace

    A case-insensitive collation key that, unlike :func:`search_key`,
    **preserves base accented characters** rather than folding them away.
    It keeps the accent so accented and unaccented forms stay distinct
    (``"Über"`` folds to ``"über"``, not ``"uber"``) and the accent survives
    for a locale-aware collator. Non-Latin scripts are still folded to a
    consistent Latin form (``"Война"`` → ``"voyna"``) so cross-script titles
    interfile. This is the collation counterpart to :func:`search_key`, which
    folds accents away for exact-match lookup — the two are deliberately *not*
    interchangeable for accented Latin input.

    Note: the result is a normalized string, not a UCA collation-weight key, so
    comparing keys with plain codepoint ordering will *not* interfile ``über``
    with ASCII ``u…`` words. Pass the key to a Unicode/locale collator when
    linguistically-correct order matters; the value here is that the accent is
    preserved for it rather than folded away.

    Because Latin letters are preserved verbatim, ``lang`` only affects
    transliteration of non-Latin runs; an accented Latin letter is never expanded
    by a language profile here (e.g. ``sort_key("Über", lang="de")`` is
    ``"über"``, whereas ``search_key("Über", lang="de")`` is ``"ueber"``).

    Args:
        text: Input text to generate a sort key from.
        lang: Language code for transliteration of non-Latin scripts
            (e.g. "ru", "de").

    Returns:
        Normalized sort key string.

    Examples:
        >>> sort_key("Война и мир")
        'voyna i mir'
        >>> sort_key("Über allen Gipfeln")
        'über allen gipfeln'
        >>> sort_key("  Café  ")
        'café'
    """
    return _sort_key(text, lang=lang)


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


def strip_tags(text: str) -> str:
    """Strip the Unicode Tags block (U+E0000–U+E007F) — the "ASCII smuggling" channel.

    Preserves well-formed emoji subdivision flag sequences (``U+1F3F4`` + tag
    letters + ``U+E007F``, e.g. the Scotland flag); stray tag characters
    (including the deprecated language tag ``U+E0001``) are removed.

    Examples:
        >>> strip_tags("hi\\U000e0050\\U000e0057\\U000e004e")  # tag-encoded "PWN"
        'hi'
    """
    return _strip_tags(text)


def strip_variation_selectors(text: str) -> str:
    """Strip every variation selector (VS1–VS16 and VS17–VS256).

    These are the arbitrary-byte smuggling channel. Use ``display_clean`` if you
    need to keep the VS15/VS16 presentation selectors for rendering.

    Examples:
        >>> strip_variation_selectors("g\\ufe01data")  # VS2
        'gdata'
    """
    return _strip_variation_selectors(text)


def strip_noncharacters(text: str) -> str:
    """Strip every Unicode noncharacter (U+FDD0–U+FDEF, and U+xFFFE/U+xFFFF per plane).

    Examples:
        >>> strip_noncharacters("a\\ufffeb")
        'ab'
    """
    return _strip_noncharacters(text)


def strip_pua(text: str) -> str:
    """Strip every Private Use Area code point (BMP and planes 15/16).

    PUA renders as arbitrary, font-defined glyphs (icon fonts, platform logos).
    Stripped by the comparison presets; use this helper to apply the same policy
    directly, or ``display_clean`` to *preserve* PUA for rendering.

    Examples:
        >>> strip_pua("a\\ue000b")
        'ab'
    """
    return _strip_pua(text)


def normalize_user_input(text: str) -> str:
    """Unicode hygiene for user-submitted input — **not** an injection defense.

    .. warning::
       This normalizes Unicode; it does **not** make text safe to emit into
       HTML, JS, URLs, SQL, or shells. It performs no escaping and does not
       strip ``<``, ``>``, ``&`` — ``<script>alert(1)</script>`` passes through
       unchanged, and the NFKC step can *surface* ASCII metacharacters from
       fullwidth lookalikes (``＜script＞`` → ``<script>``). This is **not** XSS
       or injection protection: encode at the output sink (framework
       auto-escaping, DOMPurify, parameterized queries). Run this *before* that
       encoder, never instead of it. The name predates this clarification.

    Preserves the original script (no transliteration) while neutralizing
    Unicode-level attack vectors: zalgo stacking, homoglyph spoofing, bidi
    overrides, zero-width injections, and control characters.

    Pipeline: ``NFKC → strip_bidi → strip_zero_width → strip_control → strip_zalgo
    → confusables → collapse_whitespace → (path-separator neutralization)`` (invisibles are stripped before zalgo-capping so they
    cannot split combining-mark runs, keeping the output idempotent)

    Args:
        text: User-submitted input string.

    Returns:
        A Unicode-normalized string. Safe for storage/comparison; **encode it
        before emitting into any markup or query context** (see warning above).

    Examples:
        >>> normalize_user_input("Hello, world!")
        'Hello, world!'
        >>> normalize_user_input("p\\u0430ypal")  # Cyrillic а → Latin a
        'paypal'
        >>> normalize_user_input("admin\\u202euser")  # RLO stripped
        'adminuser'
    """
    return _normalize_user_input(text)


def strip_obfuscation(text: str) -> str:
    """Maximum-strength text deobfuscation.

    Neutralizes homoglyph spoofing, zalgo abuse, invisible character
    injection, and bidi attacks. Uses TR39 confusable mapping (visual
    similarity) — Cyrillic р→p, с→c, В→B — not phonetic transliteration.

    **Not an output sanitizer.** Resolves *Unicode* obfuscation only; performs
    no HTML/JS/SQL escaping and does not strip ``<``, ``>``, ``&``. Encode at
    the output sink — this is not XSS or injection protection.

    **Does not transliterate.** Non-Latin scripts that have no Latin
    confusable equivalent pass through unchanged. Chain with
    ``transliterate()`` explicitly if you also need romanization.

    **Preserves case.** Case is not deception — proper nouns, acronyms,
    and sentence boundaries are meaningful. Chain with ``fold_case()``
    if lowercasing is also needed.

    Pipeline: ``NFKC → strip_zalgo(max_marks=0) → strip_bidi → strip_zero_width
    → demojize → confusables → strip_accents → collapse_whitespace``
    (confusables runs after demojize so typographic punctuation in emoji names is
    folded too, keeping the output idempotent)

    Args:
        text: Input text (user-generated, adversarial, multilingual).

    Returns:
        Deobfuscated string with homoglyphs resolved, zalgo stripped,
        invisible characters removed. Case is preserved.

    Examples:
        >>> strip_obfuscation("P\\u0430yP\\u0430l")  # Cyrillic а → Latin a
        'PayPal'
        >>> strip_obfuscation("\\u0420rodu\\u0441t")  # Cyrillic Р→P, с→c
        'Product'
        >>> strip_obfuscation("H\\u0338a\\u0338t\\u0338e\\u0338 speech")
        'Hate speech'
    """
    return _strip_obfuscation(text)


def is_zalgo(text: str, *, threshold: int = 3) -> bool:
    """Detect whether text contains zalgo-style combining mark abuse.

    Returns ``True`` if any base character has more than *threshold*
    consecutive combining marks in NFD decomposition.

    Args:
        text: Input string to check.
        threshold: Maximum allowed combining marks per base character
            (default: ``3``).  Vietnamese ``ệ`` has 2 marks in NFD —
            the default is safe for all legitimate scripts.

    Returns:
        ``True`` if zalgo-style stacking is detected.

    Examples:
        >>> is_zalgo("café")
        False
        >>> is_zalgo("Việt Nam")
        False
        >>> is_zalgo("ḧ̸̡̢̧̛̗̱̜̼̯̞̙́̑̾̊̿̏̒̓̕ě̵̢̧̛̗̱̜̼̯̞̙̈́̑̾̊̿̏̒̓̕l̸̡̢̧̛̗̱̜̼̯̞̙̈́̑̾̊̿̏̒̓̕l̸̡̢̧̛̗̱̜̼̯̞̙̈́̑̾̊̿̏̒̓̕ơ̵̢̧̗̱̜̼̯̞̙̈́̑̾̊̿̏̒̓̕")
        True
    """
    return _is_zalgo(text, threshold=threshold)


def strip_zalgo(text: str, *, max_marks: int = 2) -> str:
    """Strip excessive combining marks, preserving legitimate diacritics.

    Caps the number of combining marks per base character at *max_marks*.
    Operates in NFD space and recomposes to NFC.

    Args:
        text: Input string (may contain zalgo abuse).
        max_marks: Maximum combining marks to keep per base character
            (default: ``2``).  Set to ``0`` to strip all combining marks
            (equivalent to :func:`strip_accents`).

    Returns:
        String with excess combining marks removed.

    Examples:
        >>> strip_zalgo("café")  # 1 combining mark — preserved
        'café'
        >>> strip_zalgo("Việt Nam")  # 2 marks — preserved
        'Việt Nam'
    """
    return _strip_zalgo(text, max_marks=max_marks)


# --- Preset pipeline metadata ---

PRESETS: dict[str, list[tuple[str, str | None]]] = {
    "security_clean": [
        ("normalize", "NFKC"),
        ("strip_bidi", None),
        # #413: strip Unicode Tags / variation selectors / CGJ / noncharacters /
        # PUA (keeping valid emoji flags). "comparison" = strip PUA, strip all VS.
        ("strip_invisibles", "comparison"),
        ("collapse_whitespace", None),
        # #429: cap combining marks at 2 per base (anti-zalgo). After
        # collapse_whitespace so a stripped control/zero-width between marks cannot
        # split a mark run and hide the count (#121).
        ("strip_zalgo", None),
        # NFC sandwich around confusables (#416): the strips can leave a base next
        # to a combining mark; the first NFC composes it so the fold sees a
        # consistent form, the second recomposes the fold's output. TR39
        # skeletoning is not normalization-stable, so without this the pipeline is
        # not a fixed point (f(f(x)) != f(x)).
        ("normalize", "NFC"),
        ("confusables", "latin"),
        ("normalize", "NFC"),
    ],
    "ml_normalize": [
        ("normalize", "NFKC"),
        ("demojize", "cldr"),
        ("strip_accents", None),
        ("fold_case", None),
        ("collapse_whitespace", None),
    ],
    "catalog_key": [
        ("normalize", "NFKC"),
        ("strip_bidi", None),
        ("transliterate", None),
        ("confusables", "latin"),
        ("strip_accents", None),
        ("fold_case", None),
        ("collapse_whitespace", None),
    ],
    "display_clean": [
        ("strip_bidi", None),
        # #413: rendering policy — keep VS15/VS16 after a base and PRESERVE the PUA
        # (icon fonts); still strip Tags (keeping flags), CGJ, and noncharacters.
        ("strip_invisibles", "rendering"),
        ("collapse_whitespace", None),
    ],
    "search_key": [
        ("normalize", "NFKC"),
        ("strip_bidi", None),
        ("transliterate", None),
        ("strip_accents", None),
        ("fold_case", None),
        ("collapse_whitespace", None),
    ],
    "sort_key": [
        ("normalize", "NFKC"),
        ("strip_bidi", None),
        # "non_latin": transliterate folds only non-Latin scripts; base accented
        # Latin characters are preserved so the accent can order the key (this is
        # what distinguishes sort_key from search_key, which strips accents here).
        ("transliterate", "non_latin"),
        ("fold_case", None),
        ("collapse_whitespace", None),
        # Terminal NFC (#416): sort_key preserves accents (#411), so a combining
        # mark separated from its base by a now-stripped zero-width must be
        # recomposed here or the key is not a fixed point.
        ("normalize", "NFC"),
    ],
    "normalize_user_input": [
        # #121: order and steps corrected to match actual Rust execution in
        # presets.rs — bidi/invisible stripping runs FIRST for idempotency.
        ("normalize", "NFKC"),
        ("strip_bidi", None),
        ("strip_zero_width", None),
        ("strip_control", None),
        # #413: strip Tags / variation selectors / CGJ / noncharacters / PUA
        # (comparison policy). Runs after the invisible strips so it cannot split a
        # mark run that the zalgo cap below then counts (the #121 lesson).
        ("strip_invisibles", "comparison"),
        ("strip_zalgo", None),
        ("confusables", "latin"),
        ("collapse_whitespace", None),
        # Terminal NFC (#416/#413): recompose any base+mark adjacency left by an
        # invisible (e.g. a CGJ) stripped from between them, so the pipeline stays
        # a fixed point.
        ("normalize", "NFC"),
    ],
    "strip_obfuscation": [
        ("normalize", "NFKC"),
        ("strip_zalgo", "max_marks=0"),
        ("strip_bidi", None),
        ("strip_zero_width", None),
        ("demojize", "cldr"),
        # #413: strip Tags / variation selectors / noncharacters / PUA after
        # demojize (so the emoji pass sees flags/selectors intact). CGJ is already
        # gone via the strip_zalgo(0) combining-mark strip above.
        ("strip_invisibles", "comparison"),
        # confusables runs AFTER demojize (matches src/presets.rs::_strip_obfuscation):
        # typographic punctuation in emoji names must be folded too, for idempotency (#141).
        ("confusables", "latin"),
        ("strip_accents", None),
        ("collapse_whitespace", None),
    ],
}
"""Named preset pipelines and their ordered steps.

Each key is a preset function name; each value is a list of
``(step_name, parameter)`` tuples in execution order.  Use this to
audit exactly which transforms a preset applies.

This is one of **two distinct registries** and is easy to confuse with the
other:

* ``PRESETS`` (this dict) — *preset* pipelines: fixed, ordered sequences of
  cleaning/normalization steps exposed as the ``security_clean``,
  ``ml_normalize``, ``normalize_user_input`` … helpers. Defined here, in Python.
* Policy *profiles* (see :func:`list_profiles` / :func:`get_pipeline`) —
  parameter sets for transliteration workflows (e.g.
  ``scholarly_cyrillic_iso9``). Defined in the Rust core (``src/pipeline.rs``).

A name from one registry is **not** valid in the other: pass profile names to
:func:`get_pipeline`, and use the keys here to look up preset step lists.
"""


# --- Policy profiles ---
#
# The profile registry (names + step configuration) lives in the Rust core
# (`src/pipeline.rs`), the single source of truth, so every binding shares one
# definition and the Python side cannot drift from what Rust executes (#229).


def get_pipeline(profile: str) -> TextPipeline:
    """Return a TextPipeline configured for a named policy profile.

    Policy profiles are pre-defined parameter sets for common institutional
    and application workflows.  Each call returns a fresh ``TextPipeline``
    instance.

    Args:
        profile: Profile name (see :func:`list_profiles`).

    Returns:
        A configured ``TextPipeline``.

    Raises:
        InvalidArgumentError: If *profile* is not a known profile name.

    Examples:
        >>> pipe = get_pipeline("scholarly_cyrillic_iso9")
        >>> pipe("Москва")  # doctest: +SKIP
        'moskva'
    """
    return TextPipeline._from_inner(_get_pipeline(profile))


def list_profiles() -> list[str]:
    """Return sorted names of available policy *profiles*.

    Policy profiles (consumed by :func:`get_pipeline`) are distinct from the
    *preset* pipelines in :data:`PRESETS`: profiles are transliteration
    parameter sets defined in the Rust core, whereas presets are fixed cleaning
    step-lists defined in Python. A profile name is not a valid preset name and
    vice versa.

    Returns:
        Sorted list of profile name strings.

    Examples:
        >>> "scholarly_cyrillic_iso9" in list_profiles()
        True
    """
    return _list_profiles()
