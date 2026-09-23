"""Finding 5: `PRESETS` is not what the presets run.

`PRESETS["canonicalize"]` is documented as "what `canonicalize()` runs" and as a way to
"build equivalent `TextPipeline` configurations". This executes every `PRESETS` list
literally, step by step, with the public function each step names, and compares the result
with the preset on a few words. It also prints the steps the Rust lists carry and the
mirror does not.
"""

from __future__ import annotations

from common import w

import disarm


def strip_invisibles(policy: str, s: str) -> str:
    s = disarm.strip_tags(s)
    s = disarm.strip_noncharacters(s)
    s = s.replace(chr(0x34F), "")
    if policy == "comparison":
        s = disarm.strip_pua(s)
        s = disarm.strip_variation_selectors(s)
    return s


def translit(param: str | None, s: str) -> str:
    if param != "non_latin":
        return disarm.transliterate(s, errors="preserve")
    # `transliterate_preserving_latin_into`: keep Latin / Common / Inherited, romanize the rest.
    out = []
    for ch in s:
        scripts = [x.value for x in disarm.detect_scripts(ch)]
        keep = ch.isascii() or scripts in ([], ["Latin"])
        out.append(ch if keep else disarm.transliterate(ch, errors="preserve"))
    return "".join(out)


STEP = {
    "normalize": lambda p, s: disarm.normalize(s, form=p),
    "strip_bidi": lambda p, s: disarm.strip_bidi(s),
    "strip_invisibles": lambda p, s: strip_invisibles(p, s),
    "strip_control": lambda p, s: disarm.strip_control_chars(s),
    "strip_zero_width": lambda p, s: disarm.strip_zero_width_chars(s),
    "collapse_whitespace": lambda p, s: disarm.collapse_whitespace(s),
    "strip_zalgo": lambda p, s: disarm.strip_zalgo(s, max_marks=0 if p == "max_marks=0" else 3),
    "confusables": lambda p, s: disarm.normalize_confusables(s),
    "fold_case": lambda p, s: disarm.fold_case(s),
    "strip_accents": lambda p, s: disarm.strip_accents(s),
    "transliterate": lambda p, s: translit(p, s),
    "demojize": lambda p, s: disarm.demojize(s),
}


def run_mirror(name: str, s: str) -> str:
    for step, param in disarm.PRESETS[name]:
        s = STEP[step](param, s)
    return s


WORDS = [
    ("a BS b", w(0x61, 0x8, 0x62)),
    ("grinning face", w(0x1F600)),
    ("a + acute x4", w(0x61, 0x301, 0x301, 0x301, 0x301)),
    ("Y with grave + acute", w(0x1EF2, 0x301)),
    ("ab + PUA", w(0x61, 0x62, 0xE000)),
    ("ab + VS16", w(0x61, 0x62, 0xFE0F)),
]
for name in (
    "canonicalize",
    "canonicalize_strict",
    "strip_obfuscation",
    "search_key",
    "catalog_key",
    "sort_key",
    "ml_normalize",
    "strip_format",
):
    f = getattr(disarm, name)
    for label, s in WORDS:
        real, mirror = f(s), run_mirror(name, s)
        if real != mirror:
            print(
                f"{name:<20} {label:<22} preset={ascii(real):<14} PRESETS executed={ascii(mirror)}"
            )

print()
print("skeleton_key in PRESETS:", "skeleton_key" in disarm.PRESETS)
print(
    "resolve_deletions in any PRESETS list:",
    any(step == "resolve_deletions" for v in disarm.PRESETS.values() for step, _ in v),
)
print(
    "strip_obfuscation lists demojize:", ("demojize", "cldr") in disarm.PRESETS["strip_obfuscation"]
)
cs = [s for s, _ in disarm.PRESETS["canonicalize_strict"]]
print(
    "canonicalize_strict lists strip_zalgo before confusables:",
    cs.index("strip_zalgo") < cs.index("confusables"),
)
for k in ("search_key", "catalog_key", "sort_key"):
    print(
        f"{k} lists strip_invisibles:", any(s == "strip_invisibles" for s, _ in disarm.PRESETS[k])
    )
