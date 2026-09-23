"""Shared test fixtures and Hypothesis strategies for disarm.

Centralizes Unicode sample data and property-based testing strategies
so that new tests can import them from one place instead of
rediscovering or redeclaring them per file.
"""

from __future__ import annotations

import functools
from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings
from hypothesis import strategies as st

from disarm._enums import Script

# ---------------------------------------------------------------------------
# Repository corpora
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent


#: Skipped by name at any depth, whatever the marker search finds. `.venv` is the
#: name every tool defaults to, and the environments that carry no `pyvenv.cfg` —
#: conda's, or one nested deeper than the search below goes — are still found by it.
#: `.claude` is gitignored and holds agent worktrees, whole other checkouts of this
#: repository on other branches, so walking it polices files this tree does not have.
#: `.lake` is Lake's build and package directory under each `formal/lean` model.
ALWAYS_SKIPPED = frozenset({".git", ".venv", ".claude", ".lake"})


@functools.cache
def venv_dirs(root: Path = ROOT) -> frozenset[Path]:
    """Python virtual environments under `root`, as paths relative to it.

    Two test modules walk the whole tree and skipped build output by NAME, and the name
    they knew was `.venv`. A contributor whose environment is `venv/`, `.venv312/`,
    `env/` or `.tox/` therefore swept all of site-packages into the corpus: 1,516 of
    2,123 files in one of them, which is slow and — for the gates that refuse literal
    bidi controls and invisibles — a false positive waiting for whichever dependency
    ships one in a fixture.

    `pyvenv.cfg` is what makes a directory a virtual environment, so that is what this
    looks for, rather than a longer list of names to be wrong about later. Only the top
    two levels are searched: deeper is not where anyone puts one, and the search should
    not cost more than the walk it saves.

    Paths, not names (#997 review). The first version returned `cfg.parent.name` and the
    walkers matched it against every component of every path, so tox's `.tox/docs`
    environment excluded this repository's own `docs/` tree along with it.

    `root` is a parameter so the behaviour can be tested against a synthetic tree rather
    than against whatever happens to be checked out — a test that can only ask about this
    repository can only restate the answer back to itself.
    """
    markers = [*root.glob("*/pyvenv.cfg"), *root.glob("*/*/pyvenv.cfg")]
    return frozenset(cfg.parent.relative_to(root) for cfg in markers)


def in_skipped_dir(path: Path, root: Path, skip: frozenset[str]) -> bool:
    """Whether `path`, a file under `root`, is not ours to police.

    True when a directory between `root` and the file is named in `skip` or
    `ALWAYS_SKIPPED`, or is one of `venv_dirs(root)`. Only the part of the path inside
    `root` is looked at: matching the absolute path, as this used to, emptied the corpus
    of any checkout that lives under a directory called `build` or `tmp` — which includes
    every pytest `tmp_path` (#997 review).
    """
    rel = path.relative_to(root)
    if any(part in skip or part in ALWAYS_SKIPPED for part in rel.parts[:-1]):
        return True
    venvs = venv_dirs(root)
    return any(parent in venvs for parent in rel.parents)


# ---------------------------------------------------------------------------
# Hypothesis profiles
# ---------------------------------------------------------------------------

#: What `nightly-hypothesis.yml` runs under, with a seed it generates and logs. It is
#: Hypothesis's own `ci` profile — spelled out rather than inherited, so it does not
#: depend on that profile existing — minus `derandomize`. Hypothesis loads `ci` by
#: itself whenever `CI` is set, and a derandomized test seeds itself from its own
#: source and ignores `--hypothesis-seed`, so every night replayed the same examples
#: whatever seed was passed (#997 review). `tests/test_nightly_hypothesis_seed.py`
#: holds the workflow and this together. Reproduce a nightly failure locally with
#: `pytest -m hypothesis --hypothesis-profile=nightly --hypothesis-seed=<logged seed>`.
settings.register_profile(
    "nightly",
    derandomize=False,
    deadline=None,
    database=None,
    print_blob=True,
    suppress_health_check=[HealthCheck.too_slow],
)

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

#: Full Unicode text including BMP, SMP, combining marks, emoji, CJK, etc.
unicode_text = st.text(alphabet=st.characters(codec="utf-8"))

#: The four Unicode normalization forms as strings.
nf_forms = st.sampled_from(["NFC", "NFD", "NFKC", "NFKD"])

#: An emoji the CLDR name table does not name — the shape `demojize`'s `errors` mode
#: exists for. A lone regional indicator is `Emoji_Presentation=Yes` and CLDR names no
#: single one of them, because a flag needs the pair. Shared so the two modules that
#: depend on it move together, and so the guard in
#: `test_demojize.TestUnknownEmojiSpacingParity.test_precondition_codepoint_is_unmapped`
#: covers every use rather than only its own (#990).
#:
#: Do not double it: two regional indicators are one flag, which the scanner consumes as
#: a single emoji, so `UNNAMED_EMOJI * 2` does not mean "two unnamed emoji".
UNNAMED_EMOJI = "\U0001f1e6"


# ---------------------------------------------------------------------------
# Canonical script samples — one per Script enum member (excluding meta)
# ---------------------------------------------------------------------------
# Keys: Script enum member
# Values: short string containing ONLY characters of that script
#         (no Common/Inherited characters like digits or spaces)

SCRIPT_SAMPLES: dict[Script, str] = {
    # Major world scripts
    Script.LATIN: "abcdef",
    Script.CYRILLIC: "Москва",
    Script.GREEK: "Ελλάδα",
    Script.ARABIC: "العربية",
    Script.HEBREW: "עברית",
    # Indic scripts
    Script.DEVANAGARI: "हिन्दी",
    Script.BENGALI: "বাংলা",
    Script.GURMUKHI: "ਗੁਰਮੁਖੀ",
    Script.GUJARATI: "ગુજરાતી",
    Script.ORIYA: "ଓଡ଼ିଆ",
    Script.TAMIL: "தமிழ்",
    Script.TELUGU: "తెలుగు",
    Script.KANNADA: "ಕನ್ನಡ",
    Script.MALAYALAM: "മലയാളം",
    Script.MEETEI_MAYEK: "\uabc0\uabc1\uabc2",  # ꯀꯁꯂ
    Script.OL_CHIKI: "\u1c5a\u1c5b\u1c5c",  # ᱚᱛᱜ
    Script.SINHALA: "සිංහල",
    # East Asian scripts
    Script.HAN: "中文漢字",
    Script.HIRAGANA: "ひらがな",
    Script.KATAKANA: "カタカナ",
    Script.HANGUL: "한국어",
    Script.LISU: "\ua4d0\ua4d1\ua4d2",  # ꓐꓑꓒ
    # Southeast Asian scripts
    Script.THAI: "ภาษาไทย",
    Script.LAO: "ພາສາລາວ",
    Script.MYANMAR: "မြန်မာ",
    Script.KHMER: "ភាសាខ្មែរ",
    Script.BALINESE: "\u1b05\u1b13\u1b17",  # ᬅᬓᬗ
    Script.BUGINESE: "\u1a00\u1a01\u1a02",  # ᨀᨁᨂ
    Script.CHAM: "\uaa00\uaa01\uaa02",  # ꨀꨁꨂ
    Script.JAVANESE: "\ua984\ua989\ua98e",  # ꦄꦉꦎ
    Script.SUNDANESE: "\u1b83\u1b84\u1b85",  # ᮃᮄᮅ
    Script.TAGALOG: "\u1700\u1701\u1702",  # ᜀᜁᜂ
    # #775: the core resolved these four and the Script enum could not name them, so
    # `detect_scripts` warned and returned an empty list on non-empty input.
    Script.BUHID: "ᝀᝁᝂ",
    Script.HANUNOO: "ᜠᜡᜢ",
    Script.TAGBANWA: "ᝠᝡᝢ",
    Script.BATAK: "ᯀᯁᯂ",
    Script.TAI_LE: "\u1950\u1951\u1952",  # ᥐᥑᥒ
    Script.TAI_THAM: "\u1a20\u1a21\u1a22",  # ᨠᨡᨢ
    Script.NEW_TAI_LUE: "\u1980\u1981\u1982",  # ᦀᦁᦂ
    # Central/North Asian scripts
    Script.TIBETAN: "བོད་སྐད",
    Script.MONGOLIAN: "\u1820\u1821\u1822",  # ᠠᠡᠢ
    # Caucasian scripts
    Script.GEORGIAN: "ქართული",
    Script.ARMENIAN: "Հայերեն",
    # African scripts
    Script.ETHIOPIC: "አማርኛ",
    Script.NKO: "\u07c1\u07c2\u07c3",  # ߁߂߃
    Script.BAMUM: "\ua6a0\ua6a1\ua6a2",  # ꚠꚡꚢ
    Script.TIFINAGH: "\u2d30\u2d31\u2d33",  # ⴰⴱⴳ
    Script.VAI: "\ua500\ua501\ua502",  # ꔀꔁꔂ
    # Middle Eastern scripts
    Script.SYRIAC: "\u0710\u0712\u0713",  # ܐܒܓ
    Script.THAANA: "\u0780\u0781\u0782",  # ހށނ
    Script.COPTIC: "\u2c80\u2c81\u2c82",  # Ⲁⲁⲃ
    # Americas
    Script.CHEROKEE: "\u13a0\u13a1\u13a2",  # ᎠᎡᎢ
    Script.CANADIAN_ABORIGINAL: "\u1401\u1402\u1403",  # ᐁᐂᐃ
    # Historical European scripts
    Script.RUNIC: "\u16a0\u16a1\u16a2",  # ᚠᚡᚢ
    Script.OGHAM: "\u1681\u1682\u1683",  # ᚁᚂᚃ
    Script.GOTHIC: "\U00010330\U00010331\U00010332",  # 𐌰𐌱𐌲
    # Ancient Near Eastern scripts
    Script.OLD_PERSIAN: "\U000103a0\U000103a1\U000103a2",  # 𐎠𐎡𐎢
    Script.CUNEIFORM: "\U00012000\U00012001\U00012002",  # 𒀀𒀁𒀂
    Script.LINEAR_B: "\U00010000\U00010001\U00010002",  # 𐀀𐀁𐀂
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def script_samples() -> dict[Script, str]:
    """Return the canonical SCRIPT_SAMPLES dictionary."""
    return SCRIPT_SAMPLES
