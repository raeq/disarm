"""Suites anchored to a practitioner's tool or repository.

The rest of the registry came from reading the literature, and that left a blind
spot: the people publishing attack tooling on GitHub are not writing papers, so a
search of arXiv never reaches them. They are worth reading and they are not all
worth scoring, because a popular repository is rarely a labelled one.

Three rules hold the family to that, and the base classes enforce the first two:

1. A suite scores only where each case has a known answer. Applying a published
   transform to text we chose fixes the answer before the subject runs.
2. An unlabelled corpus stays a fixture. Every number is a census, so it can catch
   a regression and it can never reach a ranking.
3. Every suite runs the delete-everything control on every run, including a run
   that scores only disarm. A known-answer suite refuses to report if the control
   scores anything, since a metric that control can pass measures nothing.

A copyleft source is cached from a pinned commit and never vendored, so nothing
here can quietly edit it and nothing of it enters this repository. Corpus text
never reaches a report: these suites print counts, and the names of transforms.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import re
import shutil
import statistics
import subprocess
import unicodedata
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, replace
from itertools import combinations
from pathlib import Path
from typing import ClassVar

from .. import damage
from ..base import FETCH_CACHE, SuiteBase, add, record, thin
from ..fetch import Source
from ..protocol import Availability, Evidence, Family, Outcome, Provenance
from ..subjects import Capability, Job, Role

#: Filed as this pull request, because no separate issue exists for the tier.
TIER_ISSUE = 1131


def _delete_everything(_text: str) -> str:
    """The degenerate answer. A control that is meant to fail proves a metric can."""
    return ""


def _identity(text: str) -> str:
    """The do-nothing floor."""
    return text


class _PractitionerSuite(SuiteBase):
    family = Family.PRACTITIONER
    availability = Availability.NETWORK
    MULTI_SUBJECT = True
    JOB = Job.PROMPT_HYGIENE

    def _sanitizer(self) -> Callable[[str], str] | None:
        surfaces = (
            self.subject.role(Role.SANITIZER, job=self.JOB) if self.subject is not None else {}
        )
        return next(iter(surfaces.values()), None)


class _KnownAnswerSuite(_PractitionerSuite):
    """A suite whose cases have an answer fixed before the subject runs."""

    def scored(self, outcome: Outcome, limit: int | None) -> None:  # pragma: no cover
        raise NotImplementedError

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        self.scored(outcome, limit)
        control = outcome.measurement("control_delete_everything")
        if control is None:
            raise ValueError(f"{self.name} did not run the delete-everything control")
        if control.value:
            raise ValueError(
                f"{self.name}: deleting everything scored {control.value:g}, so this "
                "metric cannot fail and no number from it is reported"
            )


class _FixtureSuite(_PractitionerSuite):
    """An unlabelled corpus: regression and stress input, never a score."""

    def census(self, outcome: Outcome, limit: int | None) -> None:  # pragma: no cover
        raise NotImplementedError

    def measure(self, outcome: Outcome, limit: int | None) -> None:
        self.census(outcome, limit)
        directed = [m.key for m in outcome.measurements if m.higher_is_better is not None]
        if directed:
            raise ValueError(f"{self.name} is a fixture and cannot score: {directed}")
        if not any(m.key.startswith("control_delete_everything") for m in outcome.measurements):
            raise ValueError(f"{self.name} did not run the delete-everything control")


def tree_digest(root: Path) -> str:
    """sha256 over the path and bytes of every file under ``root``.

    Held against the extracted tree and not the archive. GitHub does not promise
    that a generated tarball stays byte-identical, and the tree is what runs.
    """
    h = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix().encode()
        if path.is_symlink():
            h.update(b"symlink\0" + relative + b"\0")
        elif path.is_file():
            h.update(relative + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


_P4RS3LT0NGV3_COMMIT = "a6cb7c9054800e106b63888d362601922477a614"

#: Fixed from upstream's own directory names before any score was read, and not to
#: be moved to improve one. `unicode` is upstream's "presentation styles".
_STYLE_FOLDERS = frozenset({"unicode"})
_STYLE_NAMES = frozenset({"concealment/homoglyph"})
#: Hide a payload in code points a reader cannot see. The answer is the cover.
_CARRIER_NAMES = frozenset(
    {
        "concealment/invisible-text",
        "concealment/whitespace-steganography",
        "concealment/zerowidth-steganography",
    }
)
#: Ciphers, encodings and invented alphabets, and classical stego in plain letters.
#: Mostly not a Unicode sanitizer's job, so they are counted and never scored.
_BOUNDARY_FOLDERS = frozenset(
    {"cipher", "encoding", "signwriting", "symbol", "technical", "visual"}
)
_BOUNDARY_NAMES = frozenset(
    {
        "concealment/acrostic",
        "concealment/cardan-grille",
        "concealment/null-cipher",
        "concealment/trevanion",
    }
)
#: Text utilities and a randomizer. Reversing or de-duplicating text is not an attack
#: with a recoverable answer, and case is a property of the subject.
_EXCLUDED_FOLDERS = frozenset({"case", "format", "special"})


def classify_transform(relative: str) -> str:
    """``style``, ``carrier``, ``boundary`` or ``excluded``, for a path under the root."""
    stem = relative.removesuffix(".js")
    folder = stem.partition("/")[0]
    if stem in _CARRIER_NAMES:
        return "carrier"
    if folder in _STYLE_FOLDERS or stem in _STYLE_NAMES:
        return "style"
    if folder in _BOUNDARY_FOLDERS or stem in _BOUNDARY_NAMES:
        return "boundary"
    if folder in _EXCLUDED_FOLDERS:
        return "excluded"
    raise ValueError(f"unclassified transform {relative}: a pinned tree has none")


class P4rs3lt0ngv3Transforms(_KnownAnswerSuite):
    name = "p4rs3lt0ngv3-transforms"
    env_var = "DISARM_META_P4RS3LT0NGV3"
    summary = "Does a sanitizer undo a practitioner's published text transforms?"
    provenance = Provenance(
        origin="elder-plinius",
        citation="P4RS3LT0NGV3, src/transformers",
        url="https://github.com/elder-plinius/P4RS3LT0NGV3",
        version=f"commit {_P4RS3LT0NGV3_COMMIT[:12]}, 222 transforms",
        licence="AGPL-3.0 per LICENSE (package.json says MIT; the stricter one is followed)",
        issues=(TIER_ISSUE,),
        evidence=Evidence.KNOWN_ANSWER,
        finding=(
            "On 0.18.0, through the prompt-hygiene surface: 48 of 64 restyled pairs and 12 of "
            "12 carrier pairs. Eight styles stay unrecovered: mirror, parenthesized, "
            "regional-indicator, small-caps, superscript, upside-down, vaporwave and "
            "wide-spacing. decancer recovers 53 of 64 and no carrier pair. No subject recovers "
            "mirror, upside-down, vaporwave or wide-spacing. These are measurements and not "
            "requests for a mapping: the guardrail from #39 and #40 applies."
        ),
        notes=(
            "A generator gives what an unlabelled corpus cannot: the transform runs on "
            "text we chose, so the answer is known before the subject runs. Upstream's "
            "code is cached, never vendored, and runs only under Node's permission model "
            "after a digest check of the tree.\n\n"
            "**Restyling** is recovered when the transformed text and the clean text land "
            "on one non-empty form. **Carriers** hide a fixed benign word, appended to a "
            "known cover and inserted after its first space, and count as removed when "
            "the result lands on the same form as the cover. A transform that leaves a "
            "text unchanged is held out of the denominator. Ciphers, encodings and "
            "invented alphabets are reported as a census with no direction: a low count "
            "there is the expected answer. Classes come from upstream's directories and "
            "were fixed before any score was read."
        ),
    )
    SOURCES = (
        Source(
            url=f"https://codeload.github.com/elder-plinius/P4RS3LT0NGV3/tar.gz/{_P4RS3LT0NGV3_COMMIT}",
            filename="p4rs3lt0ngv3",
            licence="AGPL-3.0",
            kind="tar.gz",
            member=f"P4RS3LT0NGV3-{_P4RS3LT0NGV3_COMMIT}/src/transformers",
            note="Cached, never vendored. Pinned to a commit; the tree is digest-checked.",
        ),
    )

    #: Digest of `src/transformers` at the pinned commit. A mismatch refuses to run.
    TREE_SHA256 = "d6c81d3f8b0781834d34b8b960d5752aac172714bc53b781758e84b2acf18835"
    #: The first Node whose permission model also denies the network.
    MIN_NODE_MAJOR = 25
    DRIVER = Path(__file__).with_name("practitioner_driver.js")
    GENERATE_TIMEOUT_S = 120
    SEED = 20261031

    #: Pangrams, so a gap in a transform's map shows up whatever the letter frequency.
    CLEAN_TEXTS = (
        "the quick brown fox jumps over the lazy dog",
        "Pack my box with five dozen liquor jugs 0123456789",
    )
    HIDDEN_WORD = "hidden"

    @staticmethod
    def _node_major(node: str) -> int | None:
        try:
            done = subprocess.run(
                [node, "--version"], capture_output=True, text=True, timeout=10, check=True
            )
        except (OSError, subprocess.SubprocessError):
            return None
        found = re.match(r"v(\d+)\.", done.stdout.strip())
        return int(found.group(1)) if found else None

    def available(self) -> tuple[bool, str]:
        ready, reason = super().available()
        if not ready:
            return ready, reason
        node = shutil.which("node")
        major = self._node_major(node) if node else None
        if major is None or major < self.MIN_NODE_MAJOR:
            return False, (
                f"needs Node >= {self.MIN_NODE_MAJOR} for its permission model; "
                f"found {'none' if major is None else major}"
            )
        root = self.locate()
        assert root is not None
        digest = tree_digest(root)
        if digest != self.TREE_SHA256:
            return False, (
                f"refusing to execute: tree digest {digest[:16]} is not the pinned "
                f"{self.TREE_SHA256[:16]}"
            )
        return True, ""

    def discover(self, root: Path) -> list[str]:
        return sorted(p.relative_to(root).as_posix() for p in root.glob("*/*.js"))

    def generate(
        self, root: Path, transforms: list[str], texts: list[str]
    ) -> dict[str, dict[str, object]]:
        """Run upstream's code, in the sandbox, on our text. See the driver's header."""
        node = shutil.which("node")
        assert node is not None
        resolved = root.resolve()
        done = subprocess.run(
            [
                node,
                "--permission",
                f"--allow-fs-read={resolved}",
                "-e",
                self.DRIVER.read_text(encoding="utf-8"),
                "--",
                str(resolved),
            ],
            input=json.dumps({"transforms": transforms, "texts": texts, "seed": self.SEED}),
            capture_output=True,
            encoding="utf-8",
            timeout=self.GENERATE_TIMEOUT_S,
            check=False,
        )
        if done.returncode != 0:
            raise RuntimeError(f"the transform driver failed: {done.stderr[-300:]}")
        return json.loads(done.stdout)

    def scored(self, outcome: Outcome, limit: int | None) -> None:
        root = self.locate()
        assert root is not None
        every = self.discover(root)
        chosen = [every[i] for i in thin(list(range(len(every))), limit)]
        texts = [*self.CLEAN_TEXTS, self.HIDDEN_WORD]
        generated = self.generate(root, chosen, texts)

        pairs: dict[str, list[tuple[str, str, str]]] = {"style": [], "carrier": [], "boundary": []}
        held_out = errors = excluded = 0
        for relative in chosen:
            kind = classify_transform(relative)
            if kind == "excluded":
                excluded += 1
                continue
            result = generated[relative]
            outputs = result["outputs"] if not result["error"] else []
            if not outputs:
                errors += 1
                continue
            label = relative.removesuffix(".js")
            if kind == "carrier":
                run = str(outputs[-1])
                for cover in self.CLEAN_TEXTS:
                    head, _, tail = cover.partition(" ")
                    pairs[kind].append((label, f"{cover}{run}", cover))
                    pairs[kind].append((label, f"{head} {run}{tail}", cover))
                continue
            for clean, output in zip(self.CLEAN_TEXTS, outputs, strict=False):
                if output == clean:
                    held_out += 1
                else:
                    pairs[kind].append((label, str(output), clean))

        directed = len(pairs["style"]) + len(pairs["carrier"])
        outcome.population = directed + len(pairs["boundary"])
        fn = self._sanitizer()
        record(
            outcome,
            domain=f"{len(chosen)} of {len(every)} transforms on {len(self.CLEAN_TEXTS)} texts",
            predicates=[self.JOB],
            commit=_P4RS3LT0NGV3_COMMIT,
            seed=self.SEED,
            clean_texts=list(self.CLEAN_TEXTS),
            hidden_word=self.HIDDEN_WORD,
        )
        add(outcome, "transforms", len(chosen), unit="transforms")
        add(outcome, "transforms_excluded", excluded, of=len(chosen), unit="transforms")
        add(outcome, "transforms_that_failed_to_run", errors, of=len(chosen), unit="transforms")
        add(outcome, "pairs_held_out_unchanged", held_out, unit="pairs")

        everything = pairs["style"] + pairs["carrier"]
        for key, control in (
            ("control_delete_everything", _delete_everything),
            ("control_identity", _identity),
        ):
            add(
                outcome,
                key,
                self._recovered(control, everything),
                of=directed,
                detail="must be zero, or the metric below has a degenerate solution",
            )
        if fn is None:
            return

        add(
            outcome,
            "styles_recovered",
            self._recovered(fn, pairs["style"]),
            of=len(pairs["style"]),
            higher_is_better=True,
            detail="transformed and clean text land on one non-empty form",
        )
        add(
            outcome,
            "carriers_removed",
            self._recovered(fn, pairs["carrier"]),
            of=len(pairs["carrier"]),
            higher_is_better=True,
            detail="cover plus hidden run lands on the same form as the cover",
        )
        add(
            outcome,
            "boundary_recovered",
            self._recovered(fn, pairs["boundary"]),
            of=len(pairs["boundary"]),
            detail="ciphers, encodings and invented alphabets: a census, and low is expected",
        )
        add(
            outcome,
            "clean_text_intact",
            sum(damage.apply(fn, t).casefold() == t.casefold() for t in self.CLEAN_TEXTS),
            of=len(self.CLEAN_TEXTS),
            detail="the cost beside the coverage: the clean text survives, up to case",
        )
        by_transform: dict[str, list[int]] = {}
        for label, left, right in everything + pairs["boundary"]:
            cell = by_transform.setdefault(label, [0, 0])
            cell[0] += damage.collides([fn], left, right)
            cell[1] += 1
        outcome.extra = {"recovered_of_pairs_by_transform": by_transform}

    @staticmethod
    def _recovered(fn: Callable[[str], str], pairs: list[tuple[str, str, str]]) -> int:
        return sum(damage.collides([fn], left, right) for _, left, right in pairs)


_GARAK_COMMIT = "4b7761c2108446043012549cbe8f7c942cabb26d"


def literal_constants(source: str) -> dict[str, list[str]]:
    """Read module-level string lists from Python source without running any of it.

    Handles a literal list and ``NAME + [...]``, which is what the garak file uses.
    Anything else is left out.
    """

    def value(node: ast.expr, known: dict[str, list[str]]) -> list[str] | None:
        if isinstance(node, ast.Name):
            return known.get(node.id)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = value(node.left, known), value(node.right, known)
            return None if left is None or right is None else left + right
        try:
            literal = ast.literal_eval(node)
        except ValueError:
            return None
        if isinstance(literal, list) and all(isinstance(item, str) for item in literal):
            return literal
        return None

    known: dict[str, list[str]] = {}
    for statement in ast.parse(source).body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            if isinstance(target, ast.Name):
                found = value(statement.value, known)
                if found is not None:
                    known[target.id] = found
    return known


class GarakAnsiEscapes(_KnownAnswerSuite):
    name = "garak-ansi-escapes"
    JOB = Job.REVIEW_DISPLAY
    summary = "Are garak's terminal escape payloads neutralized, with the text around them kept?"
    provenance = Provenance(
        origin="NVIDIA garak",
        citation="garak/resources/ansi.py, LIVE_PAYLOADS against RAW_SEQS and RAW_COMMANDS",
        url="https://github.com/NVIDIA/garak",
        version=f"commit {_GARAK_COMMIT[:12]}",
        licence="Apache-2.0",
        issues=(TIER_ISSUE,),
        evidence=Evidence.KNOWN_ANSWER,
        finding=(
            "On 0.18.0, through the review-display surface: disarm 7 of 7, decancer 7, ftfy 6, "
            "the three transliterators 2 each, and CPython normalization 0."
        ),
        notes=(
            "garak's `ansiescape` probe deploys into a terminal, so the job is text a "
            "person reads. The oracle is garak's own: a payload counts as neutralized "
            "when none of the file's escape tokens remain. The payload sits inside a known "
            "cover whose words must survive, because deleting everything also removes "
            "every escape. The file is parsed with `ast` and is never imported, because "
            "Python offers no sandbox like the one the Node generator runs in. That is also "
            "why garak's other Unicode probes are not suites yet: see the README."
        ),
    )
    SOURCES = (
        Source(
            url=f"https://raw.githubusercontent.com/NVIDIA/garak/{_GARAK_COMMIT}/garak/resources/ansi.py",
            filename="garak-ansi.py",
            licence="Apache-2.0",
            sha256="066fb898ff65ef306da71537bdd26156eed327c3bf8558f5da7df2f9ce4bcaaa",
        ),
    )
    COVER = ("before", "after")

    def _neutralized(self, fn: Callable[[str], str], payloads: list[str], tokens: list[str]) -> int:
        count = 0
        for payload in payloads:
            out = damage.apply(fn, f"{self.COVER[0]} {payload} {self.COVER[1]}")
            kept = all(word in out.casefold() for word in self.COVER)
            if kept and not any(token in out for token in tokens):
                count += 1
        return count

    def scored(self, outcome: Outcome, limit: int | None) -> None:
        path = self.locate()
        assert path is not None
        constants = literal_constants(path.read_text(encoding="utf-8"))
        payloads = constants["LIVE_PAYLOADS"][: limit or None]
        tokens = sorted({*constants["RAW_SEQS"], *constants["RAW_COMMANDS"]})
        outcome.population = len(payloads)
        fn = self._sanitizer()
        record(
            outcome,
            domain=f"{len(payloads)} escape payloads inside a known cover",
            predicates=[self.JOB],
            commit=_GARAK_COMMIT,
            cover=list(self.COVER),
        )
        add(outcome, "payloads", len(payloads), unit="payloads")
        for key, control in (
            ("control_delete_everything", _delete_everything),
            ("control_identity", _identity),
        ):
            add(
                outcome,
                key,
                self._neutralized(control, payloads, tokens),
                of=len(payloads),
                detail="must be zero, or the metric below has a degenerate solution",
            )
        if fn is not None:
            add(
                outcome,
                "escapes_neutralized",
                self._neutralized(fn, payloads, tokens),
                of=len(payloads),
                higher_is_better=True,
                detail="no escape token left, and the cover's words still present",
            )


_L1B3RT4S_COMMIT = "f441d65d901b29ca92ac20ee1afb5c9d0b6f8ef6"
_SELECTORS = f"{chr(0xFE00)}-{chr(0xFE0F)}{chr(0xE0100)}-{chr(0xE01EF)}"
_TAGS = f"{chr(0xE0000)}-{chr(0xE007F)}"
_CARRIER = re.compile(f"[{_SELECTORS}{_TAGS}]")
_RUN = re.compile(f"[{_SELECTORS}]{{8,}}|[{_TAGS}]{{8,}}")


def _payload_of(run: str) -> bytes:
    """Decode a carrier run with no help from the subject."""
    out = bytearray()
    for ch in run:
        cp = ord(ch)
        if cp <= 0xFE0F:
            out.append(cp - 0xFE00)
        elif cp <= 0xE007F:
            out.append(cp - 0xE0000)
        else:
            out.append(cp - 0xE0100 + 16)
    return bytes(out)


class L1b3rt4sFixtures(_FixtureSuite):
    name = "l1b3rt4s-fixtures"
    env_var = "DISARM_META_L1B3RT4S"
    summary = "Three pinned fixtures from an unlabelled jailbreak corpus: counts, never a score."
    provenance = Provenance(
        origin="elder-plinius",
        citation="L1B3RT4S repository",
        url="https://github.com/elder-plinius/L1B3RT4S",
        version=f"commit {_L1B3RT4S_COMMIT[:12]}",
        licence="AGPL-3.0",
        issues=(1122, 1123, 1124),
        evidence=Evidence.FIXTURE,
        finding=(
            "On 0.17.2: 169 of 182 heading-split sections carry no Unicode obfuscation and "
            "nothing records whether a prompt worked, so this is not a benchmark. It led to "
            "three documentation issues and no behaviour defect."
        ),
        notes=(
            "Three fixtures, none of them scored. **Smuggled runs**: carriers left by the "
            "surface, beside an independent decoder's agreement with `decode_smuggled`; "
            "deleting everything also leaves none, which is why this cannot rank. "
            "**Convergence**: `GROK-MEGA.mkd` styles one template differently per line, so "
            "the median 5-gram Jaccard rises as styling is undone. It has no ceiling and "
            "deleting everything scores 1.0, so it is relative and sits beside the "
            "characters kept. **Stress**: `TOKEN80M8.mkd` holds 5.86 million code points, "
            "and the suite records that the surface completes. Counts only: the corpus "
            "holds jailbreak prompts, its README hides a payload in variation selectors, "
            "and none of its text may reach a report, an issue or this record."
        ),
    )
    SOURCES = (
        Source(
            url=f"https://codeload.github.com/elder-plinius/L1B3RT4S/tar.gz/{_L1B3RT4S_COMMIT}",
            filename="l1b3rt4s",
            licence="AGPL-3.0",
            kind="tar.gz",
            member=f"L1B3RT4S-{_L1B3RT4S_COMMIT}",
            note="Cached, never vendored. Holds jailbreak prompts; count it, do not read it.",
        ),
    )
    CONVERGENCE_FILE = "GROK-MEGA.mkd"
    STRESS_FILE = "TOKEN80M8.mkd"
    #: A line this long is one of the styled templates, not prose around them.
    CONVERGENCE_MIN_LINE = 1000

    @staticmethod
    def _grams(text: str) -> set[str]:
        flat = re.sub(r"\s+", " ", text.lower())
        return {flat[i : i + 5] for i in range(max(len(flat) - 4, 1))}

    @classmethod
    def _convergence(cls, fn: Callable[[str], str], lines: list[str]) -> tuple[float, float]:
        """Median pairwise 5-gram Jaccard over the lines, and the characters kept."""
        outputs = [damage.apply(fn, line) for line in lines]
        grams = [cls._grams(out) for out in outputs]
        scores = [len(a & b) / max(len(a | b), 1) for a, b in combinations(grams, 2)]
        kept = sum(map(len, outputs)) / max(sum(map(len, lines)), 1)
        return (statistics.median(scores) if scores else 0.0), kept

    def census(self, outcome: Outcome, limit: int | None) -> None:
        root = self.locate()
        assert root is not None
        fn = self._sanitizer() or _identity
        texts: dict[str, str] = {}
        for path in sorted(root.rglob("*")):
            if path.is_file():
                try:
                    texts[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
        outcome.population = len(texts)
        record(
            outcome,
            domain=f"{len(texts)} text files at the pinned commit",
            predicates=[self.JOB],
            commit=_L1B3RT4S_COMMIT,
            evidence="fixture: every number here is a census",
        )
        add(outcome, "files", len(texts), unit="files")
        self._smuggled(outcome, fn, {k: v for k, v in texts.items() if k != self.STRESS_FILE})
        self._convergent(outcome, fn, texts.get(self.CONVERGENCE_FILE, ""))
        stress = texts.get(self.STRESS_FILE, "")
        self._stress(outcome, fn, stress[: limit or None])

    def _smuggled(self, outcome: Outcome, fn: Callable[[str], str], texts: dict[str, str]) -> None:
        runs = [m.group() for text in texts.values() for m in _RUN.finditer(text)]
        carriers = sum(len(_CARRIER.findall(text)) for text in texts.values())
        add(outcome, "smuggled_runs", len(runs), unit="runs")
        add(
            outcome,
            "carriers_left",
            sum(len(_CARRIER.findall(damage.apply(fn, text))) for text in texts.values()),
            of=carriers,
            detail="a census: the delete-everything control below also leaves none",
        )
        add(outcome, "control_delete_everything_carriers_left", 0, of=carriers)
        add(outcome, "control_identity_carriers_left", carriers, of=carriers)
        if outcome.method.subject == "disarm":
            agreed = self._decoder_agreement(texts, runs)
            if agreed is not None:
                add(
                    outcome,
                    "decoder_agrees_on_runs",
                    agreed,
                    of=len(runs),
                    detail="`decode_smuggled` against a decoder written apart from it",
                )

    @staticmethod
    def _decoder_agreement(texts: dict[str, str], runs: list[str]) -> int | None:
        import disarm

        decode = getattr(disarm, "decode_smuggled", None)
        if decode is None:
            return None
        found: set[bytes] = set()
        for text in texts.values():
            for item in decode(text):
                data = bytes(getattr(item, "data", b"") or b"")
                found.add(data or str(getattr(item, "text", "") or "").encode("utf-8"))
        return sum(_payload_of(run) in found for run in runs)

    def _convergent(self, outcome: Outcome, fn: Callable[[str], str], text: str) -> None:
        lines = [line for line in text.split("\n") if len(line) > self.CONVERGENCE_MIN_LINE]
        add(outcome, "convergence_lines", len(lines), unit="lines")
        if len(lines) < 2:
            return
        for key, surface in (
            ("convergence", fn),
            ("control_delete_everything_convergence", _delete_everything),
            ("control_identity_convergence", _identity),
        ):
            median, kept = self._convergence(surface, lines)
            add(outcome, f"{key}_median", median, of=1.0, unit="ratio")
            add(outcome, f"{key}_chars_kept", kept, of=1.0, unit="ratio")

    def _stress(self, outcome: Outcome, fn: Callable[[str], str], text: str) -> None:
        add(outcome, "stress_code_points", len(text), unit="code points")
        try:
            out = fn(text)
        except Exception:  # noqa: BLE001 - a surface may refuse; the census records that
            add(outcome, "stress_completed", 0, of=1)
            return
        add(outcome, "stress_completed", 1, of=1)
        add(outcome, "stress_carriers_left", len(_CARRIER.findall(out)), of=len(text))


def _csv_prompts(path: Path) -> list[str]:
    """Each non-empty `prompt` cell. A long prompt passes csv's default field limit."""
    csv.field_size_limit(10_000_000)
    with open(path, encoding="utf-8", newline="") as fh:
        return [row["prompt"] for row in csv.DictReader(fh) if row.get("prompt")]


def _nonblank_lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _jsonl_text(path: Path) -> list[str]:
    return [json.loads(line)["text"] for line in _nonblank_lines(path)]


def _taxonomy_examples(path: Path) -> list[str]:
    """Every example under every evasion, whichever container holds the list of them."""
    evasions = json.loads(path.read_text(encoding="utf-8"))["evasions"]
    items = (
        evasions
        if isinstance(evasions, list)
        else next(v for v in evasions.values() if isinstance(v, list))
    )
    return [
        example if isinstance(example, str) else json.dumps(example, ensure_ascii=False)
        for item in items
        for example in item.get("examples", [])
    ]


@dataclass(frozen=True)
class _Corpus:
    """One pinned practitioner file, and how to take its texts out of it."""

    name: str
    source: Source
    read: Callable[[Path], list[str]]


_JAILBREAK_LLMS_COMMIT = "4f4031bf8be187f4478c7f94f42b08714722c12e"
_FUZZYAI_COMMIT = "8184b9667a665aa27fb69ef81a7a30615d13faf5"
_PALISADE_COMMIT = "4d1728acdb916c74e44a8465672aa088ff298b08"
_ARCANUM_COMMIT = "e02cf5b6e202f195c6b6c01484e99519f797acc6"


def _jailbreak_llms(stem: str, sha256: str) -> _Corpus:
    return _Corpus(
        name=f"jailbreak_llms:{stem}",
        source=Source(
            url=(
                "https://raw.githubusercontent.com/verazuo/jailbreak_llms/"
                f"{_JAILBREAK_LLMS_COMMIT}/data/prompts/{stem}.csv"
            ),
            filename=f"practitioner-corpora/jailbreak_llms/{stem}.csv",
            licence="MIT",
            sha256=sha256,
            note="Its README says the data can hold personal information. Count, never print.",
        ),
        read=_csv_prompts,
    )


#: Files a number can come from without labelling anything. A corpus suite that also
#: reads one of these takes it from here, so each file has one pin.
PROMPT_CORPORA = (
    _jailbreak_llms(
        "regular_prompts_2023_12_25",
        "fb82e3f88fbd5d9c6edf8927b138510f339b85012cab24d41d13e1665a9c5819",
    ),
    _jailbreak_llms(
        "regular_prompts_2023_05_07",
        "2286158d3078ac9624bf5f10e679c8db9d7549c882608638e4923a62fd7b6031",
    ),
    _jailbreak_llms(
        "jailbreak_prompts_2023_12_25",
        "accf97463de96c33c48453dfee9600191ff6fd5a0c43f3f11d5ebf98d1a5de55",
    ),
    _jailbreak_llms(
        "jailbreak_prompts_2023_05_07",
        "6f0ccbea6c0118d4d563e885ae4c459980943c44b57fd66d6fbe7c869ab61e6b",
    ),
    _Corpus(
        name="fuzzyai:benign_prompts",
        source=Source(
            url=(
                f"https://raw.githubusercontent.com/cyberark/FuzzyAI/{_FUZZYAI_COMMIT}"
                "/src/fuzzyai/resources/benign_prompts.txt"
            ),
            filename="practitioner-corpora/fuzzyai/benign_prompts.txt",
            licence="Apache-2.0",
            sha256="95366fd7c23e37ff47054ba7407c231050e95da4eab8cd92ef4c91ac20da5eed",
        ),
        read=_nonblank_lines,
    ),
    _Corpus(
        name="palisade:benchmark",
        source=Source(
            url=(
                f"https://raw.githubusercontent.com/RootVandal/palisade/{_PALISADE_COMMIT}"
                "/palisade/data/benchmark.jsonl"
            ),
            filename="practitioner-corpora/palisade/benchmark.jsonl",
            licence="MIT",
            sha256="0ac34ef295d1c70ae8737816725a16ce988b0d249516c07542b13e6eb783d877",
        ),
        read=_jsonl_text,
    ),
    _Corpus(
        name="arcanum:taxonomy",
        source=Source(
            url=(
                f"https://raw.githubusercontent.com/Arcanum-Sec/arc_pi_taxonomy/{_ARCANUM_COMMIT}"
                "/docs/data/taxonomy.json"
            ),
            filename="practitioner-corpora/arcanum/taxonomy.json",
            licence="CC-BY-4.0",
            sha256="fc26b73a909faf73087dac4829cbd2118eb3f4505db6729dc048bc6fb3e1daa7",
            note="Attribution: Arcanum Information Security, Arc PI Taxonomy.",
        ),
        read=_taxonomy_examples,
    ),
)


class _CorporaSuite(_FixtureSuite):
    """A fixture over files declared as `_Corpus`, reading whichever of them are cached."""

    CORPORA: tuple[_Corpus, ...] = ()

    def read_corpora(self) -> dict[str, list[str]]:
        """Each corpus that is in the cache. An absent one is left out, and counted."""
        return {
            corpus.name: corpus.read(FETCH_CACHE / corpus.source.filename)
            for corpus in self.CORPORA
            if (FETCH_CACHE / corpus.source.filename).exists()
        }


def _always_raises(_text: str) -> str:
    raise ValueError("a surface that always raises, to show the sweep can see one")


def _always_grows(text: str) -> str:
    return text + "x"


class LabelFreeInvariants(_CorporaSuite):
    """Three questions whose answer comes from the library's contract, not from a label.

    Does a surface raise, is its output a fixed point, and does a sanitizer's output
    report what its input did not. Each one is undirected on purpose: raising and
    moving have a right answer, and deleting everything earns it, so neither can rank
    a tool. A change shows up as drift.
    """

    name = "label-free-invariants"
    summary = (
        "Raises, fixed point and gained kinds over the provisioned practitioner corpora: "
        "counts, never a score."
    )
    provenance = Provenance(
        origin="an audit of 67 practitioner repositories",
        citation="verazuo/jailbreak_llms, cyberark/FuzzyAI, RootVandal/palisade, Arc PI Taxonomy",
        url="https://gist.github.com/raeq/1d1c2c3c354e390693a225ff0b879d0c",
        version=(
            f"commits {_JAILBREAK_LLMS_COMMIT[:8]}, {_FUZZYAI_COMMIT[:8]}, "
            f"{_PALISADE_COMMIT[:8]}, {_ARCANUM_COMMIT[:8]}"
        ),
        licence="MIT, Apache-2.0, MIT and CC-BY-4.0, per source",
        issues=(1163, 1157, 1158),
        evidence=Evidence.FIXTURE,
        finding=(
            "On 0.18.0 over 67 repositories and 670,101 texts, nothing raised and no preset "
            "or profile failed to be a fixed point. Over this suite's four corpora `rag_ingest` "
            "output gains no kind, while `canonicalize` gains `mixed_script` and `bidi_mixed`, "
            "which #1157 records as intended, and `enclosing_mark`, which is #1158. `demojize` "
            "moves on 10 of 22,897 texts, because the CLDR names of `U+1F550` and three others "
            "hold a quotation mark that a second pass names. It is not a preset, and "
            "`tests/test_adversarial_oracle.py` records it as no documented fixed point."
        ),
        notes=(
            "Counts only: the corpora hold prompts, some with personal information, and no "
            "text reaches a report. `raised` and `not_fixed_point` stay undirected, because "
            "deleting everything also scores zero on both and they could only ever tie. The "
            "sweep proves it can see a failure on every run, and a run whose call count is not "
            "texts times surfaces is an error. Gained kinds are reported for disarm alone, "
            "since scoring another tool with disarm's detector would be circular. Attribution "
            "for the taxonomy: Arcanum Information Security, Arc PI Taxonomy, CC-BY-4.0."
        ),
    )
    CORPORA = PROMPT_CORPORA
    SOURCES = tuple(corpus.source for corpus in CORPORA)
    #: `rag_ingest` is the contrast the other three are read against.
    SANITIZERS = (
        "canonicalize",
        "profile:llm_guardrail",
        "strip_obfuscation",
        "profile:rag_ingest",
    )

    @staticmethod
    def _sweep(surface: Callable[[str], str], texts: list[str]) -> tuple[int, int, int]:
        """Calls, raises and outputs that are not a fixed point, for one surface."""
        calls = raised = moved = 0
        for text in texts:
            calls += 1
            try:
                once = surface(text)
                if surface(once) != once:
                    moved += 1
            except Exception:  # noqa: BLE001 - the count is the result, and it is reported
                raised += 1
        return calls, raised, moved

    def _check_the_sweep_can_fail(self) -> None:
        """An earlier sweep printed 0 moved because `except` hid that nothing had run."""
        probe = ["x"]
        if self._sweep(_always_raises, probe) != (1, 1, 0):
            raise ValueError(f"{self.name}: the sweep cannot see a surface that raises")
        if self._sweep(_always_grows, probe) != (1, 0, 1):
            raise ValueError(f"{self.name}: the sweep cannot see a moved output")

    def census(self, outcome: Outcome, limit: int | None) -> None:
        corpora = self.read_corpora()
        texts = [text for rows in corpora.values() for text in rows][: limit or None]
        surfaces = self.transforms()
        if not texts or not surfaces:
            raise ValueError(f"{len(texts)} texts and {len(surfaces)} surfaces: nothing to sweep")
        self._check_the_sweep_can_fail()
        outcome.population = len(texts)
        record(
            outcome,
            domain=f"{len(texts)} texts from {len(corpora)} provisioned corpora",
            predicates=sorted(surfaces),
            commit=self.provenance.version,
            evidence="fixture: every number here is a census",
        )
        add(outcome, "corpora_read", len(corpora), of=len(self.CORPORA), unit="corpora")
        add(outcome, "texts", len(texts), unit="texts")
        add(outcome, "characters", sum(map(len, texts)), unit="characters")
        add(outcome, "surfaces", len(surfaces), unit="surfaces")
        calls = raised = moved = 0
        for name, surface in sorted(surfaces.items()):
            made, its_raised, its_moved = self._sweep(surface, texts)
            calls, raised, moved = calls + made, raised + its_raised, moved + its_moved
            add(outcome, f"raised:{name}", its_raised, of=len(texts))
            add(outcome, f"not_fixed_point:{name}", its_moved, of=len(texts))
        expected = len(texts) * len(surfaces)
        if calls != expected:
            raise ValueError(f"the sweep made {calls} calls where it owed {expected}")
        add(outcome, "calls", calls, unit="calls")
        add(outcome, "raised", raised, of=calls)
        add(outcome, "not_fixed_point", moved, of=calls)
        _, control_raised, control_moved = self._sweep(_delete_everything, texts)
        add(outcome, "control_delete_everything_raised", control_raised, of=len(texts))
        add(outcome, "control_delete_everything_not_fixed_point", control_moved, of=len(texts))
        if outcome.method.subject == "disarm":
            self._gained_kinds(outcome, surfaces, texts)

    def _gained_kinds(
        self, outcome: Outcome, surfaces: dict[str, Callable[[str], str]], texts: list[str]
    ) -> None:
        import disarm

        inspect = getattr(disarm, "inspect_anomalies", None)
        if inspect is None:
            return
        for name in self.SANITIZERS:
            surface = surfaces.get(name)
            if surface is None:
                continue
            reports = rows = 0
            gained: Counter[str] = Counter()
            for text in texts:
                try:
                    output = surface(text)
                except Exception:  # noqa: BLE001 - no output to inspect, and `raised:` counts it
                    continue
                after = set(inspect(output).kinds)
                reports += bool(after)
                new = after - set(inspect(text).kinds)
                rows += bool(new)
                gained.update(new)
            add(outcome, f"output_reports:{name}", reports, of=len(texts))
            add(outcome, f"gained_a_kind:{name}", rows, of=len(texts))
            for kind, count in sorted(gained.items()):
                add(outcome, f"gained_kind:{name}:{kind}", count, of=len(texts))


_SPIKEE_COMMIT = "8f8e9ad3b684e5f3e2f9b507cae550bdc8372514"
_PROMPTS = {corpus.name: corpus for corpus in PROMPT_CORPORA}
#: The first word long enough to split, for a measure that does not need a label.
_PLANTABLE = re.compile(r"[A-Za-z]{4,}")


def _palisade_benign(path: Path) -> list[str]:
    rows = (json.loads(line) for line in _nonblank_lines(path))
    return [row["text"] for row in rows if row["label"] == "benign"]


def _plant_zero_width(text: str) -> str | None:
    """`text` with a `U+200B` inside its first long word, or None if it has none."""
    found = _PLANTABLE.search(text)
    if found is None:
        return None
    at = found.start() + 2
    return f"{text[:at]}\u200b{text[at:]}"


def _fires(detector: Callable[[str], bool], text: str) -> bool:
    try:
        return bool(detector(text))
    except Exception:  # noqa: BLE001 - a rival may refuse an input, which is not a finding
        return False


class BenignControls(_CorporaSuite):
    """Text people type into a model, which `gutenberg-benign` is not."""

    name = "benign-controls"
    JOB = Job.CLEAN_COST
    REQUIRES_ANY = (Capability.TRANSFORM, Capability.DETECT)
    summary = "Prompts their upstream labels regular or benign: fires and rewrites, per set."
    provenance = Provenance(
        origin="practitioner repositories",
        citation=(
            "verazuo/jailbreak_llms, cyberark/FuzzyAI, RootVandal/palisade, ReversecLabs/spikee"
        ),
        url="https://gist.github.com/raeq/3bfb88e7db7d249fbe23602d3baf322d",
        version=(
            f"commits {_JAILBREAK_LLMS_COMMIT[:8]}, {_FUZZYAI_COMMIT[:8]}, "
            f"{_PALISADE_COMMIT[:8]}, {_SPIKEE_COMMIT[:8]}"
        ),
        licence="MIT, Apache-2.0, MIT and Apache-2.0, per source",
        issues=(1154, 1153, 1155, 759),
        evidence=Evidence.FIXTURE,
        finding=(
            "On 0.18.0 `has_anomalies` fires on 1,881 of the 13,735 prompts jailbreak_llms "
            "labels regular, and 1,658 of those come from curly quotes, the ellipsis and "
            "fullwidth punctuation. That led to #1153 and #1155."
        ),
        notes=(
            "Each set is reported alone, because pooling would let 13,735 rows hide 24. An "
            "upstream label says regular or benign and not free of obfuscation, so a rate here "
            "is a ceiling and every number is a census. Silence has a degenerate solution, a "
            "detector that never fires, so each detector is also shown what it does with a "
            "`U+200B` planted inside the first long word of the same rows. The sets were fixed "
            "before a score was read. jailbreak_llms says its data can hold personal "
            "information and reports in aggregate, so this fetches by commit and digest, "
            "vendors nothing, and no row reaches a report."
        ),
    )
    CORPORA = (
        _PROMPTS["jailbreak_llms:regular_prompts_2023_12_25"],
        _PROMPTS["jailbreak_llms:regular_prompts_2023_05_07"],
        _PROMPTS["fuzzyai:benign_prompts"],
        replace(_PROMPTS["palisade:benchmark"], name="palisade:benign", read=_palisade_benign),
        _Corpus(
            name="spikee:seeds-investment-advice-fp",
            source=Source(
                url=(
                    f"https://raw.githubusercontent.com/ReversecLabs/spikee/{_SPIKEE_COMMIT}"
                    "/spikee/data/workspace/datasets/seeds-investment-advice-fp"
                    "/standalone_user_inputs.jsonl"
                ),
                filename="practitioner-corpora/spikee/seeds-investment-advice-fp.jsonl",
                licence="Apache-2.0",
                sha256="ae518e6861365a04f043fa2df0edb1901a38129c2c05d03ff73f9552c6092e2b",
            ),
            read=_jsonl_text,
        ),
    )
    SOURCES = tuple(corpus.source for corpus in CORPORA)

    def census(self, outcome: Outcome, limit: int | None) -> None:
        corpora = {name: rows[: limit or None] for name, rows in self.read_corpora().items()}
        outcome.population = sum(map(len, corpora.values()))
        if not outcome.population:
            raise ValueError("no benign rows to count")
        detectors = self.detect()
        sanitizer = self._sanitizer()
        record(
            outcome,
            domain=f"{outcome.population} rows from {len(corpora)} provisioned sets",
            predicates=[self.JOB, *sorted(detectors)],
            commit=self.provenance.version,
            evidence="fixture: every number here is a census",
        )
        add(outcome, "sets_read", len(corpora), of=len(self.CORPORA), unit="sets")
        for name, rows in corpora.items():
            self._count_set(outcome, name, rows, detectors, sanitizer)

    @staticmethod
    def _count_set(
        outcome: Outcome,
        name: str,
        rows: list[str],
        detectors: dict[str, Callable[[str], bool]],
        sanitizer: Callable[[str], str] | None,
    ) -> None:
        total = len(rows)
        add(outcome, f"rows:{name}", total, unit="rows")
        add(outcome, f"non_ascii:{name}", sum(not text.isascii() for text in rows), of=total)
        planted = [p for p in map(_plant_zero_width, rows) if p is not None]
        for detector_name, detector in sorted(detectors.items()):
            fires = sum(_fires(detector, text) for text in rows)
            found = sum(_fires(detector, text) for text in planted)
            add(outcome, f"fires:{detector_name}:{name}", fires, of=total)
            add(outcome, f"planted_detected:{detector_name}:{name}", found, of=len(planted))
        if sanitizer is not None:
            rewritten = sum(damage.apply(sanitizer, text) != text for text in rows)
            add(outcome, f"rewritten:{name}", rewritten, of=total)
        deleted = sum(_delete_everything(text) != text for text in rows)
        add(outcome, f"control_delete_everything_rewritten:{name}", deleted, of=total)
        unchanged = sum(_identity(text) != text for text in rows)
        add(outcome, f"control_identity_rewritten:{name}", unchanged, of=total)


_GHOSTCHARS_COMMIT = "6ea70c64c0a01092e8243f71da1ded2c62cb2e7a"


class GhostcharsLabels(_KnownAnswerSuite):
    """Another project's hand labels, including the class of text a detector gets wrong."""

    name = "ghostchars-labels"
    REQUIRES_ANY = (Capability.TRANSFORM, Capability.DETECT)
    summary = "468 hand-labelled excerpts and 75 fixtures from another detector's own studies."
    provenance = Provenance(
        origin="antonsoo",
        citation="ghostchars, studies/",
        url="https://github.com/antonsoo/ghostchars",
        version=f"commit {_GHOSTCHARS_COMMIT[:12]}",
        licence="MIT",
        issues=(1161, 1134, 1153),
        evidence=Evidence.KNOWN_ANSWER,
        finding=(
            "On 0.18.0 `has_anomalies` fires on 40 of the 49 excerpts labelled ordinary "
            "orthography and on all 26 labelled as ghostchars' own tool errors, which is "
            "independent evidence for #1153. Markup, typography and legacy control bytes read "
            "0 of 17, 0 of 16 and 0 of 10, and all 24 flag cases agree on findings."
        ),
        notes=(
            "The excerpts were selected by another detector firing, so a class count says "
            "nothing about prevalence and no rate here should be quoted as one. What each "
            "label asks was fixed from the study's README before a score was read: O should "
            "fire, L, T, M and A should stay silent, and the rest are a census. H is on that "
            "list because an excerpt lacks the hidden text it was labelled for, so its count "
            "is no detection rate. The flag cases are known answers from `cases.json`. The "
            "code-identifier studies ask a different question, since disarm's presets are not "
            "code-safe, so every study's fixtures are counted and not scored. Counts only: no "
            "excerpt reaches a report."
        ),
    )
    SOURCES = (
        Source(
            url=f"https://codeload.github.com/antonsoo/ghostchars/tar.gz/{_GHOSTCHARS_COMMIT}",
            filename="ghostchars",
            licence="MIT",
            kind="tar.gz",
            member=f"ghostchars-{_GHOSTCHARS_COMMIT}/studies",
            note="Cached, never vendored. Pinned to a commit; the tree is digest-checked.",
        ),
    )
    #: Digest of `studies/` at the pinned commit. A mismatch refuses to report.
    TREE_SHA256 = "95e4b7c0ad1ec0423184c4f459470b4f7372b930b7d86ea41bd82f279f985373"
    SHOULD_FIRE = frozenset({"O"})
    SHOULD_STAY_SILENT = frozenset({"L", "T", "M", "A"})

    def available(self) -> tuple[bool, str]:
        ready, reason = super().available()
        if not ready:
            return ready, reason
        root = self.locate()
        assert root is not None
        digest = tree_digest(root)
        if digest != self.TREE_SHA256:
            return False, (f"tree digest {digest[:16]} is not the pinned {self.TREE_SHA256[:16]}")
        return True, ""

    def _direction(self, label: str) -> bool | None:
        if label in self.SHOULD_FIRE:
            return True
        return False if label in self.SHOULD_STAY_SILENT else None

    def _repair_surfaces(self) -> dict[str, Callable[[str], str]]:
        """What a subject ships to clean text, and what it ships for text a person reads."""
        assert self.subject is not None
        return {
            **self.subject.role(Role.SANITIZER),
            **self.subject.role(Role.SANITIZER, job=Job.REVIEW_DISPLAY),
        }

    def scored(self, outcome: Outcome, limit: int | None) -> None:
        root = self.locate()
        assert root is not None
        census = json.loads((root / "prompt-census/classification.json").read_text("utf-8"))
        rows = next(value for value in census.values() if isinstance(value, list))
        rows = rows[: limit or None]
        cases = json.loads((root / "flag-tag-payloads/cases.json").read_text("utf-8"))
        studies = {
            study.name: [path.read_text("utf-8") for path in sorted(study.glob("fixtures/*"))]
            for study in sorted(root.iterdir())
            if (study / "fixtures").is_dir()
        }
        detectors = self.detect()
        outcome.population = len(rows) + sum(map(len, studies.values()))
        record(
            outcome,
            domain=f"{len(rows)} labelled excerpts and {len(studies)} studies' fixtures",
            predicates=sorted(detectors),
            commit=_GHOSTCHARS_COMMIT,
            evidence="known answers where a label or a case fixes one, and a census elsewhere",
        )
        self._labels(outcome, rows, detectors)
        self._flag_cases(outcome, cases, detectors)
        self._studies(outcome, studies, detectors)

    def _labels(
        self, outcome: Outcome, rows: list[dict], detectors: dict[str, Callable[[str], bool]]
    ) -> None:
        add(outcome, "labelled_rows", len(rows), unit="rows")
        by_label: dict[str, list[str]] = {}
        for row in rows:
            by_label.setdefault(row["label"], []).append(row.get("excerpt") or "")
        for label, excerpts in sorted(by_label.items()):
            add(outcome, f"label_{label}_rows", len(excerpts), unit="rows")
            for name, detector in sorted(detectors.items()):
                fired = sum(bool(text) and _fires(detector, text) for text in excerpts)
                add(
                    outcome,
                    f"label_{label}_fired:{name}",
                    fired,
                    of=len(excerpts),
                    higher_is_better=self._direction(label),
                )

    def _flag_cases(
        self, outcome: Outcome, cases: list[dict], detectors: dict[str, Callable[[str], bool]]
    ) -> None:
        total = len(cases)
        for name, detector in sorted(detectors.items()):
            agree = sum(bool(c["findings"]) == _fires(detector, c["text"]) for c in cases)
            add(
                outcome,
                f"flag_findings_agree:{name}",
                agree,
                of=total,
                higher_is_better=True,
            )
        for name, surface in sorted(self._repair_surfaces().items()):
            matched = sum(damage.apply(surface, c["text"]) == c["expected"] for c in cases)
            add(
                outcome,
                f"flag_expected_matched:{name}",
                matched,
                of=total,
                higher_is_better=True,
            )
        deleted = sum(_delete_everything(c["text"]) == c["expected"] for c in cases)
        add(outcome, "control_delete_everything", deleted, of=total)
        untouched = sum(_identity(c["text"]) == c["expected"] for c in cases)
        add(outcome, "control_identity", untouched, of=total)

    @staticmethod
    def _studies(
        outcome: Outcome,
        studies: dict[str, list[str]],
        detectors: dict[str, Callable[[str], bool]],
    ) -> None:
        for study, texts in studies.items():
            add(outcome, f"fixtures:{study}", len(texts), unit="fixtures")
            for name, detector in sorted(detectors.items()):
                fired = sum(_fires(detector, text) for text in texts)
                add(outcome, f"fixtures_fired:{name}:{study}", fired, of=len(texts))


_PYRIT_COMMIT = "d3446e045960b5ebee4641aa70fdeb03af186587"
_GARAK_SMUGGLING_COMMIT = "4b7761c2108446043012549cbe8f7c942cabb26d"


class TokenSmugglingConstructions(_KnownAnswerSuite):
    """What two red-team tools ship, rebuilt from their descriptions, against a known cover.

    Neither package is imported. PyRIT has about 100 converters behind about 50
    dependencies, Python has no sandbox like the one Node's generator runs in, and these
    constructions are short and fully specified.
    """

    name = "token-smuggling-constructions"
    availability = Availability.DERIVED
    summary = "Seven Unicode constructions from PyRIT and garak, each with a known cover."
    provenance = Provenance(
        origin="microsoft/PyRIT, NVIDIA/garak",
        citation="PyRIT token-smuggling converters; garak smuggling probes",
        url="https://github.com/microsoft/PyRIT",
        version=f"commits {_PYRIT_COMMIT[:8]} and {_GARAK_SMUGGLING_COMMIT[:8]}",
        licence="MIT and Apache-2.0, quoted and not vendored",
        issues=(1143, 1136, 701),
        evidence=Evidence.KNOWN_ANSWER,
        finding=(
            "On 0.18.0 the prompt-hygiene surface recovers all seven, unidecode and anyascii "
            "six each and decancer one. Sneaky bits appeared in no suite before this one, and "
            "`decode_smuggled` has no scheme for it, which is #1136."
        ),
        notes=(
            "Sources. Sneaky bits, fixed eight bits: PyRIT `SneakyBitsSmugglerConverter`. Sneaky "
            "bits, unpadded with `U+200B` for a space: garak `InjectSneakyBits`, scored apart "
            "because a letter takes seven bits and a digit six. Variation-selector bytes on an "
            "emoji: PyRIT `VariationSelectorSmugglerConverter` and garak "
            "`InjectUnicodeVariantSelectors`. Tag characters: PyRIT `AsciiSmugglerConverter` and "
            "garak `InjectUnicodeTagChars`. Bidi wraps: PyRIT `BidiConverter`. `U+200B` between "
            "every character: PyRIT `ZeroWidthConverter`. The rest of both tools does not earn a "
            "row: their zalgo, homoglyph, leetspeak and Arabic forms repeat "
            "`p4rs3lt0ngv3-transforms` and promptfoo's maps. `constructions_decoded` is a census "
            "for disarm alone and moves when #1136 lands."
        ),
    )
    COVER = "the quick brown fox jumps over the lazy dog"
    PAYLOAD = "hidden"
    EMOJI = "\U0001f60a"

    @staticmethod
    def sneaky_bits(text: str, *, pad: bool) -> str:
        """`U+2062` for 0 and `U+2064` for 1, in either of the two framings."""

        def carrier(bits: str) -> str:
            return "".join("\u2064" if bit == "1" else "\u2062" for bit in bits)

        if pad:
            return carrier("".join(format(byte, "08b") for byte in text.encode("utf-8")))
        return "".join("\u200b" if ch == " " else carrier(format(ord(ch), "b")) for ch in text)

    def _constructions(self) -> dict[str, tuple[str, str]]:
        """Each construction's text, and the cover it has to come back to."""
        cover = self.COVER
        payload = self.PAYLOAD.encode("utf-8")
        selectors = "".join(
            chr(0xFE00 + byte) if byte < 16 else chr(0xE0100 + byte - 16) for byte in payload
        )
        tags = "".join(chr(0xE0000 + byte) for byte in payload)
        return {
            "sneaky bits, fixed eight": (cover + self.sneaky_bits(self.PAYLOAD, pad=True), cover),
            "variation-selector bytes on an emoji": (
                cover + self.EMOJI + selectors,
                cover + self.EMOJI,
            ),
            "tag characters": (cover + tags, cover),
            "bidi override wrap": (f"\u202e{cover}\u202c", cover),
            "bidi embedding wrap": (f"\u202b{cover}\u202c", cover),
            "bidi isolate wrap": (f"\u2067{cover}\u2069", cover),
            "U+200B between every character": ("\u200b".join(cover), cover),
        }

    def scored(self, outcome: Outcome, limit: int | None) -> None:
        cases = self._constructions()
        unpadded = self.COVER + self.sneaky_bits(self.PAYLOAD, pad=False)
        total = len(cases)
        outcome.population = total + 1
        record(
            outcome,
            domain=f"{total} constructions and one further framing, on one fixed cover",
            predicates=[self.JOB],
            pyrit=_PYRIT_COMMIT,
            garak=_GARAK_SMUGGLING_COMMIT,
            evidence="known answer: the cover each construction was applied to",
        )
        fn = self._sanitizer() or _identity
        recovered = {
            name: int(damage.collides([fn], attack, answer))
            for name, (attack, answer) in cases.items()
        }
        add(
            outcome,
            "constructions_recovered",
            sum(recovered.values()),
            of=total,
            higher_is_better=True,
        )
        add(
            outcome,
            "sneaky_bits_unpadded_recovered",
            int(damage.collides([fn], unpadded, self.COVER)),
            of=1,
            higher_is_better=True,
        )
        for key, surface in (
            ("control_delete_everything", _delete_everything),
            ("control_identity", _identity),
        ):
            add(
                outcome,
                key,
                sum(damage.collides([surface], a, b) for a, b in cases.values()),
                of=total,
            )
        outcome.extra = {"recovered_by_construction": recovered}
        if outcome.method.subject == "disarm":
            self._decoded(outcome, [*(attack for attack, _ in cases.values()), unpadded])

    @staticmethod
    def _decoded(outcome: Outcome, attacks: list[str]) -> None:
        import disarm

        decode = getattr(disarm, "decode_smuggled", None)
        if decode is None:
            return
        add(
            outcome,
            "constructions_decoded",
            sum(bool(decode(attack)) for attack in attacks),
            of=len(attacks),
        )


_ST3GG_COMMIT = "35f8b2b8529a74091c97ce622ee0cbf1ae3bd260"


def _without(*code_points: int) -> Callable[[str], str]:
    table: dict[int, None] = dict.fromkeys(code_points)
    return lambda text: text.translate(table)


def _spaced(*code_points: int) -> Callable[[str], str]:
    table = dict.fromkeys(code_points, " ")
    return lambda text: text.translate(table)


def _without_trailing_whitespace(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.split("\n"))


def _bold_to_ascii(text: str) -> str:
    """The generator's math alphanumeric style, `U+1D400` to `U+1D433`, undone."""
    out = []
    for ch in text:
        cp = ord(ch)
        if 0x1D400 <= cp <= 0x1D419:
            out.append(chr(cp - 0x1D400 + ord("A")))
        elif 0x1D41A <= cp <= 0x1D433:
            out.append(chr(cp - 0x1D41A + ord("a")))
        else:
            out.append(ch)
    return "".join(out)


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _literal_dict(source: str, name: str) -> dict[str, str]:
    """A module-level dict from Python source, read without running any of it."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == name:
            return ast.literal_eval(node.value)
    return {}


class St3ggTextExamples(_KnownAnswerSuite):
    """Static example files, each with a cover its generator's constants fix."""

    name = "st3gg-text-examples"
    summary = "ST3GG's eleven Unicode text examples: recovery against a known cover."
    provenance = Provenance(
        origin="elder-plinius",
        citation="ST3GG, examples/",
        url="https://github.com/elder-plinius/ST3GG",
        version=f"commit {_ST3GG_COMMIT[:12]}",
        licence="AGPL-3.0, cached and never vendored",
        issues=(1141, 1134),
        evidence=Evidence.KNOWN_ANSWER,
        finding=(
            "On 0.18.0 the prompt-hygiene surface recovers 11 of 11, and decancer, unidecode "
            "and anyascii 7 each. `has_anomalies` is silent on 5, and two of those, the spread "
            "variation selector and spread `U+034F`, are the real gap in #1134."
        ),
        notes=(
            "Each cover is derived from the example by undoing what the generator's constants "
            "say it did, and that per-file mapping in `TECHNIQUES` is the one part that is ours. "
            "A derivation that changes nothing is an error. The generator is parsed with `ast` "
            "and never run, and the files are read as data, so no upstream code runs. "
            "Capitalization, misspelling, word choice, sentence length, emoji substitution, "
            "emoji skin tone, Morse, base32, Punycode, Braille and the QR text carry no invisible "
            "signal, so they are counted and not scored. The repository's README hides 122 "
            "zero-width characters and invites decoding them, and this suite reads neither it "
            "nor the README under `examples`."
        ),
    )
    SOURCES = (
        Source(
            url=f"https://codeload.github.com/elder-plinius/ST3GG/tar.gz/{_ST3GG_COMMIT}",
            filename="st3gg",
            licence="AGPL-3.0",
            kind="tar.gz",
            member=f"ST3GG-{_ST3GG_COMMIT}/examples",
            note="Cached, never vendored. Its README hides a payload; do not read it.",
        ),
    )
    #: Digest of `examples/` at the pinned commit. A mismatch refuses to report.
    TREE_SHA256 = "d223ad5c033993d973d3a922c8eefdd0b37bf472b3b7c28992f1aeab74238b2c"
    GENERATOR = "generate_examples.py"
    #: Technique, file, and how the generator's constants say the cover comes back.
    TECHNIQUES: ClassVar[dict[str, tuple[str, Callable[[str], str] | None]]] = {
        "zero width": ("example_zero_width.txt", _without(0x200B, 0x200C, 0x200D)),
        "tag characters": ("example_invisible_ink.txt", _without(*range(0xE0000, 0xE0080))),
        "variation selector, spread": ("example_variation_selector.txt", _without(0xFE01)),
        "U+034F, spread": ("example_combining_diacritics.txt", _without(0x34F)),
        "directional override": (
            "example_directional_override.txt",
            _without(0x202C, 0x202D, 0x202E),
        ),
        "hangul filler": ("example_hangul_filler.txt", _spaced(0x3164)),
        "confusable whitespace": (
            "example_confusable_whitespace.txt",
            _spaced(0x2002, 0x2003, 0x2009),
        ),
        "trailing whitespace": ("example_whitespace.txt", _without_trailing_whitespace),
        #: None: this one reads `HOMOGLYPH_MAP` out of the generator.
        "homoglyph": ("example_homoglyph.txt", None),
        "math alphanumeric": ("example_math_alphanumeric.txt", _bold_to_ascii),
        "NFC against NFD": ("example_normalization.txt", _nfc),
    }
    BOUNDARY_FILES = (
        "example_capitalization.txt",
        "example_misspelling.txt",
        "example_word_choice.txt",
        "example_sentence_length.txt",
        "example_emoji_substitution.txt",
        "example_emoji_skin_tone.txt",
        "example_morse.txt",
        "example_multibase.txt",
        "example_punycode.txt",
        "example_braille.txt",
        "example_qr_steg.txt",
    )

    def available(self) -> tuple[bool, str]:
        ready, reason = super().available()
        if not ready:
            return ready, reason
        root = self.locate()
        assert root is not None
        digest = tree_digest(root)
        if digest != self.TREE_SHA256:
            return False, f"tree digest {digest[:16]} is not the pinned {self.TREE_SHA256[:16]}"
        return True, ""

    def _cases(self, root: Path) -> dict[str, tuple[str, str]]:
        """Each technique's example and the cover derived from it."""
        generator = (root / self.GENERATOR).read_text(encoding="utf-8")
        homoglyphs = {
            ord(glyph): letter
            for letter, glyph in _literal_dict(generator, "HOMOGLYPH_MAP").items()
        }
        cases: dict[str, tuple[str, str]] = {}
        for technique, (filename, derive) in self.TECHNIQUES.items():
            with open(root / filename, encoding="utf-8", newline="") as fh:
                text = fh.read()
            cover = derive(text) if derive else text.translate(homoglyphs)
            if cover == text:
                raise ValueError(f"{technique}: the derived cover is the example itself")
            cases[technique] = (text, cover)
        return cases

    def scored(self, outcome: Outcome, limit: int | None) -> None:
        root = self.locate()
        assert root is not None
        cases = self._cases(root)
        total = len(cases)
        outcome.population = total
        detectors = self.detect()
        record(
            outcome,
            domain=f"{total} static text examples at the pinned commit",
            predicates=[self.JOB, *sorted(detectors)],
            commit=_ST3GG_COMMIT,
            evidence="known answer: a cover the generator's constants fix",
        )
        fn = self._sanitizer() or _identity
        recovered = {
            technique: int(damage.collides([fn], text, cover))
            for technique, (text, cover) in cases.items()
        }
        add(
            outcome,
            "techniques_recovered",
            sum(recovered.values()),
            of=total,
            higher_is_better=True,
        )
        for name, detector in sorted(detectors.items()):
            fired = sum(_fires(detector, text) for text, _ in cases.values())
            add(outcome, f"techniques_detected:{name}", fired, of=total)
        for key, surface in (
            ("control_delete_everything", _delete_everything),
            ("control_identity", _identity),
        ):
            add(
                outcome,
                key,
                sum(damage.collides([surface], a, b) for a, b in cases.values()),
                of=total,
            )
        present = sum((root / name).is_file() for name in self.BOUNDARY_FILES)
        add(outcome, "boundary_files", present, unit="files")
        outcome.extra = {"recovered_by_technique": recovered}


class ArcanumTaxonomy(_FixtureSuite):
    """A named technique per example, which an unlabelled corpus cannot say.

    It holds no covers, so it can say whether a technique is seen or changed, and not
    whether the cover comes back.
    """

    name = "arcanum-taxonomy"
    REQUIRES_ANY = (Capability.TRANSFORM, Capability.DETECT)
    summary = "Arcanum's 104 non-ASCII examples under 27 named techniques: seen, and changed."
    provenance = Provenance(
        origin="Arcanum Information Security",
        citation="Arc PI Taxonomy, docs/data/taxonomy.json",
        url="https://github.com/Arcanum-Sec/arc_pi_taxonomy",
        version=f"commit {_ARCANUM_COMMIT[:12]}",
        licence="CC-BY-4.0",
        issues=(1160, 1138, 1156),
        evidence=Evidence.FIXTURE,
        finding=(
            "On 0.18.0 `has_anomalies` fires on 41 of the 104 non-ASCII examples, and most of "
            "the silent titles are the right answer. Strikethrough reads 0 of 4 and zalgo 1 of "
            "4, which is #1156."
        ),
        notes=(
            "Attribution: Arcanum Information Security, Arc PI Taxonomy, CC-BY-4.0. The classes "
            "were chosen by Claude on 2026-10-31 from each title's name, for #1160, whose census "
            "table had already been read, so they are not blind. Do not move a title to improve "
            "a number. A disguise is what a character-level sanitizer should answer, a style "
            "restyles letters that a fold may or may not bring back, and the boundary is "
            "ciphers, encodings, other languages and markup. Examples are counted and never "
            "printed, and a raw 41 of 104 means nothing without the classes."
        ),
    )
    SOURCES = (_PROMPTS["arcanum:taxonomy"].source,)
    CLASSES: ClassVar[dict[str, frozenset[str]]] = {
        "disguise": frozenset(
            {
                "ANSI Escape Concealment (Terminal Codes)",
                "Bidirectional Text Override (Trojan Source)",
                "Homoglyphs",
                "Invisible Text",
                "Metacharacter Confusion",
                "Spaces / Whitespace",
                "Strikethrough / Underline / Overlay",
                "Zalgo Text",
            }
        ),
        "style": frozenset(
            {
                "Bubble / Enclosed Text",
                "Fullwidth Characters",
                "Mathematical Unicode",
                "Regional Indicators",
                "Small Caps / Subscript / Superscript",
                "Upside Down Text",
                "Vertical Text",
                "Wingdings / Symbol Fonts",
            }
        ),
        "boundary": frozenset(
            {
                "A1Z26 Number Substitution",
                "ASCII",
                "Acrostics",
                "Adversarial Poetry",
                "Alternative Base Encodings (Base32 / Base58 / Base85)",
                "Alternative Language",
                "Ancient Scripts",
                "Baconian Cipher",
                "Base64",
                "Bijection Learning",
                "Binary",
                "Braille",
                "Brainfuck / Esoteric Languages",
                "Case Changing",
                "Cipher",
                "Code Switching / Randomizer",
                "Code-Structure Encoding (CodeAttack)",
                "Compression Encoding (gzip / zlib)",
                "Delimiter",
                "Emoji",
                "Fictional & Constructed Languages",
                "Graph Nodes",
                "HTML Entities",
                "Hexadecimal",
                "JSON",
                "Japanese Scripts",
                "Layered Encoding (Encoding Chains)",
                "Legacy Charset Confusion (GB18030 / UTF-7)",
                "Link Smuggling",
                "Markdown",
                "Morse Code",
                "NATO Phonetic Alphabet",
                "Numeric Code-Point Encoding (Octal / Decimal)",
                "Phonetic Substitution",
                "Query-Language Encoding (QueryAttack)",
                "Rail Fence Cipher",
                "Reverse",
                "Semaphore",
                "Splats",
                "Steganography",
                "Symbolic Math Encoding (MathPrompt)",
                "Synonyms / Word Substitution",
                "Tap Code",
                "Truncation & Misspelling",
                "URL Encoding",
                "Waveforms / Frequencies",
                "XML",
            }
        ),
    }

    def _class_of(self, title: str) -> str:
        for name, titles in self.CLASSES.items():
            if title in titles:
                return name
        raise ValueError(f"unclassed title {title!r}: a pinned file has none")

    def census(self, outcome: Outcome, limit: int | None) -> None:
        path = self.locate()
        assert path is not None
        items = json.loads(path.read_text(encoding="utf-8"))["evasions"]
        by_title = {
            item["title"]: [
                example if isinstance(example, str) else json.dumps(example, ensure_ascii=False)
                for example in item.get("examples", [])
            ]
            for item in items
        }
        wide = {
            title: [text for text in examples if not text.isascii()]
            for title, examples in by_title.items()
        }
        classes = {title: self._class_of(title) for title in by_title}
        total = sum(map(len, wide.values()))
        outcome.population = total
        detectors = self.detect()
        sanitizer = self._sanitizer()
        record(
            outcome,
            domain=f"{total} non-ASCII examples under {len(by_title)} titles",
            predicates=[self.JOB, *sorted(detectors)],
            commit=_ARCANUM_COMMIT,
            evidence="fixture: a named technique and no cover, so every number is a census",
        )
        add(outcome, "titles", len(by_title), unit="titles")
        add(outcome, "titles_with_non_ascii", sum(bool(v) for v in wide.values()), unit="titles")
        add(outcome, "non_ascii_examples", total, unit="examples")
        for name, detector in sorted(detectors.items()):
            fired = sum(_fires(detector, text) for rows in wide.values() for text in rows)
            add(outcome, f"fired:{name}", fired, of=total)
        for cls in self.CLASSES:
            rows = [
                text for title, texts in wide.items() if classes[title] == cls for text in texts
            ]
            self._count_class(outcome, cls, rows, detectors, sanitizer)
        outcome.extra = {
            "by_title": {
                title: {
                    "class": classes[title],
                    "examples": len(texts),
                    "fired": {
                        name: sum(_fires(detector, text) for text in texts)
                        for name, detector in sorted(detectors.items())
                    },
                }
                for title, texts in wide.items()
                if texts
            }
        }

    @staticmethod
    def _count_class(
        outcome: Outcome,
        cls: str,
        rows: list[str],
        detectors: dict[str, Callable[[str], bool]],
        sanitizer: Callable[[str], str] | None,
    ) -> None:
        total = len(rows)
        add(outcome, f"examples:{cls}", total, unit="examples")
        for name, detector in sorted(detectors.items()):
            add(outcome, f"fired:{name}:{cls}", sum(_fires(detector, t) for t in rows), of=total)
        if sanitizer is not None:
            changed = sum(damage.apply(sanitizer, text) != text for text in rows)
            add(outcome, f"changed:{cls}", changed, of=total)
        deleted = sum(_delete_everything(text) != text for text in rows)
        add(outcome, f"control_delete_everything_changed:{cls}", deleted, of=total)
        untouched = sum(_identity(text) != text for text in rows)
        add(outcome, f"control_identity_changed:{cls}", untouched, of=total)


SUITES = [
    P4rs3lt0ngv3Transforms(),
    GarakAnsiEscapes(),
    L1b3rt4sFixtures(),
    LabelFreeInvariants(),
    BenignControls(),
    GhostcharsLabels(),
    TokenSmugglingConstructions(),
    St3ggTextExamples(),
    ArcanumTaxonomy(),
]
