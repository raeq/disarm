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

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import ClassVar, Protocol, runtime_checkable


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

    def available(self) -> tuple[bool, str]: ...
    def capabilities(self) -> set[str]: ...
    def transforms(self) -> dict[str, Callable[[str], str]]: ...
    def detectors(self) -> dict[str, Callable[[str], bool]]: ...
    def keys(self) -> dict[str, Callable[[str], str]]: ...


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

    def transforms(self) -> dict[str, Callable[[str], str]]:
        return {}

    def detectors(self) -> dict[str, Callable[[str], bool]]:
        return {}

    def keys(self) -> dict[str, Callable[[str], str]]:
        return {}

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


class DisarmSubject(_Base):
    """The library under review: every preset, profile, detector and key builder."""

    def __init__(self) -> None:
        super().__init__()
        import disarm

        self.info = SubjectInfo(
            name="disarm",
            version=getattr(disarm, "__version__", "?"),
            origin="raeq/disarm",
            url="https://github.com/raeq/disarm",
            role="Unicode security normalization, detection and key building",
        )

    def available(self) -> tuple[bool, str]:
        return (True, "") if _import("disarm") else (False, "disarm is not importable")

    def transforms(self) -> dict[str, Callable[[str], str]]:
        import disarm

        out: dict[str, Callable[[str], str]] = {
            name: getattr(disarm, name) for name in sorted(disarm.PRESETS)
        }
        for profile in disarm.list_profiles():
            out[f"profile:{profile}"] = disarm.get_pipeline(profile)
        return out

    def detectors(self) -> dict[str, Callable[[str], bool]]:
        import disarm

        return {
            "has_anomalies": disarm.has_anomalies,
            "is_confusable": lambda s: bool(disarm.is_confusable(s)),
            "is_mixed_script": disarm.is_mixed_script,
            "is_zalgo": disarm.is_zalgo,
            "has_bidi_conflict": disarm.has_bidi_conflict,
            "has_bidi_control": disarm.has_bidi_control,
        }

    def keys(self) -> dict[str, Callable[[str], str]]:
        import disarm

        return {
            "search_key": disarm.search_key,
            "catalog_key": disarm.catalog_key,
            "sort_key": disarm.sort_key,
        }


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

    def transforms(self) -> dict[str, Callable[[str], str]]:
        return {"identity": lambda s: s}


ALL: tuple[type[_Base], ...] = (
    DisarmSubject,
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
