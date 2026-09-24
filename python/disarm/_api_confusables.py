"""Confusables and identifier spoofing: detection, coverage, smuggled payloads, key
collisions, and the edit-distance half of the same question."""

from __future__ import annotations

import warnings as _warnings
from collections.abc import Iterable

from disarm._api_common import _target_script
from disarm._boundary import (
    KeyCollision,
    NearestMatch,
    SmuggledPayload,
    _confusable_coverage,
    _decode_smuggled,
    _edit_distance,
    _find_confusables,
    _find_key_collisions,
    _find_unmapped_confusables,
    _is_confusable,
    _nearest_match,
    _unmapped_confusables,
)
from disarm._enums import (
    ConfusableCoverage,
    Script,
)


def is_confusable(
    text: str,
    *,
    target_script: str | Script = "latin",
    # confusable_homoglyphs compatibility
    greedy: bool | None = None,
    preferred_aliases: list[str] | None = None,
) -> bool:
    """True if text contains characters confusable with target-script characters.

    **Printable ASCII is never a detection (#957).** ``"``, the backtick and ``|`` are TR39
    confusable sources and the fold rewrites all three — deliberately, and recorded under
    *Five surfaces rewrite printable ASCII* in the limitations page. Counting them here
    made this return ``True`` for every quoted sentence and every JSON document; 588 of
    the 1,342 pure-ASCII lines of this repository's own prose fired. The rows stay in the
    fold and stop being reported, so ``normalize_confusables('|')`` is still ``'l'`` while
    ``is_confusable('|')`` is ``False``.

    Args:
        text: Input string.
        target_script: Script to check confusability against: ``"latin"``
            (default), ``"cyrillic"``, ``"arabic"`` or ``"hebrew"``, the same four
            targets `normalize_confusables` takes. Any other value raises
            ``DisarmError``.
        greedy: ``confusable_homoglyphs`` compatibility — ignored, with a
            ``DeprecationWarning`` *when explicitly passed*. disarm always checks
            all characters.
        preferred_aliases: ``confusable_homoglyphs`` compatibility — ignored,
            with a ``DeprecationWarning`` *when explicitly passed*. disarm uses
            its own script detection engine.

    Returns:
        True if any confusable homoglyphs are present.

    Raises:
        DisarmError: If *target_script* is not one of the four targets.

    Examples:
        >>> is_confusable("pаypal")  # Cyrillic а looks like Latin a
        True
        >>> is_confusable("paypal")  # all genuine Latin
        False
    """
    if greedy is not None:
        _warnings.warn(
            "The 'greedy' parameter is not supported by disarm.is_confusable(); "
            "disarm always checks all characters.",
            DeprecationWarning,
            stacklevel=2,
        )
    if preferred_aliases is not None:
        _warnings.warn(
            "The 'preferred_aliases' parameter is not supported by "
            "disarm.is_confusable(); disarm uses its own script detection.",
            DeprecationWarning,
            stacklevel=2,
        )
    return _is_confusable(text, target_script=_target_script(target_script))


def unmapped_confusables(*, target_script: str | Script = "latin") -> frozenset[str]:
    """Every upstream confusable source disarm's bundled table does not fold (#563).

    Read this as **exposure**, not as a score. A tool at 95% per-source coverage is not
    95% safe — it is one query away from the other 5%, and this set is where an adaptive
    attacker goes when the mapped sources stop working.

    Most of the set is out of scope rather than missing: a source whose upstream target
    is non-Latin has no business in the to-Latin table. Cross-reference
    `CONFUSABLES_VERSION` and ``docs/provenance.md`` before reading any one
    codepoint as a defect.

    **The population is TR39's, not the world's (#738).** This enumerates the 6,565
    single-code-point sources in ``confusables_upstream_sources.tsv`` — what upstream
    lists and disarm drops. A pair upstream never listed is outside the denominator as
    well as outside the table: ``U+4E28`` and ``U+3021`` score higher against ``l`` than
    most of TR39 in a measured font survey, and neither appears here. THREAT_MODEL.md's
    *normalization is enumerate-the-known* is the honest reading; this is not a complete
    gap report. It is also single-code-point by construction, so the multi-character
    direction (``rn`` → ``m``, ``vv`` → ``w``, ``cl`` → ``d``) has no denominator at all —
    disarm's answer there is three contraction rows, reachable only from
    `is_suspicious_hostname` with ``contractions=True``, against a measured population of
    571,753 bigram-to-character pairs, most of them not registrable.

    The set includes five ASCII characters — ``%``, ``0``, ``1``, ``I`` and ``m``. TR39
    is a *skeleton* transform (m→rn, I/1→l, 0→O), so those are upstream sources; disarm
    does not apply those rows because folding a legitimate ASCII ``m`` to ``rn`` corrupts
    prose. Nothing is filtered out here: a coverage report that quietly drops rows reads
    as coverage it does not have.

    Args:
        target_script: Which bundled table to report against — a `Script` member, or
            the lowercase token ``"latin"`` (default), ``"cyrillic"``, ``"arabic"`` or
            ``"hebrew"``. They have genuinely different coverage, and the residue is
            largest for the RTL targets because most of TR39 has no Arabic or Hebrew
            member at all.

            **Two spellings, and the member bridges them (#767).** `list_scripts` returns
            ``"Arabic"`` and this parameter's raw-string form takes ``"arabic"``; a raw
            string stays strict on purpose, so a caller who hard-coded the wrong one finds
            out. Pass the member and the question does not arise, since
            ``Script("Arabic")`` converts a name from `list_scripts`:
            ``unmapped_confusables(target_script=Script(name))``.

            **Four tables, 62 known scripts.** `list_scripts` answers "which scripts can
            disarm identify"; this parameter answers "which scripts can disarm fold
            *toward*", and those are different questions. A script with no bundled table
            is refused rather than answered with a count, because a number determined
            entirely by a table's absence reads as coverage and is not. For the fair
            per-script figure — of the sources whose prototype is in script X, how many
            disarm reaches — call `confusable_coverage`, which answers for every script
            including the ones with no bundled table (#963).

    Returns:
        A frozenset of single-character strings.

    Raises:
        InvalidArgumentError: If *target_script* is not a supported script.

    Examples:
        >>> unmapped = unmapped_confusables()
        >>> "\u0430" in unmapped  # Cyrillic а IS folded, so it is not exposure
        False
        >>> "m" in unmapped  # TR39 skeleton source m→rn, deliberately not applied
        True
    """
    return frozenset(_unmapped_confusables(target_script=_target_script(target_script)))


def confusable_coverage(script: str | Script) -> ConfusableCoverage:
    """TR39 sources whose prototype is in *script*, and how many disarm folds (#963).

    The denominator `unmapped_confusables` does not have. That function measures one
    bundled table against the whole 6,565-source population, which is the right question
    for a target disarm ships and a misleading one for a script it does not: Greek
    reports almost the entire population unmapped, and the number means only *"there is
    no Greek table"*. A count determined by a table's absence is a blind spot with a
    number in front of it, which is worse than the exception it replaced, because it
    looks like data.

    This is the fair figure — of the sources whose prototype is in this script, how many
    does disarm reach:

    Args:
        script: Script name in disarm's spelling (``"Greek"``) or a `Script` member.

    Returns:
        A `ConfusableCoverage` dict with ``script``, ``sources`` and ``folded`` keys.

    Raises:
        InvalidArgumentError: If *script* is neither a script disarm knows nor one the
            census has a row for.

    Note:
        ``folded`` counts sources any bundled table reaches, not sources folded *toward*
        this script. Greek is not zero: 71 of its 159 sources are Greek letters the Latin
        table folds. The question a caller has is whether disarm neutralizes the source
        at all, not which prototype TR39 picked for it.

        The grouping uses the UCD's script property, but the census is keyed in disarm's
        namespace — the UCD name with underscores removed, which is the spelling
        `list_scripts` returns for every script the two tables share. So 18 scripts appear
        that disarm's own enum does not name (``"Yi"``, ``"Siddham"``, ``"PauCinHau"`` and
        15 others, 69 sources between them), spelled the same way as the rest. A script
        disarm knows that TR39 never uses as a prototype returns ``0`` of ``0``.

    Examples:
        >>> confusable_coverage("Greek")["sources"]
        159
        >>> confusable_coverage("Han")["folded"]  # 1,393 sources, no CJK fold table
        0
        >>> confusable_coverage(Script.THAANA)  # a script TR39 never targets
        {'script': 'Thaana', 'sources': 0, 'folded': 0}
    """
    key = script.value if isinstance(script, Script) else script
    name, sources, folded = _confusable_coverage(key)
    return {"script": name, "sources": sources, "folded": folded}


def find_confusables(
    text: str,
    *,
    target_script: str | Script = "latin",
    allowed_scripts: Iterable[str | Script] | None = None,
) -> list[tuple[str, int, str]]:
    """Find the confusables in *text* that disarm's table **does** fold (#737).

    The mirror of `find_unmapped_confusables`: that one answers *"what would survive the
    fold?"* — exposure — and this one answers *"what did the fold change, and to what?"* —
    evidence.

    Note:
        **Pair this with a key reducer; neither is complete (#882).** This function
        reports what *looks like* something else. `canonicalize` and the other key
        reducers report what two strings *collapse to*. Measured over
        ``confusable-bench.v1`` — 120 malicious identifiers, 20 benign — this catches 66
        and the six reducers together catch 72, but **either one firing catches 108**, at
        0 false positives for each alone and for the pair.

        The split is structural rather than incidental. This sees a character that has a
        fold target, so it takes the composability (31/31) and impersonation (35/35)
        classes outright and cannot see evasion (0/54), where the attack is in what has
        no fold target and survives. The reducers are the mirror: 42/54 on evasion, 0/31
        on composability. A registry needs both questions asked — see
        *Detection and reduction answer different questions* in the confusables guide.

    `is_confusable` returns a bare ``bool`` and `normalize_confusables` returns the folded
    string; neither says **where**. Diffing the two does not work either, because the fold
    is not length-preserving (``ﬁ`` becomes ``fi``).

    Composition runs exactly as it does in `normalize_confusables`, and offsets are
    anchored in *text* rather than in the composed intermediate — the same contract the
    sibling gives. Each reported character is the one *text* holds at that offset: a
    decomposed homoglyph is found as the character it composes to and reported as its
    base, as written, with the fold of the composed character as ``target`` (#1040).

    **This asks what could imitate a `target_script` letter, not what is
    suspicious (#900).** It runs one character at a time with no reference to the
    string around it, so a word written entirely in another script comes back as a
    list of findings — ``find_confusables("Москва")`` is six findings out of six
    letters, and Moscow is not an attack. A caller who gates registration on
    ``bool(find_confusables(name))`` has built a registry that rejects its own
    users' language.

    ``allowed_scripts`` is how you say what legitimate input looks like. A
    character belonging to one of those scripts is not reported; everything else
    still is.

    It cannot suppress a scriptless spoof, by construction: ``Common`` and
    ``Inherited`` are never allowed whatever you pass, and the characters that
    carry a spoof without belonging to any script — ``ℐ``, ``Ⅰ``, ``𝐈``, the
    mathematical alphanumerics — are ``Common``. So declaring a script narrows the
    false positives without reopening the whole-script substitutions this function
    exists to catch.

    Args:
        text: Input Unicode string.
        target_script: Which bundled table to report against (default ``"latin"``).
        allowed_scripts: Scripts whose characters are legitimate here, named as
            `detect_scripts` names them (``"Cyrillic"``) and matched
            case-insensitively. ``None`` (default) reports every folded confusable.

    Returns:
        List of ``(char, byte_offset, target)`` for each folded confusable.

    Raises:
        TypeError: If *text* is not a ``str``.
        InvalidArgumentError: If *target_script* or any *allowed_scripts* entry is
            not a supported script.

    Examples:
        >>> find_confusables("p\u0251ypal")
        [('\u0251', 1, 'a')]
        >>> find_confusables("paypal")
        []
        >>> len(find_confusables("Москва"))  # every letter, and none of it an attack
        6
        >>> find_confusables("Москва", allowed_scripts=["Cyrillic"])
        []
        >>> find_confusables("hell\u043e", allowed_scripts=["Latin"])  # still caught
        [('\u043e', 4, 'o')]
    """
    if not isinstance(text, str):
        raise TypeError(f"find_confusables() expects str, got {type(text).__name__}")
    allowed = (
        None
        if allowed_scripts is None
        else [s.value if isinstance(s, Script) else str(s) for s in allowed_scripts]
    )
    result: list[tuple[str, int, str]] = _find_confusables(
        text, target_script=_target_script(target_script), allowed_scripts=allowed
    )
    return result


def decode_smuggled(text: str) -> list[SmuggledPayload]:
    """Decode what a smuggled run *spells*, rather than reporting one is present (#701).

    disarm strips the three ASCII-smuggling carriers and `inspect_anomalies` reports
    that invisible characters are there. Neither answer tells you the run reads
    ``tracked-by:acct-99213``.

    Presence and decode are different strengths of evidence. An invisible character
    can arrive by accident — a copy-paste artefact, a BOM, an editor quirk. A run
    that decodes to readable text cannot: random damage does not spell words. A
    successful decode needs no threshold and no policy to interpret, which is why it
    is worth reporting separately from the ``invisible`` kind.

    Three schemes, all arithmetic on code point values with no table behind them:

    | scheme | carrier | encoding |
    |---|---|---|
    | ``tag_ascii`` | ``U+E0020``–``U+E007E`` | subtract ``0xE0000``, one byte each |
    | ``variation_bytes`` | ``U+FE00``–``U+FE0F``, ``U+E0100``–``U+E01EF`` | index 0–255 |
    | ``zero_width_binary`` | ``U+200B`` = 0, ``U+200C`` = 1 | MSB first; ZWJ/WJ/BOM separate |
    | ``percent_escape`` | ``%XX``, two hex digits | one byte per triple, decoded once (#727) |

    ``text`` is populated **only** when the bytes are valid UTF-8 and wholly
    printable — meaning *a reader would see it*, not merely "no control character".
    A payload of ``U+202E`` + ``U+200B`` is valid UTF-8 with no control in it and
    renders as nothing, so it comes back as bytes with ``text=None``, as does a run
    of arbitrary selectors. Reporting garbage would undo the reason a decode is
    trustworthy.

    A carrier of the same scheme beside a payload is not read into it. A
    presentation selector (``U+FE0E`` or ``U+FE0F``) attached to the character before
    it, such as the ``VS16`` that ends a fully qualified emoji, is left out of a
    variation run whenever the rest of the run decodes as text. A zero-width run whose
    bit count is not a multiple of 8 has two candidate frames, stray bits dropped from
    the end or from the start: ``text`` is set only when exactly one frame is
    printable, and otherwise the head-aligned bytes come back with ``text=None``.
    When both frames are printable, `inspect_anomalies` still reports the run as
    ``smuggled``, with both readings as the token (``"44 | hi"``).

    ``units`` counts the characters the run **consumed**, which is not the same as
    the carriers that carried a byte: the zero-width scheme counts its
    ``ZWJ``/``WJ``/``BOM`` separators and the tag scheme counts a trailing
    ``CANCEL TAG``.

    A well-formed emoji subdivision flag is not a payload: ``U+1F3F4`` + tag letters
    + ``U+E007F`` spelling one of the three RGI values is the Scotland flag, and the
    allowlist used here is the stripper's own rather than a second copy of it.

    ``percent_escape`` is the one scheme that is **not** fed to the anomaly
    detector. A ``%XX`` run spelling readable text is ordinary in any URL, where the
    three invisible carriers are never ordinary; `inspect_anomalies` would fire
    ``smuggled`` on every escaped query string. This function reports it — as
    evidence, decoded once — and the detector does not. ``%25%32%45`` spells
    ``%2E``, and that ``text`` is the sign of double-encoding, not a prompt to
    decode again.

    Args:
        text: Input string.

    Returns:
        One `SmuggledPayload` per run, in order of appearance.

    Examples:
        >>> hidden = "".join(chr(ord(c) + 0xE0000) for c in "hi")
        >>> found = decode_smuggled(f"hello{hidden}")
        >>> found[0].text, found[0].scheme, found[0].start
        ('hi', 'tag_ascii', 5)
        >>> decode_smuggled("hello world")
        []
    """
    result: list[SmuggledPayload] = _decode_smuggled(text)
    return result


def find_unmapped_confusables(
    text: str, *, target_script: str | Script = "latin"
) -> list[tuple[str, int]]:
    """Find confusable sources in *text* that disarm's table does not fold (#563).

    The confusables analogue of `find_untranslatable`, and it follows the same
    convention: ``(character, byte_offset)`` pairs in order of appearance. This is what
    turns `unmapped_confusables` from a global number into something answerable
    against your own traffic.

    Composition runs exactly as it does in `normalize_confusables`, so a
    *decomposed* homoglyph whose precomposed form is mapped counts as covered rather
    than as a gap — otherwise the report would disagree with what the transform does.
    Offsets are anchored in *text*, never in the composed intermediate, and each reported
    character is the one *text* holds at its offset (#1040).

    Ordinary English will report the letter ``m``; see `unmapped_confusables` for
    why that is deliberate.

    Args:
        text: Input Unicode string.
        target_script: Which bundled table to report against (default ``"latin"``).

    Returns:
        List of ``(char, byte_offset)`` for each unmapped confusable source.

    Raises:
        TypeError: If *text* is not a ``str``.
        InvalidArgumentError: If *target_script* is not a supported script.

    Examples:
        >>> find_unmapped_confusables("p\u0430ypal")  # Cyrillic а folds — covered
        []
        >>> find_unmapped_confusables("hello")
        []
    """
    if not isinstance(text, str):
        raise TypeError(f"find_unmapped_confusables() expects str, got {type(text).__name__}")
    return _find_unmapped_confusables(text, target_script=_target_script(target_script))


def find_key_collisions(
    values: list[str],
    *,
    key: str,
    lang: str | None = None,
) -> list[KeyCollision]:
    """Which of *values* reduce to the same identity key (#620).

    Every other disarm detector is a single-string predicate, and a collision is
    not a property of a single string — ``groß.txt`` is an ordinary German
    filename, and ``аdmin`` is only a problem next to ``admin``. This is the
    set-shaped question: **given these names, which of them are the same name?**

    That is what node-tar's ``PathReservations`` guard failed to ask before
    extracting two paths in parallel (CVE-2026-23950), and what a registry has to
    ask before accepting a second ``admin`` (CVE-2013-7236). The two want opposite
    policies from the same answer — one refuses the batch, the other refuses the
    registration — so this reports and decides nothing.

    **Choosing *key* is choosing the policy**, and there is no default. Measured
    against the four collision CVEs in the validation matrix:

    ============================ ========== ========== ========= =========
    key                          2026-23950 2019-19844 2013-7236 2020-12063
    ============================ ========== ========== ========= =========
    ``"fold_case"``              yes        --         --        --
    ``"search_key"``             yes        yes        yes       yes
    ``"catalog_key"``            yes        yes        yes       yes
    ``"canonicalize"``           --         yes        yes       yes
    ``"canonicalize_strict"``    --         yes        yes       yes
    ``"normalize_confusables"``  --         yes        yes       yes
    ============================ ========== ========== ========= =========

    A stronger key finds more collisions, including ones nobody attacked:
    ``search_key`` collides ``Muller`` with ``Müller`` and ``Ivan`` with ``Иван``.
    That is not a false positive — they really are one key — it is the cost of the
    key you chose. ``sort_key`` is deliberately not offered: a sort key exists *to*
    collide, so reporting its collisions would be noise.

    Reducing and grouping happen in one pass over one reducer, so the report
    cannot disagree with the collapse it describes. A group is returned only when
    it holds **two or more distinct inputs** — the same string twice is the same
    name twice, which a reservation table already handles.

    **The return is not a partition, and the two counts do not add (#763).** A name
    that collides with nothing never appears, so the groups do not cover the input.
    The quantity a registry actually wants — *after reduction, how many distinct
    identities does this batch hold?* — has to be derived, and there is one correct
    spelling::

        reduced = len(set(values)) - sum(len(g.values) for g in groups) + len(groups)

    ``values`` and ``indices`` have **different denominators by design** (see
    `KeyCollision`), so they must never be arithmetically combined. Substituting
    ``g.indices`` for ``g.values`` above, or ``len(values)`` for ``len(set(values))``,
    gives a formula that is right on every duplicate-free batch and wrong the moment an
    input repeats. Measured over 400 duplicate-free batches all four spellings agree
    with the truth; over 400 with one repeat injected, only this one does.

    Args:
        values: The set to check. Order is preserved in the report; the batch cap
            is the same 100,000 every other batch entry point uses.
        key: Which reducer builds the keys — one of ``"fold_case"``,
            ``"search_key"``, ``"catalog_key"``, ``"canonicalize"``,
            ``"canonicalize_strict"``, ``"normalize_confusables"``.
        lang: Language hint, reaching ``search_key`` and ``catalog_key``, whose
            romanization is language-dependent; ignored by the rest. Under
            ``lang="de"``, ``Müller`` and ``Mueller`` are one key.

    Returns:
        A `KeyCollision` per colliding group, in order of the first index
        that participates. Each has ``key`` (the shared reduced form), ``values``
        (the distinct inputs, first-appearance order) and ``indices`` (every
        position, ascending — not parallel to ``values``).

    Raises:
        TypeError: If *values* is not a list of ``str``.
        InvalidArgumentError: If *key* is not one of the six.
        ResourceLimitError: If *values* exceeds the batch cap.

    Examples:
        >>> found = find_key_collisions(
        ...     ["groß.txt", "gross.txt", "other.txt"], key="fold_case"
        ... )
        >>> found[0].key
        'gross.txt'
        >>> found[0].values
        ['groß.txt', 'gross.txt']
        >>> found[0].indices
        [0, 1]
        >>> find_key_collisions(["a.txt", "b.txt"], key="fold_case")
        []

        A repeated input — the shape every other example omits, and the only shape
        that separates the correct derivation from its three near-misses:

        >>> names = ["admin", "admin", "Admin"]
        >>> groups = find_key_collisions(names, key="fold_case")
        >>> groups[0].values          # distinct inputs: two
        ['admin', 'Admin']
        >>> groups[0].indices         # occurrences: three
        [0, 1, 2]
        >>> len(set(names)) - sum(len(g.values) for g in groups) + len(groups)
        1

        Three names, one identity. The three near-misses give 2, 0 and 1 — the last
        by cancellation rather than by construction.
    """
    if not isinstance(values, list):
        raise TypeError(f"find_key_collisions() expects list[str], got {type(values).__name__}")
    for value in values:
        if not isinstance(value, str):
            raise TypeError(
                f"find_key_collisions() expects list[str], got {type(value).__name__} in the list"
            )
    return _find_key_collisions(values, key=key, lang=lang)


def edit_distance(a: str, b: str) -> int:
    """Levenshtein edit distance between *a* and *b*, in **characters**.

    The one class of registry spoofing disarm's Unicode machinery deliberately does not
    model. ``paypa1``, ``g1thub``, ``adm1n`` and ``supp0rt`` are ASCII substitutions, and
    no confusable table should fold ASCII ``1`` onto ``l`` — doing so would wreck ordinary
    text. So every key reducer misses all twelve such rows in ``confusable-bench.v1``, and
    so does `find_confusables`. That is correct behaviour, and it left the class with no
    reachable defence from Python even though the function was already compiled into the
    wheel (#883).

    All twelve are **distance 1** from the name they imitate, so guarding a reserved list
    needs only ``edit_distance(candidate, reserved) <= 1``.

    Counts **Unicode scalar values**, not UTF-8 bytes: ``"é"`` is one unit, so ``"é"`` and
    ``"e"`` are one edit apart rather than two.

    That is not the same as ignoring composition. A composed ``"café"`` and a decomposed
    ``"cafe\u0301"`` are **2** edits apart, because the decomposed form is one scalar
    longer and the letter differs. Reduce first when you want them to compare equal —
    ``edit_distance(canonicalize(a), canonicalize(b))`` is 0 for that pair.

    Args:
        a: First string.
        b: Second string.

    Returns:
        The number of single-character insertions, deletions or substitutions
        that turn *a* into *b*. ``0`` when they are equal.

    Examples:
        >>> edit_distance("paypa1", "paypal")
        1
        >>> edit_distance("stripe", "stripe")
        0
        >>> edit_distance("xx", "paypal")
        6

    See Also:
        `nearest_match`: the same distance against a list of protected names.
    """
    return _edit_distance(a, b)


def nearest_match(
    value: str, candidates: list[str], *, max_distance: int = 1
) -> NearestMatch | None:
    """The candidate closest to *value*, with its distance — or ``None`` if none is close.

    Reports; it does not decide. `find_key_collisions` set that precedent and this follows
    it: the distance comes back so **you** apply the policy, rather than the library
    applying one it cannot know.

    Note:
        **Exact matches are reported, with distance 0.** disarm's internal *"did you
        mean …?"* helper skips them, because there the caller has already rejected the
        input — a registry asking about a name it protects verbatim would have been told
        ``None``. That, and a threshold tuned for two-letter language codes, is why this
        is a separate function rather than that one exposed (#883).

    Ties go to the **first** candidate at the lowest distance, so the order you supply
    decides. Sort *candidates* if that matters to you.

    Args:
        value: The identifier to check.
        candidates: The protected names to check it against.
        max_distance: Largest distance to report. ``1`` catches every ASCII
            substitution in ``confusable-bench.v1``; raising it trades precision
            for reach and is your call to make.

    Returns:
        A `NearestMatch` with ``value`` and ``distance`` for the closest candidate
        within *max_distance*, or ``None``. A named object rather than a tuple,
        because ``(str, int)`` at a call site does not say which number is which.

    Examples:
        >>> RESERVED = ["paypal", "stripe", "admin"]
        >>> hit = nearest_match("paypa1", RESERVED)
        >>> hit.value, hit.distance
        ('paypal', 1)
        >>> nearest_match("admin", RESERVED).distance
        0
        >>> nearest_match("something-else", RESERVED) is None
        True

    See Also:
        `find_confusables`: the Unicode half of the same question.
        `canonicalize`: reduce first when you want accents and homoglyphs ignored too.
    """
    return _nearest_match(value, candidates, max_distance=max_distance)
