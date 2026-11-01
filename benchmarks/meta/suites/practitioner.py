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
import random
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
    LETTERS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

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

        letters, styles, no_letter, failed_on_letters = self._letter_pairs(root, chosen)
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
            letters=self.LETTERS,
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
            add(
                outcome,
                f"{key}_letters",
                self._recovered(control, letters),
                of=len(letters),
                detail="must be zero, or the per-letter metric has a degenerate solution",
            )
        add(
            outcome,
            "styles_changing_no_letter",
            no_letter,
            of=styles,
            unit="transforms",
            detail="whitespace and reversal: these leave the alphabet alone, so a census",
        )
        add(outcome, "styles_that_failed_on_letters", failed_on_letters, of=styles)
        if fn is None:
            return

        add(
            outcome,
            "style_letters_recovered",
            self._recovered(fn, letters),
            of=len(letters),
            higher_is_better=True,
            detail="one letter a style changed lands on the same form as the plain letter",
        )
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
        missed: dict[str, list[str]] = {}
        for label, left, right in letters:
            if not damage.collides([fn], left, right):
                missed.setdefault(label, []).append(right)
        outcome.extra = {
            "recovered_of_pairs_by_transform": by_transform,
            "missed_letters_by_transform": missed,
        }

    def _letter_pairs(
        self, root: Path, chosen: list[str]
    ) -> tuple[list[tuple[str, str, str]], int, int, int]:
        """Each style on each letter, keeping the letters it changed.

        A pangram holds every letter, so one unmapped letter costs a style both of its pairs:
        ``unicode/small-caps`` scores 0 of 2 and misses only ``q`` and ``Q`` (#1140). Returns
        the pairs, the styles run, those changing no letter, and those that failed on them.
        """
        styles = [relative for relative in chosen if classify_transform(relative) == "style"]
        generated = self.generate(root, styles, list(self.LETTERS)) if styles else {}
        pairs: list[tuple[str, str, str]] = []
        no_letter = failed = 0
        for relative in styles:
            result = generated[relative]
            outputs = result["outputs"] if not result["error"] else []
            if len(outputs) != len(self.LETTERS):
                failed += 1
                continue
            changed = [
                (relative.removesuffix(".js"), str(output), letter)
                for output, letter in zip(outputs, self.LETTERS, strict=True)
                if output != letter
            ]
            pairs.extend(changed)
            no_letter += not changed
        return pairs, len(styles), no_letter, failed

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
    summary = "Eight Unicode constructions from PyRIT, garak and spikee, each with a known cover."
    provenance = Provenance(
        origin="microsoft/PyRIT, NVIDIA/garak",
        citation="PyRIT token-smuggling converters; garak smuggling probes",
        url="https://github.com/microsoft/PyRIT",
        version=f"commits {_PYRIT_COMMIT[:8]} and {_GARAK_SMUGGLING_COMMIT[:8]}",
        licence="MIT and Apache-2.0, quoted and not vendored",
        issues=(1143, 1136, 701, 1166),
        evidence=Evidence.KNOWN_ANSWER,
        finding=(
            "On 0.18.0 the prompt-hygiene surface recovers all eight, unidecode seven, "
            "anyascii six and decancer one. Sneaky bits appeared in no suite before this one, and "
            "`decode_smuggled` has no scheme for it, which is #1136."
        ),
        notes=(
            "Sources. Sneaky bits, fixed eight bits: PyRIT `SneakyBitsSmugglerConverter`. Sneaky "
            "bits, unpadded with `U+200B` for a space: garak `InjectSneakyBits`, scored apart "
            "because a letter takes seven bits and a digit six. Variation-selector bytes on an "
            "emoji: PyRIT `VariationSelectorSmugglerConverter` and garak "
            "`InjectUnicodeVariantSelectors`. Tag characters: PyRIT `AsciiSmugglerConverter` and "
            "garak `InjectUnicodeTagChars`. Tag characters between `U+E0001` and `U+E007F`: "
            "spikee `ascii_smuggler`, read and not run. Bidi wraps: PyRIT `BidiConverter`. `U+200B` between "
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
            "tag characters between U+E0001 and U+E007F": (
                f"{cover}{chr(0xE0001)}{tags}{chr(0xE007F)}",
                cover,
            ),
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


_PROMPTFOO_COMMIT = "5582f347bbc5359b201ce2d48c9c7fbebd8dcbd9"
_HOMOGLYPH_ROW = re.compile(r"^\s*'?(\w)'?:\s*'(.)'", re.MULTILINE)
_ARABIC_ROW = re.compile(r"^\s*(\S):\s*'(.)'", re.MULTILINE)


class PromptfooLiteralMaps(_KnownAnswerSuite):
    """Two object literals in TypeScript, which give an answer per row and run nothing."""

    name = "promptfoo-literal-maps"
    summary = "promptfoo's homoglyph and Arabic presentation maps: 105 rows with a known answer."
    provenance = Provenance(
        origin="promptfoo",
        citation="promptfoo, src/redteam/strategies",
        url="https://github.com/promptfoo/promptfoo",
        version=f"commit {_PROMPTFOO_COMMIT[:12]}",
        licence="MIT",
        issues=(1142, 40),
        evidence=Evidence.KNOWN_ANSWER,
        finding=(
            "On 0.18.0 the prompt-hygiene surface recovers 61 of 62 homoglyph rows and 43 of 43 "
            "Arabic rows. The one miss is `U+042F` for `R`, which TR39 has no row for, so under "
            "the guardrail from #39 and #40 it is a measurement and not a request for a row."
        ),
        notes=(
            "The maps are read with a regular expression and never run, and a row count other "
            "than 62 or 43 is an error, because a changed parser and a changed file look the "
            "same. The rest of promptfoo adds nothing this can score: its emoji encoding is in "
            "`token-smuggling-constructions`, its leetspeak, ROT13, hex, base64, Morse and Pig "
            "Latin have no Unicode signal, and its `asciiSmuggling` plugin is an LLM grader with "
            "no test cases in it."
        ),
    )
    SOURCES = tuple(
        Source(
            url=(
                f"https://raw.githubusercontent.com/promptfoo/promptfoo/{_PROMPTFOO_COMMIT}"
                f"/src/redteam/strategies/{stem}.ts"
            ),
            filename=f"practitioner-corpora/promptfoo/{stem}.ts",
            licence="MIT",
            sha256=digest,
        )
        for stem, digest in (
            ("homoglyph", "1597bbec12537840ad15c7588b127fdca97bf51e9764787154f1f5d845accb23"),
            (
                "arabicPresentationForms",
                "51674fcad910ad78d0720b8ddaa8c92d6cfc4a7f2bdccbc55365abb22c2ab70a",
            ),
        )
    )
    NEEDS_EVERY_SOURCE = True
    EXPECTED_ROWS: ClassVar[dict[str, int]] = {"homoglyph": 62, "arabic": 43}

    def read_maps(self) -> dict[str, list[tuple[str, str]]]:
        """Each map's `(letter, what replaces it)` rows, from the literal in the file."""
        homoglyph, arabic = (
            (FETCH_CACHE / source.filename).read_text(encoding="utf-8") for source in self.SOURCES
        )
        body = homoglyph[homoglyph.index("homoglyphMap") : homoglyph.index("export function")]
        maps = {"homoglyph": _HOMOGLYPH_ROW.findall(body), "arabic": _ARABIC_ROW.findall(arabic)}
        for name, rows in maps.items():
            if len(rows) != self.EXPECTED_ROWS[name]:
                raise ValueError(
                    f"{name} parsed to {len(rows)} rows where the pinned file holds "
                    f"{self.EXPECTED_ROWS[name]}"
                )
        return maps

    def scored(self, outcome: Outcome, limit: int | None) -> None:
        maps = self.read_maps()
        rows = [pair for pairs in maps.values() for pair in pairs]
        outcome.population = len(rows)
        record(
            outcome,
            domain=f"{len(rows)} literal map rows at the pinned commit",
            predicates=[self.JOB],
            commit=_PROMPTFOO_COMMIT,
            evidence="known answer: the letter each row replaces",
        )
        fn = self._sanitizer() or _identity
        missed: list[str] = []
        for name, pairs in maps.items():
            found = 0
            for letter, glyph in pairs:
                if damage.collides([fn], glyph, letter):
                    found += 1
                else:
                    missed.append(f"{letter} U+{ord(glyph):04X}")
            add(
                outcome,
                f"{name}_rows_recovered",
                found,
                of=len(pairs),
                higher_is_better=True,
            )
        for key, surface in (
            ("control_delete_everything", _delete_everything),
            ("control_identity", _identity),
        ):
            add(
                outcome,
                key,
                sum(damage.collides([surface], glyph, letter) for letter, glyph in rows),
                of=len(rows),
            )
        if outcome.method.subject == "disarm":
            outcome.extra = {"missed": missed}


_AUGUSTUS_COMMIT = "84487332f25a64b3797f03ae60e7701cc223b412"

_GO_STRING = r'"(?:[^"\\\n]|\\.)*"'
_GO_TERM = rf"(?:{_GO_STRING}|[A-Za-z_]\w*)"
_GO_EXPRESSION = rf"{_GO_TERM}(?:\s*\+\s*{_GO_TERM})*"
#: A string, a rune and a raw string are matched so that a `//` inside one is not a comment.
_GO_TOKEN = re.compile(rf"""{_GO_STRING}|'(?:[^'\\\n]|\\.)+'|`[^`]*`|//[^\n]*""")
_GO_PAIR = re.compile(
    rf"\b(?:input|text)\s*:\s*({_GO_EXPRESSION})\s*,\s*expected\s*:\s*({_GO_EXPRESSION})"
)
_GO_ASSIGNMENT = re.compile(rf"^\s*([A-Za-z_]\w*)\s*:=\s*({_GO_EXPRESSION})\s*$", re.MULTILINE)
_GO_ESCAPE = re.compile(
    r"\\U([0-9a-fA-F]{8})|\\u([0-9a-fA-F]{4})|\\x([0-9a-fA-F]{2})|\\(.)", re.DOTALL
)
_GO_SIMPLE_ESCAPES = {"n": "\n", "t": "\t", "r": "\r"}


def _go_string(literal: str) -> str:
    """A Go interpreted string literal's value."""

    def one(match: re.Match[str]) -> str:
        code_point, short, byte, simple = match.groups()
        if byte is not None:
            # Above ASCII it is a raw byte, and `range` over the string reads an invalid one so.
            return chr(int(byte, 16)) if int(byte, 16) <= 0x7F else "\N{REPLACEMENT CHARACTER}"
        if simple is not None:
            return _GO_SIMPLE_ESCAPES.get(simple, simple)
        return chr(int(code_point or short, 16))

    return _GO_ESCAPE.sub(one, literal[1:-1])


def _go_value(expression: str, constants: dict[str, str]) -> str:
    """A concatenation of literals and of names assigned earlier in the file."""
    parts = []
    for term in re.findall(_GO_TERM, expression):
        if term.startswith('"'):
            parts.append(_go_string(term))
        elif term in constants:
            parts.append(constants[term])
        else:
            raise ValueError(f"the Go constant {term} has no literal value in this file")
    return "".join(parts)


def read_go_pairs(source: str) -> list[tuple[str, str]]:
    """Each `input`/`expected` pair of a Go test table, read as data and never run.

    Comments go first, because upstream writes them between the two fields. A name resolves
    to a `name := ...` in the same file, and a name with no value there is an error, because
    dropping it would read as a shorter table.
    """
    code = _GO_TOKEN.sub(lambda m: "" if m.group().startswith("//") else m.group(), source)
    constants: dict[str, str] = {}
    for name, expression in _GO_ASSIGNMENT.findall(code):
        if all(
            term.startswith('"') or term in constants for term in re.findall(_GO_TERM, expression)
        ):
            constants[name] = _go_value(expression, constants)
    return [
        (_go_value(left, constants), _go_value(right, constants))
        for left, right in _GO_PAIR.findall(code)
    ]


class AugustusKnownAnswers(_KnownAnswerSuite):
    """A Go red-team tool's encoder tests: an input, and the exact string it must produce."""

    name = "augustus-known-answers"
    REQUIRES_ANY = (Capability.TRANSFORM, Capability.DETECT)
    summary = "Augustus' encoder test tables, each with the input its answer was encoded from."
    provenance = Provenance(
        origin="praetorian-inc/augustus",
        citation="Augustus, internal/encoding test tables",
        url="https://github.com/praetorian-inc/augustus",
        version=f"commit {_AUGUSTUS_COMMIT[:12]}",
        licence="Apache-2.0",
        issues=(1162, 1136, 1143),
        evidence=Evidence.KNOWN_ANSWER,
        finding=(
            "On 0.18.0 the prompt-hygiene surface removes all 8 carrier rows and recovers all 12 "
            "rebuilt zalgo rows, and none of the 5 leet rows. `decode_smuggled` reads the 4 tag "
            "rows and none of the 4 sneaky-bits rows, which is #1136. Of 76 boundary rows it "
            "recovers none, as expected."
        ),
        notes=(
            "The Go is read as data and never run, and a row count other than the pinned one is "
            "an error. 114 pairs are literal, and resolving comments, constants and concatenation "
            "reaches 121. `sneaky_bits` is the unpadded framing: each character's bits with no "
            "leading zeros and `U+200B` for a space, where PyRIT's is a fixed eight bits. "
            "`leet` ran with no lexicon on the sanitizer and detector rows, because `has_anomalies` "
            "names a leet word only from one. `leet_reported_given_its_word` passes the row's own "
            "input, which checks the mechanism and is not a rate. A digit-folding sanitizer would "
            "score on `leet_rows_recovered`, and its cost is in `benign-controls`. `zalgo` has no "
            "answers upstream, since the encoder draws from `math/rand`, so its rows are rebuilt "
            "from upstream's mark tables, limits and test inputs on a seeded stream. An `emoji` "
            "input holds a raw byte, read as `U+FFFD` as Go's `range` reads it. `charcode` is "
            "decimal code points and no table of this form, `splitpunct` is a helper and no "
            "encoder, and `internal/buffs/encoding` chooses among encoders and adds no answer."
        ),
    )
    TABLES: ClassVar[dict[str, str]] = {
        "atbash": "35482c6b54db0eeb56d2b420c64792cf609e62cfae988c0fb9e00aa3111c9608",
        "braille": "16f8b28fc965fbc5e98ee209d1f8e650031f3aa057dde963cc7f42732db1a920",
        "emoji": "91190bd54983ec2504e34e5ae3a5eeaa5af39e069f8403462b6debc627af4f2e",
        "leet": "e4d34d42378521eb8e9ca20dc0af92d33d37e9b6d426d7f5d7d45ca95ca71332",
        "morse": "166f8436bb1159b565e0a03a54bd983eb03217e94cb02e9688eaecef07f57fb6",
        "nato": "aa43356ec724d2bea646f04735ac145e2294fc57ef80c1d8c2dc9b78187c0500",
        "piglatin": "caf58001fa16b0ee669f13965ad0c9ae7b8b62c7d5c827a473077ec9927b3c4e",
        "rot13": "bceefffc8eba8f2593eef712442174e6f27ac5f525c85c0903f9a9cce05c2d06",
        "sneaky_bits": "6b247a1a29b76b3f45762591ac9841b86acf14fad0155d96e4338e41ee69a939",
        "unicode_tags": "2a4b78ff6da55bf72472d85367b46118132623232e62d752d72196bce1b4ccd1",
    }
    ZALGO_FILES: ClassVar[dict[str, str]] = {
        "zalgo_test.go": "750fd4e0fe513d48f454ad87dd7979af97d583a613b4d39c5bda51d44059a571",
        "zalgo.go": "4aa039f6e5d578d8f97cb3c954839af26947094717c945afd445121140fd5c6c",
    }
    SOURCES = tuple(
        Source(
            url=(
                "https://raw.githubusercontent.com/praetorian-inc/augustus/"
                f"{_AUGUSTUS_COMMIT}/internal/encoding/{stem}"
            ),
            filename=f"practitioner-corpora/augustus/{stem}",
            licence="Apache-2.0",
            sha256=digest,
        )
        for stem, digest in (
            *((f"{table}_test.go", digest) for table, digest in TABLES.items()),
            *ZALGO_FILES.items(),
        )
    )
    NEEDS_EVERY_SOURCE = True
    #: Fixed here before any score, and a carrier and a style are scored differently. A cipher,
    #: Braille and emoji substitution are boundary under `THREAT_MODEL.md`.
    CLASSES: ClassVar[dict[str, str]] = {
        "atbash": "boundary",
        "braille": "boundary",
        "emoji": "boundary",
        "morse": "boundary",
        "nato": "boundary",
        "piglatin": "boundary",
        "rot13": "boundary",
        "unicode_tags": "carrier",
        "sneaky_bits": "carrier",
        "zalgo": "style",
        "leet": "style",
    }
    EXPECTED_ROWS: ClassVar[dict[str, int]] = {
        "atbash": 7,
        "braille": 8,
        "emoji": 47,
        "leet": 6,
        "morse": 7,
        "nato": 7,
        "piglatin": 22,
        "rot13": 7,
        "sneaky_bits": 5,
        "unicode_tags": 5,
    }
    EXPECTED_MARKS: ClassVar[dict[str, int]] = {
        "combiningAbove": 21,
        "combiningBelow": 30,
        "combiningMiddle": 12,
    }
    COVER = "the quick brown fox jumps over the lazy dog"
    SEED = 20261031
    ZALGO_DRAWS = 4

    def _read(self, stem: str) -> str:
        return (FETCH_CACHE / f"practitioner-corpora/augustus/{stem}").read_text(encoding="utf-8")

    def read_tables(self) -> dict[str, list[tuple[str, str]]]:
        """Each table's `(input, answer)` rows, from its test file."""
        tables = {t: read_go_pairs(self._read(f"{t}_test.go")) for t in self.EXPECTED_ROWS}
        for table, rows in tables.items():
            if len(rows) != self.EXPECTED_ROWS[table]:
                raise ValueError(
                    f"{table} parsed to {len(rows)} rows where the pinned file holds "
                    f"{self.EXPECTED_ROWS[table]}"
                )
        return tables

    def rebuild_zalgo(self) -> list[tuple[str, str]]:
        """`(input, answer)` rows, from upstream's mark tables, its limits and its test inputs.

        The encoder draws from `math/rand`, so its test states properties and holds no answer.
        The distribution here is upstream's and the stream is ours, seeded, because a known
        answer needs only the input. Upstream's `char <= ' '` rule keeps spaces unmarked.
        """
        code = self._read("zalgo.go")
        marks: dict[str, list[str]] = {}
        for name, count in self.EXPECTED_MARKS.items():
            body = re.search(rf"{name}\s*=\s*\[\]rune\{{([^}}]*)\}}", code)
            marks[name] = [
                chr(int(digits, 16))
                for digits in re.findall(r"'\\u([0-9a-fA-F]{4})'", body.group(1) if body else "")
            ]
            if len(marks[name]) != count:
                raise ValueError(f"{name} parsed to {len(marks[name])} marks, not {count}")
        limit = re.search(r"zalgoWithIntensity\(s, (\d+)\)", code)
        if limit is None:
            raise ValueError("zalgo.go states no intensity")
        intensity = int(limit.group(1))
        test = self._read("zalgo_test.go")
        inputs = [
            *re.findall(r'\binput\s*:\s*"([^"\\]+)"', test),
            *re.findall(r'\bZalgo\("([^"\\]+)"\)', test),
        ]
        rows = []
        for clean in inputs:
            for draw in range(self.ZALGO_DRAWS):
                rng = random.Random(f"{self.SEED}:{clean}:{draw}")  # noqa: S311 - a fixture
                out = []
                for ch in clean:
                    out.append(ch)
                    if ch <= " ":
                        continue
                    out += rng.choices(marks["combiningAbove"], k=rng.randint(0, intensity))
                    out += rng.choices(marks["combiningBelow"], k=rng.randint(0, intensity))
                    if rng.random() < 0.3:
                        k = rng.randint(0, intensity // 2)
                        out += rng.choices(marks["combiningMiddle"], k=k)
                rows.append((clean, "".join(out)))
        return rows

    def carrier_rows(
        self, tables: dict[str, list[tuple[str, str]]]
    ) -> dict[str, list[tuple[str, str, str]]]:
        """`(text, what it must come back to, the hidden input)` per carrier table.

        A carrier has no answer to return to on its own, so each row is appended to a cover.
        Upstream's own empty row says what the encoder keeps with nothing to hide: an emoji
        for `unicode_tags`, and nothing for `sneaky_bits`.
        """
        carriers = {}
        for table, kind in self.CLASSES.items():
            if kind != "carrier":
                continue
            kept = dict(tables[table]).get("", "")
            carriers[table] = [
                (self.COVER + answer, self.COVER + kept, clean)
                for clean, answer in tables[table]
                if clean
            ]
        return carriers

    def scored(self, outcome: Outcome, limit: int | None) -> None:
        tables = self.read_tables()
        zalgo = self.rebuild_zalgo()
        read = sum(map(len, tables.values()))
        carriers = self.carrier_rows(tables)
        pairs: dict[str, list[tuple[str, str]]] = {"zalgo": zalgo}
        boundary: dict[str, list[tuple[str, str]]] = {}
        held_out = 0
        for table, rows in tables.items():
            kind = self.CLASSES[table]
            if kind == "carrier":
                held_out += sum(not clean for clean, _ in rows)
                continue
            changed = [(clean, answer) for clean, answer in rows if clean != answer]
            held_out += len(rows) - len(changed)
            (boundary if kind == "boundary" else pairs)[table] = changed
        outcome.population = read + len(zalgo)
        record(
            outcome,
            domain=f"{read} table rows and {len(zalgo)} rebuilt zalgo rows at the pinned commit",
            predicates=[self.JOB],
            commit=_AUGUSTUS_COMMIT,
            evidence="known answer: the input upstream's test encodes",
            sneaky_bits_framing=(
                "unpadded: each character's bits with no leading zeros and U+200B for a space"
            ),
            leet_lexicon="none on the sanitizer and detector rows",
            zalgo=f"rebuilt, seed {self.SEED}, {self.ZALGO_DRAWS} draws per input",
            cover=self.COVER,
        )
        add(outcome, "pairs_read", read, unit="pairs")
        add(
            outcome,
            "pairs_held_out_unchanged",
            held_out,
            unit="pairs",
            detail="a row that changes nothing, or a carrier row with nothing to hide",
        )
        directed = [
            *((text, answer) for rows in carriers.values() for text, answer, _ in rows),
            *((answer, clean) for rows in pairs.values() for clean, answer in rows),
        ]
        for key, control in (
            ("control_delete_everything", _delete_everything),
            ("control_identity", _identity),
        ):
            add(
                outcome,
                key,
                sum(damage.collides([control], text, answer) for text, answer in directed),
                of=len(directed),
                detail="must be zero, or the metric below has a degenerate solution",
            )
        self._recovered(outcome, carriers, pairs, boundary)
        self._reported(outcome, carriers, pairs)
        if outcome.method.subject == "disarm":
            self._disarm_alone(outcome, carriers, tables["leet"])

    def _recovered(
        self,
        outcome: Outcome,
        carriers: dict[str, list[tuple[str, str, str]]],
        pairs: dict[str, list[tuple[str, str]]],
        boundary: dict[str, list[tuple[str, str]]],
    ) -> None:
        fn = self._sanitizer()
        if fn is None:
            return
        for table, rows in carriers.items():
            add(
                outcome,
                f"{table}_rows_removed",
                sum(damage.collides([fn], text, answer) for text, answer, _ in rows),
                of=len(rows),
                higher_is_better=True,
                detail="the cover plus the encoded input lands on the cover",
            )
        for table, rows in pairs.items():
            add(
                outcome,
                f"{table}_rows_recovered",
                sum(damage.collides([fn], answer, clean) for clean, answer in rows),
                of=len(rows),
                higher_is_better=True,
                detail="the encoded input lands on the input",
            )
        by_table = {
            table: [sum(damage.collides([fn], answer, clean) for clean, answer in rows), len(rows)]
            for table, rows in boundary.items()
            if rows
        }
        add(
            outcome,
            "boundary_rows_recovered",
            sum(found for found, _ in by_table.values()),
            of=sum(total for _, total in by_table.values()),
            detail="ciphers and substitution alphabets: a census, and low is expected",
        )
        outcome.extra = {"boundary_rows_recovered_by_table": by_table}

    def _reported(
        self,
        outcome: Outcome,
        carriers: dict[str, list[tuple[str, str, str]]],
        pairs: dict[str, list[tuple[str, str]]],
    ) -> None:
        texts = {
            **{table: [text for text, _, _ in rows] for table, rows in carriers.items()},
            **{table: [answer for _, answer in rows] for table, rows in pairs.items()},
        }
        for name, detector in self.detect().items():
            add(outcome, f"cover_reported:{name}", int(_fires(detector, self.COVER)), of=1)
            for table, rows in texts.items():
                add(
                    outcome,
                    f"{table}_rows_reported:{name}",
                    sum(_fires(detector, text) for text in rows),
                    of=len(rows),
                )

    @staticmethod
    def _disarm_alone(
        outcome: Outcome,
        carriers: dict[str, list[tuple[str, str, str]]],
        leet: list[tuple[str, str]],
    ) -> None:
        import disarm

        for table, rows in carriers.items():
            add(
                outcome,
                f"{table}_rows_decoded",
                sum(
                    any(found.text == clean for found in disarm.decode_smuggled(text))
                    for text, _, clean in rows
                ),
                of=len(rows),
            )
        words = [(clean, answer) for clean, answer in leet if clean != answer]
        add(
            outcome,
            "leet_reported_given_its_word",
            sum(disarm.has_anomalies(answer, lexicon=[clean]) for clean, answer in words),
            of=len(words),
            detail="the row's own input as the lexicon, so a mechanism check and not a rate",
        )


class PalisadeLabels(_KnownAnswerSuite):
    """A labelled set whose Unicode attacks are few, and whose other attacks are not ours."""

    name = "palisade-labels"
    REQUIRES_ANY = (Capability.DETECT,)
    summary = "palisade's three Unicode attacks, its ASCII attacks kept out of any rate."
    provenance = Provenance(
        origin="RootVandal/palisade",
        citation="palisade, data/benchmark.jsonl",
        url="https://github.com/RootVandal/palisade",
        version=f"commit {_PALISADE_COMMIT[:12]}",
        licence="MIT",
        issues=(1166, 1154),
        evidence=Evidence.KNOWN_ANSWER,
        finding=(
            "`has_anomalies` reports all 3 Unicode rows, none of the 29 ASCII attacks and none of "
            "the 24 benign rows. The ASCII figure is the boundary and not a miss."
        ),
        notes=(
            "Three of the 32 attack rows carry Unicode and those are the score. The other 29 are "
            "ASCII and semantic, which `THREAT_MODEL.md` puts out of scope, so they are a census "
            "and in no rate. The 24 benign rows are read beside the score, because a detector "
            "that always fires would otherwise take it, and `benign-controls` owns their rate."
        ),
    )
    SOURCES = (_PROMPTS["palisade:benchmark"].source,)
    UNICODE_TAGS: ClassVar[frozenset[str]] = frozenset(
        {"obf-homoglyph", "obf-unicode-tags", "obf-zerowidth"}
    )
    EXPECTED_ROWS: ClassVar[dict[str, int]] = {"attack": 32, "benign": 24}

    def read_rows(self) -> dict[str, list[str]]:
        """Each class's texts. A row whose tag and bytes disagree is an error, not a guess."""
        path = FETCH_CACHE / self.SOURCES[0].filename
        rows = [json.loads(line) for line in _nonblank_lines(path)]
        for label, expected in self.EXPECTED_ROWS.items():
            found = sum(row["label"] == label for row in rows)
            if found != expected:
                raise ValueError(f"{label} parsed to {found} rows, where the file holds {expected}")
        classes: dict[str, list[str]] = {"unicode": [], "ascii": [], "benign": []}
        for row in rows:
            if row["label"] == "benign":
                classes["benign"].append(row["text"])
            elif (row["tag"] in self.UNICODE_TAGS) == row["text"].isascii():
                raise ValueError(f"the {row['tag']} row disagrees with the class its tag gives it")
            else:
                classes["unicode" if row["tag"] in self.UNICODE_TAGS else "ascii"].append(
                    row["text"]
                )
        return classes

    def scored(self, outcome: Outcome, limit: int | None) -> None:
        classes = self.read_rows()
        unicode_rows, ascii_rows, benign = classes["unicode"], classes["ascii"], classes["benign"]
        outcome.population = sum(map(len, classes.values()))
        record(
            outcome,
            domain=f"{outcome.population} labelled rows at the pinned commit",
            predicates=[self.JOB],
            commit=_PALISADE_COMMIT,
            evidence="known answer: upstream's label and tag",
        )
        for key, surface, texts in (
            ("control_delete_everything", _delete_everything, unicode_rows),
            ("control_identity", _identity, []),
        ):
            add(outcome, key, sum(bool(surface(text)) for text in texts), of=len(unicode_rows))
        add(outcome, "control_fires_on_everything_unicode", len(unicode_rows), of=len(unicode_rows))
        add(outcome, "control_fires_on_everything_benign", len(benign), of=len(benign))
        for name, detector in sorted(self.detect().items()):
            add(
                outcome,
                f"unicode_rows_reported:{name}",
                sum(_fires(detector, text) for text in unicode_rows),
                of=len(unicode_rows),
                higher_is_better=True,
            )
            add(
                outcome,
                f"ascii_attack_rows_reported:{name}",
                sum(_fires(detector, text) for text in ascii_rows),
                of=len(ascii_rows),
                detail="boundary: semantic, and in no rate",
            )
            add(
                outcome,
                f"benign_rows_reported:{name}",
                sum(_fires(detector, text) for text in benign),
                of=len(benign),
                detail="read beside the score, and `benign-controls` owns the rate",
            )


class SpikeeSeedCensus(_FixtureSuite):
    """Seven seed sets from a prompt-injection tool: counted per file, and never printed."""

    name = "spikee-seed-census"
    REQUIRES_ANY = (Capability.TRANSFORM, Capability.DETECT)
    summary = "spikee's seven populated seed sets, 640 rows: counts per file, never a score."
    provenance = Provenance(
        origin="ReversecLabs/spikee",
        citation="spikee, spikee/data/workspace/datasets",
        url="https://github.com/ReversecLabs/spikee",
        version=f"commit {_SPIKEE_COMMIT[:12]}",
        licence="Apache-2.0",
        issues=(1166, 875),
        evidence=Evidence.FIXTURE,
        finding=(
            "158 of the 640 rows hold non-ASCII. `has_anomalies` fires on 8 of them on 0.18.0 and "
            "on none once #1153 and #1155 are in, which is what those two fixes were for."
        ),
        notes=(
            "`results/v0.1` holds 98 files, 52 of them recorded runs from December 2024: 14 on six "
            "guardrails and 38 on model endpoints. These are not comparable, so no number of "
            "theirs is reported here. The guardrail files keep each input and a `success` flag "
            "that says a guardrail let a semantic injection through. `plugin` is empty on all "
            "1,876 of those rows and `has_anomalies` fires on none, so the question is a different "
            "one, on a different target, under a different judge. The model files judge a "
            "response, which disarm does not have. Their seed set, `targeted-2024-12`, is not in "
            "this commit either. spikee's `ascii_smuggler` and `homoglyph` plugins were read and "
            "not run. The first wraps its tags in `U+E0001` and `U+E007F`, which the battery "
            "lacked and `token-smuggling-constructions` now holds. The second holds 30 rows, 27 "
            "of them in promptfoo's map, and the prompt-hygiene surface recovers all 30, so it "
            "earns no suite. One set here, `seeds-investment-advice-fp`, is also in "
            "`benign-controls`, which owns it as a false-positive set."
        ),
    )
    FILES: ClassVar[dict[str, str]] = {
        "seeds-cybersec-2026-01/base_user_inputs.jsonl": (
            "235d32e765e5f4ca4a8f3e37ab532b4cabe9edce8bc5eb65b15200c3d04b6b99"
        ),
        "seeds-cybersec-2026-01/instructions.jsonl": (
            "f185065b578be3053a7334364acaacef84d9b7b6b6e0522be68cda72129c9364"
        ),
        "seeds-cybersec-2026-01/jailbreaks.jsonl": (
            "6d093aa78a65aecd688849cd185f1cfce865c9649e2fe8c87732417dc7b8e8cb"
        ),
        "seeds-cybersec-2026-01/standalone_user_inputs.jsonl": (
            "a4ce8335fde7fc50c4ca423418a7d6250b470dc325eb849aff8737c7253aedd0"
        ),
        "seeds-harmful-instructions-only/base_user_inputs.jsonl": (
            "96cf7ff047e0701578948bd74dc89db4e769f748619bb9bbf05c355d0b89ab0b"
        ),
        "seeds-harmful-instructions-only/instructions.jsonl": (
            "ae7a4bbd136ee1131034fc69de1883b35379af3533d35d6c4b4849e3c9936793"
        ),
        "seeds-harmful-instructions-only/jailbreaks.jsonl": (
            "5485e12b934f4469cc95b90742ad6b91376f02fc434962c3c6f58f423e960711"
        ),
        "seeds-investment-advice/base_user_inputs.jsonl": (
            "0b31d82e79dc3fc2a2979ce1296b3872b775fa0f8dddaf5d71fb46f704e5a7a8"
        ),
        "seeds-investment-advice/instructions.jsonl": (
            "6918f008709facdb3a818e26563dd135a1401d9aeae0f6b9172cbc913f21f2ae"
        ),
        "seeds-investment-advice/jailbreaks.jsonl": (
            "32c123d7cace45d4b06e76e36d1125b34f6a71a07a9eb9463c62550be65f0f44"
        ),
        "seeds-investment-advice/standalone_user_inputs.jsonl": (
            "6b7be5354199c4be6885e9180100852deac1ceed69dbe11a2d5ce1c771c22556"
        ),
        "seeds-investment-advice-fp/standalone_user_inputs.jsonl": (
            "ae518e6861365a04f043fa2df0edb1901a38129c2c05d03ff73f9552c6092e2b"
        ),
        "seeds-llm-mailbox/base_user_inputs.jsonl": (
            "fe7955027d2b3636307292b85c96115ae9c6a0d85a6a43d6ca6532c25ed9a104"
        ),
        "seeds-llm-mailbox/instructions.jsonl": (
            "c6579819dfd31842e4272df9657ddbc0c5240d530e05bb90591668223c6fb023"
        ),
        "seeds-llm-mailbox/jailbreaks.jsonl": (
            "aae08f0706b3eb0781dac179fde6b4de40eb192807a63f435d4390e07b916d83"
        ),
        "seeds-mini-test/base_user_inputs.jsonl": (
            "c623b07aeb1cdb53729ba1555850f0957c3fa31f531f621322e5b91e171bfb8c"
        ),
        "seeds-mini-test/instructions.jsonl": (
            "5181d0feb2ebef98940ea5065c63802dfc1525cedaad1c50a626115b43a054d3"
        ),
        "seeds-mini-test/jailbreaks.jsonl": (
            "47f439d44fac6b16134a622d322a868f4a1754f26c645f6935d614d596dab5d3"
        ),
        "seeds-mini-test/standalone_user_inputs.jsonl": (
            "663b34d5b603d37b6290934a5918342392cfa53f4202b3683f83cc07face4dbd"
        ),
        "seeds-sysmsg-extraction-2025-04/base_user_inputs.jsonl": (
            "235d32e765e5f4ca4a8f3e37ab532b4cabe9edce8bc5eb65b15200c3d04b6b99"
        ),
        "seeds-sysmsg-extraction-2025-04/instructions.jsonl": (
            "a8fff3ba9b28c3513c2b04e9a84d918a4475771c35ee55f34cb28a676e78f83a"
        ),
        "seeds-sysmsg-extraction-2025-04/jailbreaks.jsonl": (
            "cb2e5aa206eb5e8fbe60a3ac0ced859860420aca6ebb3acd5897bc561873d07a"
        ),
    }
    SOURCES = tuple(
        Source(
            url=(
                f"https://raw.githubusercontent.com/ReversecLabs/spikee/{_SPIKEE_COMMIT}"
                f"/spikee/data/workspace/datasets/{relative}"
            ),
            filename=f"practitioner-corpora/spikee/{relative}",
            licence="Apache-2.0",
            sha256=digest,
        )
        for relative, digest in FILES.items()
    )
    NEEDS_EVERY_SOURCE = True
    EXPECTED_ROWS: ClassVar[dict[str, int]] = {
        "seeds-cybersec-2026-01": 94,
        "seeds-harmful-instructions-only": 45,
        "seeds-investment-advice": 194,
        "seeds-investment-advice-fp": 112,
        "seeds-llm-mailbox": 67,
        "seeds-mini-test": 10,
        "seeds-sysmsg-extraction-2025-04": 118,
    }
    TEXT_FIELDS = ("text", "instruction", "jailbreak", "document")

    def read_files(self) -> dict[str, list[str]]:
        """Each pinned file's texts, from whichever field that file holds them in."""
        files: dict[str, list[str]] = {}
        for relative in self.FILES:
            path = FETCH_CACHE / f"practitioner-corpora/spikee/{relative}"
            texts = []
            for line in _nonblank_lines(path):
                row = json.loads(line)
                value = next((row[f] for f in self.TEXT_FIELDS if row.get(f)), "")
                if value and isinstance(value, str):
                    texts.append(value)
            files[relative] = texts
        for seed, expected in self.EXPECTED_ROWS.items():
            found = sum(len(v) for k, v in files.items() if k.startswith(f"{seed}/"))
            if found != expected:
                raise ValueError(f"{seed} parsed to {found} rows where it holds {expected}")
        return files

    def census(self, outcome: Outcome, limit: int | None) -> None:
        files = self.read_files()
        rows = [text for texts in files.values() for text in texts]
        outcome.population = len(rows)
        record(
            outcome,
            domain=f"{len(rows)} rows in {len(self.EXPECTED_ROWS)} seed sets at the pinned commit",
            predicates=[self.JOB],
            commit=_SPIKEE_COMMIT,
            evidence="a census: seeds carry no label a score could use, and none is printed",
        )
        add(outcome, "rows_read", len(rows), unit="rows")
        by_seed: dict[str, list[str]] = {}
        for relative, texts in files.items():
            add(outcome, f"rows:{relative}", len(texts), unit="rows")
            add(
                outcome, f"non_ascii:{relative}", sum(not t.isascii() for t in texts), of=len(texts)
            )
            by_seed.setdefault(relative.partition("/")[0], []).extend(texts)
        for key, surface in (
            ("control_delete_everything_rewritten", _delete_everything),
            ("control_identity_rewritten", _identity),
        ):
            add(outcome, key, sum(surface(text) != text for text in rows), of=len(rows))
        fn = self._sanitizer()
        for seed, texts in by_seed.items():
            for name, detector in sorted(self.detect().items()):
                add(
                    outcome,
                    f"fired:{seed}:{name}",
                    sum(_fires(detector, text) for text in texts),
                    of=len(texts),
                )
            if fn is not None:
                add(
                    outcome,
                    f"rewritten:{seed}",
                    sum(damage.apply(fn, text) != text for text in texts),
                    of=len(texts),
                )


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
    PromptfooLiteralMaps(),
    AugustusKnownAnswers(),
    PalisadeLabels(),
    SpikeeSeedCensus(),
]
