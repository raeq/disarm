"""Python binding for the out-of-place-character detector (#389).

The exhaustive per-branch coverage lives in the Rust core (src/anomalies.rs);
these tests verify the binding wiring, the lexicon contract, and the report shape.
"""

import disarm
from disarm import AnomalyReport, Finding, has_anomalies, inspect_anomalies

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
