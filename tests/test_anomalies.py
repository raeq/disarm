"""Python binding for the out-of-place-character detector (#389).

The exhaustive per-branch coverage lives in the Rust core (src/anomalies.rs);
these tests verify the binding wiring, the lexicon contract, and the report shape.
"""

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
