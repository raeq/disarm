# The meta-benchmark

One harness over every externally produced benchmark the 0.15.0 cycle used to find
and verify a defect. It runs `n` of `m`, consolidates the results into one report,
and compares them against a committed baseline.

```bash
python -m benchmarks.meta --list                       # show m, and what is runnable
python -m benchmarks.meta --run --only-available       # run what the machine has
python -m benchmarks.meta --run --select 'uts39-*'     # run one group
python -m benchmarks.meta --run --sample 5 --seed 3    # a reproducible partial pass
python -m benchmarks.meta --run --family cve academic --report out.md --json out.json
```

## Why the benchmarks are all somebody else's

A library that writes its own benchmark grades its own homework. Every suite here
is anchored to an artifact produced outside this repository — a corpus released
with a paper, a public dataset, a normative Unicode/IETF/ICANN table, a published
CVE, a released tokenizer, or a third-party labelled benchmark. The harness
supplies the runner, the selection, the provenance record and the report. It
supplies no vectors.

That boundary is checked, not promised. `Provenance.external` is a field, the
runner tags every outcome with it, the report renders external and introspective
results in separate sections, and `tests/test_meta_benchmark.py` asserts that no
external suite is scored against a file disarm generated.

The last one is not hypothetical. `data/confusables_lgr.tsv` looks like an ideal
local oracle for the ICANN suite: it is an extract of ICANN's Latin second-level
LGR, it is already in the repo, and it needs no network. It is also the file the
shipped fold was built from, so scoring the fold against it returns 100% by
construction. The suite requires ICANN's published LGR or reports nothing.

Inherited guardrail, from #39/#40: these corpora are measuring instruments, never
optimization targets. Do not add a confusable mapping to improve a number here.
Coverage grows from authoritative sources; a principled miss is routed to #40.

## The five external families, and the sixth tier

| family | anchor | examples |
|---|---|---|
| `normative` | a table that *defines* the right answer | UTS #39 §5.1/§5.3, UCD Scripts.txt, UAX #9, UAX #29, ICANN LGR, CLDR |
| `cve` | a published vulnerability's own vector | CVE-2026-17084's stringprep B.3 delta, the Trojan Source PoC files |
| `academic` | a corpus released with a paper | Bad Characters, XOXO, GCG suffixes, GAversary, ESTI, arXiv:2405.14490 |
| `dataset` | a public corpus | BitAbuse, YouTube-Spam, TREC-2007, MeAJOR, benign Gutenberg prose |
| `model` | a released model artifact | chat-template delimiters read from published `tokenizer.json` files |
| `comparator` | a third-party labelled benchmark or rival tool | `confusable-bench.v1`, confusable-vision, untrace |

`introspective` is the sixth tier and is not a benchmark. Its sweeps run over the
UCD code-point domain, which is external, but disarm is the only oracle for what
the answer should be — so a number moving there proves nothing on its own. They
are registered because dropping them would leave a hole in the 0.15.0 record, and
because they catch silent regressions. They are excluded unless you pass
`--include-introspective`, and they never enter an external total.

## What a run reports

Three things per suite, kept apart on purpose:

**Found during the cycle** is historical — what the benchmark measured when it was
run against 0.14.1, quoted from the issue it produced. It is never edited to match
a fresh run.

**How it is measured** is methodology, and stays true over time.

**Measured now** is this run. The gap between the first and the third is the most
useful column in the report: it is where a landed fix shows up as a number.

Several already do. UTS #39 §5.3 Mixed Numbers was unimplemented when #777 was
filed and now reports 75 of 75 numbering systems. `has_bidi_conflict` was neutral
to 1,786 of 3,018 strong-RTL code points under #773 and now reaches all 3,018.

## Missing artifacts skip, and say so

An absent corpus is not a passing corpus. A suite that cannot find its artifact
returns `SKIPPED` with the environment variable to set, and the report lists every
one under **Not run**. Nothing is inferred from a benchmark that did not execute.

Most academic corpora need a manual download — copying an attack corpus into this
repository would make it disarm's corpus, and a corpus disarm owns is a corpus
disarm can be tuned against. Point each suite at its data:

```bash
export DISARM_META_CACHE=~/disarm-benchmarks          # where suites look by default
export DISARM_META_BAD_CHARACTERS=~/corpora/bad_characters.jsonl
export DISARM_META_GCG=~/corpora/gcg_evaluated_data.jsonl
python -m benchmarks.meta --run --only-available
```

Loaders accept JSONL or delimited files with a header. A text column is required
and a clean/reference column turns on recovery scoring; both are matched
case-insensitively against the name lists in `suites/academic.py`, so most
upstream releases load without conversion.

## Drift

```bash
python -m benchmarks.meta --run --only-available --update-baseline
python -m benchmarks.meta --run --only-available          # later: reports what moved
```

The harness reports and does not gate. A moved number never fails a run; only a
suite that threw does, because that is a harness defect rather than a result.

Baselines are keyed by suite *and* population. A ratio measured over 4,000 code
points and one measured over 150,000 are not comparable, and the report marks such
a row rather than subtracting it. `--limit` samples by stride rather than
truncating, because the first N code points of any sorted domain are Latin, Greek
and Cyrillic — the best-covered part of every table here — and a quick pass that
samples only those would disagree with a full one for the wrong reason.

## Adding a benchmark

A suite is one class: set `name`, `family`, `availability` and a `Provenance`, then
implement `measure()`. Subclass `SuiteBase` for the availability, timing and skip
handling, or `AttackCorpusSuite` if the artifact is a corpus of perturbed text.

The `Provenance` is the part that matters. It carries the citation, the pinned
version, the licence, the issues the benchmark identified, and `external`. A suite
whose right answer only disarm can supply belongs in `introspective` with
`external=False`.
