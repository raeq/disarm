"""Emoji: `demojize`, `replace_emoji` and the emoji-name provider."""

from __future__ import annotations

import warnings as _warnings

from disarm._boundary import (
    _demojize,
    _replace_emoji,
    _set_emoji_provider,
)
from disarm._types import (
    EmojiProvider,
    ErrorMode,
)


def demojize(
    text: str,
    *,
    replacement: str | None = None,
    strip_modifiers: bool = False,
    errors: ErrorMode = "replace",
    replace_with: str = "[?]",
    provider: EmojiProvider | None = None,
    # emoji library compatibility
    delimiters: tuple[str, str] | None = None,
) -> str:
    """Name every emoji, or replace every emoji with one string.

    Two modes, and they read different tables because they answer different questions.

    **Naming** (the default) asks *what does CLDR call this?*, so its domain is the CLDR
    name table — which is wider than the emoji: ``demojize("x™y")`` is ``"x trade mark y"``
    because CLDR annotates ``U+2122``.

    **Replacing** (``replacement=...``) asks *is this an emoji by the UCD's properties?*,
    so its domain is the emoji-presentation set: ``Emoji_Presentation=Yes``, an
    ``Emoji`` or ``Extended_Pictographic`` base carrying ``U+FE0F``, and the ZWJ,
    modifier, keycap and flag sequences built on those. Nothing else moves — ``©`` and ``™`` stay, where naming
    would have written a word over them (#972).

    Args:
        text: Input string potentially containing emoji.
        replacement: ``None`` names each emoji. A string writes that string in place of
            each emoji, verbatim: no padding and no whitespace collapse. The two useful
            values want opposite things and neither can be a default — ``""`` closes an
            intra-word split (``aa🔥bb`` → ``aabb``, the Emoji Attack construction) and
            ``" "`` keeps two words apart (``stop🛑now`` → ``stop now``). Under a
            replacement the naming options do not apply and are ignored: *strip_modifiers*,
            *errors*, *replace_with* and *provider* all describe what to **call** an
            emoji, and this caller has said not to call it anything.
        strip_modifiers: If True, collapse skin tone and hair style variants
            to their base form (e.g. "woman raising hand" instead of
            "woman raising hand: medium-dark skin tone").
        errors: How to handle an emoji that neither the provider nor the built-in CLDR
                table names. As bundled that is 122 single code points: the 26 regional
                indicators, which CLDR names only in pairs, and the 96 Plane 14 tag
                characters when they stand alone, which are removed here because it is
                the only coverage of that block `ml_normalize` has (#914). Add any
                sequence a future UCD adds ahead of CLDR. A text-default symbol followed
                by ``U+FE0F`` does not count: ``©\ufe0f`` keeps the ``©``.
                "replace" — substitute with replace_with.
                "ignore" — silently drop.
                "preserve" — keep the original emoji.

                It governs emoji only. Until #990 it also caught anything in a handful
                of block ranges, so ``☆`` and 776 other characters carrying no emoji
                property became ``[?]``; the branch now asks the UCD's properties, the
                same question *replacement* asks.

                A provider's ``None`` does **not** reach here: it means "I don't name
                this", and the built-in table answers next. To suppress a name, return
                the text you want; to remove emoji, use *replacement* or `replace_emoji`.
        replace_with: Replacement string when errors="replace".
        provider: An object implementing the `EmojiProvider` protocol.
            Overrides the global provider for this call.
            None uses the global provider or the built-in default.
            Returning ``None`` from ``lookup`` falls through to the built-in CLDR
            table rather than to *errors*, so a provider can add and override names
            but cannot withhold one.
        delimiters: ``emoji`` library compatibility — ignored, with a
            ``DeprecationWarning`` *when explicitly passed*. disarm always outputs
            bare CLDR short names without delimiters; wrap the result yourself if
            you need delimiters (e.g. ``f":{name}:"``).

    Returns:
        Text with emoji replaced by their descriptions.

    Raises:
        DisarmError: If an internal Rust error occurs.

    Warns:
        UserWarning: If the provider raises an exception or returns a
            non-string value. The built-in CLDR tables are used as a
            fallback for that sequence.

    Examples:
        >>> demojize("I ❤️ Python 🐍")
        'I red heart Python snake'
        >>> demojize("aa🔥bb", replacement="")
        'aabb'
        >>> demojize("stop🛑now", replacement=" ")
        'stop now'
        >>> demojize("x©y", replacement="")
        'x©y'
    """
    if not isinstance(text, str):
        raise TypeError(f"demojize() expects str, got {type(text).__name__}")
    if delimiters is not None:
        _warnings.warn(
            "The 'delimiters' parameter is not supported by disarm.demojize(); "
            "disarm always outputs bare CLDR short names. "
            "Wrap the result yourself if you need delimiters.",
            DeprecationWarning,
            stacklevel=2,
        )
    if replacement is not None and not isinstance(replacement, str):
        raise TypeError(
            f"demojize() replacement must be str or None, got {type(replacement).__name__}"
        )
    return _demojize(
        text,
        replacement=replacement,
        strip_modifiers=strip_modifiers,
        errors=errors,
        replace_with=replace_with,
        provider=provider,
    )


def replace_emoji(text: str, replacement: str = "") -> str:
    """Replace every emoji with *replacement*, verbatim (#972).

    The counterpart to `demojize`, and a different question of a different table.
    `demojize` asks *what does CLDR call this?*, so its domain is the CLDR name table,
    which is wider than the emoji: ``demojize("x™y")`` is ``"x trade mark y"``. This asks
    *is this an emoji by the UCD's properties?*, so its domain is the emoji-presentation
    set — ``Emoji_Presentation=Yes``, an ``Emoji`` or ``Extended_Pictographic`` base
    carrying ``U+FE0F``, and the ZWJ, modifier, keycap and flag sequences built on
    those. Nothing else moves.

    Identical to ``demojize(text, replacement=...)``; this is the spelling every other
    binding carries, and the one to reach for when the operation is the point rather than
    a mode of naming.

    Args:
        text: Input string potentially containing emoji.
        replacement: Written in place of each emoji, exactly as given — no padding and no
            whitespace collapse. The two useful values want opposite things and neither
            can be a default: ``""`` closes an intra-word split (the Emoji Attack
            construction, arXiv:2411.01077) and ``" "`` keeps two words apart.

    Returns:
        Text with every emoji replaced.

    Note:
        No shipped preset or profile does this. `llm_guardrail` keeps a visible emoji on
        a measured decision (#910): naming writes attacker-chosen English into screened
        text, and removing fuses the words an emoji separates. Which is right depends on
        whether the caller's emoji sit inside a word or between two.

    Examples:
        >>> replace_emoji("aa🔥bb")
        'aabb'
        >>> replace_emoji("stop🛑now", " ")
        'stop now'
        >>> replace_emoji("x©y")
        'x©y'
    """
    if not isinstance(text, str):
        raise TypeError(f"replace_emoji() expects str, got {type(text).__name__}")
    if not isinstance(replacement, str):
        raise TypeError(
            f"replace_emoji() replacement must be str, got {type(replacement).__name__}"
        )
    return _replace_emoji(text, replacement)


def set_emoji_provider(provider: EmojiProvider | None = None) -> None:
    """Set a global emoji provider for all demojize calls.

    The provider must implement the `EmojiProvider` protocol.

    Pass None to reset to the built-in default (latest English CLDR).

    Note:
        **Sequence-length cap (#199).** The provider's ``lookup()`` is offered a
        look-ahead window of at most **9 codepoints** — the length of the longest
        built-in CLDR emoji sequence. A provider cannot match a sequence longer
        than 9 codepoints: the extra codepoints fall through to the built-in
        tables / per-codepoint handling. This cap is fixed (it sizes a
        stack-allocated scan window, so widening it would cost every ``demojize``
        call); design custom mappings to key on ≤ 9 codepoints. Skin-tone and
        variation-selector modifiers trailing a matched sequence are consumed
        separately and do not count toward the 9.

    Args:
        provider: An object implementing the `EmojiProvider` protocol,
            or None to reset to the built-in default.

    Examples:
        >>> set_emoji_provider(None)  # reset to default provider
    """
    if provider is not None and not callable(getattr(provider, "lookup", None)):
        raise TypeError(
            f"EmojiProvider must have a callable lookup() method; got {type(provider).__name__}"
        )
    _set_emoji_provider(provider)
