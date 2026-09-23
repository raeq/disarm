"""Python reproductions (README: B1, B2; the last block is a suspicion that did not reproduce).

DISARM_PYTHON=... $DISARM_PYTHON formal/bindings/repro/python_repro.py
"""

import disarm


def show(label, f):
    try:
        r = ascii(f())
    except Exception as e:  # noqa: BLE001
        r = f"raised {type(e).__name__}: {str(e)[:90]}"
    print(f"{label:60} {r}")


print("-- B1: strip_zalgo default cap (core DEFAULT_MAX_MARKS = 3, #788) --")
stack = "a\u0316\u0317\u0318"
show("strip_zalgo(stack)", lambda: disarm.strip_zalgo(stack))

print("-- B2: an unknown `lang` is rejected here, and nowhere else --")
show(
    "transliterate(kyiv, lang='UK')",
    lambda: disarm.transliterate("\u041a\u0438\u0457\u0432", lang="UK"),
)
show("slugify('M\\u00fcnchen', lang='dee')", lambda: disarm.slugify("M\u00fcnchen", lang="dee"))

print("-- not confirmed: the surrogate retry re-reading an exhausted iterator --")
vals = ["Paypal", "paypal", "x\ud800"]
show(
    "find_key_collisions(list, key='fold_case')",
    lambda: disarm.find_key_collisions(list(vals), key="fold_case"),
)
show(
    "find_key_collisions(generator, key='fold_case')",
    lambda: disarm.find_key_collisions((v for v in vals), key="fold_case"),
)
show(
    "find_key_collisions(generator without a surrogate)",
    lambda: disarm.find_key_collisions((v for v in vals[:2]), key="fold_case"),
)
show(
    "nearest_match('paypa1', generator)",
    lambda: disarm.nearest_match("paypa1", (c for c in ["paypal", "x\ud800"])),
)
show("nearest_match('paypa1', list)", lambda: disarm.nearest_match("paypa1", ["paypal", "x\ud800"]))
show(
    "has_anomalies('fr33 x\\ud800', generator)",
    lambda: disarm.has_anomalies("fr33 x\ud800", (w for w in ["free"])),
)
show("has_anomalies('fr33 x\\ud800', list)", lambda: disarm.has_anomalies("fr33 x\ud800", ["free"]))
show(
    "slugify('a the b\\ud800', stopwords=generator)",
    lambda: disarm.slugify("a the b\ud800", stopwords=(w for w in ["the"])),
)
show(
    "slugify('a the b\\ud800', stopwords=list)",
    lambda: disarm.slugify("a the b\ud800", stopwords=["the"]),
)
