"""Normalization and cleanup: Unicode normalization, the confusable fold, filenames,
accents, case, whitespace and invisibles, and the normalization predicates."""

from __future__ import annotations

from disarm._api_common import (
    _checked_i64_max,
    _norm_form,
    _target_script,
)
from disarm._boundary import (
    _collapse_whitespace,
    _fold_case,
    _is_ascii,
    _is_canonical,
    _is_case_fold_stable,
    _is_normalized,
    _is_normalized_stream_safe,
    _normalize_confusables,
    _sanitize_filename,
    _stream_safe,
    _strip_control_chars,
    _strip_zero_width_chars,
)
from disarm._enums import Script
from disarm._types import (
    NF,
    NormalizationForm,
    Platform,
)


def normalize_confusables(
    text: str,
    *,
    target_script: str | Script = "latin",
    digit_policy: str = "numeric",
) -> str:
    """Replace Unicode confusable homoglyphs with target-script equivalents.

    Uses Unicode TR39 confusables table. Characters without a confusable
    equivalent in the target script pass through unchanged (visual mapping
    only, not transliteration).

    Warning:
        **Folds confusables and nothing else.** Bidi controls, zero-width
        characters, control characters and private-use characters all pass
        through untouched — a right-to-left override goes in and comes back out.
        This is the first thing an API search for *homoglyph* finds, so it is
        worth saying plainly: it is one transform, not a screen. Use
        `canonicalize` or `strip_obfuscation` when the input is
        untrusted rather than merely mixed-script.

    Warning:
        **`target_script` folds toward a script; it does not protect one** (#907).
        Passing a script does not mean "leave this script alone". It means "send
        confusables to this script's letters", and a word written in some *third*
        script is rewritten into the target::

            normalize_confusables("Москва", target_script="arabic")
            # 'Мهсква'  — U+0647 ARABIC LETTER HEH replacing the Cyrillic о

        That is an Arabic letter inside a Cyrillic word. Text already in the target
        survives because its characters are not sources in that table, which is a
        side effect rather than a policy. There is also no Greek target — the four
        are ``latin``, ``cyrillic``, ``arabic`` and ``hebrew`` — so Greek text has no
        value that preserves it by design, and survives ``arabic`` or ``hebrew`` only
        because those tables happen not to map Greek.

        Declaring which scripts a caller considers legitimate is a different question
        with a different answer. It is tracked as ``allowed_scripts`` in #900.

    Warning:
        **The presets fold a different table, because NFKC runs first (#834).**
        Every preset and profile that folds confusables normalizes to NFKC
        before doing it, so the fold sees a decomposed image of the input and
        **65 code points get a different answer** than they do here (5 for the
        Cyrillic target)::

            normalize_confusables("\u017f")   # 'f'  — TR39: a long s looks like an f
            canonicalize("\u017f")            # 's'  — NFKC decomposed it first

        Neither order is right everywhere, which is why both ship: 43 of the 65
        favour the preset answer (``\u2474`` is ``(1)`` rather than ``(l)``, and
        the mathematical ``m`` is ``m`` rather than ``rn``), 15 favour this one
        (``\u00b4`` is ``'`` here and a space plus a combining acute there), and
        7 are judgment calls. What matters is that they differ.

        The consequence for keys: this function alone is **not** a canonical
        skeleton. ``\u2474`` folds to ``(l)`` while ASCII ``(1)`` stays ``(1)``,
        because the table has only three ASCII sources (#725) — so two strings
        a reader cannot tell apart get different keys here and the same key
        under any preset. Build keys with ``canonicalize`` or ``search_key``.

    Note:
        **Stability.** A patch upgrade never changes this function's output; a
        minor upgrade may, and is a possible reindex event (#644, #733). Read the
        *Upgrade notes* of any minor release before deploying it against stored
        values. The contract, and what has moved so far, is in ``docs/RUST_API.md``
        under *Key stability*.

    Args:
        text: Input string potentially containing homoglyphs.
        target_script: Script to normalize toward. Supported values:
            ``"latin"`` (default, 2,356 mappings), ``"cyrillic"`` (1,352 mappings),
            ``"arabic"`` (373 mappings) and ``"hebrew"`` (261 mappings).

            The two RTL targets exist because generation drops an equivalence
            class entirely when no member belongs to the target script, so a
            class whose members are all Arabic folded to nothing under either of
            the first two (#791/#792). They do **not** reach an intra-Arabic pair
            such as ``"\u06a9"`` against ``"\u0643"``: both members are already in
            the target script, which a cross-script table cannot express (#848).
        digit_policy: How non-Latin **digits** fold (#561).

            ``"numeric"`` (default) sends them to the ASCII digit — ``०`` becomes
            ``0`` — which is the right reading for prose, where a Devanagari zero
            really is a zero and folding it to a letter corrupts the number.

            ``"tr39"`` uses upstream's targets, which send most of these digits to a
            Latin *letter* (``०`` → ``o``, ``೦`` → ``O``, ``١`` → ``l``). Three of the
            47 rows do not land on a letter: ``٠`` and ``۰`` fold to ``.``, and ``𑣣``
            folds to the two characters ``rn`` — which matters if the result feeds a
            label- or path-shaped key. That is what an
            identifier *skeleton* wants: its only job is to make two confusable
            identifiers collide, and it does not care whether the collision target
            reads sensibly. Reach for it when comparing against a TR39-derived
            benchmark. The two policies differ on 47 rows and agree everywhere else.

            Scoped to the Latin target: the override rows are generated from the
            Latin table and carry TR39's Latin-script targets, so with
            ``target_script="cyrillic"`` this is a no-op.

            ``"preserve"`` leaves the digit alone (#648). The other two both rewrite
            a non-Latin numeral and neither keeps the script: ``२०२४`` becomes
            ``२0२४`` under ``"numeric"`` and ``२o२४`` under ``"tr39"``. Both are
            *mixed-script* numerals, which is neither the original nor a clean fold.
            This declines the digit rows and folds everything else as usual. Unlike
            ``"tr39"`` it applies under every target script, because declining to
            fold is not a Latin-specific act.

    Returns:
        String with confusable characters replaced by target-script equivalents.

    Raises:
        DisarmError: If *target_script* or *digit_policy* is not a supported value.

    Examples:
        >>> normalize_confusables("Ηello")  # Greek Η looks like Latin H
        'Hello'
        >>> normalize_confusables("раypal")  # Cyrillic р/а look like Latin p/a
        'paypal'
        >>> normalize_confusables("paypal", target_script="cyrillic")
        'раура\u04cf'
        >>> normalize_confusables("g००gle")  # Devanagari zeros stay numeric
        'g00gle'
        >>> normalize_confusables("२०२४", digit_policy="preserve")  # keep the script
        '२०२४'
        >>> normalize_confusables("g००gle", digit_policy="tr39")  # …or collide
        'google'
    """
    if not isinstance(text, str):
        raise TypeError(f"normalize_confusables() expects str, got {type(text).__name__}")
    return _normalize_confusables(
        text, target_script=_target_script(target_script), digit_policy=digit_policy
    )


def sanitize_filename(
    text: str,
    *,
    separator: str = "_",
    max_length: int = 255,
    platform: Platform = "universal",
    lang: str | None = None,
    preserve_extension: bool = True,
    # pathvalidate compatibility aliases
    replacement_text: str | None = None,
    max_len: int | None = None,
) -> str:
    """Sanitize a string into a safe filename.

    Transliterate → strip OS-illegal chars → collapse separators →
    handle reserved names (CON, NUL, etc.) → truncate respecting extension.

    Args:
        text: Input string (title, user input, etc.).
        separator: Replacement for spaces and stripped characters.
            Also accepted as ``replacement_text`` (pathvalidate compatibility).
            It reaches the output without passing the filter, so it must be
            printable, non-space ASCII, contain no character illegal on
            *platform* and no path separator (``/`` or ``\\``); anything else
            raises `InvalidArgumentError`. ``""`` is allowed and drops
            stripped characters outright, and ``" "`` on its own is allowed
            for readable names (a space inside a longer separator is not).
        max_length: Maximum filename length measured in **bytes** (UTF-8
            encoded), not characters. Default 255 matches the ext4/APFS/NTFS
            filesystem limit. Truncation always lands on a character boundary
            to avoid splitting multi-byte sequences.
            Also accepted as ``max_len`` (pathvalidate compatibility).
        platform: Target platform — ``"universal"``, ``"windows"``, or
            ``"posix"``.
        lang: Language code for transliteration (e.g. ``"de"``, ``"ja"``).
        preserve_extension: When ``True`` (default), the file extension is
            kept intact within *max_length*. If the extension alone (including
            the leading ``.``) is ≥ *max_length*, the extension is dropped and
            the whole result is truncated to *max_length* bytes. When
            ``False``, the entire string is truncated to *max_length* bytes
            without special treatment of the extension.

    Returns:
        Safe filename string. It is a fixed point — sanitizing it again with
        the same arguments returns it unchanged — and on the ``"universal"``
        and ``"windows"`` platforms it is never a device name (``CON``,
        ``NUL``, …) as Windows reads one: the part before the first dot,
        trailing spaces ignored.

    Raises:
        InvalidArgumentError: If *separator* contains a character a filename
            must not carry (see above), *platform* or *lang* is unknown, or
            *max_length* is negative.

    Examples:
        >>> sanitize_filename("My Report (final).pdf")
        'My_Report_(final).pdf'
        >>> sanitize_filename("CON.txt")  # reserved on Windows
        '_CON.txt'
        >>> sanitize_filename("résumé.docx", lang="fr")
        'resume.docx'

    Warning:
        **A safe filename is not a safe URL path segment.** ``%`` is legal in a
        filename on every supported platform, so a ``%`` the caller typed is kept:
        ``sanitize_filename("..%2Fetc")`` returns ``"%2Fetc"``, with the literal
        ``..`` collapsed and the percent-encoded spelling of the same traversal
        left alone. A consumer that percent-decodes the result must validate
        *after* decoding.

        What the sanitizer will not do is manufacture one. Compatibility folding
        maps five code points to ``%`` (``؉`` U+0609, ``؊`` U+060A, ``٪`` U+066A,
        ``﹪`` U+FE6A, ``％`` U+FF05), which used to assemble ``%2E%2E%2F`` out of
        input containing no ``%`` at all (#721). The rule is exact and per
        character: **every ``%`` in the output is one the input contained** (or
        part of a separator the caller chose). Typing one ``%`` does not let a
        folded one through.

        >>> sanitize_filename("％２Ｅ％２Ｅ％２Ｆetc.txt")
        '_2E_2E_2Fetc.txt'
    """
    if not isinstance(text, str):
        raise TypeError(f"sanitize_filename() expects str, got {type(text).__name__}")
    # pathvalidate compatibility: replacement_text → separator
    if replacement_text is not None:
        separator = replacement_text
    # pathvalidate compatibility: max_len → max_length
    if max_len is not None:
        max_length = max_len
    # max_length's non-negative contract is enforced by the Rust core (#231).
    return _sanitize_filename(
        text,
        separator=separator,
        max_length=_checked_i64_max(max_length, "max_length"),  # #255
        platform=platform,
        lang=lang,
        preserve_extension=preserve_extension,
    )


def fold_case(text: str) -> str:
    """Full Unicode case folding per CaseFolding.txt (Unicode 16.0).

    Unlike ``str.lower()``, this implements the complete Unicode Case Folding
    algorithm with all 1,557 status-C and status-F mappings.  Covers Latin
    (ß→ss, ſ→s, İ→i̇), Greek (ς→σ, variant forms ϐ→β, ϑ→θ, ϕ→φ, ϖ→π,
    ϰ→κ, ϱ→ρ), Cyrillic, Armenian (ligature և→եւ), Georgian Mtavruli,
    Cherokee, Adlam, Deseret, Osage, Warang Citi, fullwidth Latin,
    and all Latin ligature expansions (ﬁ→fi, ﬂ→fl, ﬀ→ff, ﬃ→ffi,
    ﬄ→ffl, ﬅ→st, ﬆ→st).

    Equivalent to ``str.casefold()`` on a Python whose ``unicodedata`` is also
    Unicode 16.0 (Python 3.14), but executed in Rust via a compile-time PHF (perfect
    hash function) table.  The table is disarm's, not the host's: on an older Python
    the two differ on the cased letters added since that Python's Unicode version
    (``U+1C89``, ``U+A7CB``, Garay, ...).  Pure-ASCII strings take a branchless fast
    path with no table lookup.

    Note:
        **Stability.** A patch upgrade never changes this function's output; a
        minor upgrade may, and is a possible reindex event (#644, #733). Read the
        *Upgrade notes* of any minor release before deploying it against stored
        values. The contract, and what has moved so far, is in ``docs/RUST_API.md``
        under *Key stability*.

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
    if not isinstance(text, str):
        raise TypeError(f"fold_case() expects str, got {type(text).__name__}")
    if text.isascii():
        return text.lower()
    return _fold_case(text)


#: Alias for `fold_case` — matches ``str.casefold()`` naming for drop-in use.
casefold = fold_case


def is_case_fold_stable(text: str) -> bool:
    """True if ``text`` is a stable identity key under case folding.

    Answers whether `fold_case` and a simple lowercase agree on ``text`` (which
    lowercase is below).  A ``False`` result says some *other* string folds to the
    same value, so a table keyed on this one can collide — ``groß.txt`` and
    ``gross.txt`` are the pair node-tar collided on (CVE-2026-23950),
    and ``ſtraße``/``straße`` and ``ﬁle``/``file`` are the same
    shape.  Roughly 2,000 code points behave this way, including every Latin
    ligature, ``ẛ``, the micro sign, and all of Cherokee (whose fold direction
    runs small→capital, so both cases move).

    **This is a fact about the string, not an accusation.**  ``groß`` is an
    ordinary German word, so a ``False`` here is not a report of an attack and
    the predicate is deliberately kept out of `has_anomalies`.  What to do
    about it is the caller's decision: reserve both forms, reject the name, or
    key the table on `fold_case` rather than ``str.lower()``.

    ``str.lower()`` is the correct comparison basis and ``str.casefold()`` is
    not: casefolding performs the very transform under test, so a predicate
    written against it is ``True`` everywhere.

    **Both sides are compiled into disarm; neither is your Python's.**  The fold is
    disarm's own table (Unicode 16.0), and the lowercase is the Rust toolchain's that
    built the wheel (``to_lowercase``, Unicode 17.0 on a current toolchain; see
    ``docs/provenance.md``).  So this is ``fold_case(text) == text.lower()`` only where
    all three know the same letters.  It is not, on letters one side knows and another
    does not: the 28 cased letters Unicode 17 added (``U+A7CE``, ``U+A7D2``,
    ``U+A7D4``, ``U+16EA0``-``U+16EB8``) read ``False`` here on every current Python,
    where ``fold_case(c) == c.lower()`` holds, and the cased letters Unicode 16 added
    (``U+1C89``, ``U+A7CB``, Garay, ...) read ``True`` here, where that comparison fails
    on Python 3.13 and older.  A ``False`` for a letter one side does not know is a
    collision hazard for the same reason as any other: two functions that disagree
    build two keys that disagree.

    A ``True`` result is **not** a uniqueness guarantee: two distinct stable
    strings can still collide under some *other* normalization.

    Args:
        text: Input string.

    Returns:
        True if full case folding and simple lowercasing agree on ``text``.

    Examples:
        >>> is_case_fold_stable("gross.txt")
        True
        >>> is_case_fold_stable("groß.txt")
        False
        >>> is_case_fold_stable("ΟΔΟΣ")  # Greek final sigma: οδος vs οδοσ
        False
    """
    if not isinstance(text, str):
        raise TypeError(f"is_case_fold_stable() expects str, got {type(text).__name__}")
    if text.isascii():
        return True
    return _is_case_fold_stable(text)


def collapse_whitespace(text: str) -> str:
    """Fold all Unicode whitespace runs to single ASCII spaces, trimming the ends.

    Folds **whitespace only** (#433): the line controls (TAB/LF/VT/FF/CR), the
    information separators (U+001C–U+001F), NEL, the ``Zs``/``Zl``/``Zp`` spaces,
    and the blank-rendering set (Braille blank, the Hangul fillers) each fold to a
    single space. It does **not** delete control or zero-width characters — for
    that, call `strip_control_chars` / `strip_zero_width_chars`, or
    use a preset that sequences them ahead of the fold (``canonicalize`` and
    ``canonicalize_strict`` both do).

    Folding the line controls (rather than deleting them) means a carriage return
    between two tokens becomes a space, never a silent join: ``"a\\rb"`` →
    ``"a b"``.

    Args:
        text: Input string.

    Returns:
        String with whitespace runs folded to single spaces and ends trimmed.

    Examples:
        >>> collapse_whitespace("  hello   world  ")
        'hello world'
        >>> collapse_whitespace("tabs\\there\\ttoo")
        'tabs here too'
        >>> collapse_whitespace("a\\rb")  # carriage return folds, not deletes
        'a b'
    """
    if not isinstance(text, str):
        raise TypeError(f"collapse_whitespace() expects str, got {type(text).__name__}")
    return _collapse_whitespace(text)


def strip_control_chars(text: str) -> str:
    """Remove control characters that are **not** whitespace (#433).

    Deletes every C0/C1 control (NUL, BEL, ESC, DEL, the C1 block) *except* the
    ones `collapse_whitespace` folds — TAB, LF, VT, FF, CR, the information
    separators ``U+001C``–``U+001F``, and NEL. Those are preserved here so the
    fold can turn them into a space; deleting them would join the tokens either
    side, which is the invisible-join hazard the split exists to avoid.

    Pair it with `collapse_whitespace` when you want both, in that order.

    Args:
        text: Input string.

    Returns:
        String with non-whitespace controls removed.

    Examples:
        >>> strip_control_chars("a\\x00b\\x07c")
        'abc'
        >>> strip_control_chars("a\\rb")  # CR preserved for the fold to handle
        'a\\rb'
    """
    if not isinstance(text, str):
        raise TypeError(f"strip_control_chars() expects str, got {type(text).__name__}")
    return _strip_control_chars(text)


def strip_zero_width_chars(text: str) -> str:
    """Remove zero-width characters.

    Deletes the zero-width set, which renders as nothing and is used to fragment a
    token so it evades a denylist while looking unchanged. The set is exactly these
    22 code points:

    - ``U+200B``–``U+200D`` — ZWSP, ZWNJ, ZWJ
    - ``U+2060``–``U+2064`` — word joiner and the invisible operators
    - ``U+FEFF`` — BOM / zero-width no-break space
    - ``U+180E`` — Mongolian vowel separator (reclassified ``Zs`` → ``Cf`` in
      Unicode 6.3, so it is a format character despite the name)
    - ``U+1BCA0``–``U+1BCA3`` — the Duployan shorthand format controls (#813)
    - ``U+1D173``–``U+1D17A`` — the musical symbol format controls (#813)

    Args:
        text: Input string.

    Returns:
        String with zero-width characters removed.

    Examples:
        >>> strip_zero_width_chars("pay\\u200bpal")
        'paypal'
        >>> strip_zero_width_chars("a\\ufeffb")
        'ab'
    """
    if not isinstance(text, str):
        raise TypeError(f"strip_zero_width_chars() expects str, got {type(text).__name__}")
    return _strip_zero_width_chars(text)


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
    form: NormalizationForm | NF = "NFC",
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
    return _is_normalized(text, form=_norm_form(form))


def is_canonical(text: str, *, preset: str = "canonicalize") -> bool:
    """True if ``text`` is already its own canonical form under ``preset``.

    Every other normalization surface in disarm is *generation path*: text in,
    normalized text out. This is the *verification path* counterpart — the question
    to ask about bytes that arrive already bound to a decision, where quietly
    re-normalizing defends the comparison you are about to make and leaves the
    second representation free to keep circulating.

    `has_anomalies` is not this predicate, and the gap is not small. Over
    every assigned code point, 142,760 of them (5,292 excluding the Private Use
    Area) are reported clean by the detector and are *not* their own canonical
    form — CJK compatibility ideographs, Arabic presentation forms, Kangxi
    radicals, fullwidth and halfwidth forms. None go the other way. An accept
    gate written as "reject if ``has_anomalies``, otherwise take the bytes as
    given" admits every one of them.

    That is not a detector bug to be fixed by widening it: ``ＮＨＫ`` is how a
    Japanese broadcaster writes its own name, and a detector that flags it is one
    callers turn off (#633, #907). Two questions, two answers — ask this one when
    you need canonicity, and ``has_anomalies`` when you need suspicion.

    Equivalent to ``globals()[preset](text) == text`` and defined by it, but it
    does not build the normalized copy to answer a boolean, and nothing crosses
    the extension boundary but the result.

    Args:
        text: Input string.
        preset: A preset name (`PRESETS`) or a policy profile name
            (`list_profiles`). Defaults to ``"canonicalize"``.

    Returns:
        True if ``preset`` would leave ``text`` unchanged.

    Raises:
        DisarmError: If ``preset`` names neither a preset nor a profile.

    Examples:
        >>> is_canonical("paypal.com")
        True
        >>> is_canonical("ＡＢＣ")  # fullwidth — clean to the detector
        False
        >>> has_anomalies("ＡＢＣ")  # ...and this is the point
        False
        >>> is_canonical("abc", preset="search_key")
        True
    """
    return _is_canonical(text, preset=preset)


def stream_safe(text: str) -> str:
    """Apply the Unicode Stream-Safe Text Format (UAX #15).

    Inserts ``U+034F COMBINING GRAPHEME JOINER`` to break any run of more than 30
    non-starters. That bound exists so text can be processed in fixed-size buffers
    without a normalization boundary landing inside one, which makes this an
    **interoperability** primitive.

    Three things it is not, because each is a plausible misreading:

    - **Not canonically equivalent.** It inserts a character, so ``stream_safe(s) != s``
      and the normalized forms differ too. Never build a comparison key from it — use
      ``search_key()`` or ``canonicalize()``.
    - **Not a zalgo control.** ``strip_zalgo()`` answers that. 30 non-starters is far
      above anything a reader would call stacking abuse, and this makes no judgement about
      whether the text is abusive.
    - **Not a size bound.** The presets already cap how far a call can grow its input;
      this does not change how much text a call returns.

    Args:
        text: Input string.

    Returns:
        The text with joiners inserted where a non-starter run exceeded the bound.

    Examples:
        >>> stream_safe("Hello world")          # nothing to bound
        'Hello world'
        >>> long_stack = "a" + "\u0301" * 40
        >>> "\u034f" in stream_safe(long_stack)
        True
    """
    return _stream_safe(text)


def is_normalized_stream_safe(
    text: str,
    *,
    form: NormalizationForm | NF = "NFC",
) -> bool:
    """True if *text* is **both** in normalization form *form* **and** Stream-Safe.

    It is a conjunction, and the name says so. The underlying predicate is
    ``unicode-normalization``'s ``is_nfc_stream_safe``, whose own documentation reads "is
    Stream-Safe NFC" — a string can be stream-safe without being normalized, and this
    returns ``False`` for it.

    Args:
        text: Input string.
        form: Normalization form. The compatibility forms are answered by their canonical
            counterparts, since compatibility folding does not change how long a
            non-starter run is.

    Returns:
        True if the string is normalized *and* within the Stream-Safe bound.

    Examples:
        >>> is_normalized_stream_safe("café")
        True
        >>> is_normalized_stream_safe("e\u0301")   # stream-safe, but not NFC
        False
    """
    return _is_normalized_stream_safe(text, form=_norm_form(form))
