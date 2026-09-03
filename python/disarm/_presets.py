"""Precompiled pipeline presets and named policy profiles.

These compose the public transforms in `_api` (and the Rust
backend) into ready-made canonicalization pipelines.  Re-exported from the
``disarm`` package root.
"""

from __future__ import annotations

import warnings

from disarm._api import TextPipeline
from disarm._boundary import (
    _canonicalize,
    _canonicalize_strict,
    _catalog_key,
    _fold_punctuation,
    _get_pipeline,
    _is_zalgo,
    _list_profiles,
    _ml_normalize,
    _search_key,
    _skeleton_key,
    _sort_key,
    _strip_bidi,
    _strip_format,
    _strip_noncharacters,
    _strip_obfuscation,
    _strip_pua,
    _strip_tags,
    _strip_variation_selectors,
    _strip_zalgo,
)

# --- Precompiled pipelines ---


#: The Unicode version the census below was measured under — the OLDEST any interpreter
#: in CI runs (CPython 3.12 ships 15.0.0; 3.13 ships 15.1.0; 3.14 ships 16.0.0). `tests/test_empty_key.py` compares exactly on that
#: version and asserts a lower bound on any newer one.
#:
#: The version has to be stated, because "assigned code points" is not one set. The first
#: version of this table was measured on a 16.0.0 host and was high by exactly the 16.0
#: additions each surface takes to `""` — 51 on `search_key`, 63 on `ml_normalize` — and
#: CI could not see them and failed the gate. The second pin, 15.1.0 from a 3.13 host,
#: was refused by CI's 3.12 at 15.0.0: nine surfaces are identical across the two and
#: `slugify` is 627 lower, which is every 15.1 addition it drops. Measured, not assumed. Surfaces that reach `""` only by
#: stripping (`canonicalize`, `sort_key`, `skeleton_key`) are identical across the two;
#: the ones that reach it through transliteration and the confusable fold are not.
_EMPTY_KEY_CENSUS_UCD = "15.0.0"

#: Single-character inputs whose key is `""`, as (all assigned, excluding the PUA), at
#: `_EMPTY_KEY_CENSUS_UCD`. Frozen by `tests/test_empty_key.py`.
_EMPTY_KEY_CENSUS = {
    "canonicalize": (137_955, 487),
    "canonicalize_strict": (137_955, 487),
    "strip_obfuscation": (140_200, 2_732),
    "ml_normalize": (4_047, 4_047),
    "search_key": (139_870, 2_402),
    "catalog_key": (139_867, 2_399),
    "sort_key": (138_404, 936),
    "skeleton_key": (137_955, 487),
    "slugify": (243_399, 105_931),
    "sanitize_filename": (0, 0),
}


def _on_empty(text: str, key: str, on_empty: str | None) -> str:
    """Apply the caller's empty-key policy (#728).

    Every preset and key builder maps some non-empty input to `""`, so a value that was
    entirely stripped is indistinguishable from a value that was never there. Measured,
    `search_key` alone takes 2,453 non-PUA code points there, and every string built from
    them. A caller storing the key as a uniqueness constraint has all of them, plus
    "no value", competing for one slot: first writer takes it, everyone after collides
    with a record that is not a user.

    `sanitize_filename` is the one surface that already reserved a sentinel — `_`, from
    #485 — and arXiv:2608.06508v1 §7.5 is explicit that the remedy is to redefine the
    mapping so the sentinel sits outside the value range, not to normalize harder.

    A post-pass rather than a step inside the pipeline, and deliberately so: the answer is
    a property of the *output*, not of any transform, and the pipeline has no more
    information at the end than the caller does. It is here for discoverability and to pin
    what it means.

    **It applies only when the input was not empty**, which is the whole point. An empty
    input has an empty key legitimately — nothing in, nothing out — and substituting a
    sentinel there would put absence and a stripped value back in one slot, which is the
    collision this exists to break. `search_key("")` is `""` with or without the
    parameter; `search_key("\u200b")` is the sentinel.

    **The sentinel is the caller's to choose, and disarm cannot check it.** A value that a
    real input also keys to reintroduces the collision one step over; `on_empty` is only
    safe when it is outside the range the builder can produce.
    """
    if key or on_empty is None or not text:
        return key
    return on_empty


def canonicalize(text: str, *, digit_policy: str = "numeric") -> str:
    r"""Canonicalize text for security-sensitive comparison.

    For **cleaning untrusted input before comparison**, this is the entry point.
    It does not make text safe to emit; encode at the sink.

    **It is half of a spoof-resistance answer, not all of it (#882).** This reports what
    two strings *collapse to*; `find_confusables` reports what *looks like* something
    else. Measured over ``confusable-bench.v1``, the six key reducers together catch 72
    of 120 malicious identifiers and `find_confusables` catches 66 — but **either one
    firing catches 108**, at 0 false positives on the 20 benign controls for each alone
    and for the pair. The reducers take the evasion class (42/54) that the detector
    cannot see, and the detector takes the composability class (31/31) the reducers
    cannot. A registry needs both questions asked.

    **Two steps introduce ASCII, not one** (#719). The leading NFKC is the obvious
    one; the confusable fold is the second and reaches characters NFKC leaves
    alone. ``U+2236 RATIO`` has no decomposition at all and becomes ``:``,
    ``U+2044 FRACTION SLASH`` becomes ``/``, ``U+2216 SET MINUS`` becomes ``\``.
    232 code points reach ASCII by the fold alone, 76 of them producing one of
    ``: = % & ? # / \``. A string that carried no delimiter can leave here carrying
    one — encode at the sink.

    `inspect_anomalies` reports it as ``confusable`` **when the word also carries an
    ASCII letter**, which is #633's gate and what keeps ``Привет`` from firing. A
    delimiter-only string such as ``∶∶∶`` folds to ``:::`` and is not reported.

    Pipeline: NFKC → strip bidi/format → strip invisible classes (#413) →
    strip_control → strip_zero_width → collapse_whitespace → cap combining marks
    (anti-zalgo, #429) → NFC → confusables → NFC (the confusable fold is
    sandwiched between two NFC passes so TR39 skeletoning is normalization-stable
    and the preset is idempotent — #416)

    Collapses fullwidth bypasses, neutralizes homoglyph spoofing, strips
    dangerous bidi overrides and soft hyphens, then normalizes whitespace
    (collapsing runs, stripping control chars and zero-width injections).

    **Scoped to identifiers, not body text** (#624). The confusable fold runs toward
    Latin, so it rewrites non-Latin text that has a Latin lookalike — Arabic alef
    becomes ``l``, Hebrew yod becomes ``'``, and ``Ελληνικά`` comes back as
    ``Eλλnvikά``. It also removes ``U+200C``, which Persian orthography requires.
    Nothing flags this first, because ordinary Persian is not an anomaly. Use it on
    usernames, hostnames, filenames and log lines; see `Limitations` (docs/limitations.md)
    before pointing it at a sentence.

    **The fold is not a romanization** (#907). It runs without transliterating first, so a
    Cyrillic word reaches the Latin table as shapes rather than as sounds: ``Москва`` comes
    back ``Mockba``, where ``search_key`` and ``catalog_key`` give the romanization
    ``moskva``. ``Mockba`` is not a spelling of anything. It is what the confusable table
    does to letters that no transliteration step has already handled, and ``catalog_key``'s
    own step list states the rule: transliterate first, so non-Latin scripts are romanized
    before confusables.

    Here that order is a decision rather than an omission, because the collapse is the
    point: an attacker's Latin ``Mockba`` and a Cyrillic ``Москва`` are meant to meet, and
    the romanizing surfaces cannot make them —
    ``find_key_collisions(["Москва", "Mockba"], key="search_key")`` is empty. Pick by what
    you need. `normalize` applies Unicode normalization and nothing else, so the script
    survives — but it is not an identity function, and NFC still recomposes ``e`` followed
    by U+0301 into ``é``. The key builders give a romanization, and this gives the
    collapse.

    Warning:
        Canonicalizes Unicode for *comparison*; it is **not** an output
        sanitizer and provides no XSS/HTML/SQL/injection protection. The NFKC
        step maps fullwidth lookalikes to live ASCII metacharacters by design
        (``＜`` → ``<``), so the output may be *more* important to context-encode
        on the way out, not less. Encode at the sink; never emit this result
        into markup or a query unescaped.

    Note:
        **Stability.** A patch upgrade never changes this function's output; a
        minor upgrade may, and is a possible reindex event (#644, #733). Read the
        *Upgrade notes* of any minor release before deploying it against stored
        values. The contract, and what has moved so far, is in ``docs/RUST_API.md``
        under *Key stability*.

    Args:
        text: Input string (user-submitted, network-received, etc.).

    Returns:
        A canonicalized string suitable for security-sensitive *comparison*
        (e.g. against a denylist). **Not** safe to emit unescaped into any
        execution or markup context — see warning above.

    Examples:
        >>> canonicalize("Ηello Ꮤorld")  # Greek Η + Cherokee Ꮤ → Latin
        'Hello World'

    Note:
        **`digit_policy`, and why the default cannot move (#885).** ``"tr39"`` folds digit
        variants onto the letters they imitate, and over `confusable-bench.v1` the six key
        builders reach **92 of 120** malicious rows under it against **72** by default.

        It is still not the right default, and the corpus does not show why. TR39's digit
        mappings cover **every non-Latin numeral system**, not just the styled Latin ones:
        Arabic-Indic zero folds to ``.``, one to ``l``, five to ``o``. So the Arabic year
        ``٢٠٢٤`` keys as ``٢.٢٤`` and the Persian ``۱۴۰۳`` as ``l۴.۳``. The 20 benign
        controls that measured "zero false-positive cost" contain no non-Latin digits at
        all, so the population that pays is not in the sample.

        ``"numeric"`` therefore stays the default and is a **genuine no-op** — passing it
        gives output byte-identical to not passing it, so no stored key moves. Pass
        ``"tr39"`` when your inputs are Latin identifiers and the extra reach is worth it.
        Do not pass it to text that may carry Arabic, Persian, Indic or Thai numerals.

        ``"preserve"`` (#648) keeps a non-Latin numeral in its own script, and since #896
        that holds here: the fold on the raw text and the preset's own fold both run under
        the policy, where the earlier pre-pass left the preset's fold at the default and
        the setting did nothing (#949).

    **The output can be the empty string (#728).**

    Measured at Unicode 15.0.0, **137,955** single
    characters reduce to ``""`` here (487 excluding the Private Use
    Area), and so does every string built from them. A caller keying a table
    on this has all of them, plus "no value", competing for one slot.

    There is no ``on_empty`` here: this returns text rather than a key. The
    four key builders take one.
    """
    return _canonicalize(text, digit_policy=digit_policy)


def security_clean(text: str) -> str:
    """Deprecated alias for `canonicalize`.

    Deprecated:
        Since 0.11.0. The ``*_clean`` name overpromised safety (see ``THREAT_MODEL.md``). Use
        `canonicalize`. This alias is removed in 1.0.
    """
    warnings.warn(
        "security_clean is deprecated; use canonicalize (removed in 1.0)",
        DeprecationWarning,
        stacklevel=2,
    )
    return canonicalize(text)


def ml_normalize(
    text: str,
    *,
    lang: str | None = None,
    emoji: str = "cldr",
    fold_case: bool = True,
) -> str:
    """ML/NLP text normalization pipeline.

    Pipeline: NFKC → emoji→text → [transliterate] → strip_accents →
              [fold_case] → strip_control → strip_zero_width → collapse_whitespace

    Produces clean, accent-free text suitable for tokenizers, embeddings, and
    feature extraction. Emoji are expanded to their CLDR short-name descriptions.

    "Emoji" means the Unicode property, not the CLDR table. The annotation data also
    names 326 code points that carry neither ``Emoji`` nor ``Extended_Pictographic`` —
    the curly quotes, the dashes, the currency signs, the math operators — and naming
    those inserts words into ordinary prose: ``film’s`` came back as
    ``film right apostrophe s``, one token to four with the possessive gone. They pass
    through unchanged since 0.15.0. `demojize` called directly still names them.

    Case folding is on by default. Turn it off for a **cased** downstream model:
    folding is destructive and cannot be undone later in the chain, and an uncased
    evaluation harness cannot measure what it costs. This is the one preset where
    folding is a side effect rather than the point — `catalog_key`,
    `search_key`, and `sort_key` fold because a key has to collide, so
    they have no such switch.

    ``fold_case=False`` does not mean "preserve the input untouched": *strip_accents*
    still runs, so ``José`` becomes ``Jose`` with the capital kept. Use
    `normalize_confusables` when diacritics must survive as well.

    Warning:
        **Not a security preset.** It assumes trusted input, and the name
        describes a use case rather than an operation, which is the one way to
        pick it by mistake. Bidi controls, private-use characters and homoglyphs
        all pass straight through: a right-to-left override survives, and
        Cyrillic ``аpple`` does not fold onto ``apple``. For anything
        user-supplied reach for `canonicalize`, or
        ``get_pipeline("llm_guardrail")`` when the text is headed for a model.

    Args:
        text: Input Unicode string.
        lang: Optional language code for transliteration (e.g. "de", "ja").
        emoji: Emoji handling mode.
               ``"cldr"`` — expand emoji to CLDR short names (default).
               ``"none"`` — leave emoji characters unchanged.
        fold_case: Apply Unicode case folding (default ``True``, the historical
               behaviour). ``False`` drops that one step and leaves every other
               stage unchanged.

    Returns:
        Clean, accent-free text — lowercased unless *fold_case* is ``False``.

    Raises:
        InvalidArgumentError: If *emoji* is not ``"cldr"`` or ``"none"``.
        DisarmError: If an internal Rust error occurs (base of the above).

    Examples:
        >>> ml_normalize("Café RÉSUMÉ")
        'cafe resume'
        >>> ml_normalize("München", lang="de")
        'muenchen'
        >>> ml_normalize("José Martínez", fold_case=False)
        'Jose Martinez'

    **The output can be the empty string (#728).**

    Measured at Unicode 15.0.0, **4,047** single
    characters reduce to ``""`` here (4,047 excluding the Private Use
    Area), and so does every string built from them. A caller keying a table
    on this has all of them, plus "no value", competing for one slot.

    There is no ``on_empty`` here: this returns text rather than a key. The
    four key builders take one.
    """
    return _ml_normalize(text, lang=lang, emoji_style=emoji, fold_case=fold_case)


def catalog_key(
    text: str,
    *,
    lang: str | None = None,
    strict_iso9: bool = False,
    digit_policy: str = "numeric",
    on_empty: str | None = None,
) -> str:
    """Library catalog key generation pipeline.

    Pipeline: NFKC → strip_bidi → strip invisibles → fold_case → transliterate →
    confusables → strip_accents →
              fold_case → collapse_whitespace

    Produces a canonical deduplication key for bibliographic titles.

    Warning:
        **The confusable fold runs after transliteration, so it rarely sees a
        homoglyph.** Anything that romanizes to something other than its
        lookalike is consumed before the fold can act: Cherokee ``Ꮃ`` *looks*
        like ``W`` and romanizes to ``la``, so ``Ꮃorld`` keys as ``laorld``.

        **Cyrillic and Greek are not the exception this warning used to claim**
        (#735). They romanize like every other non-Latin script, and a
        romanization is a *sound*, not a shape — so a letter that looks like one
        Latin letter routinely keys as a different one::

            раураl  → raural     not "paypal"  (Cyrillic а, р, у)
            аррlе   → arrle      not "apple"
            В       → v          looks like B
            Ѕ       → dz         looks like S
            Η       → i          Greek Eta, looks like H

        Measured over the Cyrillic and Greek letter blocks, 29 of 96 and 31 of
        129 letters key off their visual target. The ones that *do* line up —
        ``а``/``a``, ``е``/``e``, ``о``/``o`` — line up because the sound and the
        shape happen to agree, which is a coincidence of those letters rather
        than a property of the pipeline.

        Private-use characters survive into the key. This builds a key; screen
        adversarial input separately, and use ``normalize_confusables`` or
        ``is_confusable`` if what you need is the *visual* question.

    Note:
        **Stability.** A patch upgrade never changes this function's output; a
        minor upgrade may, and is a possible reindex event (#644). Read the
        *Upgrade notes* of any minor release before deploying it against stored
        keys. The contract, and what has moved so far, is in ``docs/RUST_API.md``
        under *Key stability*.

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

    Note:
        **`digit_policy`** folds digit variants on the raw text, before the key is built and
        before transliteration consumes them (#896). ``"numeric"`` is the default and a
        genuine no-op; ``"tr39"`` reaches more spoofs but destroys the numeric reading of
        Arabic, Persian, Indic and Thai digits. ``"preserve"`` keeps a numeral through the
        fold, and this builder's transliteration then romanizes it anyway — a key that maps
        every script to Latin cannot keep one. See `canonicalize` for the measurements and
        the trade (#885).

    **The output can be the empty string (#728).**

    Measured at Unicode 15.0.0, **139,867** single
    characters reduce to ``""`` here (2,399 excluding the Private Use
    Area), and so does every string built from them. A caller keying a table
    on this has all of them, plus "no value", competing for one slot.

    ``on_empty`` reserves a sentinel for that case — the fix
    `sanitize_filename` already made with ``_`` (#485). It applies only when
    the *input* was non-empty, so absence keeps its own key.
    """
    return _on_empty(
        text,
        _catalog_key(text, lang=lang, strict_iso9=strict_iso9, digit_policy=digit_policy),
        on_empty,
    )


def strip_format(text: str) -> str:
    """Strip bidi/format and invisible-injection vectors from rendered content.

    Pipeline: strip bidi/format → strip invisibles (#413, rendering policy) →
              strip control → strip zero-width → collapse_whitespace

    Lightweight cleanup for user-submitted content destined for rendering.
    Strips bidirectional overrides (which can visually reorder text to hide
    malicious content), soft hyphens, control characters, and zero-width
    injections, then collapses runs of whitespace to single spaces.

    Warning:
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
        >>> strip_format("hello\\x00world\\u200b!")
        'helloworld!'
        >>> strip_format("  spaced   out  ")
        'spaced out'
    """
    return _strip_format(text)


def display_clean(text: str) -> str:
    """Deprecated alias for `strip_format`.

    Deprecated:
        Since 0.11.0. ``display_clean`` implied markup-safety it does not provide (see
        ``THREAT_MODEL.md``). Use `strip_format`. Removed in 1.0.
    """
    warnings.warn(
        "display_clean is deprecated; use strip_format (removed in 1.0)",
        DeprecationWarning,
        stacklevel=2,
    )
    return strip_format(text)


def search_key(
    text: str,
    *,
    lang: str | None = None,
    digit_policy: str = "numeric",
    on_empty: str | None = None,
) -> str:
    """Search index key generation pipeline.

    Pipeline: NFKC → strip_bidi → strip invisibles → fold_case → transliterate →
    strip_accents → fold_case →
              collapse_whitespace

    Produces a case-insensitive, accent-insensitive, script-insensitive
    lookup key.  Like `catalog_key` but without confusable
    normalization — lighter and faster for search indexes.

    Warning:
        **Homoglyph collisions here are a side effect of transliteration, not a
        confusable fold.** There is no confusables step in this pipeline.
        Cyrillic ``аpple`` and Greek ``gοogle`` do collide with their Latin
        spellings, because those letters romanize to ``a`` and ``o`` — but a
        lookalike that romanizes to something else does not. Cherokee ``Ꮃ``
        *looks* like ``W`` and romanizes to ``la``, so ``Ꮃorld`` keys as
        ``laorld`` and never meets ``world``. Private-use characters survive into
        the key unchanged. This builds a key; screen adversarial input separately
        with `is_confusable` or `has_anomalies`.

    Note:
        **Stability.** A patch upgrade never changes this function's output; a
        minor upgrade may, and is a possible reindex event (#644). Read the
        *Upgrade notes* of any minor release before deploying it against stored
        keys. The contract, and what has moved so far, is in ``docs/RUST_API.md``
        under *Key stability*.

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

    Note:
        **`digit_policy`** folds digit variants on the raw text, before the key is built and
        before transliteration consumes them (#896). ``"numeric"`` is the default and a
        genuine no-op; ``"tr39"`` reaches more spoofs but destroys the numeric reading of
        Arabic, Persian, Indic and Thai digits. ``"preserve"`` keeps a numeral through the
        fold, and this builder's transliteration then romanizes it anyway — a key that maps
        every script to Latin cannot keep one. See `canonicalize` for the measurements and
        the trade (#885).

    **The output can be the empty string (#728).**

    Measured at Unicode 15.0.0, **139,870** single
    characters reduce to ``""`` here (2,402 excluding the Private Use
    Area), and so does every string built from them. A caller keying a table
    on this has all of them, plus "no value", competing for one slot.

    ``on_empty`` reserves a sentinel for that case — the fix
    `sanitize_filename` already made with ``_`` (#485). It applies only when
    the *input* was non-empty, so absence keeps its own key.
    """
    return _on_empty(text, _search_key(text, lang=lang, digit_policy=digit_policy), on_empty)


def skeleton_key(text: str, *, digit_policy: str = "numeric", on_empty: str | None = None) -> str:
    """A spoof key: the TR39 skeleton plus the prototype classes disarm keeps apart.

    Pipeline: NFKC → strip_bidi → strip invisibles → confusables → **prototype
    fold** → fixed-point(fold_case → confusables) → strip_control →
    strip_zero_width → collapse_whitespace

    The confusable fold runs **twice**, and the second pass is not redundant. The
    table's entry for a homoglyph is often on the *lowercase* form, so a capital
    the first pass cannot match becomes matchable the moment case is folded:
    ``Ω`` (U+2126 OHM SIGN) reaches the fold as ``Ω``, folds to ``ω``, and only
    then to ``w``. With a single pass ``skeleton_key("Ω")`` returned ``ω`` while
    ``skeleton_key("ω")`` returned ``w`` — and a key that is not a fixed point is
    not a key. A second pass rather than a reorder: the first has to see cased
    text or the prototype fold has nothing to work with.

    TR39 puts ``I``, ``l`` and ``1`` in one equivalence class and ``O``/``0`` in
    another. disarm's table stops short of both — every member of the capital-I
    family folds to ``I`` and stops there — so ``paypaI`` survives every other
    surface intact. This closes it.

    **Why a separate builder.** The letter half costs six collision groups in the
    235,976 entries of ``/usr/share/dict/words``, and ``Ione``/``lone`` is the only
    ordinary-word merge among them. That price holds *only on cased text*: after a
    case fold, ``I ≡ l`` is ``i ≡ l``, and the same class costs 264 groups of
    ordinary vocabulary — ``boiling``/``bolling``, ``doit``/``dolt``, ``ail``/``all``.
    A factor of 44. No existing key builder runs a confusable fold before folding
    case, and `catalog_key` cannot be reordered to (#419).

    **Not for display.** The output is a key, and it is more destructive than any
    preset that forwards text — the same split `canonicalize` and
    `canonicalize_strict` already make.

    Args:
        text: Input string.
        digit_policy: ``"numeric"`` (default) applies the letter half only.
            ``"tr39"`` adds ``1 ≡ l`` and ``0 ≡ O``, which is what an identifier
            skeleton wants and what a deduplication key must not have — see below.

    Returns:
        The skeleton, lowercased and whitespace-collapsed.

    Raises:
        DisarmError: If *digit_policy* is not a supported value.

    Examples:
        >>> skeleton_key("paypaI")  # the class catalog_key cannot reach
        'paypal'
        >>> skeleton_key("paypal") == skeleton_key("paypaI")
        True
        >>> skeleton_key("SKU-1O0")  # digits kept apart by default
        'sku-1o0'
        >>> skeleton_key("SKU-1O0", digit_policy="tr39")  # ...and merged on request
        'sku-loo'

    The digit half is destructive by design. Under ``"tr39"`` every one of
    ``SKU-100``, ``SKU-1O0``, ``SKU-IOO`` and ``SKU-l00`` is one key, as are
    ``v1.0.1``, ``vI.O.I`` and ``vl.o.l``. For a spoof detector that is the point;
    for a deduplication key over anything carrying a part number, a version or an
    ISBN it destroys the field.

    **The output can be the empty string (#728).**

    Measured at Unicode 15.0.0, **137,955** single
    characters reduce to ``""`` here (487 excluding the Private Use
    Area), and so does every string built from them. A caller keying a table
    on this has all of them, plus "no value", competing for one slot.

    ``on_empty`` reserves a sentinel for that case — the fix
    `sanitize_filename` already made with ``_`` (#485). It applies only when
    the *input* was non-empty, so absence keeps its own key.
    """
    return _on_empty(text, _skeleton_key(text, digit_policy=digit_policy), on_empty)


def sort_key(
    text: str,
    *,
    lang: str | None = None,
    digit_policy: str = "numeric",
    on_empty: str | None = None,
) -> str:
    """Sort key generation pipeline.

    Pipeline: NFKC → strip_bidi → strip invisibles → fold_case → transliterate-non-Latin →
    fold_case → collapse_whitespace

    A case-insensitive collation key that, unlike `search_key`,
    **preserves base accented characters** rather than folding them away.
    It keeps the accent so accented and unaccented forms stay distinct
    (``"Über"`` folds to ``"über"``, not ``"uber"``) and the accent survives
    for a locale-aware collator. Non-Latin scripts are still folded to a
    consistent Latin form (``"Война"`` → ``"voyna"``) so cross-script titles
    interfile. This is the collation counterpart to `search_key`, which
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

    Warning:
        **No confusable fold.** As with `search_key`, any homoglyph
        collision is a side effect of transliteration: Cherokee ``Ꮃ`` romanizes
        to ``la`` rather than folding onto the ``W`` it resembles, and
        private-use characters survive into the key. This produces a collation
        key, not a screen.

    Note:
        **Stability.** A patch upgrade never changes this function's output; a
        minor upgrade may, and is a possible reindex event (#644). Read the
        *Upgrade notes* of any minor release before deploying it against stored
        keys. The contract, and what has moved so far, is in ``docs/RUST_API.md``
        under *Key stability*.

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

    Note:
        **`digit_policy`** folds digit variants on the raw text, before the key is built and
        before transliteration consumes them (#896). ``"numeric"`` is the default and a
        genuine no-op; ``"tr39"`` reaches more spoofs but destroys the numeric reading of
        Arabic, Persian, Indic and Thai digits. ``"preserve"`` keeps a numeral through the
        fold, and this builder's transliteration then romanizes it anyway — a key that maps
        every script to Latin cannot keep one. See `canonicalize` for the measurements and
        the trade (#885).

    **The output can be the empty string (#728).**

    Measured at Unicode 15.0.0, **138,404** single
    characters reduce to ``""`` here (936 excluding the Private Use
    Area), and so does every string built from them. A caller keying a table
    on this has all of them, plus "no value", competing for one slot.

    ``on_empty`` reserves a sentinel for that case — the fix
    `sanitize_filename` already made with ``_`` (#485). It applies only when
    the *input* was non-empty, so absence keeps its own key.
    """
    return _on_empty(text, _sort_key(text, lang=lang, digit_policy=digit_policy), on_empty)


def strip_bidi(text: str) -> str:
    """Strip bidirectional override and formatting characters (UAX #9).

    Removes: soft hyphen (U+00AD), Arabic Letter Mark (U+061C),
    LRM/RLM (U+200E/F), bidi embeddings/overrides (U+202A–U+202E),
    bidi isolates (U+2066–U+2069).

    **Keeps the logical order.** This is a pure filter: the controls are deleted
    and the code-point order is untouched, so the result is the order the bytes
    are in, not the order a reader saw.
    ``"\\u202e" + "paypal"[::-1] + "\\u202c"`` renders as ``paypal`` and comes
    back as ``lapyap``.

    That is correct for a compiler, a filesystem or an identifier comparison,
    which all read logical order — the Trojan Source direction
    (CVE-2021-42574). It is the wrong answer for a search index, an NLP model or
    content moderation, which want what was displayed. disarm has no surface
    that returns display order; see "Stripping preserves logical order, not
    display order" in the limitations page (#740).

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


def fold_punctuation(text: str) -> str:
    """Fold typographic punctuation to its ASCII spelling (#703).

    The dash family and the minus sign become ``-``; the curly and low-9 quotes and the
    primes become ``'`` / ``"``; the ellipsis becomes ``...``; the non-standard spaces
    become a space. Nothing else in disarm does this as a stated purpose: `canonicalize`
    folds five dashes and skips the em dash and the horizontal bar, `transliterate` folds
    those two and rejects the other four, and a key built from either treats ``a—b`` and
    ``a-b`` as distinct while treating ``a–b`` and ``a-b`` as the same. A separate
    primitive rather than a change to either, because `canonicalize` is a security fold
    entitled to map ``“`` to ``''`` — a confusable skeleton for a double quote and a poor
    replacement for one.

    **Not covered, on purpose.** ``U+3002 IDEOGRAPHIC FULL STOP`` and ``U+060C ARABIC
    COMMA`` are those scripts' own full stop and comma; the middle dot ``U+00B7`` is a
    letter in Catalan ``l·l``; the bullet stays. Spaces fold rather than delete, so words
    do not glue together.

    Idempotent, and the identity on ASCII. Form-preserving, like the targeted strips: it
    folds one character class and composes nothing, so a decomposed letter leaves as it
    arrived. Compose it with a preset when boundary normalization is wanted too.

    Examples:
        >>> fold_punctuation("He said \u201cok\u201d \u2014 then\u2026")
        'He said "ok" - then...'
        >>> fold_punctuation("l\u00b7l")  # Catalan: a letter, not punctuation
        'l·l'
    """
    return _fold_punctuation(text)


def strip_variation_selectors(text: str) -> str:
    """Strip every variation selector (VS1–VS16 and VS17–VS256).

    These are the arbitrary-byte smuggling channel. Use ``strip_format`` if you
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
    directly, or ``strip_format`` to *preserve* PUA for rendering.

    Examples:
        >>> strip_pua("a\\ue000b")
        'ab'
    """
    return _strip_pua(text)


def canonicalize_strict(text: str, *, digit_policy: str = "numeric") -> str:
    """Strict Unicode canonicalization of user input — **not** an injection defense.

    Warning:
        This normalizes Unicode; it does **not** make text safe to emit into
        HTML, JS, URLs, SQL, or shells. It performs no escaping and does not
        strip ``<``, ``>``, ``&`` — ``<script>alert(1)</script>`` passes through
        unchanged, and the NFKC step can *surface* ASCII metacharacters from
        fullwidth lookalikes (``＜script＞`` → ``<script>``). This is **not** XSS
        or injection protection: encode at the output sink (framework
        auto-escaping, DOMPurify, parameterized queries). Run this *before* that
        encoder, never instead of it. The name predates this clarification.

    **Scoped to identifiers, not body text** (#624). The confusable fold runs toward
    Latin, so it rewrites non-Latin text that has a Latin lookalike — Arabic alef
    becomes ``l``, Hebrew yod becomes ``'``, and ``Ελληνικά`` comes back as
    ``Eλλnvikά``. It also removes ``U+200C``, which Persian orthography requires.
    Nothing flags this first, because ordinary Persian is not an anomaly. Use it on
    usernames, hostnames, filenames and log lines; see `Limitations` (docs/limitations.md)
    before pointing it at a sentence.

    **The fold is not a romanization** (#907). ``Москва`` comes back ``Mockba``, where the
    key builders give ``moskva``; the confusable table runs without transliterating first,
    so a non-Latin word reaches it as shapes rather than as sounds. See `canonicalize` for
    why that order is deliberate and what to use instead.

    Runs no transliteration step while neutralizing Unicode-level attack vectors:
    zalgo stacking, homoglyph spoofing, bidi overrides, zero-width injections, and
    control characters. It used to say it "preserves the original script", which the
    paragraph above disproves: the confusable fold rewrites individual letters, and
    only the *romanization* step is absent (#907).

    Pipeline: ``NFKC → strip_bidi → strip_zero_width → strip_control → strip
    invisible classes (#413) → strip_zalgo → confusables → collapse_whitespace →
    NFC`` (invisibles are stripped before zalgo-capping so they cannot split
    combining-mark runs, and the terminal NFC recomposes any base+mark left
    adjacent by a stripped invisible — keeping the output idempotent, #416/#413)

    Note:
        **Stability.** A patch upgrade never changes this function's output; a
        minor upgrade may, and is a possible reindex event (#644, #733). Read the
        *Upgrade notes* of any minor release before deploying it against stored
        values. The contract, and what has moved so far, is in ``docs/RUST_API.md``
        under *Key stability*.

    Args:
        text: User-submitted input string.

    Returns:
        A Unicode-normalized string. Safe for storage/comparison; **encode it
        before emitting into any markup or query context** (see warning above).

    Examples:
        >>> canonicalize_strict("Hello, world!")
        'Hello, world!'
        >>> canonicalize_strict("p\\u0430ypal")  # Cyrillic а → Latin a
        'paypal'
        >>> canonicalize_strict("admin\\u202euser")  # RLO stripped
        'adminuser'

    Note:
        **`digit_policy`** folds digit variants before the key is built, and the builder's
        own confusable fold runs under the same policy (#896). ``"numeric"`` is the default
        and a genuine no-op; ``"tr39"`` reaches more spoofs but destroys the numeric reading
        of Arabic, Persian, Indic and Thai digits; ``"preserve"`` keeps a non-Latin numeral
        in its own script (#949). See `canonicalize` for the measurements and the trade
        (#885).

    **The output can be the empty string (#728).**

    Measured at Unicode 15.0.0, **137,955** single
    characters reduce to ``""`` here (487 excluding the Private Use
    Area), and so does every string built from them. A caller keying a table
    on this has all of them, plus "no value", competing for one slot.

    There is no ``on_empty`` here: this returns text rather than a key. The
    four key builders take one.
    """
    return _canonicalize_strict(text, digit_policy=digit_policy)


def normalize_user_input(text: str) -> str:
    """Deprecated alias for `canonicalize_strict`.

    Deprecated:
        Since 0.11.0. The old name predated the canonicalize/sanitize distinction in
        ``THREAT_MODEL.md``. Use `canonicalize_strict`. Removed in 1.0.
    """
    warnings.warn(
        "normalize_user_input is deprecated; use canonicalize_strict (removed in 1.0)",
        DeprecationWarning,
        stacklevel=2,
    )
    return canonicalize_strict(text)


def strip_obfuscation(text: str, *, digit_policy: str = "numeric") -> str:
    """Maximum-strength text deobfuscation.

    Neutralizes homoglyph spoofing, zalgo abuse, invisible character
    injection, and bidi attacks. Uses TR39 confusable mapping (visual
    similarity) — Cyrillic р→p, с→c, В→B — not phonetic transliteration.

    Warning:
        **Not an output sanitizer.** Resolves *Unicode* obfuscation only; performs
        no HTML/JS/SQL escaping and does not strip ``<``, ``>``, ``&``. The NFKC
        step folds fullwidth ``＜`` to a live ``<``, so the output can be *more*
        important to encode than the input. Encode at the output sink — this is
        not XSS or injection protection.

    **Does not transliterate.** Non-Latin scripts that have no Latin
    confusable equivalent pass through unchanged. Chain with
    ``transliterate()`` explicitly if you also need romanization.

    Read the exclusion in that sentence literally: the scripts that *do* have a
    Latin confusable equivalent are rewritten. 22 Arabic code points, 12 Hebrew and
    65 Greek fold to ASCII, so wholly non-Latin text comes back with Latin letters
    in it. This preset also strips combining marks, which takes Indic vowel signs
    along with Latin accents — ``বাংলা`` becomes ``বল``, which is not a word.

    **Scoped to identifiers, not body text** (#624). The confusable fold runs toward
    Latin, so it rewrites non-Latin text that has a Latin lookalike — Arabic alef
    becomes ``l``, Hebrew yod becomes ``'``, and ``Ελληνικά`` comes back as
    ``Eλλnvikά``. It also removes ``U+200C``, which Persian orthography requires.
    Nothing flags this first, because ordinary Persian is not an anomaly. Use it on
    usernames, hostnames, filenames and log lines; see `Limitations` (docs/limitations.md)
    before pointing it at a sentence.

    **The fold is not a romanization** (#907). ``Москва`` comes back ``Mockba``, where the
    key builders give ``moskva``; the confusable table runs without transliterating first,
    so a non-Latin word reaches it as shapes rather than as sounds. See `canonicalize` for
    why that order is deliberate and what to use instead.

    **Preserves case.** Case is not deception — proper nouns, acronyms,
    and sentence boundaries are meaningful. Chain with ``fold_case()``
    if lowercasing is also needed.

    Pipeline: ``NFKC → strip_zalgo(max_marks=0) → strip_bidi → strip_zero_width
    → demojize → confusables → strip_accents → collapse_whitespace``
    (confusables runs after demojize so typographic punctuation in emoji names is
    folded too, keeping the output idempotent)

    Note:
        **Stability.** A patch upgrade never changes this function's output; a
        minor upgrade may, and is a possible reindex event (#644, #733). Read the
        *Upgrade notes* of any minor release before deploying it against stored
        values. The contract, and what has moved so far, is in ``docs/RUST_API.md``
        under *Key stability*.

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

    Note:
        **`digit_policy`** folds digit variants before the key is built, and the builder's
        own confusable fold runs under the same policy (#896). ``"numeric"`` is the default
        and a genuine no-op; ``"tr39"`` reaches more spoofs but destroys the numeric reading
        of Arabic, Persian, Indic and Thai digits; ``"preserve"`` keeps a non-Latin numeral
        in its own script (#949). See `canonicalize` for the measurements and the trade
        (#885).

    **The output can be the empty string (#728).**

    Measured at Unicode 15.0.0, **140,200** single
    characters reduce to ``""`` here (2,732 excluding the Private Use
    Area), and so does every string built from them. A caller keying a table
    on this has all of them, plus "no value", competing for one slot.

    There is no ``on_empty`` here: this returns text rather than a key. The
    four key builders take one.
    """
    return _strip_obfuscation(text, digit_policy=digit_policy)


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


def strip_zalgo(text: str, *, max_marks: int = 3) -> str:
    """Strip excessive combining marks, preserving legitimate diacritics.

    Caps the number of combining marks per base character at *max_marks*.
    Operates in NFD space and recomposes to NFC.

    The default equals `is_zalgo`'s threshold on purpose (#788). It was ``2`` while the
    threshold was ``3``, so this stripped from text the library had just declined to call
    suspicious: pointed and cantillated Hebrew routinely carries a vowel, a dot and an
    accent on one consonant, `is_zalgo` correctly returns ``False`` for it, and this
    removed the accent anyway. Three marks is ordinary text in Hebrew and Arabic; the
    Vietnamese ``ệ`` that set the original figure has two.

    Args:
        text: Input string (may contain zalgo abuse).
        max_marks: Maximum combining marks to keep per base character
            (default: ``3``).  Set to ``0`` to strip all combining marks
            (equivalent to `strip_accents`), as `ml_normalize` does.

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
#
# The step recipes behind the top-level functions: `PRESETS["canonicalize"]` is what
# `canonicalize()` runs. These keys are NOT policy-profile names — the two namespaces
# are disjoint, so `get_pipeline("canonicalize")` raises and `PRESETS["rag_ingest"]`
# is a KeyError. Profiles live behind `get_pipeline()` / `list_profiles()` (#600).
#
# This dict is a hand-maintained MIRROR of the `const STEPS` arrays in
# `src/presets.rs`. Nothing executes it — it exists for introspection and docs. It has
# drifted before (`ml_normalize` was missing `transliterate` and the #498 second
# `demojize`), so when you change a step list in Rust, change it here in the same
# commit and check `tests/test_mutant_killers.py::test_preset_steps_exact`.

PRESETS: dict[str, list[tuple[str, str | None]]] = {
    "canonicalize": [
        ("normalize", "NFKC"),
        ("strip_bidi", None),
        # #413: strip Unicode Tags / variation selectors / CGJ / noncharacters /
        # PUA (keeping valid emoji flags). "comparison" = strip PUA, strip all VS.
        ("strip_invisibles", "comparison"),
        # #433: control/zero-width stripping is now explicit (was fused into
        # collapse_whitespace); collapse folds whitespace only. Runs before
        # strip_zalgo so a stripped invisible between marks cannot split a run.
        ("strip_control", None),
        ("strip_zero_width", None),
        ("collapse_whitespace", None),
        # #429: cap combining marks at 2 per base (anti-zalgo). After the
        # control/zero-width strip so a stripped invisible between marks cannot
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
        # Only when a `lang` is set, and in Ignore mode: ML pipelines want clean
        # ASCII-ish output, so an unmapped character is dropped, not preserved.
        ("transliterate", None),
        ("strip_accents", None),
        # #498: a second demojize AFTER strip_accents. A negated-relation symbol
        # (`≇` U+2247) is not in the CLDR name table, so the first pass leaves it;
        # strip_accents drops the overlay and exposes the bare base (`≅`), which IS
        # named. Without this pass that base is only named on the following call —
        # non-idempotent.
        ("demojize", "cldr"),
        ("fold_case", None),
        # #433: explicit strip steps (was fused into collapse_whitespace).
        ("strip_control", None),
        ("strip_zero_width", None),
        ("collapse_whitespace", None),
    ],
    "catalog_key": [
        ("normalize", "NFKC"),
        ("strip_bidi", None),
        # #419: fold_case runs BEFORE transliterate so a case pair whose folded
        # form is in the translit table (Mtavruli Ჱ → Mkhedruli ჱ → "he") is
        # stable across passes; a second fold after transliterate catches the
        # uppercase ASCII full transliteration can emit (£ → GBP).
        ("fold_case", None),
        ("transliterate", None),
        ("confusables", "latin"),
        ("strip_accents", None),
        ("fold_case", None),
        # #433: explicit strip steps (was fused into collapse_whitespace).
        ("strip_control", None),
        ("strip_zero_width", None),
        ("collapse_whitespace", None),
    ],
    "strip_format": [
        ("strip_bidi", None),
        # #413: rendering policy — keep VS15/VS16 after a base and PRESERVE the PUA
        # (icon fonts); still strip Tags (keeping flags), CGJ, and noncharacters.
        ("strip_invisibles", "rendering"),
        # #433: explicit strip steps (was fused into collapse_whitespace).
        ("strip_control", None),
        ("strip_zero_width", None),
        ("collapse_whitespace", None),
    ],
    "search_key": [
        ("normalize", "NFKC"),
        ("strip_bidi", None),
        # #419: fold_case BEFORE transliterate (case-pair idempotency) and AGAIN
        # after (full transliteration can emit uppercase, e.g. £ → GBP).
        ("fold_case", None),
        ("transliterate", None),
        ("strip_accents", None),
        ("fold_case", None),
        # #433: explicit strip steps (was fused into collapse_whitespace).
        ("strip_control", None),
        ("strip_zero_width", None),
        ("collapse_whitespace", None),
    ],
    "sort_key": [
        ("normalize", "NFKC"),
        ("strip_bidi", None),
        # #419: fold_case BEFORE transliterate so a case pair whose folded form is
        # in the translit table is stable across passes.
        ("fold_case", None),
        # "non_latin": transliterate folds only non-Latin scripts; base accented
        # Latin characters are preserved so the accent can order the key (this is
        # what distinguishes sort_key from search_key, which strips accents here).
        ("transliterate", "non_latin"),
        # fold_case AGAIN: transliteration can emit uppercase from a non-Latin
        # source the pre-fold can't reach (Old Persian 𐏈 → "Auramazda"), so fold
        # here too for idempotency. fold_case only lowercases, so accents survive.
        ("fold_case", None),
        # #433: explicit strip steps (was fused into collapse_whitespace).
        ("strip_control", None),
        ("strip_zero_width", None),
        ("collapse_whitespace", None),
        # Terminal NFC (#416): sort_key preserves accents (#411), so a combining
        # mark separated from its base by a now-stripped zero-width must be
        # recomposed here or the key is not a fixed point.
        ("normalize", "NFC"),
    ],
    "canonicalize_strict": [
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
        # #433: explicit strip_control before the fold (zero-width already stripped
        # above); collapse folds whitespace only.
        ("strip_control", None),
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
  cleaning/normalization steps exposed as the ``canonicalize``,
  ``ml_normalize``, ``canonicalize_strict`` … helpers. Defined in the Rust core
  (``src/presets.rs``); this dict is a hand-maintained **mirror** of those step
  lists for introspection, and nothing executes it.
* Policy *profiles* (see `list_profiles` / `get_pipeline`) —
  parameter sets for transliteration workflows (e.g.
  ``scholarly_cyrillic_iso9``). Defined in the Rust core (``src/pipeline.rs``).

A name from one registry is **not** valid in the other: pass profile names to
`get_pipeline`, and use the keys here to look up preset step lists.

The deprecated preset names (``security_clean``, ``display_clean``,
``normalize_user_input``) remain valid keys through the 0.11 deprecation cycle
and are removed in 1.0 — prefer the new names.
"""

# Deprecated preset-name aliases (#430): keep the old keys resolving to the same
# step lists for the 0.11 deprecation cycle. Removed in 1.0.
PRESETS["security_clean"] = PRESETS["canonicalize"]
PRESETS["display_clean"] = PRESETS["strip_format"]
PRESETS["normalize_user_input"] = PRESETS["canonicalize_strict"]


# --- Policy profiles ---
#
# The profile registry (names + step configuration) lives in the Rust core
# (`src/pipeline.rs`), the single source of truth, so every binding shares one
# definition and the Python side cannot drift from what Rust executes (#229).


def get_pipeline(profile: str, *, digit_policy: str = "numeric") -> TextPipeline:
    """Return a TextPipeline configured for a named policy profile.

    Policy profiles are pre-defined parameter sets for common institutional
    and application workflows.  Each call returns a fresh ``TextPipeline``
    instance.

    ``digit_policy`` is fixed here, at construction (#646). A profile is a resolved
    pipeline and calling it takes text and nothing else, so the policy is chosen before
    any text arrives — the position it holds on the key builders. The default reproduces
    every profile byte for byte, and the setting shows in ``steps`` only when it is not
    the default. Three profiles carry a confusables step (``llm_guardrail``,
    ``normalize_web_input``, ``library_catalog_key_eu``); on the others a policy would
    never run, so a non-default one is refused rather than kept. ``rag_ingest`` recovers
    by transliteration, not by a fold.

    Note:
        A *profile* name is not a `PRESETS` key, and the two sets are
        disjoint — ``get_pipeline("canonicalize")`` raises. `PRESETS` holds
        the step recipes behind the top-level functions (``canonicalize``,
        ``search_key``, …); profiles are ready-made policy pipelines named for a
        workflow. Call `list_profiles` for the valid values here.

    Args:
        profile: Profile name (see `list_profiles`).
        digit_policy: ``"numeric"`` (default), ``"tr39"`` or ``"preserve"`` — the policy
            the profile's confusables step folds digits under.

    Returns:
        A configured ``TextPipeline``.

    Raises:
        InvalidArgumentError: If *profile* is not a known profile name, if
            *digit_policy* is not a supported value, or if it is not the default and
            the profile has no confusables step to apply it.

    Examples:
        >>> pipe = get_pipeline("scholarly_cyrillic_iso9")
        >>> pipe("Москва")  # doctest: +SKIP
        'moskva'
        >>> get_pipeline("llm_guardrail")("g੦ogle")  # GURMUKHI ZERO read as a digit
        'g0ogle'
        >>> get_pipeline("llm_guardrail", digit_policy="tr39")("g੦ogle")  # ...as "o"
        'google'
    """
    return TextPipeline._from_inner(_get_pipeline(profile, digit_policy=digit_policy))


def list_profiles() -> list[str]:
    """Return sorted names of available policy *profiles*.

    Policy profiles (consumed by `get_pipeline`) are distinct from the
    *preset* pipelines in `PRESETS`: profiles are transliteration
    parameter sets, whereas presets are the fixed cleaning step-lists behind the
    top-level functions. A profile name is not a valid preset name and vice
    versa.

    Both are defined in the Rust core. `PRESETS` is a hand-maintained
    Python *mirror* of those step lists for introspection — nothing executes it,
    so treat it as documentation of what Rust runs rather than as the source of
    truth.

    Each profile also says what it is *for*, in one sentence, so the list and the reasons
    to pick between them are one line apart (#860)::

        {p: get_pipeline(p).purpose for p in list_profiles()}

    Returns:
        Sorted list of profile name strings.

    Examples:
        >>> "scholarly_cyrillic_iso9" in list_profiles()
        True
        >>> get_pipeline("search_index").purpose
        'Full-text search index generation, cross-language search keys.'
    """
    return _list_profiles()
