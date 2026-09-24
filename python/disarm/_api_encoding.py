"""Encodings at the edges: the output encoders for a sink, and byte-level input
detection and decoding."""

from __future__ import annotations

from disarm._boundary import (
    _decode_to_utf8,
    _detect_encoding,
    _escape_html,
    _percent_encode,
    _strip_log_injection,
)
from disarm._enums import Component

# --- Output encoders (terminal, context-explicit — NOT pipeline steps) ---


def escape_html(text: str) -> str:
    """Escape the five HTML metacharacters for element/quoted-attribute context.

    ``&`` -> ``&amp;``, ``<`` -> ``&lt;``, ``>`` -> ``&gt;``, ``"`` -> ``&quot;``,
    ``'`` -> ``&#x27;``. Everything else passes through unchanged.

    Correct for HTML **element-body and quoted-attribute** context. It is **not**
    correct inside ``<script>``/``<style>``, unquoted attributes, URL/``href``/
    ``src`` attributes, or HTML comments -- there, entity escaping is insufficient
    or corrupting. This is a terminal output encoder: apply it at the sink,
    exactly once. It is **not** idempotent (encoding twice double-encodes ``&``),
    and disarm is not an XSS framework -- see the Threat Model.

    Args:
        text: The string to escape.

    Returns:
        The escaped string (the original object when nothing needs escaping).

    Examples:
        >>> escape_html("<b>a & b</b>")
        '&lt;b&gt;a &amp; b&lt;/b&gt;'
        >>> escape_html("plain text")
        'plain text'
    """
    return _escape_html(text)


def percent_encode(text: str, *, component: Component) -> str:
    """RFC 3986 percent-encode ``text`` for a named URL ``component``.

    The input is UTF-8 encoded first, then every byte outside the component's
    safe set becomes ``%XX`` (``e`` with an accent -> ``%C3%A9``); the output is
    pure ASCII. ``component`` is required because the safe set depends on where
    the value is placed (`Component`: ``PATH``/``SEGMENT``/``QUERY``/
    ``FORM``; ``FORM`` uses ``application/x-www-form-urlencoded`` space -> ``+``).

    Percent-encoding is **not** a defense against ``javascript:``/``data:``
    scheme injection or open redirects -- those are URL-*construction* concerns,
    out of scope. Apply at the output sink, exactly once.

    **The result is opaque to the rest of the library (#727).** The output is
    valid, NFC, all-ASCII Unicode -- it is simply not the Unicode that carries
    the meaning -- and every detector reports it clean rather than unknown:
    ``has_anomalies("ad\\u200bmin")`` is ``True`` and
    ``has_anomalies(percent_encode("ad\\u200bmin", component=Component.QUERY))``
    is ``False``. That is why *once* and *at the sink* matter: a value that
    arrives already encoded has to be decoded before disarm can see it, which is
    the same ordering rule as canonicalize-before-validate. `decode_smuggled`
    reports what a ``%XX`` run *spells*, as evidence, for the inspection case.

    Args:
        text: The string to encode.
        component: Which URL component the value will be placed in.

    Returns:
        The percent-encoded ASCII string.

    Examples:
        >>> from disarm import Component
        >>> percent_encode("a b&c", component=Component.QUERY)
        'a%20b%26c'
        >>> percent_encode("a b&c", component=Component.FORM)
        'a+b%26c'
    """
    # Accept a Component (the typed contract) but pass a bare string straight
    # through so a stringly-typed caller gets the core's clear
    # InvalidArgumentError rather than an AttributeError on ``.value``.
    value = component.value if isinstance(component, Component) else component
    return _percent_encode(text, component=value)


def strip_log_injection(text: str, *, replacement: str = "\ufffd", keep_tab: bool = False) -> str:
    """Neutralize log-injection / terminal-control characters in ``text``.

    Replaces -- rather than dropping, so a redaction stays visible -- every CR,
    LF, NEL (U+0085), LS (U+2028), PS (U+2029), NUL, C0/C1 control, ESC, and DEL
    with ``replacement`` (default U+FFFD; pass ``replacement=""`` to drop). ``\t`` is **also** neutralized by
    default (``keep_tab=False``): a tab is a field separator in TSV/logfmt logs,
    so keeping it permits column injection; pass ``keep_tab=True`` for
    human-readable tabular logs. ANSI escape sequences are neutralized by
    replacing their introducer (``ESC``), leaving the inert ``[31m`` residue.

    Idempotent; the output never contains a raw CR/LF/ESC. This makes a log line
    safe to *write*, not safe to later *render as HTML*: it is **not** an
    HTML/SQL output sanitizer (it preserves ``< > &`` -- encode those at the log
    *viewer* with `escape_html`), and **not** a defense against
    logging-framework interpolation (log4shell). See the Threat Model.

    Args:
        text: The (untrusted) string destined for a log line.
        replacement: String substituted for each neutralized character (``""``
            drops them). Must not itself contain a neutralized character (else
            ``DisarmError``).
        keep_tab: Keep ``\t`` instead of neutralizing it.

    Returns:
        The neutralized string (the original object when nothing needs it).

    Examples:
        >>> strip_log_injection("user=admin\nFAKE LOG ENTRY")
        'user=admin\ufffdFAKE LOG ENTRY'
        >>> strip_log_injection("a\x1b[31mb")
        'a\ufffd[31mb'
    """
    return _strip_log_injection(text, replacement=replacement, keep_tab=keep_tab)


# --- Encoding detection ---


def detect_encoding(data: bytes) -> tuple[str, float]:
    """Detect the encoding of a byte sequence.

    Returns (encoding_name, confidence) where confidence is 0.0–1.0.
    Uses the chardetng algorithm (Firefox's encoding detector).

    Note (#194): chardetng (since the 1.0 migration, #164) does not expose a
    graded score — it reports a fixed confidence of ``0.95`` for every
    successful detection. The float is kept for API stability and to align with
    chardet-style ranges, but callers cannot use it to rank detection quality.

    Important: automatic encoding detection is inherently probabilistic.
    A high confidence score does NOT guarantee correctness. For critical
    pipelines, always prefer explicit encoding metadata over detection.

    **UTF-16** (#710). Two cases are decided *before* chardetng runs, because
    chardetng never produces a UTF-16 label at all:

    - **A BOM.** ``FF FE``, ``FE FF`` and ``EF BB BF`` yield ``UTF-16LE``,
      ``UTF-16BE`` and ``UTF-8`` directly. A BOM is not a probabilistic signal.
      This is the same WHATWG sniff `decode_to_utf8` performs when it
      auto-detects, so the two agree by construction — they used to disagree
      silently, with
      ``detect_encoding`` reporting ``KOI8-U`` at confidence 0.95 for the bytes
      `decode_to_utf8` read correctly as UTF-16LE.
    - **BOM-less UTF-16 over ASCII-range text**, where every second byte is
      ``00`` and the position of the NUL is the endianness. Deterministic, not a
      frequency guess.

    **BOM-less UTF-16 outside the ASCII range is not detected.** In UTF-16LE
    Cyrillic the high byte is ``04``, not ``00``, so ``"Привет"`` without a BOM
    carries no NUL and there is no deterministic signal to read. Such input
    decodes as a single-byte encoding and yields mojibake, with no flag — supply
    the encoding explicitly when you know the source emits BOM-less UTF-16.

    Args:
        data: Raw byte sequence to analyze.

    Returns:
        Tuple of (encoding_name, confidence) where confidence is 0.0–1.0.

    Raises:
        DisarmError: If the byte sequence cannot be analyzed.

    Examples:
        >>> enc, conf = detect_encoding(b"Hello World")
        >>> enc
        'UTF-8'
    """
    return _detect_encoding(data)


def decode_to_utf8(
    data: bytes,
    encoding: str | None = None,
    *,
    min_confidence: float = 0.95,
    strict: bool = False,
) -> tuple[str, bool]:
    """Decode a byte sequence to UTF-8.

    Returns (decoded_text, had_errors) where had_errors is True if a U+FFFD
    replacement character was inserted during decoding.

    ``had_errors=False`` is **not** a fidelity guarantee: single-byte encodings
    such as windows-1252 map every byte to some codepoint without ever inserting
    U+FFFD, so a wrong-encoding decode can produce mojibake with
    ``had_errors=False`` and no exception. For critical data, prefer explicit
    encoding metadata over auto-detection (and see ``strict`` below).

    If encoding is None, auto-detects using the chardetng algorithm. Note that
    ``min_confidence`` is effectively a binary accept/reject knob (see #194 and
    the argument docs below), not a quality grade.

    **Byte-order marks.** Auto-detection reads a BOM first. An *explicit*
    ``encoding`` is never overridden by one: only that encoding's own BOM is
    removed, and any other is decoded as data, so ``b"\\xfe\\xff\\x00A"`` given
    as ``"utf-8"`` is malformed UTF-8 (an error with ``strict=True``), not
    UTF-16BE ``"A"``. A UTF-16 label that names no byte order (``"utf-16"``,
    ``"unicode"``, ``"ucs-2"``) still takes its byte order from a UTF-16 BOM;
    ``"utf-16le"`` and ``"utf-16be"`` do not.

    Supports all WHATWG encodings (UTF-8, windows-1252, ISO-8859-1,
    Shift_JIS, EUC-JP, EUC-KR, Big5, GB18030, etc.).

    Args:
        data: Raw byte sequence to decode.
        encoding: Encoding name (e.g. "windows-1252"). None to auto-detect.
        min_confidence: Confidence threshold (0.0–1.0) applied when
            auto-detecting; raises DisarmError if the detected confidence is
            below it. When ``encoding`` is given explicitly the confidence gate
            is bypassed (nothing is detected), but the value is still
            range-validated — an out-of-range ``min_confidence`` raises
            regardless (#217). Defaults to ``0.95``.

            **Effectively a binary knob (#194).** Since the chardetng 1.0
            migration (#164) the detector reports a fixed ``0.95`` for every
            successful detection, so ``min_confidence`` cannot grade detection
            quality: any value ``<= 0.95`` (including the ``0.95`` default)
            accepts every guess, and any value ``> 0.95`` (e.g. ``1.0``) rejects
            auto-detection outright. The default therefore does **not** reject
            low-quality detections — to require high-quality input, pass the
            encoding explicitly rather than relying on this threshold. Pass
            ``0.0`` to be explicit about accepting any guess.
        strict: When ``True``, raise `DisarmError` instead of silently
            returning ``had_errors=True`` if the input contains byte sequences
            that decode to the U+FFFD replacement character (#189). Use this to
            turn lossy decodes — a common silent-data-loss source — into a hard
            failure. Note ``had_errors`` is a *replacement-character* flag, not a
            full fidelity guarantee (see the module docs), so ``strict`` catches
            malformed input, not every lossy remapping.

    Returns:
        Tuple of (decoded_text, had_errors). With ``strict=True`` the second
        element is always ``False`` (any error raises instead).

    Raises:
        DisarmError: If the encoding name is unknown, decoding fails,
            auto-detection confidence is below min_confidence, or
            ``strict=True`` and the decode was lossy.

    Examples:
        >>> text, had_errors = decode_to_utf8(b"caf\\xe9", "windows-1252")
        >>> text
        'café'
        >>> had_errors
        False
    """
    # The [0.0, 1.0] range check lives in the Rust core (decode_to_utf8_impl),
    # the single source of truth every caller crosses — no Python-side duplicate.
    return _decode_to_utf8(data, encoding=encoding, min_confidence=min_confidence, strict=strict)
