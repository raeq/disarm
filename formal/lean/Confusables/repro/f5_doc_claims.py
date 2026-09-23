#!/usr/bin/env python3
"""F5-F9: documentation the library contradicts. Each check prints the claim, where it
is made, and what the library does. Exits 0 when every contradiction reproduces."""

import inspect
import pathlib

import disarm

ROOT = pathlib.Path(__file__).resolve().parents[4]
ok = []

# F5. "disarm and upstream TR39 disagree on 45 rows" / "The two differ on 45 rows and agree
#     on everything else" (docs/user-guide/confusables.md:319,325; src/api/safety.rs:128;
#     src/confusables.rs:68; python/disarm/_api.py:879; python/disarm/_text.py:125).
diff = [
    cp
    for cp in range(0x110000)
    if not 0xD800 <= cp <= 0xDFFF
    and disarm.normalize_confusables(chr(cp))
    != disarm.normalize_confusables(chr(cp), digit_policy="tr39")
]
rows = [
    line
    for line in (ROOT / "src/tables/data/confusables_digit_tr39.tsv").read_text().splitlines()
    if line and not line.startswith("#")
]
print(
    f"F5  claim: 45 rows differ.  measured: {len(diff)} code points differ; the override table has {len(rows)} rows"
)
ok.append(len(diff) == 47 and len(rows) == 47)


# F6. normalize_confusables docstring: "68 code points get a different answer (8 for the
#     Cyrillic target)" with "44 / 15 / 9"; src/pipeline.rs:154 also says 68. The guide,
#     the limitations page and tests/test_fold_order_divergence.py pin 65 and 5.
def divergent(target: str) -> int:
    n = 0
    for cp in range(0x110000):
        c = chr(cp)
        alone = disarm.normalize_confusables(c, target_script=target)
        if alone != c and alone != disarm.normalize_confusables(
            disarm.normalize(c, form="NFKC"), target_script=target
        ):
            n += 1
    return n


lat, cyr = divergent("latin"), divergent("cyrillic")
doc = inspect.getdoc(disarm.normalize_confusables)
print(
    f"F6  docstring says 68 / 8: {'68 code points' in doc and '(8 for' in doc}.  measured: {lat} / {cyr}"
)
ok.append("68 code points" in doc and (lat, cyr) == (65, 5))

# F7. is_confusable docstring: 'Currently only "latin" is supported; any other value
#     raises DisarmError'.
doc = inspect.getdoc(disarm.is_confusable)
res = {t: disarm.is_confusable("\u0430", target_script=t) for t in ("cyrillic", "arabic", "hebrew")}
print(
    f"F7  docstring claims only latin is accepted: {'only' in doc and 'latin' in doc}.  library: {res} (no error)"
)
ok.append("Currently only" in doc)

# F8. docs/user-guide/confusables.md:348: "The presets (canonicalize, catalog_key,
#     search_key, ...) have no such switch and always fold numerically".
r = {
    f: getattr(disarm, f)("\u0966", digit_policy="tr39")
    for f in ("canonicalize", "search_key", "catalog_key")
}
print(f"F8  guide: presets have no digit switch.  library: {r}")
ok.append(all(v != "0" for v in r.values()))

# F9. python/disarm/_text.pyi:27 types Text.normalize_confusables without digit_policy;
#     the implementation (python/disarm/_text.py:118) takes it.
stub = (ROOT / "python/disarm/_text.pyi").read_text()
line = next(ln for ln in stub.splitlines() if "def normalize_confusables" in ln)
sig = inspect.signature(disarm.Text.normalize_confusables)
print(f"F9  stub: {line.strip()}\n    runtime: {sig}")
ok.append("digit_policy" not in line and "digit_policy" in sig.parameters)

print("reproduced:", ok)
raise SystemExit(0 if all(ok) else 1)
