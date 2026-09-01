"""Suites anchored to a published vulnerability.

The external artifact is the vector as the CVE (or the fixing commit) published
it — not a reconstruction. Where the upstream vector is a *table delta* it is
vendored and frozen; where it is a set of source files it must be downloaded,
and the suite reports SKIPPED without them.
"""

from __future__ import annotations

from pathlib import Path

from ..base import CACHE, FIXTURES, SuiteBase, add, artifact, surfaces
from ..protocol import Availability, Family, Outcome, Provenance


class CVE202617084Stringprep(SuiteBase):
    name = "cve-2026-17084-stringprep"
    family = Family.CVE
    availability = Availability.VENDORED
    summary = "CPython stringprep B.3 pre/post-fix delta: does any key builder collide the pair?"
    provenance = Provenance(
        origin="CPython / NVD",
        citation="CVE-2026-17084",
        url="https://nvd.nist.gov/vuln/detail/CVE-2026-17084",
        version="Lib/stringprep.py at 7e109d0 and its parent, frozen",
        licence="PSF-2.0 (derived table)",
        issues=(713, 715),
        reproduces=(
            "cve-2026-17084-repro.py — the count of B.3 rows whose pre-fix and "
            "post-fix outputs differ, which is the row set the CVE creates."
        ),
        finding=(
            "#713: a key-builder-only row — the two IDNA-2003 spellings collide in "
            "the key builders and no detector reports either of them."
        ),
        notes=(
            "stringprep/IDNA 2003 drifting off Unicode 3.2.0. The fixture is a "
            "code-point-keyed delta; the interpreter that generated it is named in "
            "the file header, because pre-fix B.3 falls through to str.lower(), so "
            "the row count moves with the interpreter's UCD."
        ),
    )

    REPRO_EXPECTED = {"divergent_rows": 684}

    def locate(self) -> Path | None:
        return artifact(FIXTURES / "cve_2026_17084_b3.tsv", env="DISARM_META_CVE_B3")

    def reproduce(self) -> dict[str, float]:
        path = self.locate()
        assert path is not None
        divergent = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) != 3:
                continue
            pre = cols[1].encode().decode("unicode_escape")
            post = cols[2].encode().decode("unicode_escape")
            if pre != post:
                divergent += 1
        return {"divergent_rows": divergent}

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        import disarm

        path = self.locate()
        assert path is not None
        rows: list[tuple[str, str, str]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.rstrip()
            if not line or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) != 3:
                continue
            source = chr(int(cols[0], 16))
            pre = cols[1].encode().decode("unicode_escape")
            post = cols[2].encode().decode("unicode_escape")
            rows.append((source, pre, post))
        if limit is not None and limit < len(rows):
            step = max(1, len(rows) // limit)
            rows = rows[::step][:limit]
        outcome.population = len(rows)

        builders = {
            "search_key": disarm.search_key,
            "catalog_key": disarm.catalog_key,
            "sort_key": disarm.sort_key,
        }
        # Rows where the two outputs are already equal collide for free and would
        # inflate every builder to 100%. They are counted and then excluded, so
        # the reported rate is over the rows the CVE actually splits.
        divergent = [(s_, pre, post) for s_, pre, post in rows if pre != post]
        collides = {name: 0 for name in builders}
        detected = 0
        for _source, pre, post in divergent:
            if disarm.has_anomalies(pre) or disarm.has_anomalies(post):
                detected += 1
            for name, fn in builders.items():
                if fn(pre) == fn(post):
                    collides[name] += 1
        n = len(divergent)
        add(outcome, "delta_rows", len(rows), unit="codepoints")
        add(
            outcome,
            "divergent_rows",
            n,
            of=len(rows),
            detail="pre-fix and post-fix B.3 outputs actually differ",
        )
        add(
            outcome,
            "detected",
            detected,
            of=n,
            higher_is_better=True,
            detail="has_anomalies flags either spelling",
        )
        for name, hits in collides.items():
            add(
                outcome,
                f"collides_{name}",
                hits,
                of=n,
                higher_is_better=True,
                detail="the two IDNA-2003 outputs land on one key",
            )


class TrojanSourcePoC(SuiteBase):
    name = "cve-2021-42574-trojan-source"
    family = Family.CVE
    availability = Availability.MANUAL
    env_var = "DISARM_META_TROJAN_SOURCE"
    summary = "The published multi-line Trojan Source PoC files, not a one-line fragment."
    provenance = Provenance(
        origin="Boucher & Anderson",
        citation="CVE-2021-42574 / CVE-2021-42694",
        url="https://trojansource.codes/",
        version="published PoC set",
        licence="MIT (upstream repository)",
        issues=(744, 745, 746),
        finding=(
            "#744: on the published multi-line PoC, four of the five listed "
            "neutralizers returned output that was no longer source code. Both gate "
            "vectors are single-line fragments, and a one-line vector has no "
            "newlines to lose."
        ),
        notes=(
            "The real PoC is a source file, so line structure is scored alongside "
            "bidi removal. Point the env var at a directory of them."
        ),
    )

    def locate(self) -> Path | None:
        return artifact(CACHE / "trojan-source", env=self.env_var)

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        root = self.locate()
        assert root is not None
        files = sorted(p for p in Path(root).rglob("*") if p.is_file())
        if limit is not None:
            files = files[:limit]
        outcome.population = len(files)
        if not files:
            add(outcome, "poc_files", 0)
            return

        import disarm

        surface_map = surfaces()
        still_source = {name: 0 for name in surface_map}
        bidi_removed = {name: 0 for name in surface_map}
        for path in files:
            text = path.read_text(encoding="utf-8", errors="replace")
            lines_before = text.count("\n")
            for name, fn in surface_map.items():
                try:
                    out = fn(text)
                except Exception:  # noqa: BLE001 - a surface may reject the input
                    continue
                if lines_before and out.count("\n") == lines_before:
                    still_source[name] += 1
                if not disarm.has_bidi_control(out):
                    bidi_removed[name] += 1
        add(outcome, "poc_files", len(files), unit="files")
        add(
            outcome,
            "surfaces_preserving_line_structure",
            sum(1 for v in still_source.values() if v == len(files)),
            of=len(surface_map),
            higher_is_better=True,
            detail="output is still a source file on every PoC",
        )
        add(
            outcome,
            "surfaces_removing_bidi",
            sum(1 for v in bidi_removed.values() if v == len(files)),
            of=len(surface_map),
            higher_is_better=True,
        )
        outcome.extra = {
            "line_structure_preserved": still_source,
            "bidi_removed": bidi_removed,
        }


SUITES = [CVE202617084Stringprep(), TrojanSourcePoC()]
