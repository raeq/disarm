"""Hostname safety and anomaly detection."""

from __future__ import annotations

from collections.abc import Iterable

from disarm._boundary import (
    AnomalyReport,
    HostnameAnalysis,
    Lexicon,
    _has_anomalies,
    _has_anomalies_lex,
    _inspect_anomalies,
    _inspect_anomalies_lex,
    _is_suspicious_hostname,
)

# --- Hostname safety ---


def is_suspicious_hostname(
    hostname: str, *, contractions: bool = False
) -> tuple[bool, HostnameAnalysis]:
    """Flag a hostname as *suspicious* for Unicode homoglyph spoofing.

    Returns ``(suspicious, analysis)`` where ``analysis`` is a
    ``HostnameAnalysis`` with attributes:

    - ``suspicious``: bool — True if a problem was detected (mixed-script, a
      bundled-table confusable, or a bidi-direction conflict). Because the
      confusable check is an *any-character* screen, this flags essentially every
      hostname with a non-Latin letter — legitimate (``москва.рф``) as well as
      spoofs — so it is a **maximally conservative screen**, not a precise verdict.
    - ``scripts``: list[str] — Unicode scripts found across all labels.
    - ``mixed_script``: bool — True if any single label contains more than one script.
    - ``has_confusables``: bool — True if confusable homoglyphs found. Read *after*
      the UTS #46 mapping and NFKC, so it cannot see a compatibility form by
      construction: ``ｇoogle.com`` is already ``google.com`` by the time this is
      computed, and ``False`` is the correct answer — after mapping there is no
      confusable left. Seeing ``canonical`` differ from the input while this stays
      ``False`` means ``compat_fold``, not a defect.
    - ``bidi_conflict``: bool — True if the decoded hostname mixes strong
      left-to-right and strong right-to-left characters (the "BiDi Swap" reorder
      precondition). Folded into ``suspicious``.
    - ``bidi_control``: bool — True if the decoded hostname carries a UAX #9 bidi
      control character: an override (``U+202D``/``U+202E``), embedding
      (``U+202A``\u2013``U+202C``), isolate (``U+2066``\u2013``U+2069``) or directional
      mark (``U+200E``/``U+200F``/``U+061C``). Disjoint from ``bidi_conflict``, which
      reads strong-direction *letters* only and is therefore blind to the RLO
      extension spoof. IDNA2008 disallows every character in the set, so this is
      folded into ``suspicious`` and the characters are stripped from ``canonical``.
    - ``has_invisible``: bool — True if the decoded hostname carries an invisible
      character of any class: zero-width (``U+200B``-``U+200D``,
      ``U+2060``-``U+2064``, ``U+FEFF``, ``U+180E``), tag (``U+E0000``-``U+E007F``),
      variation selector (``U+FE00``-``U+FE0F``, ``U+E0100``-``U+E01EF``),
      noncharacter (``U+FDD0``-``U+FDEF`` and the last two of every plane),
      private use (``U+E000``-``U+F8FF``, planes 15 and 16), or any other
      ``Default_Ignorable_Code_Point``, which UTS #46 deletes as it maps
      (``U+00AD``, ``U+034F``, ``U+115F``-``U+1160``, ``U+17B4``-``U+17B5``,
      ``U+180B``-``U+180F``, ``U+206A``-``U+206F``, ``U+3164``, ``U+FFA0``,
      ``U+1BCA0``-``U+1BCA3``, ``U+1D173``-``U+1D17A``, and the unassigned
      ``U+FFF0``-``U+FFF8`` and ``U+E0080``-``U+E0FFF``; bidi controls excepted). Disjoint from
      ``bidi_control`` — these carry no direction at all, so neither bidi field can
      see them. RFC 5892 puts the tag, variation-selector, noncharacter and
      private-use classes in DISALLOWED outright, which is what justifies including
      private use and variation selectors here. ``U+200C``/``U+200D`` are the
      exception — CONTEXTJ, so conditionally permitted; the screen flags them anyway
      as a deliberate fail-closed policy. Folded into ``suspicious``. They are
      removed per label *before* any other field is computed, so a hostname whose
      only non-ASCII is an invisible no longer reports a phantom script (``U+FEFF``
      sits in the Arabic Presentation Forms block, ``U+FDD0`` in its range).
    - ``compat_fold``: bool — True if any label carried a Unicode **compatibility
      form** before normalization: fullwidth (``ｇoogle``), ligature (``ﬁle``),
      Roman numeral (``Ⅰ``BM), mathematical alphanumeric (``𝗀𝗈𝗈𝗀𝗅𝖾``), circled,
      superscript, and the rest of the compatibility repertoire. The predicate is
      RFC 5892 §2.1's, applied **per code point**: a character ``c`` where
      ``toNFKC(c) != c`` is DISALLOWED in an IDN label, so IDNA2008 disallows the
      whole set and this is folded into ``suspicious`` on the same footing as
      ``bidi_control`` and ``has_invisible``. The threat is a blocklist bypass
      rather than a lookalike: ``ｅvil.com`` is absent from a blocked set, screens
      clean, and resolves to ``evil.com``. Tested per character rather than "NFKC
      changed the label", which would fire on decomposed input that is entirely
      valid (``한국.kr`` written with conjoining jamo). Read per **label**, not over
      the whole hostname: three of the four UTS #46 label separators carry a
      compatibility decomposition (``U+FF0E`` and ``U+FF61`` do, ``U+3002`` does
      not), and a separator is structure rather than label content. This is the one
      field read from the **raw** input — every other field is computed after
      normalization, which is what makes them work and also what erases this
      evidence.
    - ``cross_label_script``: bool — True if the labels span more than one
      distinct script. Broader and noisier than ``bidi_conflict`` (it fires on
      benign IDN ccTLDs like ``google.рф``), so it is **not** folded into
      ``suspicious``; exposed for caller policy.
    - ``label_scripts``: list[list[str]] — per-label resolved scripts, left to right.
    - ``whole_script_confusable``: bool — True if any label is a *whole-script
      confusable*: single-script, non-Latin, whose confusable skeleton is entirely
      Latin (e.g. Cyrillic ``аррӏе`` → ``apple``). A graded **signal, not a
      verdict** — on its own it fires on short non-Latin ccTLDs (``ру``→``py``) and
      on real words (``оса``→``oca``), so it is **not** folded into ``suspicious``.
    - ``label_whole_script_confusable``: list[bool] — per-label flags, parallel to
      ``label_scripts``, so a caller can exclude the TLD label. The precise,
      low-false-positive policy is ``wsc(non-TLD label) and TLD-is-Latin`` (plus a
      caller-supplied protected-name list for the irreducible ``оса``-style case).
    - ``canonical``: str — Latin-normalized form of the hostname.

    A hostname is flagged suspicious if any single label is mixed-script
    (draws on more than one Unicode script, excluding Common/Inherited),
    contains confusable homoglyphs, or has a bidi-direction conflict
    (``bidi_conflict``), carries a bidi control character (``bidi_control``), or
    carries a zero-width/invisible character (``has_invisible``), or carries a
    compatibility form (``compat_fold``).
    The mixed-script rule is conservative and fails closed:
    it flags benign combinations such as Latin+CJK as well as spoofing ones, so a
    caller wanting a more permissive policy can inspect the ``mixed_script`` and
    ``scripts`` fields and decide for itself.

    **A ``False`` (not-suspicious) result is not a safety guarantee.** It means
    only that no mixed-script label and no confusable *from the bundled TR39
    table* was found. Confusables outside the bundled table are not detected and
    report not-suspicious. Base allow/deny decisions on the granular findings
    (including ``whole_script_confusable``) plus your own policy — a detector can
    attest the presence of a problem, never the absence of all problems.

    Args:
        hostname: Hostname string to check (e.g. "example.com").
        contractions: Also fold ASCII digraphs that can impersonate a single letter
            — ``rn`` to ``m``, ``vv`` to ``w``, ``cl`` to ``d`` — into ``canonical``,
            so ``arnazon.com`` canonicalizes to ``amazon.com`` (#562).

            **Off by default, and deliberately confined to hostnames.** Unconditional
            contraction is worse than none: ``rn`` to ``m`` is right for ``arnazon``
            and wrong for ``earnings``, ``turnip`` and ``born``. A hostname is the one
            place where the threat model justifies those false positives and there is
            no running prose to corrupt, so this is not reachable from
            `normalize_confusables` at all.

            Matching is leftmost-longest, and applied per label, so a digraph can never
            form across a dot.

    Returns:
        Tuple of (suspicious, analysis) where analysis is a HostnameAnalysis.

    Examples:
        >>> suspicious, analysis = is_suspicious_hostname("google.com")
        >>> suspicious
        False
        >>> analysis.canonical
        'google.com'
        >>> _s, a = is_suspicious_hostname("arnazon.com", contractions=True)
        >>> a.canonical
        'amazon.com'
    """
    return _is_suspicious_hostname(hostname, contractions=contractions)


# --- Anomaly detection (#389) ---


def has_anomalies(text: str, lexicon: Iterable[str] | Lexicon | None = None) -> bool:
    """Whether any whitespace token carries out-of-place characters that disguise a real word.

    Reports a *technical fact* — a cross-script homoglyph, leet, segmentation, a
    zero-width / bidi control, or zalgo — and leaves the malicious-or-not judgement
    to the caller, exactly as `is_suspicious_hostname` does for hostnames.

    **The confusable table is consulted since #737, and was not before.** `canonicalize`
    has two steps that can put ASCII into its output: NFKC, and the confusable fold. This
    reported the first (``compat_fold``) and had no rule for the second, so
    ``has_anomalies("pɑypal")`` was ``False`` while ``is_confusable`` was ``True`` and
    ``canonicalize`` returned ``paypal``. The ``confusable`` kind closes it. A clean
    result still is not a claim about *unmapped* confusables — see
    `find_unmapped_confusables` for that exposure set.

    **A clean result is not a claim of canonicity (#730).** 142,760 assigned code
    points (5,292 excluding the Private Use Area) are reported clean here and are
    still not their own canonical form — CJK compatibility ideographs, Arabic
    presentation forms, Kangxi radicals, fullwidth and halfwidth forms. That is
    deliberate: ``ＮＨＫ`` is ordinary Japanese text, and a detector that flagged it
    would be one callers switch off (#633, #907). If the
    question is "may I store these bytes as they arrived", ask `is_canonical`,
    which is the verification-path predicate; this one answers "does this look
    disguised".

    ``lexicon`` is a set of common words for the language being protected; it is
    used only by the leet and segmentation branches.  The invisible, bidi, zalgo,
    and mixed-script branches are script-agnostic and **need no lexicon** — calling
    ``has_anomalies(text)`` with no lexicon (or ``lexicon=None``) is valid and will
    still catch those classes of anomaly.  Pass a lexicon if you also want leet and
    segmentation detection.

    **Reusing a large lexicon (HAI-SDLC 6.1).** Passing a raw collection rebuilds
    an internal set on every call. When calling this in a loop with a large
    lexicon, build a `Lexicon` once and pass it instead — the set is built
    a single time and reused across calls, with identical results.

    Args:
        text: Input text.
        lexicon: Common-word collection (set, list, …) for the target language,
            *or* a prebuilt `Lexicon` handle, used only by the leet and
            segmentation branches.  When ``None`` (the default) or an empty
            iterable, those two branches are effectively disabled; all other
            branches still run.

    Returns:
        True if any token tripped a detector.

    Examples:
        >>> has_anomalies("get fr33 stuff", {"free"})
        True
        >>> has_anomalies("a perfectly ordinary sentence")
        False
        >>> has_anomalies("paypаl")  # Cyrillic а — mixed-script, no lexicon needed
        True
        >>> lex = Lexicon({"free"})  # build once, reuse across calls
        >>> has_anomalies("get fr33 stuff", lex)
        True
    """
    if isinstance(lexicon, Lexicon):
        return _has_anomalies_lex(text, lexicon)
    return _has_anomalies(text, set(lexicon) if lexicon is not None else None)


def inspect_anomalies(text: str, lexicon: Iterable[str] | Lexicon | None = None) -> AnomalyReport:
    """Full anomaly analysis: every finding with its span and a plain-language reason.

    Parallel to `is_suspicious_hostname`'s ``HostnameAnalysis``. Returns an
    ``AnomalyReport`` with attributes:

    - ``anomalous``: bool — the same value `has_anomalies` returns.
    - ``kinds``: list[str] — the anomaly kinds that fired, in first-appearance
      order (``"invisible"``, ``"bidi"``, ``"zalgo"``, ``"mixed_script"``,
      ``"leet"``, ``"segmentation"``).
    - ``findings``: list[Finding] — each with ``kind``, ``token``, ``start``/``end``
      (byte offsets), ``detail``, and a plain-language ``reason``.
    - ``reason``: str | None — the first finding's reason.

    The ``lexicon`` is optional (see `has_anomalies`).  When omitted, the
    invisible, bidi, zalgo, and mixed-script branches still run; only leet and
    segmentation detection requires a lexicon.

    **A clean result is not a claim of canonicity (#730).** 142,760 assigned code
    points (5,292 excluding the Private Use Area) are reported clean here and are
    still not their own canonical form — CJK compatibility ideographs, Arabic
    presentation forms, Kangxi radicals, fullwidth and halfwidth forms. That is
    deliberate: ``ＮＨＫ`` is ordinary Japanese text, and a detector that flagged it
    would be one callers switch off (#633, #907). If the
    question is "may I store these bytes as they arrived", ask `is_canonical`,
    which is the verification-path predicate; this one answers "does this look
    disguised".

    **Reusing a large lexicon (HAI-SDLC 6.1).** As with `has_anomalies`,
    pass a prebuilt `Lexicon` to avoid rebuilding the internal set on every
    call when looping over a large lexicon.

    Args:
        text: Input text.
        lexicon: Common-word collection (set, list, …) *or* a prebuilt
            `Lexicon` handle (see `has_anomalies`).
            Defaults to ``None`` (empty — leet/segmentation branches disabled).

    Returns:
        An ``AnomalyReport``.

    Examples:
        >>> r = inspect_anomalies("get fr33", {"free"})
        >>> r.anomalous, r.kinds
        (True, ['leet'])
        >>> r.findings[0].detail
        'free'
        >>> inspect_anomalies("clean text").anomalous
        False
    """
    if isinstance(lexicon, Lexicon):
        return _inspect_anomalies_lex(text, lexicon)
    return _inspect_anomalies(text, set(lexicon) if lexicon is not None else None)
