"""Generate the string corpus for the differential harness (deterministic).

Writes one line per string: the hex of its UTF-8 bytes. Every runner decodes the same
file, so no runner ever has to agree with another on how to escape a string.

    python3 formal/bindings/gen_corpus.py OUT [N]

The pools below are written as code-point ranges, never as literal characters.
"""

from __future__ import annotations

import random
import sys

# (lo, hi) inclusive code-point ranges, each a pool the generator samples from.
POOLS: dict[str, list[tuple[int, int]]] = {
    "ascii": [(0x20, 0x7E)],
    "ascii_ctl": [(0x01, 0x1F), (0x7F, 0x7F)],
    "latin1": [(0xA0, 0xFF)],
    "latin_ext": [(0x100, 0x24F), (0x1E00, 0x1EFF)],
    "combining": [(0x300, 0x36F), (0x1AB0, 0x1AFF), (0x20D0, 0x20FF)],
    "greek": [(0x370, 0x3FF)],
    "cyrillic": [(0x400, 0x4FF)],
    "hebrew": [(0x591, 0x5F4)],
    "arabic": [(0x600, 0x6FF), (0x750, 0x77F)],
    "indic": [(0x900, 0x97F), (0x980, 0x9FF), (0xB80, 0xBFF)],
    "thai": [(0xE00, 0xE7F)],
    "hangul": [(0x1100, 0x11FF), (0xAC00, 0xD7A3)],
    "kana": [(0x3040, 0x30FF)],
    "cjk": [(0x4E00, 0x9FFF), (0x20000, 0x2A6DF)],
    "fullwidth": [(0xFF01, 0xFF5E)],
    "digits": [
        (0x660, 0x669),
        (0x6F0, 0x6F9),
        (0x966, 0x96F),
        (0xFF10, 0xFF19),
        (0x1D7CE, 0x1D7FF),
    ],
    "math": [(0x1D400, 0x1D7FF), (0x2100, 0x214F)],
    "space": [
        (0x09, 0x0D),
        (0x85, 0x85),
        (0xA0, 0xA0),
        (0x2000, 0x200A),
        (0x2028, 0x2029),
        (0x3000, 0x3000),
    ],
    "invisible": [
        (0x200B, 0x200F),
        (0x2060, 0x2064),
        (0xFEFF, 0xFEFF),
        (0xAD, 0xAD),
        (0x180E, 0x180E),
    ],
    "bidi": [(0x202A, 0x202E), (0x2066, 0x2069), (0x61C, 0x61C)],
    "vs": [(0xFE00, 0xFE0F), (0xE0100, 0xE01EF)],
    "tags": [(0xE0000, 0xE007F)],
    "emoji": [(0x1F300, 0x1F6FF), (0x1F900, 0x1F9FF), (0x2600, 0x27BF), (0x1F1E6, 0x1F1FF)],
    "emoji_mod": [(0x1F3FB, 0x1F3FF), (0x200D, 0x200D), (0x20E3, 0x20E3), (0xFE0F, 0xFE0F)],
    "pua": [(0xE000, 0xF8FF), (0xF0000, 0xF0010)],
    "nonchar": [(0xFDD0, 0xFDEF), (0xFFFE, 0xFFFF), (0x1FFFE, 0x1FFFF), (0x10FFFE, 0x10FFFF)],
    "specials": [(0xFFF9, 0xFFFD)],
    "punct": [(0x2010, 0x2027), (0x2030, 0x205E), (0x2200, 0x22FF)],
    "any": [(0x1, 0xD7FF), (0xE000, 0x10FFFF)],
}

# Hand-picked strings: known confusable spoofs, sequences, hostnames, paths.
FIXED: list[str] = [
    "",
    " ",
    "a",
    "hello world",
    "\u0430pple.com",
    "\u0430\u0440\u0440\u04cf\u0435.com",
    "xn--80ak6aa92e.com",
    "paypa1.com",
    "arnazon.com",
    "caf\u00e9 r\u00e9sum\u00e9",
    "cafe\u0301",
    "\u041c\u043e\u0441\u043a\u0432\u0430",
    "\u041a\u0438\u0457\u0432",
    "M\u00fcnchen",
    "\u6771\u4eac",
    "\u3068\u3046\u304d\u3087\u3046",
    "\u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35",
    "\u05d0\u05b8\u05c1\u0591",
    "a\u0301\u0302\u0303\u0304\u0305\u0306",
    "\U0001f468\u200d\U0001f469\u200d\U0001f467",
    "\U0001f44d\U0001f3fd",
    "1\ufe0f\u20e3",
    "\U0001f1fa\U0001f1f8",
    "\U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f",
    "\u202eevil\u202c.exe",
    "ab\u200bcd",
    "fr33 m0ney",
    "\u0968\u0966\u0968\u0966",
    "\u0660\u0661\u0662",
    "..%2Fetc/passwd",
    "CON.txt",
    " leading and trailing ",
    "\t\ttabs\nand\r\nlines\u2028ls",
    "\ufeffBOM",
    "gro\u00df.txt",
    "\u0130stanbul",
    "\u1e9e",
    "\ufb01le",
    "\u2126",
    "x" * 300,
    "\u00e9" * 5000,
]


def sample(rng: random.Random, pool: str) -> str:
    lo, hi = rng.choice(POOLS[pool])
    return chr(rng.randint(lo, hi))


def random_string(rng: random.Random) -> str:
    n = rng.choice([0, 1, 1, 2, 3, 4, 5, 8, 12, 20, 40])
    k = rng.randint(1, 3)
    pools = rng.sample(sorted(POOLS), k)
    return "".join(sample(rng, rng.choice(pools)) for _ in range(n))


def main() -> None:
    out = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 40000
    rng = random.Random(20260923)
    items = list(FIXED)
    while len(items) < n - 2:
        items.append(random_string(rng))
    # Two long strings: 64 KiB of mixed text and 1 MiB of one repeated character.
    items.append("".join(random_string(rng) for _ in range(4000)))
    items.append("\u0430" * (1 << 19))
    with open(out, "w", encoding="ascii") as f:
        for s in items:
            f.write(s.encode("utf-8").hex() + "\n")


if __name__ == "__main__":
    main()
