"""has_anomalies / explain: report that text carries out-of-place characters (a real word
disguised by homoglyph, leet, segmentation, zero-width, bidi, or zalgo), and say WHY.

The name states a technical fact, not a verdict: it reports the anomaly and leaves the
judgement of whether the text is malicious to the caller. The surface mirrors the disarm
crate so the mental model stays simple:

    has_anomalies(text)        -> bool                  like is_mixed_script / is_confusable
    inspect_anomalies(text)    -> AnomalyAnalysis       like is_suspicious_hostname / HostnameAnalysis
    why(text)                  -> str | None            convenience: the first reason
    explain(text)              -> list[Finding]         convenience: every trip, with span

(`is_suspicious` / `inspect_suspicious` / `SuspicionAnalysis` remain as deprecated aliases.)

`AnomalyAnalysis` carries `.anomalous`, `.categories`, `.findings`, `.reason`. A
`Finding` carries `.category`, `.token`, `.start`, `.end`, `.detail`, `.reason` (a plain
sentence). Categories: 'invisible', 'bidi', 'zalgo', 'mixed_script', 'leet',
'segmentation'. The span (start, end) is a character offset into `text`, so a caller can
highlight or redact the offending token.

    >>> for f in explain('please log in at paypа1.com'):
    ...     print(f.start, f.end, f.category, '::', f.reason)
    17 27 mixed_script :: 'paypа1.com' mixes Latin and Cyrillic

`lexicon` is the legitimacy model for the leet / segmentation branches: a set of common
words for the language being protected. It defaults to a bundled common-word frequency
list, so callers need not pass one. The invisible / bidi / zalgo / mixed_script branches
need no lexicon and work for any writing system.

WHAT IT CATCHES (each branch, in order)
  0a invisible : a zero-width / formatting codepoint inside a token (lexicon-free)
  0b bidi      : a bidi override anywhere, or a bidi control inside a majority-Latin
                 token (Trojan Source); spares legitimate directional marks in RTL
  0c zalgo     : excessive stacked combining marks (disarm.is_zalgo)
  1  mixed_script : two scripts inside one token (paypаl); lexicon-free, script-agnostic
  2  leet      : every out-of-place char substitutes a letter and the result is a common
                 word, or within one edit of one for longer decodes (de@lz -> dealz ~ deals)
  3  segmentation : dense separators that spell a real word (v.i.a.g.r.a)

It deliberately leaves alone: real foreign words, proper names, rare real words, and
spoof-looking-but-legitimate tokens (win32, mp3, kΩ) whose digits are literal.

MEASURED (non-circular, real + external attacks; see real_corpus_validation.md):
  homoglyph 100% · zero-width 99.2% · bidi 100% · zalgo 100% · leet 96.4% on true
  letter-substitution disguises; false positives 0.0% plain English, 0.0% spoof-legit
  ham, 0.2% foreign-in-English, and 0 across 24,000 real sentences in 12 scripts.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import disarm

_LEET = {
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "a",
    "5": "s",
    "7": "t",
    "9": "g",
    "@": "a",
    "$": "s",
    "|": "l",
}
# '!' is exclamation far more often than leet-i, so it is wrapping punctuation, not leet
_WRAP = '".,;:?!()[]{}<>«»“”‘’`—… \t' + "'"
_UNITS = {"kω", "mω", "gω", "µf", "nf", "pf", "µm", "µs", "µg", "µa", "µv", "å", "ω", "°c", "°f"}
_INVISIBLE = set("​‌‍⁠⁡⁢⁣﻿")  # soft hyphen U+00AD excluded (legit hyphenation)
_BIDI_OVERRIDE = set("‭‮")
# overrides + isolates only. Bare directional marks (LRM/RLM/ALM) and plain embeddings
# (LRE/RLE/PDF) are common-and-benign in real RTL and social text (Twitter wraps hashtags
# in LRE..PDF), whereas Trojan Source uses overrides and isolates.
_BIDI_FMT = set("‭‮⁦⁧⁨⁩")
_ALPHA = "abcdefghijklmnopqrstuvwxyz"

# branch categories
INVISIBLE = "invisible"
BIDI = "bidi"
ZALGO = "zalgo"
MIXED_SCRIPT = "mixed_script"
LEET = "leet"
SEGMENTATION = "segmentation"

_REASON = {
    INVISIBLE: "{token!r} contains an invisible character ({detail})",
    BIDI: "{token!r} contains a bidirectional control character ({detail})",
    ZALGO: "{token!r} is overloaded with combining marks (zalgo)",
    MIXED_SCRIPT: "{token!r} mixes {detail}",
    LEET: "{token!r} decodes to the word {detail!r}",
    SEGMENTATION: "{token!r} splits the word {detail!r}",
}


@dataclass(frozen=True)
class Finding:
    """One reason the text tripped. `start`/`end` are char offsets into the text."""

    category: str
    token: str
    start: int
    end: int
    detail: str = ""

    @property
    def reason(self) -> str:
        return _REASON[self.category].format(token=self.token, detail=self.detail)

    def __str__(self) -> str:
        return self.reason


@dataclass(frozen=True)
class AnomalyAnalysis:
    """Structured result, parallel to disarm.HostnameAnalysis.

    `anomalous` is the same bool `has_anomalies` returns; `categories` lists the branches
    that fired (in order of first appearance); `findings` carries the per-token detail with
    spans; `reason` is the first plain-language reason, or None.
    """

    anomalous: bool
    categories: list[str]
    findings: list[Finding]
    reason: str | None


# ---- default lexicon (bundled, lazy) ------------------------------------------------
_DEFAULT_LEXICON = None


def default_lexicon():
    """A common-word frequency list, built once and cached. Empty if unavailable."""
    global _DEFAULT_LEXICON
    if _DEFAULT_LEXICON is None:
        try:
            from spellchecker import SpellChecker

            freq = SpellChecker().word_frequency
            _DEFAULT_LEXICON = frozenset(
                w for w in freq.keys() if len(w) >= 2 and w.isalpha() and freq[w] * 1e6 >= 0.3
            )
        except Exception:
            _DEFAULT_LEXICON = frozenset()
    return _DEFAULT_LEXICON


# ---- helpers ------------------------------------------------------------------------
_SCRIPT_RANGES = [
    (0x41, 0x5A, "Latin"),
    (0x61, 0x7A, "Latin"),
    (0xC0, 0x24F, "Latin"),
    (0x370, 0x3FF, "Greek"),
    (0x400, 0x4FF, "Cyrillic"),
    (0x530, 0x58F, "Armenian"),
    (0x590, 0x5FF, "Hebrew"),
    (0x600, 0x6FF, "Arabic"),
    (0x900, 0x97F, "Devanagari"),
    (0xE00, 0xE7F, "Thai"),
    (0x3040, 0x30FF, "Kana"),
    (0x4E00, 0x9FFF, "Han"),
]


def _script_of(ch: str):
    o = ord(ch)
    for a, b, name in _SCRIPT_RANGES:
        if a <= o <= b:
            return name
    return None


def _scripts(token: str):
    seen = []
    for ch in token:
        if ch.isalpha():
            sc = _script_of(ch)
            if sc and sc not in seen:
                seen.append(sc)
    return seen


def _codepoint(ch: str) -> str:
    try:
        return "U+%04X %s" % (ord(ch), unicodedata.name(ch))
    except ValueError:
        return "U+%04X" % ord(ch)


def _latin_frac(tok: str) -> float:
    letters = [c for c in tok if c.isalpha()]
    return (sum(c.isascii() for c in letters) / len(letters)) if letters else 0.0


def _is_zalgo(text: str) -> bool:
    try:
        return bool(disarm.is_zalgo(text))
    except Exception:
        return False


def _base_ascii(c: str) -> str:
    return re.sub(r"[^a-z]", "", c.lower())


def _leet_demangle(c: str):
    """Undo leet only if every non-letter substitutes a letter; else None.
    Apostrophes are skipped so contractions decode (`d0n't` -> `dont`)."""
    out = []
    for ch in c:
        if ch.isalpha():
            out.append(ch.lower())
        elif ch in _LEET:
            out.append(_LEET[ch])
        elif ch in "'’":
            continue
        else:
            return None
    return "".join(out)


def _nearest(d: str, lexicon):
    splits = [(d[:i], d[i:]) for i in range(len(d) + 1)]
    for e in (
        [a + b[1:] for a, b in splits if b]
        + [a + c + b[1:] for a, b in splits if b for c in _ALPHA]
        + [a + c + b for a, b in splits for c in _ALPHA]
    ):
        if e in lexicon:
            return e
    return None


def _seg_word(c: str, lexicon):
    seps = sum(1 for ch in c if ch in "._-")
    letters = [ch for ch in c if ch.isalpha()]
    if seps < max(2, (len(letters) - 1) * 0.6):
        return None
    # separators must split letters singly (v.i.a.g.r.a), not wrap whole words (6-foot-6)
    if any(len(p) > 1 and any(ch.isalpha() for ch in p) for p in re.split(r"[._\-]+", c)):
        return None
    word = "".join(letters).lower()
    return word if (len(word) >= 4 and word in lexicon) else None


# ---- the classifier -----------------------------------------------------------------
def _classify(tok: str, start: int, lexicon):
    """Return a Finding for this token, or None."""
    end = start + len(tok)
    # ASCII fast-path: the invisible / bidi / zalgo / mixed-script branches can only fire
    # on codepoints above U+007F, so a pure-ASCII token skips every disarm call.
    if not tok.isascii():
        for i, ch in enumerate(tok):  # 0a invisible inside a LATIN word
            # ZWJ/ZWNJ are legitimate joiners in Indic/Arabic scripts, so require ASCII-Latin
            # letters on both sides (the Trojan-source / evasion vector targets Latin text)
            if (
                ch in _INVISIBLE
                and any(c.isascii() and c.isalpha() for c in tok[:i])
                and any(c.isascii() and c.isalpha() for c in tok[i + 1 :])
            ):
                return Finding(INVISIBLE, tok, start, end, _codepoint(ch))
        for ch in tok:  # 0b bidi override (always)
            if ch in _BIDI_OVERRIDE:
                return Finding(BIDI, tok, start, end, _codepoint(ch))
        if _latin_frac(tok) >= 0.5:  # 0b bidi control in Latin token
            for ch in tok:
                if ch in _BIDI_FMT:
                    return Finding(BIDI, tok, start, end, _codepoint(ch))
        if _is_zalgo(tok):  # 0c zalgo
            return Finding(ZALGO, tok, start, end, "stacked combining marks")
        core = tok.strip(_WRAP)
        if len(core) >= 2 and core.lower() not in _UNITS and disarm.is_mixed_script(core):
            scripts = _scripts(core)  # 1 Latin homoglyph (Cyrillic/Greek)
            if "Latin" in scripts and ("Cyrillic" in scripts or "Greek" in scripts):
                return Finding(MIXED_SCRIPT, tok, start, end, " and ".join(scripts))
    core = tok.strip(_WRAP)
    if len(core) < 2:
        return None
    if (
        any(ch.isdigit() or ch in "@$|" for ch in core)
        and re.fullmatch(r"\d+(?:st|nd|rd|th|am|pm)", core, re.IGNORECASE) is None
    ):  # 2 leet
        base = _base_ascii(core)
        d = _leet_demangle(core)
        # reject a real word with a TRAILING literal number (Power5 -> power, name1),
        # but keep interior substitutions (ab0ut) and short leet whose base fragment only
        # coincidentally sits in the list (th3 -> the, tim3 -> time): trust base only at len>=4
        literal = (
            len(base) >= 4
            and base in lexicon
            and re.match(r"^[A-Za-z]+[0-9@$|]+$", core) is not None
        )
        if d and len(base) >= 2 and not literal and len(d) >= 3 and d != base:
            if d in lexicon:
                return Finding(LEET, tok, start, end, d)
            if len(d) >= 6:
                near = _nearest(d, lexicon)
                if near:
                    return Finding(LEET, tok, start, end, near)
    seg = _seg_word(core, lexicon)  # 3 segmentation
    if seg and any(ch in "._-" for ch in core):
        return Finding(SEGMENTATION, tok, start, end, seg)
    return None


# ---- public API ---------------------------------------------------------------------
def has_anomalies(text: str, lexicon=None) -> bool:
    """Fast yes/no, parallel to `disarm.is_mixed_script` / `is_confusable` / `is_ascii`.

    Reports a technical fact: the text carries out-of-place characters (a homoglyph, leet,
    segmentation, zero-width, bidi, or zalgo). Whether that is malicious is the caller's
    judgement. Short-circuits on the first trip. `lexicon` defaults to a bundled common-word
    list.
    """
    lex = default_lexicon() if lexicon is None else lexicon
    return any(_classify(m.group(), m.start(), lex) is not None for m in re.finditer(r"\S+", text))


def inspect_anomalies(text: str, lexicon=None) -> AnomalyAnalysis:
    """Full analysis, parallel to `disarm.is_suspicious_hostname` / `HostnameAnalysis`.

    Returns an `AnomalyAnalysis` whose `.anomalous` matches `has_anomalies(text)`, with
    `.findings` (every trip, with span and reason), `.categories`, and `.reason`.
    """
    lex = default_lexicon() if lexicon is None else lexicon
    findings = []
    for m in re.finditer(r"\S+", text):
        f = _classify(m.group(), m.start(), lex)
        if f is not None:
            findings.append(f)
    categories = list(dict.fromkeys(f.category for f in findings))
    return AnomalyAnalysis(
        anomalous=bool(findings),
        categories=categories,
        findings=findings,
        reason=findings[0].reason if findings else None,
    )


def explain(text: str, lexicon=None) -> list[Finding]:
    """Convenience: every Finding. Same as `inspect_anomalies(text).findings`."""
    return inspect_anomalies(text, lexicon).findings


def why(text: str, lexicon=None):
    """Convenience: the first reason. Same as `inspect_anomalies(text).reason`."""
    return inspect_anomalies(text, lexicon).reason


def has_anomalous_token(tok: str, lexicon) -> bool:
    """Single-token boolean."""
    return _classify(tok, 0, lexicon) is not None


# ---- deprecated aliases (the old judgement-framed names) ----------------------------
# `is_suspicious` made a moral call; `has_anomalies` reports the technical fact and leaves
# the judgement to the caller. The old names are kept so existing callers keep working.
is_suspicious = has_anomalies
inspect_suspicious = inspect_anomalies
SuspicionAnalysis = AnomalyAnalysis
is_suspicious_token = has_anomalous_token
