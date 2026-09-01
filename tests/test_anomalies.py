"""Python binding for the out-of-place-character detector (#389).

The exhaustive per-branch coverage lives in the Rust core (src/anomalies.rs);
these tests verify the binding wiring, the lexicon contract, and the report shape.
"""

import re
from pathlib import Path

import disarm
from disarm import AnomalyReport, Finding, Lexicon, has_anomalies, inspect_anomalies

LEX = {"free", "viagra", "about", "paypal"}


def test_has_anomalies_fires_on_each_branch():
    assert has_anomalies("get fr33 now", LEX)  # leet
    assert has_anomalies("paypаl", LEX)  # mixed-script (Cyrillic а)
    assert has_anomalies("buy v.i.a.g.r.a now", LEX)  # segmentation
    assert has_anomalies("pay\u200bpal", LEX)  # invisible
    assert has_anomalies("user\u202etxt", LEX)  # bidi override


def test_false_positive_guards():
    assert not has_anomalies("a perfectly clean sentence", LEX)
    assert not has_anomalies("the win32 api and mp3 file", LEX)  # literal numbers


def test_lexicon_gates_the_leet_branch():
    assert not has_anomalies("get fr33", set())  # no lexicon -> can't confirm a word
    assert has_anomalies("get fr33", {"free"})


def test_lexicon_accepts_any_iterable():
    assert has_anomalies("get fr33", ["free"])  # list
    assert has_anomalies("get fr33", (w for w in ["free"]))  # generator


def test_inspect_report_shape_and_span():
    text = "log in to paypаl today"
    r = inspect_anomalies(text, {"paypal"})
    assert isinstance(r, AnomalyReport)
    assert r.anomalous is True
    assert r.kinds == ["mixed_script"]

    f = r.findings[0]
    assert isinstance(f, Finding)
    assert f.kind == "mixed_script"
    assert f.token == "paypаl"
    # start/end are byte offsets into the input
    assert text.encode()[f.start : f.end].decode() == f.token
    assert "Latin" in f.detail
    assert "Latin" in f.reason


def test_clean_report_is_empty():
    r = inspect_anomalies("nothing to see here", set())
    assert r.anomalous is False
    assert r.kinds == []
    assert r.findings == []
    assert r.reason is None


def test_has_anomalies_matches_inspect():
    for s in ["get fr33", "paypаl", "perfectly clean text", "user\u202etxt"]:
        assert has_anomalies(s, LEX) == inspect_anomalies(s, LEX).anomalous


def test_repr_is_pythonic():
    r = inspect_anomalies("paypаl", set())
    assert repr(r) == "AnomalyReport(anomalous=True, kinds=['mixed_script'])"


def test_exports():
    for name in ("has_anomalies", "inspect_anomalies", "AnomalyReport", "Finding"):
        assert name in disarm.__all__
        assert hasattr(disarm, name)


# --- Lexicon-optional tests (Finding 2.1) ---


def test_has_anomalies_no_lexicon_mixed_script():
    # "paypаl" contains Cyrillic а (U+0430) — the mixed-script branch needs no lexicon.
    assert has_anomalies("paypаl")  # no lexicon argument


def test_has_anomalies_no_lexicon_clean_text():
    # Clean ASCII text must not fire when called with no lexicon argument.
    assert not has_anomalies("clean text")


def test_inspect_anomalies_no_lexicon_returns_report():
    # inspect_anomalies must accept zero positional arguments beyond text.
    r = inspect_anomalies("clean text")
    assert isinstance(r, AnomalyReport)
    assert r.anomalous is False
    assert r.kinds == []
    assert r.findings == []
    assert r.reason is None


def test_inspect_anomalies_no_lexicon_catches_mixed_script():
    # The mixed-script branch fires without a lexicon.
    r = inspect_anomalies("paypаl")
    assert r.anomalous is True
    assert "mixed_script" in r.kinds


def test_has_anomalies_lexicon_none_explicit():
    # lexicon=None is identical to omitting it.
    assert has_anomalies("paypаl", lexicon=None)
    assert not has_anomalies("clean text", lexicon=None)


def test_inspect_anomalies_lexicon_none_explicit():
    r = inspect_anomalies("clean text", lexicon=None)
    assert r.anomalous is False


# --- Reusable Lexicon handle (HAI-SDLC 6.1) ---


def test_lexicon_is_exported():
    assert "Lexicon" in disarm.__all__
    assert hasattr(disarm, "Lexicon")
    assert disarm.Lexicon is Lexicon


def test_lexicon_len_reports_distinct_words():
    lex = Lexicon(["paypal", "free", "viagra"])
    assert len(lex) == 3
    # Duplicates collapse into the internal set.
    assert len(Lexicon(["free", "free", "free"])) == 1
    assert len(Lexicon([])) == 0


def test_has_anomalies_lexicon_matches_raw_set():
    words = ["free", "viagra", "about", "paypal"]
    lex = Lexicon(words)
    for s in ["get fr33 now", "buy v.i.a.g.r.a now", "paypаl", "a clean sentence"]:
        assert has_anomalies(s, lex) == has_anomalies(s, set(words))


def test_inspect_anomalies_lexicon_matches_raw_set():
    words = ["free", "paypal"]
    lex = Lexicon(words)
    for s in ["get fr33", "log in to paypаl today", "nothing odd here"]:
        from_lex = inspect_anomalies(s, lex)
        from_set = inspect_anomalies(s, set(words))
        assert from_lex.anomalous == from_set.anomalous
        assert from_lex.kinds == from_set.kinds
        assert [f.token for f in from_lex.findings] == [f.token for f in from_set.findings]


def test_lexicon_is_reusable_across_calls():
    # The same handle drives many calls and gives stable results each time.
    lex = Lexicon(["free", "paypal"])
    for _ in range(5):
        assert has_anomalies("get fr33", lex) is True
        assert has_anomalies("perfectly clean text", lex) is False
        assert inspect_anomalies("get fr33", lex).kinds == ["leet"]


def test_lexicon_leet_gating_matches_set_semantics():
    # An empty Lexicon disables the leet branch, exactly like an empty set.
    assert has_anomalies("get fr33", Lexicon([])) == has_anomalies("get fr33", set())
    assert has_anomalies("get fr33", Lexicon(["free"])) is True


def test_lexicon_is_case_insensitive_on_ingest():
    # The lexicon is lowercased on ingest, so a title-cased/upper wordlist still
    # matches the detector's lowercased decoded words (regression: "Free" missed fr33).
    assert has_anomalies("get fr33 now", {"Free"}) is True  # leet, raw set
    assert has_anomalies("v.i.a.g.r.a", {"VIAGRA"}) is True  # segmentation, raw set
    assert has_anomalies("get fr33 now", Lexicon(["Free"])) is True  # handle path
    assert inspect_anomalies("get fr33", {"Free"}).anomalous is True


# --- bidi_mixed direction-conflict kind (#412) ---


def test_bidi_mixed_fires_on_ltr_plus_rtl_token():
    # Latin + Hebrew in one token can visually reorder; reported as bidi_mixed,
    # the precise kind (not the generic mixed_script).
    r = inspect_anomalies("varonisו", set())
    assert r.anomalous
    assert r.kinds == ["bidi_mixed"]


def test_bidi_mixed_catches_non_latin_rtl_mix():
    # Cyrillic + Hebrew: the Latin-anchored mixed_script rule misses this, but
    # the direction conflict is still caught.
    assert has_anomalies("аום", set())
    assert inspect_anomalies("аום", set()).kinds == ["bidi_mixed"]


def test_bidi_mixed_quiet_on_same_direction():
    # Latin + Cyrillic are both LTR — still mixed_script, not bidi_mixed.
    assert inspect_anomalies("paypаl", set()).kinds == ["mixed_script"]


class TestControlCharacters:
    """#612: a non-whitespace control is never legitimate in text, and nothing saw it.

    ``strip_control_chars`` has removed these since #433, but no detector reported
    them, so ``docs/security/cve-validation.md`` listed a leading NUL and a terminal
    escape sequence among the vectors nothing flags.

    The whitespace-class controls (TAB, LF, VT, FF, CR, the information separators,
    NEL) are excluded: they are real separators, ``collapse_whitespace`` folds them
    to a space, and flagging them would fire on ordinary multi-line text.
    """

    def test_leading_nul_is_flagged(self):
        # CVE-2023-24329 — urllib.parse blocklist bypass via a leading blank.
        assert "control" in inspect_anomalies("\x00https://evil.example.net").kinds
        assert has_anomalies("\x00https://evil.example.net")

    def test_terminal_escape_is_flagged(self):
        # CVE-2008-2383 (xterm DECRQSS) and CVE-2019-9535 (iTerm2 tmux mode).
        assert "control" in inspect_anomalies("\x1bP$q\nrm -rf ~\n\x1b\\").kinds
        assert "control" in inspect_anomalies("\x1bP1000p%output %1 malicious\x1b\\").kinds

    def test_control_is_flagged_away_from_the_edges(self):
        # The reason this is presence rather than position: the last character here
        # is a backslash, so an edge-only rule would report this token clean.
        assert "control" in inspect_anomalies("malicious\x1b\\").kinds

    def test_whitespace_controls_are_not_flagged(self):
        # These are separators. collapse_whitespace folds them; flagging them would
        # fire on every multi-line string.
        for ch in ("\t", "\n", "\r", "\x0b", "\x0c", "\x1c", "\x1f", "\x85"):
            assert not has_anomalies(f"hello{ch}world"), repr(ch)

    def test_ordinary_text_is_not_flagged(self):
        for s in ("hello world", "  padded  ", "Café déjà vu", "line one\nline two"):
            assert "control" not in inspect_anomalies(s).kinds, s

    def test_del_and_c1_are_flagged(self):
        assert "control" in inspect_anomalies("hello\x7fworld").kinds
        assert "control" in inspect_anomalies("hello\x9fworld").kinds

    def test_finding_records_the_codepoint(self):
        findings = inspect_anomalies("\x00https://evil.example.net").findings
        control = [f for f in findings if f.kind == "control"]
        assert control, findings
        assert "U+0000" in control[0].detail


class TestAnomalyKindDoesNotDriftFromTheBindings:
    """Drift gate: the kind set is declared twice and nothing compared them.

    ``AnomalyKind`` is a Rust enum whose ``as_str`` arms are the wire format. It
    crosses every FFI boundary as a bare ``String``, so PyO3, Ruby, Java and the C
    ABI need no per-kind code and cannot drift. Node is the exception: it
    hand-mirrors the set as a TypeScript string union so ``Finding.kind`` is typed
    rather than ``string``.

    That union shipped without ``bidi_mixed`` from #412 until #612 — a Node caller
    matching on it got a type error for a kind the library really returns, and
    nothing caught it, because the value crosses napi as a ``String`` and
    ``index.ts`` casts.
    """

    ROOT = Path(__file__).resolve().parent.parent
    RUST = ROOT / "src" / "anomalies.rs"
    NODE = ROOT / "bindings" / "node" / "index.ts"

    def _rust_kinds(self) -> set[str]:
        """The ``as_str`` arms — the wire format, read from its definition."""
        body = self.RUST.read_text(encoding="utf-8")
        block = re.search(r"pub fn as_str\(self\) -> &'static str \{.*?\n    \}", body, re.S)
        assert block, "as_str() not found — update this gate"
        return set(re.findall(r'=> "([a-z_]+)"', block.group(0)))

    def _node_kinds(self) -> set[str]:
        text = self.NODE.read_text(encoding="utf-8")
        union = re.search(r"export type AnomalyKind = ([^\n]+)", text)
        assert union, "AnomalyKind union not found — update this gate"
        return set(re.findall(r"'([a-z_]+)'", union.group(1)))

    def test_node_union_matches_the_rust_wire_format(self):
        rust, node = self._rust_kinds(), self._node_kinds()
        assert rust == node, {
            "in Rust, missing from the TS union": sorted(rust - node),
            "in the TS union, not a real kind": sorted(node - rust),
        }

    def test_every_kind_is_reachable(self):
        """A kind nothing can produce is worse than a missing one — it is a lie."""
        samples = {
            "invisible": "pay\u200bpal",
            "bidi": "user\u202etxt.exe",
            "bidi_mixed": "varonis\u05d5",
            "zalgo": "a\u0301\u0301\u0301\u0301",
            "mixed_script": "p\u0430ypal",
            "leet": "fr33",
            "segmentation": "v.i.a.g.r.a",
            "control": "\x00evil",
            # #777, UTS #39 §5.3: ASCII `1` with an Arabic-Indic `٣`. Two systems, and
            # the shape that was clean everywhere — digits carry the script of nothing,
            # so `mixed_script` never saw it.
            "mixed_numbers": "12\u0663",
            "compat_fold": "\uff45xample.com",
            # #737: the confusable fold is `canonicalize`'s SECOND ASCII-producing step,
            # and the detector never consulted it. `p\u0251ypal` is single-script Latin,
            # so `mixed_script` cannot see it either.
            "confusable": "p\u0251ypal",
            # #724: the category is the signal, not the count. One enclosing mark per
            # base is below every threshold disarm has.
            "enclosing_mark": "I\u20ddg\u20ddn\u20dd",
        }
        assert set(samples) == self._rust_kinds(), "sample set is stale"
        # `leet` and `segmentation` are lexicon-gated by design, so they need one.
        lex = {"free", "viagra"}
        for kind, text in samples.items():
            kinds = inspect_anomalies(text, lex).kinds
            assert kind in kinds, f"{kind} unreachable via {text!r} (got {kinds})"
