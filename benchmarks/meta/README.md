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
CVE, a released tokenizer, a third-party labelled benchmark, or a practitioner's
published tool. The harness
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

Detectors built for the smuggling question, considered in #1164. Each is code the bench
venv runs, so each was read before it was pinned.

| detector | decision | why |
|---|---|---|
| `unicode-smuggling-guard` 1.3.0 | a subject | MIT, no dependencies. Its one `subprocess` call lists a repository's files and is not on the `scan` path |
| `glyphguard` 0.3.0 | a subject | Apache-2.0, no dependencies, and it ships a sanitizer too. The same is true of its `subprocess` call |
| `llm-guard` 0.3.16 | left out | `torch`, `transformers` and `presidio-*` for one `InvisibleText` scanner, which is too much installed code for one column |
| `RootVandal/palisade` | left out | git only, and its labelled rows are already `palisade-labels`. PyPI's `palisade` is a different project under a commercial licence, so that name is never pinned |
| `ghostchars` | left out | Node, which needs its own sandboxed path. npm's package names `ghostchars/ghostchars`, and the studies in `ghostchars-labels` live at `antonsoo/ghostchars`, and the two have not been shown to be one project |
| `unsmuggle` | left out | Node, for the same reason |
| `smugglecheck` | not a candidate | 404 on npm under that name |

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

`gutenberg-benign` is no longer the only false-positive axis over ordinary text. It is
manual pre-1923 prose and never meets the punctuation people type into a prompt, so
`benign-controls` reports the sets practitioner repositories label regular or benign, each one
alone. A rate there is a ceiling, because such a label does not say free of obfuscation, and it
stands beside what the same detector does with a planted `U+200B`, because a detector that never
fires reads perfect on a false-positive rate alone.

## The seven external families, and the introspective tier

| family | anchor | examples |
|---|---|---|
| `normative` | a table that *defines* the right answer | UTS #39 §5.1/§5.3, UCD Scripts.txt, UAX #9, UAX #29, ICANN LGR, CLDR |
| `cve` | a published vulnerability's own vector | CVE-2026-17084's stringprep B.3 delta, the Trojan Source PoC files |
| `academic` | a corpus released with a paper | Bad Characters, XOXO, GCG suffixes, GAversary, ESTI, arXiv:2405.14490 |
| `dataset` | a public corpus | BitAbuse, YouTube-Spam, TREC-2007, MeAJOR, benign Gutenberg prose |
| `model` | a released model artifact | chat-template delimiters read from published `tokenizer.json` files |
| `comparator` | a third-party labelled benchmark or rival tool | `confusable-bench.v1`, confusable-vision, untrace |
| `practitioner` | a tool or repository published outside the literature | P4RS3LT0NGV3's transforms, garak's escape payloads, L1B3RT4S as fixtures |

Tools differ in what they can be asked. A key-builder question put to a
transliterator has no answer, and a suite asking two separable questions — is it
detected, is it undone — lets a subject answer the half it has. The half it
cannot answer is omitted, never reported as zero: `confusable-homoglyphs` detects
and does not transform, and `recovered: 0` for it would read as total failure
rather than as a question it was never asked.

`introspective` is a separate tier and is not a benchmark. Its sweeps run over the
UCD code-point domain, which is external, but disarm is the only oracle for what
the answer should be — so a number moving there proves nothing on its own. They
are registered because dropping them would leave a hole in the 0.15.0 record, and
because they catch silent regressions. They are excluded unless you pass
`--include-introspective`, and they never enter an external total.

## Findings are historical

`Provenance.finding` records what a benchmark measured **during the 0.15.0 cycle**. It is
not a description of the library today, and it is never edited to match a fresh run — the
distance between it and the current table is the report's most useful column, and editing
the finding destroys exactly that. When a suite gains a policy, a surface or a subject,
the *run* moves and the finding stays where it is.

`notes` is the opposite field: methodology, not results, so it has to stay true as the
library changes. A number belongs in `notes` only when it describes the corpus or the
method — the paper's own carrier count, a rival tool's score — never disarm's.

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

## A leaderboard, and why it has no composite

`--leaderboard` orders the subjects without averaging the benchmarks into one
number. Every step is a named method: corrected item-total correlation for the
axis weights it reports as a diagnosis (classical test theory), item parcelling within a suite so seven
related numbers are not seven votes, Bradley-Terry by Hunter's MM algorithm for a
rank that uses only pairwise order, Cronbach's alpha and Kendall's W for whether
the battery is coherent, and bootstrap intervals over the benchmark set.

Item Response Theory is the method of record for this and is deliberately not
fitted: 2PL estimates from single-digit respondents are not stable, and fitting
one would look more rigorous while being less so.

**Each benchmark is also ranked on its own**, and those rankings always stand.
Averaging benchmarks requires them to measure one construct first; ranking within
a single benchmark requires nothing beyond that benchmark, so the per-benchmark
tables are the result. A subject that answered only part of a benchmark is listed
in that benchmark's table but not ranked in it. Coverage across the battery is
counted in benchmarks, never in axes, so a tool cannot become "partial" for
lacking a detector.

**A suite that asks one cohort more questions yields more than one axis.**
`mcp-tag-block-concealment` asks thirteen subjects whether the concealed payload
was removed, and the two with a detector two further questions besides. Averaged
into one parcel, the detector's mean over its answers was set against a
transliterator's single answer and could not win: a key answered by two subjects
is standardised on a sample of two, where the sample standard deviation caps |z|
at 0.707, below what a thirteen-subject key reaches. `disarm` gave the best
answer in the field to every question that suite asks and ranked fifth on it.
Measurements are therefore grouped by *which subjects answered them* and each
group becomes its own axis, named for its measurements — so a detector is ranked
against detectors and a transform against transforms, and a tool that answers
both appears on both.

**A detector scored on a plain-text control is scored for silence.** T1 in that
suite is the concealed instruction written out in printable ASCII; nothing is
hidden in it. A Unicode detector that fires there is reporting the words, so the
key is directed lower-is-better, the same orientation the invisible-carrier
comparator uses for its own `controls_false_positive`. Scored the other way it
made correct silence a failure and counted a false positive as coverage.

**No composite is published, whatever the run.** A composite assumes the
benchmarks measure a single construct, which this battery is not built to do:
coverage and cost are deliberately opposed, so a tool that folds more will alter
more. The weighting makes that fatal rather than merely uncertain. An axis's
weight is its corrected item-total correlation, which goes negative for an axis
that opposes the rest, and the clamp at zero deletes it — so on a battery built
from axes that trade against each other, the opposed pole is exactly what the
weighting removes. The composite ranked `null-baseline`, which deletes all input,
above real libraries. It used to be printed beneath its own blockers; a number
carried under a caveat is still the number a reader quotes, so the report now
prints the *Axis weights* table instead — what the composite would have weighted,
and which axes it deleted. Bradley-Terry, which uses only pairwise order and so
escapes the clamp, fails the same control for a different reason: most axes here
reward removal, so a delete-everything baseline genuinely beats a pure normalizer
on them. The control check covers every aggregate, not the composite alone.
Cronbach's alpha and Friedman's test on the rankings refuse an aggregation for
the same underlying reason — the benchmarks disagree about who is good.

What survives is **Pareto dominance**: a tool is on the frontier when no other
tool beats it on every axis at once. That needs no weighting and no common
construct, so it stands where an aggregate cannot. It yields a
partial order rather than a league table, which is the honest shape of a result
where two axes pull against each other.

Friedman's chi-square is k(n-1)W, so the report also prints how many benchmarks
the observed agreement would need to reach significance. More *tools* do not
help — they raise the degrees of freedom and so raise the bar. More *benchmarks*
do.

The interlock still runs, and it governs what is left. When the battery has too few
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

## What is not a benchmark

Mining paper lists produces more rejections than additions, and the reasons are
worth writing down so the same paper is not re-evaluated from scratch. Four
tests, applied in order:

**Is there an artifact?** A citation is not a benchmark. Check the abstract page,
GitHub, *and* `arxiv.org/src/` — the LaTeX bundle often carries the construction
when no dataset was released, which is where `mcp-tag-block-concealment`,
`rag-pull-invisibles`, `zero-width-stylometry` and `encoding-obfuscation` came
from. Only when nothing is published, and the construction is not specified
either, does a paper drop out here.

**Is it licensed?** Read the README, not just the licence field and a file named
LICENSE. `reverse-captcha-eval` declares MIT in prose and was wrongly excluded
once for having no licence file.

**Is it derivable?** Separate from licensing, and the reason the emoji cluster
split four ways to one. An unlicensed repository is not the end of the enquiry:
if the paper states the construction, the construction can be quoted and the
inputs taken from a normative source instead. `emoji-delimiter-segmentation`
is built that way — the repository behind arXiv:2411.01077 carries no licence in
either its metadata or its README, so nothing from it is used; the emoji set is
the UCD's `Emoji_Presentation` property and the carrier is the neutral ASCII pair
`damage` already uses. What cannot be recovered this way is an attack whose
vectors are a function of a trained model, which is what rules out HotFlip and
Emoti-Attack.

**Is it in scope?** Measure before judging. A jailbreak corpus written in valid
text has no Unicode signal to find, so scoring detection on it is a category
error — `jailbreakbench` is registered for what it *can* answer, which is what a
sanitizer costs on traffic it should not be defending against.

Rejected so far, with the reason:

| paper | reason |
|---|---|
| arXiv:1712.06751 (HotFlip) | ASCII alphabet; no released corpus; and the attack is white-box, so vectors cannot be derived without the model's gradients. Its descendants `bad-characters` and `rag-pull-invisibles` carry the lineage into Unicode, and both are wired |
| arXiv:2406.18510 (WildTeaming) | zero mentions of unicode, homoglyph, zero-width, invisible or confusable; a third valid-text jailbreak corpus duplicates `jailbreakbench` |
| arXiv:2512.13325 (Unicode watermarking) | source bundle carries no construction — three mentions of "zero-width" and no scheme |
| arXiv:2604.10271 (Doppelgänger Injection) | on topic, but isolated examples only: no table, no listing, so the substitution mapping would be ours rather than the paper's |
| arXiv:2601.00936, arXiv:2608.18164 (emoji jailbreaking) | the 50-prompt set is explicitly withheld, and "emoji stuffing"/"emoji chaining" are described qualitatively — no mapping, no algorithm |
| arXiv:2509.11141 (When 😊 Turns Hostile) | supplementary code is claimed but no URL is given; the craft step needs the target model's gradients |
| arXiv:2502.17392 (Emoti-Attack) | no artifact, and the sequence generator is a trained component — reimplementing it means retraining it |

## Practitioner sources

The paper lists above left a blind spot. People who publish attack tooling on GitHub
mostly do not write papers, so a search of the literature never reaches them, and this
registry named none of them until this tier existed. When you look for a benchmark,
search offensive tools and repositories as well as arXiv, and say which you searched.

A large following does not make a source a benchmark, so the tier has four rules.

**A known answer scores.** A published transform applied to text we chose, or a payload
placed inside a known cover, fixes the answer before the subject runs. `_KnownAnswerSuite`
is the base class for these.

**An unlabelled corpus stays a fixture.** Nothing outside disarm says what the right output
is, so every number is a census. It can catch a regression and it cannot reach a ranking.
`_FixtureSuite` turns a directed measurement into an error.
It can still answer three questions that need no label: whether a surface raises, whether its
output is a fixed point, and whether a sanitizer's output reports what its input did not. None
of them can rank a tool, and all of them can catch a regression. `label-free-invariants` asks
them over whichever of its corpora are provisioned.

**The delete-everything control runs on every run**, including a run that scores only
disarm, rather than only when `--subject all` happens to include `null-baseline`. A
known-answer suite whose control scores anything reports an error in place of its numbers.
A fixture reports the control beside its own figures, because there it does score: deleting
everything leaves no carriers and makes every line converge, which is the reason it is a
fixture.

**A copyleft source is cached from a pinned commit and never vendored.** No text from a
corpus reaches a report, an issue or a `Provenance` field. These suites print counts and the
names of transforms.

`p4rs3lt0ngv3-transforms` is the one suite here that executes third-party code, and it does
so only after three checks. The tree under `src/transformers` must match a pinned digest,
which is held against the extracted files because GitHub does not promise a stable tarball.
Node must be 25 or later, the first release whose permission model also denies the network.
The code then runs under `node --permission`, with read access to that tree and nothing else:
no other file, no write, no child process and no network. The `vm` context in
`suites/practitioner_driver.js` only keeps the loader simple and is not the boundary, and
`tests/test_meta_benchmark_practitioner.py` escapes from it on purpose to show that. If a check
fails, the suite reports SKIPPED with the reason. Its classes come from upstream's directory
names and were fixed before any score was read; do not move one to improve a number.

Read so far, so the next search starts from here:

| source | licence | status | why |
|---|---|---|---|
| P4RS3LT0NGV3 | AGPL-3.0 per `LICENSE` | `p4rs3lt0ngv3-transforms` | a generator: of 222 transforms, 35 are scored, 143 are counted and 44 are text utilities left out |
| garak `resources/ansi.py` | Apache-2.0 | `garak-ansi-escapes` | a payload list that ships the tokens to detect it by |
| L1B3RT4S | AGPL-3.0 | `l1b3rt4s-fixtures` | unlabelled: 169 of 182 sections carry no Unicode obfuscation |
| jailbreak_llms, FuzzyAI, palisade, Arc PI Taxonomy | MIT, Apache-2.0, MIT, CC-BY-4.0 | `label-free-invariants` | 22,897 texts that need no label for three contract questions, pinned by commit and digest |
| jailbreak_llms regular, FuzzyAI benign, palisade benign, spikee false-positive seeds | MIT, Apache-2.0, MIT, Apache-2.0 | `benign-controls` | text people type into a model, reported per set with `null-baseline` alongside |
| Arc PI Taxonomy | CC-BY-4.0 | `arcanum-taxonomy` | 63 named evasions in three classes fixed in the source; it holds no covers, so it says seen and changed and not recovered |
| ghostchars `studies/` | MIT | `ghostchars-labels` | another detector's hand labels and fixtures, including the class of text a detector gets wrong; the rows were selected by that detector firing, so no rate here is prevalence |
| garak `badchars` | Apache-2.0 | not a suite | follows the Bad Characters paper, already wired as `bad-characters` |
| garak `encoding`, `smuggling` at `4b7761c2` | Apache-2.0 | `token-smuggling-constructions` | rebuilt and not imported: Python has no sandbox like Node's and the constructions are short; its zalgo and homoglyph probes repeat `p4rs3lt0ngv3-transforms` |
| PyRIT at `d3446e04` | MIT | `token-smuggling-constructions` | about 100 converters behind about 50 dependencies, so seven are rebuilt from their docstrings and none is imported |
| promptfoo at `5582f347` | MIT | `promptfoo-literal-maps` | two object literals with a known answer per row, read without running them; the rest holds no answer a suite can score |
| Augustus at `84487332` | Apache-2.0 | `augustus-known-answers` | Go test tables read as data: 121 pairs and 12 rebuilt zalgo rows, each table classed in the source before a score. No Go runs. The sneaky-bits framing is the unpadded one, and `leet` ran with no lexicon. |
| palisade at `4d1728ac` | MIT | `palisade-labels` | 56 labelled rows: its three Unicode attacks are the score, its 29 ASCII attacks a census in no rate |
| spikee at `8f8e9ad3` | Apache-2.0 | `spikee-seed-census` | 640 seed rows in seven sets, counted per file and never printed. The recorded guardrail results under `results/v0.1` are not comparable; the suite's notes say why |
| pikit at `6a90c063` | MIT | no suite | 13 attack classes beside its channels. Recorded so that the next reader starts here, and not scored |
| AI-Infra-Guard at `851e3f29` | Apache-2.0 | no suite | 13 encoder functions in `skills/aig-agent-redteam/modules/mutation-attack/scripts/encodings.py`, and a scenario set at `Research/forge_bench/scenarios/v0.3_intact_control` not yet read. Recorded and not scored |
| ST3GG `examples/` at `35f8b2b8` | AGPL-3.0 | `st3gg-text-examples` | eleven text techniques with a cover its generator fixes; its `README.md` hides 122 zero-width characters and no suite reads it |
| CL4R1T4S | none checked | not read | holds system prompts, judged from its description only |
| FlipAttack at `c53880b4` | MIT | read and left out | reordered words and letters: ordinary ASCII, named in `THREAT_MODEL.md`'s out-of-scope entry |
| CipherChat at `6fce7891` | MIT | read and left out | classical ciphers and character codes: ordinary ASCII, named in the same entry |
| ArtPrompt at `6eb86644` | MIT | read and left out | ASCII art, whose 16,424 ViTC rows hold no non-ASCII; named in the same entry |
| BitBypass at `9dcdba5a` | MIT | read and left out | binary spelled in ASCII; named in the same entry |

## Adding a benchmark

A suite is one class: set `name`, `family`, `availability` and a `Provenance`, then
implement `measure()`. Subclass `SuiteBase` for the availability, timing and skip
handling, or `AttackCorpusSuite` if the artifact is a corpus of perturbed text.

The `Provenance` is the part that matters. It carries the citation, the pinned
version, the licence, the issues the benchmark identified, and `external`. A suite
whose right answer only disarm can supply belongs in `introspective` with
`external=False`. A practitioner suite also declares its `evidence`, and subclasses
`_KnownAnswerSuite` or `_FixtureSuite` to match.
