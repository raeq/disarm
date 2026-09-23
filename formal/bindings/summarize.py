"""Summarise a difftest.py report: per runner, cases compared and cases that differ.

python3 formal/bindings/summarize.py target/formal-bindings/work/full.json
"""

import json
import sys

r = json.load(open(sys.argv[1]))
print(
    f"inputs per case: {r['inputs']:,} ({r['scalars']:,} scalars + {r['corpus']:,} corpus strings)"
)
for name, rr in r["runners"].items():
    cs = rr["cases"]
    diff = {k: v for k, v in cs.items() if v["differ"] or v["blocks_differ"]}
    comparisons = sum(v["compared"] for v in cs.values())
    print(
        f"\n{name}: {len(cs)} cases, {comparisons:,} comparisons; not expressible: {rr['unsupported'] or 'none'}"
    )
    for k, v in diff.items():
        print(
            f"  {k}: {v['blocks_differ']} blocks differ, {v['differ']} inputs in the {v['blocks_examined']} examined"
        )
        for e in v["examples"][:2]:
            print("    ", json.dumps(e, ensure_ascii=True)[:400])
