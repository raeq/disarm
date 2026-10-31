"""A level for each anomaly kind, in the library and not in one of its consumers (#946).

`scan.py` carried the map, and a test read `AnomalyKind` out of the Rust source to keep it covering
every variant. Anyone else building a report on `inspect_anomalies` made the same judgement again.

`smuggled` is `error`, because it fires only on a run that decodes. Every other kind is `warning`.
`deletion` stays there: `src/anomalies.rs` records a false positive on it, a classic Mac OS file with
`CR` line endings, so its presence is not proof in the way a decode is.
"""

from __future__ import annotations

import inspect
import io
import json
import re
from pathlib import Path

import pytest

import disarm
from disarm import anomaly_severity
from disarm.scan import run

ROOT = Path(__file__).resolve().parents[1]
RUST = (ROOT / "src/anomalies.rs").read_text(encoding="utf-8")
block = re.search(
    r"pub fn as_str\(self\) -> &'static str \{.*?\n    \}",
    RUST[RUST.index("impl AnomalyKind {") :],
    re.DOTALL,
)
assert block, "AnomalyKind::as_str not found"
KINDS = sorted(set(re.findall(r'=> "([a-z_]+)"', block.group(0))))
assert len(KINDS) >= 15, KINDS

TAGS = "".join(chr(0xE0000 + ord(c)) for c in "hidden")


def test_a_decoded_payload_is_the_one_error() -> None:
    assert anomaly_severity("smuggled") == "error"


@pytest.mark.parametrize("kind", [k for k in KINDS if k != "smuggled"])
def test_every_other_kind_is_a_warning(kind: str) -> None:
    assert anomaly_severity(kind) == "warning"


def test_deletion_stays_a_warning_because_a_mac_file_is_a_known_false_positive() -> None:
    assert anomaly_severity("deletion") == "warning"
    assert "classic Mac OS" in RUST


def test_every_kind_a_report_can_hold_has_a_level() -> None:
    report = disarm.inspect_anomalies("cover" + TAGS)
    assert report.kinds
    for kind in report.kinds:
        assert anomaly_severity(kind) in {"error", "warning"}
    for finding in report.findings:
        assert anomaly_severity(finding.kind) in {"error", "warning"}


@pytest.mark.parametrize("name", ["nope", "", "Smuggled", "smuggled "])
def test_a_name_that_is_no_kind_raises(name: str) -> None:
    with pytest.raises(disarm.DisarmError, match="anomaly kind"):
        anomaly_severity(name)


def test_the_error_names_what_is_accepted() -> None:
    with pytest.raises(disarm.DisarmError) as raised:
        anomaly_severity("nope")
    assert "smuggled" in str(raised.value)
    assert "nope" in str(raised.value)


def test_it_is_public_and_in_the_stub() -> None:
    assert "anomaly_severity" in disarm.__all__
    assert list(inspect.signature(anomaly_severity).parameters) == ["kind"]
    stub = (ROOT / "python/disarm/_core.pyi").read_text(encoding="utf-8")
    assert "def _anomaly_severity(kind: str) -> str: ..." in stub


def test_the_scanner_keeps_no_map_of_its_own() -> None:
    scan = (ROOT / "python/disarm/scan.py").read_text(encoding="utf-8")
    assert "SARIF_LEVELS" not in scan
    assert "anomaly_severity" in scan


def _sarif(tmp_path: Path, text: str) -> dict:
    (tmp_path / "a.txt").write_text(text, encoding="utf-8")
    out = io.StringIO()
    run([tmp_path], as_sarif=True, out=out)
    return json.loads(out.getvalue())["runs"][0]


def test_the_sarif_writer_emits_the_core_level_for_a_payload(tmp_path: Path) -> None:
    sarif = _sarif(tmp_path, "cover" + TAGS + "\n")
    levels = {r["ruleId"]: r["level"] for r in sarif["results"]}
    assert levels["smuggled"] == "error"
    for kind, level in levels.items():
        assert level == anomaly_severity(kind), kind
    for rule in sarif["tool"]["driver"]["rules"]:
        assert rule["defaultConfiguration"]["level"] == anomaly_severity(rule["id"])


def test_the_sarif_writer_emits_a_warning_for_the_rest(tmp_path: Path) -> None:
    sarif = _sarif(tmp_path, "pay" + chr(0x200B) + "pal\n")
    assert {r["level"] for r in sarif["results"]} == {"warning"}


def test_the_guide_says_what_the_levels_mean() -> None:
    guide = (ROOT / "docs/user-guide/anomaly-detection.md").read_text(encoding="utf-8")
    assert "anomaly_severity" in guide
    assert "`deletion`" in guide


def test_the_rust_api_page_names_the_type() -> None:
    assert "AnomalySeverity" in (ROOT / "docs/RUST_API.md").read_text(encoding="utf-8")
