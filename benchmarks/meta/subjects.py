"""The tools under test.

A benchmark that only ever scores one library tells you what that library does.
It does not tell you whether the number is good. The same corpus run through
several tools turns an absolute figure into a comparison, and a comparison is
the only form in which "65.9% folded" means anything.

Subjects are drawn from ``requirements/bench.txt`` — the repo's existing
hash-locked comparator environment — so the roster is versioned by a contract
that already exists rather than one invented here. Install it with::

    pip install --require-hashes -r requirements/bench.txt

A subject that is not installed reports unavailable and its column is absent
from the report. It is never silently treated as scoring zero.

**Capabilities.** Tools do different jobs. `unidecode` transliterates and detects
nothing; `ftfy` repairs mojibake; only disarm carries detectors and key builders.
A suite declares what it needs, the runner pairs it only with subjects that
provide it, and every unmatched pair is reported as a skip with the reason.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import ClassVar, Protocol, runtime_checkable


class Role:
    """The job a declared surface does.

    A benchmark should score a *configuration* somebody could deploy, not a
    library's best surface out of however many it ships. Scoring best-of-N asks
    "what is the most this library could do for me", which assumes a reader who
    already knows which of thirteen entry points to reach for — the very problem
    the library exists to solve.
    """

    SANITIZER = "sanitizer"  # the general-purpose text-cleaning entry point
    KEY = "key"  # the comparison-key builder
    DETECTOR = "detector"  # the report-without-rewriting predicate


class Capability:
    """What a subject can be asked to do."""

    TRANSFORM = "transform"  # text -> text, some normalizing or folding surface
    DETECT = "detect"  # text -> bool, reports without rewriting
    KEY = "key"  # text -> comparison key, collisions are meaningful


@dataclass(frozen=True)
class SubjectInfo:
    name: str
    version: str
    origin: str
    url: str
    role: str  # one line: what the tool is actually for


@runtime_checkable
class Subject(Protocol):
    info: SubjectInfo
    #: One declared surface per role, so a score describes a configuration
    #: somebody could deploy rather than a library's best of however many.
    ROLES: ClassVar[dict[str, str]]

    def available(self) -> tuple[bool, str]: ...
    def capabilities(self) -> set[str]: ...
    def transforms(self) -> dict[str, Callable[[str], str]]: ...
    def detectors(self) -> dict[str, Callable[[str], bool]]: ...
    def keys(self) -> dict[str, Callable[[str], str]]: ...
    def role(self, which: str) -> dict[str, Callable[[str], str]]: ...


@dataclass
class _Base:
    """Default: nothing is provided until a subclass says otherwise."""

    #: True for the two degenerate controls. Deliberately a class attribute and
    #: not a dataclass field: a field default would silently win over a
    #: subclass's override and quietly demote both controls to tools.
    control: ClassVar[bool] = False

    _cache: dict[str, object] = field(default_factory=dict, repr=False)

    def capabilities(self) -> set[str]:
        caps = set()
        if self.transforms():
            caps.add(Capability.TRANSFORM)
        if self.detectors():
            caps.add(Capability.DETECT)
        if self.keys():
            caps.add(Capability.KEY)
        return caps

    #: The one surface per role this subject is scored on, by name. Declared
    #: before any run, so the choice is visible and arguable rather than being
    #: whichever surface happened to win.
    ROLES: ClassVar[dict[str, str]] = {}

    def transforms(self) -> dict[str, Callable[[str], str]]:
        return {}

    def detectors(self) -> dict[str, Callable[[str], bool]]:
        return {}

    def keys(self) -> dict[str, Callable[[str], str]]:
        return {}

    def role(self, which: str) -> dict[str, Callable[[str], str]]:
        """The declared surface for ``which``, as a one-entry mapping.

        Empty when the subject declares no surface for that role — which is a
        real answer (`unidecode` builds no keys) and must not be read as zero.
        Falls back to the whole set only when nothing is declared at all, so a
        subject that has not been given roles still measures something.
        """
        name = self.ROLES.get(which)
        pool = self.keys() if which == Role.KEY else self.transforms()
        if name is None:
            return {} if self.ROLES else pool
        fn = pool.get(name) or self.transforms().get(name)
        return {name: fn} if fn is not None else {}

    def available(self) -> tuple[bool, str]:
        return True, ""


def _import(module: str) -> object | None:
    try:
        return __import__(module)
    except ImportError:
        return None


def _version(dist: str) -> str:
    import importlib.metadata as md

    try:
        return md.version(dist)
    except Exception:  # noqa: BLE001
        return "?"


def _git_describe(repo: object) -> str:
    """``+g<sha>`` for a build made from a working checkout, else empty.

    ``disarm.__version__`` only moves at release, so every build between two
    releases reports the older number. Nine commits of behaviour change can sit
    behind one version string — and a leaderboard row reading `disarm@0.14.1`
    while the extension carries post-0.14.1 code is exactly the mislabelling the
    versioned-identity rule exists to prevent. A dirty tree is marked too,
    because an uncommitted change is not any commit.
    """
    import subprocess

    root = pathlib.Path(str(repo)).resolve().parent
    try:
        sha = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""
    if not sha:
        return ""
    return f"+g{sha}" + (".dirty" if dirty else "")


class DisarmSubject(_Base):
    """The library under review: every preset, profile, detector and key builder."""

    def __init__(self) -> None:
        super().__init__()
        import disarm

        released = getattr(disarm, "__version__", "?")
        self.info = SubjectInfo(
            name="disarm",
            version=released + _git_describe(getattr(disarm, "__file__", "")),
            origin="raeq/disarm",
            url="https://github.com/raeq/disarm",
            role="Unicode security normalization, detection and key building",
        )

    #: `canonicalize` is the documented general-purpose comparison form — the
    #: entry point a reader arrives at. Not `llm_guardrail`, which wins the
    #: coverage axis on best-of-N and is a ten-step application pipeline nobody
    #: reaches for to clean a username.
    ROLES: ClassVar[dict[str, str]] = {
        Role.SANITIZER: "canonicalize",
        Role.KEY: "search_key",
        Role.DETECTOR: "is_confusable",
    }

    def available(self) -> tuple[bool, str]:
        return (True, "") if _import("disarm") else (False, "disarm is not importable")

    def transforms(self) -> dict[str, Callable[[str], str]]:
        import disarm

        # Same defensiveness: a preset named in PRESETS but absent from the
        # module, or a profile the build does not ship, is skipped rather than
        # raising — the harness must survive the version it is pointed at.
        out: dict[str, Callable[[str], str]] = {}
        for name in sorted(getattr(disarm, "PRESETS", ())):
            fn = getattr(disarm, name, None)
            if callable(fn):
                out[name] = fn
        list_profiles: Callable[[], list[str]] = getattr(disarm, "list_profiles", list)
        for profile in list_profiles():
            try:
                out[f"profile:{profile}"] = disarm.get_pipeline(profile)
            except Exception:  # noqa: BLE001 - an unavailable profile is absent
                continue
        return out

    def detectors(self) -> dict[str, Callable[[str], bool]]:
        """Every detector the *installed* build actually has.

        Resolved by name rather than hardcoded, because the harness has to run
        against builds older than itself: `has_bidi_control` arrived during the
        0.15.0 cycle, and referencing it directly made every suite error out on
        0.14.1 — which defeats the cross-version comparison the versioned
        identity exists for. A surface the build lacks is absent, not zero.
        """
        import disarm

        def truthy(fn: Callable[[str], object]) -> Callable[[str], bool]:
            """`is_confusable` returns a match list; every other one returns bool."""
            return lambda s: bool(fn(s))

        out: dict[str, Callable[[str], bool]] = {}
        for name in (
            "has_anomalies",
            "is_confusable",
            "is_mixed_script",
            "is_zalgo",
            "has_bidi_conflict",
            "has_bidi_control",
        ):
            fn = getattr(disarm, name, None)
            if callable(fn):
                out[name] = truthy(fn)
        return out

    #: Profiles whose contract is to build a comparison key, not to return
    #: readable text. They collapse by design exactly as the three key functions
    #: do, and scoring them as text surfaces charged the library for having them:
    #: `library_catalog_key_eu` was the single worst "text" surface in the
    #: corruption census, which is what a catalog key is supposed to look like.
    KEY_PROFILES = (
        "library_catalog_key_eu",
        "search_index",
        "scholarly_cyrillic_iso9",
    )

    def keys(self) -> dict[str, Callable[[str], str]]:
        import disarm

        out: dict[str, Callable[[str], str]] = {}
        for name in ("search_key", "catalog_key", "sort_key"):
            fn = getattr(disarm, name, None)
            if callable(fn):
                out[name] = fn
        profiles: Callable[[], list[str]] = getattr(disarm, "list_profiles", list)
        available = set(profiles())
        for profile in self.KEY_PROFILES:
            if profile in available:
                out[f"profile:{profile}"] = disarm.get_pipeline(profile)
        return out


class DisarmComposedSubject(_Base):
    """A pipeline compiled for a purpose, rather than a profile picked off the shelf.

    Composition is disarm's answer to "no shipped profile covers my policy", and
    scoring only presets and profiles leaves the whole capability unmeasured.
    It is entered here as a *separate subject* rather than as another disarm
    surface, on the precedent that two versions of one tool may both compete: a
    composed pipeline is a different deployable artifact with different
    properties, not a better view of the same one.

    **The steps are declared once, here, and never varied per benchmark.** That
    is the whole discipline — a composition chosen per suite would be best-of-N
    with extra steps, which is what `ROLES` exists to prevent. The declaration is
    hashed into the version string, so changing a single flag changes the subject
    key and cannot be mistaken for the same configuration measured twice.

    The composition is not invented here either: it is exactly the change #910
    proposes for `llm_guardrail` — the profile with `demojize` off — so what this
    subject scores is a proposal that is already on the table.

    It is knowingly *not* equivalent to `llm_guardrail`. Per #911, `strip_pua` is
    the one `ProfileSpec` field `TextPipeline` cannot express, so this pipeline
    strips none of the 137,468 Private Use Area code points the profile strips.
    That gap is a true property of the composed API and is left in rather than
    papered over — a subject that quietly matched the profile would be measuring
    a pipeline no caller can actually build.
    """

    #: The declared composition. Frozen: see the class docstring.
    STEPS: ClassVar[dict[str, object]] = {
        "normalize": "NFKC",
        "strip_zalgo": 0,
        "strip_bidi": True,
        "strip_zero_width": True,
        "strip_control": True,
        "confusables": True,
        "strip_accents": True,
        "fold_case": True,
        "collapse_whitespace": True,
        "demojize": False,
    }

    ROLES: ClassVar[dict[str, str]] = {Role.SANITIZER: "composed"}

    def __init__(self) -> None:
        super().__init__()
        import disarm

        released = getattr(disarm, "__version__", "?")
        # The digest makes the configuration part of the identity. Two runs whose
        # step lists differ can never collide on one subject key, which is the
        # same rule the perf harness applies to its corpus.
        digest = hashlib.sha256(json.dumps(self.STEPS, sort_keys=True).encode("utf-8")).hexdigest()[
            :8
        ]
        self.info = SubjectInfo(
            name="disarm-composed",
            version=f"{released}{_git_describe(getattr(disarm, '__file__', ''))}+composed.{digest}",
            origin="raeq/disarm",
            url="https://github.com/raeq/disarm",
            role="a TextPipeline compiled from declared steps: "
            + ", ".join(f"{k}={v!r}" for k, v in sorted(self.STEPS.items())),
        )

    def available(self) -> tuple[bool, str]:
        if not _import("disarm"):
            return (False, "disarm is not importable")
        import disarm

        if not hasattr(disarm, "TextPipeline"):
            return (False, "this build has no TextPipeline")
        try:
            disarm.TextPipeline(**self.STEPS)  # type: ignore[arg-type]
        except TypeError as exc:
            # A build that does not accept a declared step must not be scored on
            # a silently different pipeline.
            return (False, f"TextPipeline rejects a declared step: {exc}")
        return (True, "")

    def transforms(self) -> dict[str, Callable[[str], str]]:
        import disarm

        return {"composed": disarm.TextPipeline(**self.STEPS)}  # type: ignore[arg-type]


class StdlibSubject(_Base):
    """CPython's own normalization — the floor every other tool must beat.

    Not a rival library. It is here because a fold that no tool beats is a
    property of Unicode, and one that only disarm reaches is a property of
    disarm; without this column the two look identical.
    """

    info = SubjectInfo(
        name="stdlib",
        version=unicodedata.unidata_version,
        origin="CPython",
        url="https://docs.python.org/3/library/unicodedata.html",
        role="NFC/NFD/NFKC/NFKD and str.casefold",
    )
    ROLES: ClassVar[dict[str, str]] = {Role.SANITIZER: "NFKC"}

    def transforms(self) -> dict[str, Callable[[str], str]]:
        return {
            "NFC": lambda s: unicodedata.normalize("NFC", s),
            "NFD": lambda s: unicodedata.normalize("NFD", s),
            "NFKC": lambda s: unicodedata.normalize("NFKC", s),
            "NFKD": lambda s: unicodedata.normalize("NFKD", s),
            "NFKC_casefold": lambda s: unicodedata.normalize("NFKC", s).casefold(),
        }


class FtfySubject(_Base):
    """Mojibake repair. Normalizes as a side effect, and is not a security tool."""

    info = SubjectInfo(
        name="ftfy",
        version=_version("ftfy"),
        origin="Robyn Speer",
        url="https://github.com/rspeer/python-ftfy",
        role="repairs text that was decoded with the wrong codec",
    )
    ROLES: ClassVar[dict[str, str]] = {Role.SANITIZER: "fix_text"}

    def available(self) -> tuple[bool, str]:
        return (True, "") if _import("ftfy") else (False, "pip install ftfy")

    def transforms(self) -> dict[str, Callable[[str], str]]:
        import ftfy

        return {
            "fix_text": ftfy.fix_text,
            "fix_text_NFKC": lambda s: ftfy.fix_text(s, normalization="NFKC"),
        }


class UnidecodeSubject(_Base):
    """ASCII transliteration. The comparator the adversarial literature uses."""

    info = SubjectInfo(
        name="unidecode",
        version=_version("Unidecode"),
        origin="Tomaz Solc",
        url="https://pypi.org/project/Unidecode/",
        role="lossy ASCII transliteration",
    )
    ROLES: ClassVar[dict[str, str]] = {Role.SANITIZER: "unidecode"}

    def available(self) -> tuple[bool, str]:
        return (True, "") if _import("unidecode") else (False, "pip install Unidecode")

    def transforms(self) -> dict[str, Callable[[str], str]]:
        from unidecode import unidecode

        return {"unidecode": unidecode}


class TextUnidecodeSubject(_Base):
    info = SubjectInfo(
        name="text-unidecode",
        version=_version("text-unidecode"),
        origin="Mikhail Korobov",
        url="https://github.com/kmike/text-unidecode",
        role="lossy ASCII transliteration, GPL-free reimplementation",
    )
    ROLES: ClassVar[dict[str, str]] = {Role.SANITIZER: "text_unidecode"}

    def available(self) -> tuple[bool, str]:
        return (True, "") if _import("text_unidecode") else (False, "pip install text-unidecode")

    def transforms(self) -> dict[str, Callable[[str], str]]:
        import text_unidecode

        return {"text_unidecode": text_unidecode.unidecode}


class AnyAsciiSubject(_Base):
    info = SubjectInfo(
        name="anyascii",
        version=_version("anyascii"),
        origin="Hunter WB",
        url="https://github.com/anyascii/anyascii",
        role="lossy ASCII transliteration, ISC-licensed",
    )
    ROLES: ClassVar[dict[str, str]] = {Role.SANITIZER: "anyascii"}

    def available(self) -> tuple[bool, str]:
        return (True, "") if _import("anyascii") else (False, "pip install anyascii")

    def transforms(self) -> dict[str, Callable[[str], str]]:
        from anyascii import anyascii

        return {"anyascii": anyascii}


class DecancerSubject(_Base):
    """The closest thing to a rival: explicitly a homoglyph/obfuscation remover."""

    info = SubjectInfo(
        name="decancer",
        version=_version("decancer-py"),
        origin="null8626",
        url="https://github.com/null8626/decancer",
        role="removes homoglyphs, diacritics and zero-width from usernames",
    )
    ROLES: ClassVar[dict[str, str]] = {Role.SANITIZER: "decancer_parse"}

    def available(self) -> tuple[bool, str]:
        return (True, "") if _import("decancer_py") else (False, "pip install decancer-py")

    def transforms(self) -> dict[str, Callable[[str], str]]:
        import decancer_py

        return {"decancer_parse": lambda s: str(decancer_py.parse(s))}


class ConfusableHomoglyphsSubject(_Base):
    """The other detector in the registry.

    Until this was added, disarm was the only subject with a ``detect``
    capability, so every detector suite was locked to it and no detection
    question had a second column. A benchmark with one participant is a
    description, not a comparison.
    """

    info = SubjectInfo(
        name="confusable-homoglyphs",
        version=_version("confusable-homoglyphs"),
        origin="Victor Felder",
        url="https://github.com/vhf/confusable_homoglyphs",
        role="detects confusable and mixed-script identifiers (UTS #39 data)",
    )
    ROLES: ClassVar[dict[str, str]] = {Role.DETECTOR: "is_confusable"}

    def available(self) -> tuple[bool, str]:
        return (
            (True, "")
            if _import("confusable_homoglyphs")
            else (False, "pip install confusable-homoglyphs")
        )

    def detectors(self) -> dict[str, Callable[[str], bool]]:
        from confusable_homoglyphs import confusables

        return {
            "is_dangerous": lambda s: bool(confusables.is_dangerous(s)),
            "is_confusable": lambda s: bool(confusables.is_confusable(s)),
            "is_mixed_script": lambda s: bool(confusables.is_mixed_script(s)),
        }


class PyUnormalizeSubject(_Base):
    """Normalization against a different UCD than the interpreter's.

    Ships its own Unicode tables, so it isolates *table version* from *algorithm*
    — the one variable the stdlib column cannot vary. When it and `stdlib`
    disagree, the difference is the UCD, not the code.
    """

    info = SubjectInfo(
        name="pyunormalize",
        version=_version("pyunormalize"),
        origin="Marc Lodewijck",
        url="https://github.com/mlodewijck/pyunormalize",
        role="NFC/NFD/NFKC/NFKD against its own bundled UCD",
    )
    ROLES: ClassVar[dict[str, str]] = {Role.SANITIZER: "NFKC"}

    def available(self) -> tuple[bool, str]:
        return (True, "") if _import("pyunormalize") else (False, "pip install pyunormalize")

    def transforms(self) -> dict[str, Callable[[str], str]]:
        import pyunormalize

        return {
            "NFC": pyunormalize.NFC,
            "NFD": pyunormalize.NFD,
            "NFKC": pyunormalize.NFKC,
            "NFKD": pyunormalize.NFKD,
        }


def _icu_version() -> str:
    try:
        import icu

        return str(icu.ICU_VERSION)
    except ImportError:
        return "not installed"


class ICUSubject(_Base):
    """ICU: the reference implementation of the standard disarm is measured against.

    ``icu.SpoofChecker`` implements UTS #39 directly and ``icu.Transliterator``
    covers the romanization axis, which makes this the most informative column
    available — and the only one that is not merely another tool but the
    standard's own implementation. Registered even when absent, because a reader
    should see that it is missing rather than not know it was an option.
    """

    info = SubjectInfo(
        name="icu",
        version=_icu_version(),
        origin="Unicode Consortium / PyICU",
        url="https://pypi.org/project/PyICU/",
        role="UTS #39 SpoofChecker and ICU Transliterator",
    )

    def available(self) -> tuple[bool, str]:
        if _import("icu"):
            return True, ""
        return False, (
            "pip install pyicu — needs the ICU C++ headers "
            "(brew install icu4c pkg-config, then PKG_CONFIG_PATH=...)"
        )

    def transforms(self) -> dict[str, Callable[[str], str]]:
        if not _import("icu"):
            return {}
        import icu

        latin = icu.Transliterator.createInstance("Any-Latin; Latin-ASCII")
        return {"Any-Latin_Latin-ASCII": latin.transliterate}

    def detectors(self) -> dict[str, Callable[[str], bool]]:
        if not _import("icu"):
            return {}
        import icu

        checker = icu.SpoofChecker()
        return {"spoof_check": lambda s: bool(checker.check(s))}


class NullBaselineSubject(_Base):
    """The degenerate solution, kept in the roster on purpose.

    Deleting all input scores perfectly on every naive coverage metric: both
    sides of every comparison become identical, so every confusable pair
    "collides", every equivalence class "closes" and every attack is "recovered".
    It was the top-scoring subject in this registry until the collision test
    began requiring a non-empty shared form.

    It stays because a control that is supposed to fail is the only thing that
    proves a metric can fail. Any measurement this subject wins is broken, and
    ``tests/test_meta_benchmark.py`` asserts that on the ones it can reach. It is
    a control, never a candidate — never quote it as a comparator.
    """

    info = SubjectInfo(
        name="null-baseline",
        version="1",
        origin="control",
        url="",
        role="deletes everything — the degenerate solution every metric must reject",
    )
    control: ClassVar[bool] = True
    ROLES: ClassVar[dict[str, str]] = {Role.SANITIZER: "delete_all"}

    def transforms(self) -> dict[str, Callable[[str], str]]:
        return {"delete_all": lambda _s: ""}


class IdentitySubject(_Base):
    """The other degenerate solution: change nothing.

    Scores zero on every coverage metric and zero on every damage metric, which
    is the point. It is the floor a tool must beat on coverage while staying
    near it on corruption, and it makes a "does nothing much" tool visible as
    such rather than as a safe one.
    """

    info = SubjectInfo(
        name="identity",
        version="1",
        origin="control",
        url="",
        role="returns input unchanged — the do-nothing floor",
    )
    control: ClassVar[bool] = True
    ROLES: ClassVar[dict[str, str]] = {Role.SANITIZER: "identity"}

    def transforms(self) -> dict[str, Callable[[str], str]]:
        return {"identity": lambda s: s}


ALL: tuple[type[_Base], ...] = (
    DisarmSubject,
    DisarmComposedSubject,
    StdlibSubject,
    DecancerSubject,
    FtfySubject,
    UnidecodeSubject,
    TextUnidecodeSubject,
    AnyAsciiSubject,
    ConfusableHomoglyphsSubject,
    PyUnormalizeSubject,
    ICUSubject,
    NullBaselineSubject,
    IdentitySubject,
)

#: The subject every suite is scored against unless told otherwise.
DEFAULT = "disarm"


def all_subjects() -> list[Subject]:
    out: list[Subject] = []
    for cls in ALL:
        try:
            out.append(cls())  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001 - an uninstallable subject is not fatal
            continue
    return out


def by_name(name: str) -> Subject | None:
    for subject in all_subjects():
        if subject.info.name == name:
            return subject
    return None


#: Names that are controls rather than tools under evaluation.
CONTROLS = ("null-baseline", "identity")


def select(names: list[str] | None = None, only_available: bool = True) -> list[Subject]:
    """Pick the subjects to score.

    ``all`` means every installed *tool* plus both controls, because a run
    without its controls cannot show that its metrics reject the degenerate
    answers. ``tools`` excludes them.
    """
    subjects = all_subjects()
    if names:
        wanted = set(names)
        if "tools" in wanted:
            subjects = [s for s in subjects if not getattr(s, "control", False)]
        elif "all" not in wanted:
            subjects = [s for s in subjects if s.info.name in wanted]
    else:
        subjects = [s for s in subjects if s.info.name == DEFAULT]
    if only_available:
        subjects = [s for s in subjects if s.available()[0]]
    return subjects
