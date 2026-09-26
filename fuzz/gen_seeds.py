"""Write the committed seed corpora under ``fuzz/seeds/``.

Run from the repository root: ``python3 fuzz/gen_seeds.py``. Deterministic: the same
inputs give byte-identical files, so a regenerated tree diffs clean.

Two sources, both chosen because they already mean something here:

* **The key-stability corpus** (``tests/fixtures/key_stability/corpus.txt``): natural words
  in fifteen scripts plus the hand-built adversarial rows (bidi controls, tags, selectors,
  noncharacters, soft hyphens, Kirat Rai, deletion classes). Every row carrying a code
  point of an interesting general category is taken, plus a stride through the rest.
* **Regression witnesses**: the minimal inputs of the formal models' findings
  (``formal/lean/*/README.md``) and of ``tests/test_*_formal_findings.py``.

Seeds are written as raw bytes, never as literals in this file: every non-ASCII character
below is an escape, per the repository's "escapes, never literals" rule (#802). Seed files
carry no suffix, so the tree-wide invisible-character guard, which reads source suffixes,
does not read them.

Two directories, one per input layout, shared by the targets that read it:

* ``fuzz/seeds/unicode/``: every text target. They take ``TEXT [0xFF OPTIONS]`` (see
  ``fuzz/src/lib.rs``), and a seed without the ``0xFF`` runs under the default options.
* ``fuzz/seeds/bytes/``: ``decode_bytes``, which takes a mode byte, then bytes.
"""

from __future__ import annotations

import hashlib
import shutil
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEEDS = ROOT / "fuzz" / "seeds"
CORPUS = ROOT / "tests" / "fixtures" / "key_stability" / "corpus.txt"

#: General categories that make a corpus row worth a seed of its own.
INTERESTING_CATEGORIES = {"Cc", "Cf", "Co", "Cn", "Mn", "Mc", "Me", "Zl", "Zp", "Nd", "Sk"}
#: Cap on corpus-derived seeds per target: enough to reach every script and class once,
#: small enough that the seeds stay a starting point rather than a corpus.
CORPUS_CAP = 120
STRIDE = 400


#: Regression witnesses: the findings of the formal models, by model.
COMMON_WITNESSES = [
    # Confusables F1 / #1024: skeleton_key fixed point, compose-at-lookup.
    "\u0390",
    "\u00a5\u0300",
    "\u04aa\u0327",
    "a\x01\u0300",
    "I\u200b\u0301",
    "\U00016d67\U00016d67",
    "\U00016d68",
    # Presets findings 2-4: tr39/preserve keys, negation overlays, separated compositions.
    "\ua760",
    "\u01c1",
    "\u0100",
    '|"`',
    "\u0440\u0430\u0443\u0440\u0430l",
    "g\u0a66ogle",
    "\u1100\u200b\u1161",
    # Detection findings 1-6 (#1023, #1025).
    "pay\u206apal",
    "Transfer \u200f\u200f100 200 300 to Bob",
    "\u00e9t\u00e9\u2067",
    "e\u0301te\u0301\u2067",
    "\u212aey",
    "\ufeffhello",
    "\u03b1\u00d7\u03b2",
    "a\u3105",
    "\u2764\ufe0f" + "".join(chr(0xFE00 + b) if b < 16 else chr(0xE0100 + b - 16) for b in b"hi"),
    "\u200b" + "".join("\u200b" if bit == "0" else "\u200c" for bit in "0110100001101001"),
    "hello" + "".join(chr(0xE0000 + b) for b in b"hi"),
    "\U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f",
    "%25%32%45",
    # Deletions findings 1-2 (#1010).
    "abc\rX\x08",
    "a\u200b\rX",
    "ab\x0bc\x7f",
    "x\u2028y\x08",
    # Emoji F1-F6 (#1011, #1015).
    "1\ufe0f\U0001f600\u20e3",
    "1\ufe0e\u20e3",
    "1\u200d\u20e3",
    "\U0001f600\U0001f1e6x",
    "x\U0001f600\u0301",
    "\u2764\ufe0f\u200d\U0001f525",
    "\U0001f3f3\ufe0f\u200d\U0001f308",
    "\U0001f452",
    # Text Z1, W1, W2.
    "a" + "\u0301" * 3 + "\u034f" + "\u0301" * 3,
    ("\u0600A") * 4,
    "x\ufe0f",
    # Transliterate: I7 worst case, normal-form edges, context and tone surfaces.
    "\u337f",
    "\u1fee\u1ffd",
    "\uf900\u5317\u4eac",
    "\u0645\u0631\u062d\u0628\u0627 hello",
    # Found by these targets (docs/architecture/testing-guarantees.md, "Baselines").
    "Q&#A session",
    "&#a" + chr(0x301),
    chr(0x4AA) + chr(0x327),
    "x" + chr(0xFE0F),
    chr(0x1F240),
    "a" + ".*" * 9,
    chr(0xF51) + chr(0xFB7),
    "C" + chr(0x327) * 9,
    "ab" + chr(0x200D) + "6",
    chr(0x1E7) + chr(0x327) + chr(0x367) + chr(0x327) * 3 + chr(0x303),
    # Sanitizers findings 1-15.
    "_.con",
    "*.con",
    " .nul",
    "../.con",
    "\x00.com1",
    "?.LPT1",
    "_.x.*",
    "ab_cd",
    "a.bcd.txt",
    "a. .b",
    "%\uff05\uff12\uff25\uff05\uff12\uff25\uff05\uff12\uff26etc.txt",
    "..%2Fetc",
    "\u24b6dmin",
    "a\u200db",
    "T\u0308",
    "\u1f82",
    "very long title here",
    "The Fox",
    "e\u00advil.com",
    "e\u115fvil.com",
    "\uff45vil.com",
    "xn--58da.com",
    "paypal\u202emoc.evil.com",
    "arnazon.com",
    "\u0430\u0440\u0440\u04cf\u0435.com",
]

#: `decode_bytes` seeds: (mode byte, payload). Mode bits 0-4 pick the label (0 = auto),
#: bit 5 is strict, bits 6-7 the confidence. The labels are `LABELS` in decode_bytes.rs:
#: 1 utf-8, 4 utf-16, 5 utf-16le, 6 utf-16be, 9 windows-1252, 19 shift_jis, 20 euc-jp.
BYTE_SEEDS: list[tuple[int, bytes]] = [
    (0, b"hello world"),
    (0, b"\xef\xbb\xbfhello"),
    (0, b"\xff\xfeA\x00B\x00"),
    (0, b"\xfe\xff\x00A\x00B"),
    (0, "h\x00e\x00l\x00l\x00o\x00".encode("latin-1")),
    (0, "\u041f\u0440\u0438\u0432\u0435\u0442".encode("utf-16-le")),
    (0, "\u041f\u0440\u0438\u0432\u0435\u0442 \u043c\u0438\u0440".encode("cp1251")),
    (0, "\u65e5\u672c\u8a9e\u306e\u30c6\u30ad\u30b9\u30c8".encode("shift_jis")),
    (0, "\u65e5\u672c\u8a9e".encode("euc_jp")),
    (0, "\u4e2d\u6587\u6587\u672c".encode("gb18030")),
    (0, "\ud55c\uad6d\uc5b4".encode("euc_kr")),
    (0, "\u05e9\u05dc\u05d5\u05dd".encode("cp1255")),
    (0, "caf\u00e9 cr\u00e8me br\u00fbl\u00e9e".encode("cp1252")),
    (0, b"\xc3\x28\xa0\xa1\xe2\x28\xa1\xf0\x28\x8c\xbc"),
    (0x21, b"\xfe\xff\x00A"),
    (0x21, b"\xed\xa0\x80"),
    (0x25, b"\xff\xfeA\x00\x00\xd8"),
    (0x04, b"\xfe\xff\x00A"),
    (0x06, b"\xff\xfe\x00A"),
    (0x09, bytes(range(256))),
    (0x13, b"\x82\xa0\x82\xa2\x81"),
    (0x14, b"\x1b$B\x46\x7c\x1b(B"),
    (0x40, b"\x80\x81\x82"),
    (0x80, b"ok"),
]


def corpus_rows() -> list[str]:
    """Corpus rows with an interesting code point, then a stride through the rest."""
    rows = [r for r in CORPUS.read_text(encoding="utf-8").split("\n") if r]
    picked = [r for r in rows if any(unicodedata.category(c) in INTERESTING_CATEGORIES for c in r)]
    picked += rows[::STRIDE]
    seen: set[str] = set()
    out = []
    for r in picked:
        if r not in seen:
            seen.add(r)
            out.append(r)
    # Spread the cap across the whole corpus rather than taking its head.
    step = max(1, len(out) // CORPUS_CAP)
    return out[::step][:CORPUS_CAP]


def write(directory: Path, data: bytes) -> None:
    """Name a seed by its content, as libFuzzer names corpus files."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / hashlib.sha1(data, usedforsecurity=False).hexdigest()).write_bytes(data)


def main() -> None:
    if SEEDS.exists():
        shutil.rmtree(SEEDS)
    rows = corpus_rows()
    for t in COMMON_WITNESSES + rows:
        write(SEEDS / "unicode", t.encode("utf-8"))
    for mode, payload in BYTE_SEEDS:
        write(SEEDS / "bytes", bytes([mode]) + payload)
    for row in rows[:40]:
        write(SEEDS / "bytes", b"\x00" + row.encode("utf-8"))
        write(SEEDS / "bytes", b"\x05" + row.encode("utf-16-le"))
    counts = {d.name: len(list(d.iterdir())) for d in sorted(SEEDS.iterdir())}
    print(counts)


if __name__ == "__main__":
    main()
