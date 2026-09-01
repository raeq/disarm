# The meta-benchmark

One harness over every externally produced benchmark the 0.15.0 cycle used to find
and verify a defect. It runs `n` of `m`, consolidates the results into one report,
and compares them against a committed baseline.

```bash
python -m benchmarks.meta --list                       # show m, and what is runnable
python -m benchmarks.meta --list-subjects              # show the tools under test
python -m benchmarks.meta --run --only-available       # run what the machine has
python -m benchmarks.meta --run --subject all          # every tool, plus the controls
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

## Versions are part of a subject's identity

A subject is `name@version`, never a bare name. Two builds of one tool are two
competitors — `disarm@0.14.1` against `disarm@0.15.0` is the comparison most worth
making here — and keying on the name alone would let them overwrite each other in
the baseline, share a column, and be averaged together in the leaderboard. Every
rendered identity carries its version, and a test enforces that.

A compiled extension cannot be imported twice in one process, so two builds
cannot be live at once. Measure each in its own run and merge:

```bash
python -m benchmarks.meta --run --json v0141.json      # in a v0.14.1 worktree
python -m benchmarks.meta --run --merge v0141.json --leaderboard
```

## More than one tool

A benchmark that only scores one library tells you what that library does, not
whether the number is good. `--subject` runs the same suites against the pinned
comparator environment in `requirements/bench.txt` — ftfy, unidecode,
text-unidecode, anyascii, decancer — plus CPython's own normalization as the
floor.

Not every suite fits every tool. A key-builder question put to a transliterator
has no answer, so those pairs report SKIPPED with the reason rather than a zero;
zeros read as results. Suites that measure a disarm-specific surface set
`MULTI_SUBJECT = False`.

Two subjects are **controls**, not candidates:

`null-baseline` deletes everything. It scores perfectly on any naive coverage
metric, because both sides of every comparison become identical — and it was the
top-scoring subject here until collisions began requiring a non-empty shared
form. It stays in the roster because a control that is meant to fail is the only
thing that proves a metric *can* fail.

`identity` changes nothing. It is the floor a tool has to beat on coverage while
staying near it on cost, and it stops a do-nothing tool reading as a safe one.

A control is a reference line and never a competitor. It is listed with its
value, and it can neither hold a rank nor be marked as the best cell in a row —
`identity` wins any "do not alter wrongly" row by never altering anything, and
`null-baseline` wins any "do not leave it unfolded" row by leaving nothing at
all. Marking either as the winner would put the degenerate answer forward as the
target, which is the same failure the non-empty collision rule fixed, resurfacing
one layer up in the report.

Never quote a control as a comparator.

## The other direction

Every coverage score has a degenerate solution, so no coverage number here is
reported alone. `corruption-cost` measures what a tool does to text that needed
nothing: code points destroyed, characters retained, injectivity (distinct
outputs per distinct input), and alteration of pure-ASCII text that has nothing
to fix. Labelled corpora get this for free — their `clean` column is, by the
corpus author's definition, text needing no repair, so anything a surface does to
it is cost.

Two rules keep that fair. **Both ends, always**: the costliest surface and the
gentlest are reported together with their names, because quoting only the worst
judges a library by an entry point nobody has to call, and quoting only the best
hides a destructive default. **Collapsing surfaces are separated**: `sort_key`
and `catalog_key` are many-to-one by contract — that is what makes two spellings
of one thing compare equal — so they are reported apart from text surfaces.
Scoring them together would make a library look destructive for doing its job,
and would rank a tool with no key builder at all as the safer one.

## The five external families, and the sixth tier

| family | anchor | examples |
|---|---|---|
| `normative` | a table that *defines* the right answer | UTS #39 §5.1/§5.3, UCD Scripts.txt, UAX #9, UAX #29, ICANN LGR, CLDR |
| `cve` | a published vulnerability's own vector | CVE-2026-17084's stringprep B.3 delta, the Trojan Source PoC files |
| `academic` | a corpus released with a paper | Bad Characters, XOXO, GCG suffixes, GAversary, ESTI, arXiv:2405.14490 |
| `dataset` | a public corpus | BitAbuse, YouTube-Spam, TREC-2007, MeAJOR, benign Gutenberg prose |
| `model` | a released model artifact | chat-template delimiters read from published `tokenizer.json` files |
| `comparator` | a third-party labelled benchmark or rival tool | `confusable-bench.v1`, confusable-vision, untrace |

Tools differ in what they can be asked. A key-builder question put to a
transliterator has no answer, and a suite asking two separable questions — is it
detected, is it undone — lets a subject answer the half it has. The half it
cannot answer is omitted, never reported as zero: `confusable-homoglyphs` detects
and does not transform, and `recovered: 0` for it would read as total failure
rather than as a question it was never asked.

`introspective` is the sixth tier and is not a benchmark. Its sweeps run over the
UCD code-point domain, which is external, but disarm is the only oracle for what
the answer should be — so a number moving there proves nothing on its own. They
are registered because dropping them would leave a hole in the 0.15.0 record, and
because they catch silent regressions. They are excluded unless you pass
`--include-introspective`, and they never enter an external total.

## Reproductions

A suite normally *generalises* its issue: the published script probed seven
cases, the suite sweeps the domain. That makes the sweep stronger and the
finding/now comparison meaningless, because the two numbers answer different
questions. So each suite also recomputes the gist's exact quantity, pinned to the
value that gist printed.

This is not decoration. The `#719` census reports 261 code points via NFKC and
232 via the confusable fold; a sweep with a looser punctuation set, a bare
detection probe and an assigned-only domain reported 266 and 253 — a difference
in method that reads as a change in behaviour. `Reproduction.matches` is the only
thing that licenses reading a finding and a measurement as a before/after, and
the report says so in both directions.

Pinned values come from *executing* the published script on a v0.14.1 build, not
from its own docstring. The segmentation census header says `total=36`; running
it says `37`.

```bash
DISARM_META_REFERENCE_BUILD=0.14.1 \
    pytest tests/test_meta_benchmark.py -k reproductions --noconftest
```

`--noconftest` is required: `tests/conftest.py` imports post-0.14.1 API.

## What a run reports

Every run records its own method — subject and version, domain and size, the
predicates actually invoked, every parameter that moves a result, the sha256 of
the artifact read, and the Unicode/UCD versions in force. It is in the JSON
always and behind a Method fold in the Markdown. The 0.15.0 work produced several
figures for one question that differed only because a predicate moved, and
nothing recorded which was which.

Three more things per suite, kept apart on purpose:

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

## Provisioning

A run fetches what the selection needs before any suite executes, and leaves
untouched anything already on disk — an operator who placed a particular revision
keeps it. `--offline` never reaches the network; `--refresh` forces a re-fetch.
Every download is recorded with URL, sha256, size and licence in a manifest
beside the cache, so a figure can be traced to the bytes it came from. Nothing
fetched is ever committed.

Only upstreams that were *checked to exist* are wired. A suite with no verified
artifact stays manual and says so, rather than implying a download nobody has
demonstrated.

A present artifact that yields nothing is an error, not a score of zero. The
ICANN suite reported `blocked_pairs: 0` for a while, which reads as perfect
agreement rather than as a broken parser.

## A leaderboard, when the battery can carry one

`--leaderboard` ranks the subjects, weighting each benchmark by how well it
separates them. Every step is a named method: corrected item-total correlation
for the weights (classical test theory), item parcelling within a suite so seven
related numbers are not seven votes, Bradley-Terry by Hunter's MM algorithm for a
rank that uses only pairwise order, Cronbach's alpha and Kendall's W for whether
the battery is coherent, and bootstrap intervals over the benchmark set.

Item Response Theory is the method of record for this and is deliberately not
fitted: 2PL estimates from single-digit respondents are not stable, and fitting
one would look more rigorous while being less so.

**Each benchmark is also ranked on its own**, and those rankings always stand.
Averaging benchmarks requires them to measure one construct first; ranking within
a single benchmark requires nothing beyond that benchmark. When the composite is
blocked — which it currently is — the per-benchmark tables are the result. A
subject scored on materially less of the battery than the others is listed but
kept out of the composite ordering: one benchmark answered is not a better result
than four answered.

**The composite is not the only leaderboard, and it is the weakest one.** It
assumes the benchmarks measure a single construct, which this battery is not
built to do: coverage and cost are deliberately opposed, so a tool that folds
more will alter more. Cronbach's alpha correctly refuses it, and Friedman's test
on the rankings refuses a rank aggregation for the same underlying reason — the
benchmarks disagree about who is good.

What survives is **Pareto dominance**: a tool is on the frontier when no other
tool beats it on every axis at once. That needs no weighting and no common
construct, so it is publishable whenever the composite is not. It yields a
partial order rather than a league table, which is the honest shape of a result
where two axes pull against each other.

Friedman's chi-square is k(n-1)W, so the report also prints how many benchmarks
the observed agreement would need to reach significance. More *tools* do not
help — they raise the degrees of freedom and so raise the bar. More *benchmarks*
do.

The interlock matters more than the composite. When the battery has too few
directed benchmarks, or alpha falls below the conventional 0.70, or no two
subjects have non-overlapping intervals, no ranking is published and the reason
is printed. On the current battery all three fire. A leaderboard that cannot fail
is not a measurement.

## Drift

```bash
python -m benchmarks.meta --run --only-available --update-baseline
python -m benchmarks.meta --run --only-available          # later: reports what moved
```

The harness reports and does not gate. A moved number never fails a run; only a
suite that threw does, because that is a harness defect rather than a result.

Baselines are keyed by subject, suite *and* population, and record the Unicode
and confusables versions in force — a table bump moves normative numbers on its
own, and without that the drift row blames the tool. A ratio measured over 4,000 code
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
