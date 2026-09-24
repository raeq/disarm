"""Script predicates: detection, mixed-script and bidi checks."""

from __future__ import annotations

import warnings as _warnings

from disarm._boundary import (
    _detect_scripts,
    _has_bidi_conflict,
    _has_bidi_control,
    _inspect_auto_lang,
    _is_mixed_script,
)
from disarm._enums import Script

# --- Predicates ---


# Cache mapping script name → Script enum member for O(1) lookup
# instead of O(N) enum scan on each call to detect_scripts().
_SCRIPT_BY_NAME: dict[str, Script] = {s.value: s for s in Script}


def detect_scripts(text: str) -> list[Script]:
    """Return the set of Unicode scripts present in text, in order of first appearance.

    The script is the UCD ``Script`` property (UAX #24), within the scripts disarm
    resolves. A code point the UCD calls Common or Inherited is not reported, even when
    it sits in a script's block: the byte order mark ``U+FEFF``, the Arabic comma
    ``U+060C``, the Devanagari danda ``U+0964`` and ``U+00D7`` MULTIPLICATION SIGN are
    all Common.

    Args:
        text: Input string.

    Returns:
        List of `Script` enum values, ordered by first appearance.

    Examples:
        >>> detect_scripts("Hello")
        [Script.LATIN]
        >>> detect_scripts("Hello Мир")
        [Script.LATIN, Script.CYRILLIC]
    """
    raw = _detect_scripts(text)
    result = []
    for name in raw:
        script = _SCRIPT_BY_NAME.get(name)
        if script is not None:
            result.append(script)
        else:
            _warnings.warn(
                f"Rust detected script {name!r} which is not in the Script enum; "
                f"upgrade disarm or report this as a bug",
                stacklevel=2,
            )
    return result


def inspect_auto_lang(text: str) -> dict[str, str | list[str] | None]:
    """Inspect how ``lang="auto"`` would resolve for the given text.

    Use this to audit or log the detection decision made by the three-stage
    auto-detection pipeline.

    Args:
        text: Input string.

    Returns:
        Dict with keys:

        - ``script``: primary non-Latin script name, or ``None``
        - ``chosen_lang``: resolved language code, or ``None``
        - ``reason``: one of ``"unambiguous_script"``, ``"discriminator"``, ``"script_default"``, ``"latin_discriminator"``, ``"no_detection"``
        - ``discriminators_hit``: list of discriminator characters found

    Examples:
        >>> inspect_auto_lang("Київ")["chosen_lang"]
        'uk'
        >>> inspect_auto_lang("Москва")["reason"]
        'script_default'
    """
    result: dict[str, str | list[str] | None] = _inspect_auto_lang(text)  # type: ignore[assignment]
    return result


def is_mixed_script(text: str, *, per_word: bool = False) -> bool:
    """True if text contains characters from more than one Unicode **writing system**.

    Resolves the UTS #39 §5.1 augmented script sets (#776), so a script pair that one
    writing system uses is not "mixed":

    ==================================  ============================
    Han + Hiragana + Katakana           Japanese
    Han + Hangul                        Korean
    Han + Bopomofo                      Chinese
    ==================================  ============================

    So ``日本語テスト`` is one writing system, not three scripts. Anything without a
    writing system in common is still mixed, including a CJK script beside a non-CJK
    one — ``例えa`` is Japanese *and* Latin, and that is the case this check exists for.

    Each character's script is the UCD ``Script`` property, as `detect_scripts`
    reports it, so a byte order mark or a danda does not make text mixed:
    ``is_mixed_script("\\ufeffhello")`` is False, and so is a Bengali word ending in
    ``U+0964``.

    Note:
        `inspect_anomalies` is deliberately more permissive: it also exempts CJK beside
        Latin, because it runs over prose where a Japanese sentence carrying a product
        name in Latin is ordinary text. A *label* doing the same is not, which is why
        this function and the hostname screen both flag it.

    Note:
        UTS #39 section 5.1 resolves through ``Script_Extensions``, which disarm does
        not bundle; this is section 5.1 over ``Script``. A Common character is
        therefore compatible with every script, including those its extensions
        exclude (``a`` beside the Arabic comma ``U+060C`` is not mixed), and a
        character whose extensions name several scripts resolves to its one
        ``Script`` (Arabic-Indic digits beside Thaana are mixed). See the
        limitations page.

    Args:
        text: Input string.

    Returns:
        True if the text spans more than one writing system (Common/Inherited excluded).

    Examples:
        >>> is_mixed_script("Hello")
        False
        >>> is_mixed_script("Hello Мир")  # Latin + Cyrillic
        True
        >>> is_mixed_script("日本語テスト")  # Han + Katakana, one writing system
        False
        >>> is_mixed_script("ひら한")  # Japanese + Korean, no set in common
        True

    **This is a string-level question, and callers compose it into a different
    one (#901).** Bilingual text triggers it by design. A reject rule written as
    ``is_mixed_script(x) or has_bidi_conflict(x) or find_confusables(x)`` turns
    away every bilingual user — measured, it rejects all four bilingual strings
    in #901's table alongside the two spoofs. `has_anomalies` is the composition
    that tells them apart; ``per_word=True`` is that distinction on its own.

    ``per_word`` splits on **words**, not whitespace tokens: `IT-специалист`,
    `email:почта` and `user@почта.рф` are ordinary text, and a whitespace split
    reports all three. It uses the detector's own splitter, so the two agree.
    """
    return _is_mixed_script(text, per_word=per_word)


def has_bidi_conflict(text: str, *, per_word: bool = False) -> bool:
    """True if text mixes strong left-to-right and strong right-to-left characters.

    This is the precondition for Unicode Bidi display-reordering (UAX #9) — the
    structural signal behind "BiDi Swap"-style spoofs, where an LTR brand label
    sits beside an RTL domain (e.g. ``"varonis.com.ו.קום"``). Unlike a
    bidi-override (``U+202x``) check, it fires on the *real letters*: Latin /
    Cyrillic / Greek / CJK are left-to-right; Hebrew / Arabic / Syriac / Thaana /
    N'Ko are right-to-left; digits, punctuation and combining marks are neutral
    and never create a conflict on their own.

    A ``False`` result is **not** a safety guarantee.

    Warning:
        **This is not the RLO check.** Because it reads *letters*, it is
        structurally blind to the ``U+202x`` overrides — the classic extension
        spoof ``"invoice\\u202Egpj.exe"`` returns ``False`` here. The two
        conditions are disjoint; a string can satisfy either, both, or neither.

        To cover an override instead, use `inspect_anomalies` (kind
        ``bidi``) to detect and `strip_bidi` to remove. Note
        `strip_bidi` does *not* close this function's case: on a real-letter
        conflict it returns the input unchanged, because there is no format
        character to remove.

    Warning:
        **This reads the whole string; `inspect_anomalies` reads one token at a
        time** (#769). ``bidi_mixed`` is the closest thing the detector has to
        this check, and it fires on a *token* that mixes directions. So a string
        whose directions are split across two whitespace-separated words is a
        conflict here and clean there::

            has_bidi_conflict("hello שלום")            True
            inspect_anomalies("hello שלום").kinds      []
            has_bidi_conflict("helloשלום")             True
            inspect_anomalies("helloשלום").kinds       ['bidi_mixed']

        Neither is wrong. A label made of two words in two scripts is ordinary
        multilingual text, and the detector declining to flag it is why it can
        be run over prose. This function asks the *structural* question — can
        UAX #9 reorder this string — and the answer for two words is yes.

        Pick by what you are protecting. A single identifier, filename or
        hostname label is one token, and the detector is the better fit because
        it says which token and why. A whole line, a display name or anything
        that may legitimately contain a space needs this function, because the
        detector will not look across the space.

    Args:
        text: Input string.

    Returns:
        True if both a strong-LTR and a strong-RTL character are present.

    Examples:
        >>> has_bidi_conflict("hello")
        False
        >>> has_bidi_conflict("helloא")  # Latin + Hebrew
        True
        >>> has_bidi_conflict("hello שלום")  # whole string, so the space is no barrier
        True
        >>> inspect_anomalies("hello שלום").kinds  # per token, so it is two clean words
        []
        >>> has_bidi_conflict("invoice\\u202Egpj.exe")  # RLO override, not letters
        False
        >>> inspect_anomalies("invoice\\u202Egpj.exe").kinds  # this is the check
        ['bidi']

    **This is a string-level question, and callers compose it into a different
    one (#901).** Bilingual text triggers it by design. A reject rule written as
    ``is_mixed_script(x) or has_bidi_conflict(x) or find_confusables(x)`` turns
    away every bilingual user — measured, it rejects all four bilingual strings
    in #901's table alongside the two spoofs. `has_anomalies` is the composition
    that tells them apart; ``per_word=True`` is that distinction on its own.

    ``per_word`` splits on **words**, not whitespace tokens: `IT-специалист`,
    `email:почта` and `user@почта.рф` are ordinary text, and a whitespace split
    reports all three. It uses the detector's own splitter, so the two agree.
    """
    return _has_bidi_conflict(text, per_word=per_word)


def has_bidi_control(text: str) -> bool:
    """True if text carries any of the twelve UAX #9 explicit formatting characters.

    The uncontexted counterpart to `has_bidi_conflict`, which reads strong-direction
    **letters** and is structurally blind to these. The two are disjoint — a string can
    satisfy either, both or neither.

    **All twelve, with no judgement applied.** `inspect_anomalies`'s ``bidi`` kind reports
    nine: it holds back LRM, RLM and ALM, because a lone directional mark is ordinary in
    right-to-left text and flagging it would fire on any page that uses one. This predicate
    makes no such distinction, which is what makes it the right tool when the caller has
    already decided their input should carry no bidi control at all — a filename, an
    identifier, a source file.

    The complete answer already existed and was reachable only through
    ``is_suspicious_hostname(...)[1].bidi_control``, which meant calling a hostname
    analyser on something that is not a hostname (#778).

    Args:
        text: Input string.

    Returns:
        ``True`` if any UAX #9 control is present.

    Examples:
        >>> has_bidi_control("invoice\u202egpj.exe")
        True
        >>> has_bidi_conflict("invoice\u202egpj.exe")  # disjoint: reads letters
        False
        >>> has_bidi_control("\u200e")  # a directional mark counts here
        True
        >>> inspect_anomalies("\u200e").kinds  # and is deliberately not an anomaly
        []
        >>> has_bidi_control("plain text")
        False
    """
    return _has_bidi_control(text)
