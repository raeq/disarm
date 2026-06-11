# Performance

This page exists for the skeptical reader who wants to know whether disarm's
performance numbers are real. Every claim here is one of three things:

1. **A relative claim** (disarm is *N×* faster than library *X*) — asserted as
   an executed inequality with a deliberately loose floor, so the doc-test
   proves *category and direction* on any CI hardware without flaking. The
   precise published figure links to its recorded measurement.
2. **An absolute number** (ns/call, chars/sec) — never asserted (it is
   hardware-dependent), only published *with its full environment fingerprint*
   and labelled non-comparable across machines.
3. **A correctness claim** — asserted directly.

The executable blocks on this page run in CI (Sybil, #154). If a comparator
library is not installed in the docs environment, its block **skips loudly** —
it never passes silently.

## Credit

disarm measures itself against [Unidecode](https://pypi.org/project/Unidecode/)
and its lineage — Sean M. Burke's original Perl `Text::Unidecode` and Tomaž
Šolc's Python port — along with
[text-unidecode](https://pypi.org/project/text-unidecode/),
[anyascii](https://pypi.org/project/anyascii/),
[python-slugify](https://pypi.org/project/python-slugify/), and
[pathvalidate](https://pypi.org/project/pathvalidate/). These projects built the
transliteration category and carried the industry for two decades. They are
reference points, not targets. Where disarm is faster, it is faster while
doing a deliberately *different* and larger job (see
[Different scope, more work](#different-scope-more-work)); where a comparator's
context-free design is the right tool, that is a feature of its design, not a
deficiency. Nothing on this page is a criticism of the libraries it measures
against.

## The two regimes

disarm has two distinct performance stories, and conflating them is the most
common way to misread a transliteration benchmark:

- **Per-call (latency) regime** — one short field per call (a name, a title, a
  single record). Here the dominant cost is the Python→Rust boundary crossing,
  not the per-character work. disarm crosses that boundary exactly once and
  returns already-ASCII input as the original `str` object (#284, #277).
- **Per-character (throughput) regime** — documents from a few hundred bytes to
  a couple of megabytes. Here the dominant cost is the per-character table
  lookup, and disarm's compile-time flat-array tables (no hashing on lookup)
  do the work in Rust.

A short-string ratio and a throughput ratio measure different things; neither
number can be substituted for the other, and this page keeps them separate.

## Measurement policy

The defence of these numbers *is* the methodology, so it is stated up front:

- **Ratios are the durable claim; absolutes are presentation.** Only ratios are
  asserted in CI. Absolute ns/char-per-sec figures are published with a full
  hardware fingerprint and explicitly marked non-comparable across machines.
- **Margin policy for the executed floors.** Where this page's prose cites,
  say, "~15–21× faster short-string", the in-page assertion checks a far looser
  floor (for example `ratio > 4`). The gap is deliberate: a loose floor proves
  the *direction and order of magnitude* on unknown, possibly loaded CI hardware
  without ever flaking, while the precise figure is backed by a recorded
  measurement. Always round our own numbers **down** and comparators' numbers
  **up**; never the reverse.
- **Interleaved measurement.** Each executed block times disarm and the
  comparator back-to-back, repeatedly, and takes the **median** of the
  per-round ratios. Transient scheduler noise hits both sides and cancels in the
  ratio.
- **Pinned, hash-locked comparators.** CI installs the exact comparator versions
  in [`requirements/bench.txt`](https://github.com/raeq/disarm/blob/main/requirements/bench.txt)
  (`--require-hashes`). The published absolute figures are bucketed by CPU
  microarchitecture and recorded on the `perf-results` branch with the
  fingerprint below.
- **ftfy is never a transliterate-axis comparator.** ftfy is a mojibake
  *repairer/normaliser*, not a transliterator; it never appears in a
  transliterate ratio.

```python
# Shared setup for the executed blocks below. One namespace runs top-to-bottom.
import time
import statistics

from disarm import transliterate, slugify, sanitize_filename


def _timed(fn, arg, inner):
    """Wall-clock seconds for `inner` calls of fn(arg)."""
    start = time.perf_counter()
    for _ in range(inner):
        fn(arg)
    return time.perf_counter() - start


def speed_ratio(translit_fn, other_fn, arg, inner=4000, reps=5):
    """Median interleaved (other / disarm) time ratio: >1 means disarm is faster.

    Timing a whole batch of `inner` calls per span amortises perf_counter
    overhead to ~0; interleaving disarm and the comparator per round and
    taking the median across `reps` rounds cancels transient load. The constant
    perf_counter overhead that remains is added to both sides, which only
    *deflates* the ratio — so the floors asserted below are conservative.
    """
    ratios = []
    for _ in range(reps):
        t = _timed(translit_fn, arg, inner)
        o = _timed(other_fn, arg, inner)
        ratios.append(o / t)
    return statistics.median(ratios)
```

## Different scope, more work

Before any speed claim: disarm's `transliterate()` is not doing the same job
as a context-free transliterator. On every call it also consults the language
override tables, applies the requested error-handling mode, checks the
replacement registry, and (optionally) runs script detection. The output
reflects that extra work — and it is asserted here, not asserted-by-arrow:

```python
# Language-specific romanisation (the default table alone does not do this).
assert transliterate("Ärger", lang="de") == "Aerger"   # German ä -> ae
assert transliterate("Київ", lang="uk") == "Kyiv"      # Ukrainian romanisation
assert transliterate("Київ") == "Kiyiv"                # default differs from uk

# Error-handling modes are part of the per-call contract.
assert transliterate("AB", errors="ignore") == "AB"
assert transliterate("AB", errors="replace") == "A[?]B"
try:
    transliterate("AB", errors="strict")
    raise AssertionError("strict mode should have raised")
except Exception as exc:
    assert type(exc).__name__ == "DisarmError"
```

A context-free library produces one fixed output; disarm's per-call price buys
language tables, error modes, and a replacement registry. That is the "different
scope" the speed numbers should be read against — not a like-for-like race.

## Transliteration vs Unidecode

### Per-call (short strings)

The per-call regime: short mixed-script fields, the common case for
record-by-record processing. The published figure is **~15–21× faster than
Unidecode** across scripts (Latin highest, Cyrillic lowest); the assertion uses
a loose floor.

```python
try:
    from unidecode import unidecode
except ImportError:                       # docs env without the pinned comparator
    import pytest
    pytest.skip("Unidecode not installed; see requirements/bench.txt")

short = "Ärger café Москва Ελληνικά"     # mixed Latin diacritics, Cyrillic, Greek
ratio = speed_ratio(transliterate, unidecode, short)
# Published: ~15-21x short-string. Loose floor proves direction without flaking.
assert ratio > 4, f"expected disarm clearly faster short-string, got {ratio:.1f}x"
```

### Throughput (document scale)

The per-character regime: a multi-kilobyte document processed in one call.
Published figure is **~38× faster than Unidecode on Latin** at document scale
(and **~15× on Cyrillic**).

```python
try:
    from unidecode import unidecode   # re-import: each block is self-contained,
except ImportError:                   # so a skipped earlier block never strands us
    import pytest
    pytest.skip("Unidecode not installed; see requirements/bench.txt")

document = ("Schöne Grüße aus München. Café au lait. "
            "Здравствуйте, мир. Ελληνικά κείμενα. ") * 40   # ~3 KB, mixed
ratio = speed_ratio(transliterate, unidecode, document, inner=400, reps=5)
# Published: ~38x Latin / ~15x Cyrillic at document scale. Loose floor here.
assert ratio > 6, f"expected disarm far faster at document scale, got {ratio:.1f}x"
```

### Unidecode's own benchmark

disarm also wins **all four cells of Unidecode's own benchmark** — the
cross-product of Unidecode's two API entry points
(`unidecode_expect_ascii`, `unidecode_expect_nonascii`) and its two sample
inputs. The clean-room replication is in
[`benchmarks/bench_unidecode_own.py`](https://github.com/raeq/disarm/blob/main/benchmarks/bench_unidecode_own.py)
(the GPL benchmark file itself is not copied — only the methodology). The sweep
below was recorded in
[PR #284](https://github.com/raeq/disarm/pull/284) and
[PR #281](https://github.com/raeq/disarm/pull/281) on an AMD EPYC 7763 CI
bucket (the fields you would record for your own run are described under
[Absolute numbers](#absolute-numbers-illustrative-and-fingerprinted)):

| Cell | Ratio (Unidecode time / disarm time) |
|---|---|
| `expect_ascii` / ASCII input | **1.43×** (71.0 ns vs 101.2 ns) |
| `expect_ascii` / non-ASCII input | **9.71×** |
| `expect_nonascii` / ASCII input | **22.67×** |
| `expect_nonascii` / non-ASCII input | **6.66×** |

The narrowest cell (1.43×) is Unidecode's strongest case — pure-ASCII text
through its ASCII-optimised entry point — and disarm still wins it via the
return-original-object fast path. These are recorded absolutes; they are *not*
asserted in CI (the four-cell pass/fail is checked by the benchmark script, not
by this page). Re-run them with `python benchmarks/bench_unidecode_own.py`.

## ASCII passthrough

Already-ASCII input still crosses into Rust once (`transliterate()` does not
short-circuit on the Python side — the validation and the borrowed fast path
live in Rust); Rust then returns the input as the *same* Python `str` object via
a borrowed `Cow`, with no copy and no allocation (#277 lever 4, #284). The
object-identity property is asserted directly:

```python
s = "plain ascii text 12345"
assert transliterate(s) is s            # same object, not just an equal copy
```

## Slugification vs python-slugify

Published figure is **~10–24× faster than python-slugify**, the advantage
growing with input length.

```python
try:
    from slugify import slugify as py_slugify
except ImportError:
    import pytest
    pytest.skip("python-slugify not installed; see requirements/bench.txt")

title = "Hello, World! Crème Brûlée & Café — a Long-ish Title for Slugging"
ratio = speed_ratio(slugify, py_slugify, title)
assert ratio > 3, f"expected disarm slugify clearly faster, got {ratio:.1f}x"
# Both produce an ASCII slug; disarm also transliterates the accented words.
assert slugify("Crème Brûlée") == "creme-brulee"
```

## Filename sanitisation vs pathvalidate

Published figure is **~10–16× faster than pathvalidate**, while also
transliterating, collapsing dot-sequences, and sanitising extensions.

```python
try:
    from pathvalidate import sanitize_filename as pv_sanitize
except ImportError:
    import pytest
    pytest.skip("pathvalidate not installed; see requirements/bench.txt")

name = "my<illegal>:name?.txt"
ratio = speed_ratio(sanitize_filename, pv_sanitize, name)
assert ratio > 3, f"expected disarm sanitize_filename clearly faster, got {ratio:.1f}x"
assert sanitize_filename(name) == "my_illegal_name.txt"
```

## Batch API

`transliterate()`, `slugify()`, `normalize()`, and `strip_accents()` accept a
`list[str]` and process the whole list in a single boundary crossing that
releases the GIL around the Rust compute loop. Its results are identical to a
loop, which is asserted; its *value* is not a raw in-process speedup:

```python
items = ["Café", "Москва", "Ελληνικά", "naïve", "Straße"] * 20   # 100 strings
assert transliterate(items) == [transliterate(x) for x in items]
```

An honest note on the in-process case: the batch advantage over a Python loop is
proportional to how expensive the boundary crossing is *relative to the work
done*. Once the single-crossing optimisation (#284) brought a scalar call down
to roughly 70 ns, an in-process batch of short strings is at rough parity with —
and on a fast single core can be marginally slower than — a plain Python loop,
because the list snapshot and chunking have their own cost. The batch API's
durable advantages are therefore (1) the **single GIL-released crossing**, which
lets multiple threads transliterate large batches in true parallel (see
[Why it is fast](#why-it-is-fast-internals)), and (2) not re-paying per-call
setup on platforms or interpreters where the boundary crossing is comparatively
expensive. Reach for it for thread-parallel and high-volume work, not as a
guaranteed speedup on a single core.

## Where disarm is slower

Visible admission of losses is the strongest defence against cherry-picking, so
this section is deliberate and not buried.

- **NFC/NFKC normalisation vs `unicodedata.normalize`.** CPython's
  `unicodedata` is a C extension operating directly on Python's internal string
  buffer with zero-copy fast paths. For a single string it is **faster** than
  disarm, which crosses into Rust. disarm's `normalize()` exists for
  *consistency*, not speed: it uses one Unicode version (16.0) across every code
  path — single string, list, and pipelines — so results never differ between
  CPython's bundled Unicode version and the Rust crate's. That consistency is
  the deliberate tradeoff.
- **Case folding vs `str.casefold()`.** `str.casefold()` is a zero-allocation C
  builtin; disarm's `fold_case()` is within a small factor at the Python level
  and is dominated by the boundary-crossing cost, not the fold itself. Use
  `str.casefold()` when you only need CPython's Unicode version and a single
  string.

These losses are real and against C builtins that disarm cannot and does not
try to beat. The functional behaviour is still asserted:

```python
from disarm import fold_case, strip_accents
assert fold_case("Straße") == "strasse"           # full Unicode case folding
assert strip_accents("café résumé") == "cafe resume"
```

## Absolute numbers (illustrative and fingerprinted)

Absolute figures are **not comparable across hardware** and are never asserted.
They are meaningful only alongside the environment that produced them. A full
fingerprint — CPU microarchitecture, CPython version and build, the exact
comparator versions, rustc version, git commit, and date — is emitted by:

```bash
python scripts/perf_fingerprint.py --json
```

The short-string figures below were recorded in
[PR #284](https://github.com/raeq/disarm/pull/284) and
[PR #281](https://github.com/raeq/disarm/pull/281) on an AMD EPYC 7763 CI
bucket (CPython 3.12, pinned comparators from `requirements/bench.txt`,
median-of-7 interleaved). They are reproduced here to illustrate the per-call
regime; **your numbers will differ**, and the only durable claims are the ratios
asserted earlier on this page.

| Input (per call) | vs Unidecode |
|---|---|
| Latin diacritics (~70–85 chars) | **~21×** |
| Mixed scripts | **~17×** |
| Greek | **~15×** |
| Cyrillic | **~15×** |
| ASCII passthrough (~71 ns) | returns original object |

Document-scale throughput (same bucket): **~450M chars/sec** Latin
(**~38×** Unidecode), **~106M chars/sec** Cyrillic (**~15×**), slugify
**~712K slugs/sec** (**~10–24×** python-slugify). These match the figures quoted
in the project README; both derive from the same recorded measurements. To
record a fresh, fully fingerprinted run, execute the `benchmarks/` scripts on a
tuned machine and append the `perf_fingerprint.py --json` record alongside the
results.

## Why it is fast (internals)

The speed comes from data layout decided at compile time and a single, cheap
boundary crossing — not from cutting memory-safety corners
(`unsafe_code = "forbid"` is enforced crate-wide):

- **Flat BMP array, no hashing on lookup.** The default Unicode→ASCII table for
  U+0080–U+FFFF is emitted by `build.rs` as a compile-time two-level page-table +
  interned-blob structure indexed by codepoint; a lookup is a bounds check and a
  couple of array reads, never a hash probe. It lives in `.rodata` and is paged
  in on demand (`src/tables/mod.rs`, `build.rs`).
- **Zero runtime data loading.** Every table — transliteration, confusables,
  emoji, case folding, Hangul — is generated at build time into the binary.
  There is no startup parse and no data file to ship.
- **One Python→Rust crossing with Rust-side defaults.** The keyword defaults are
  resolved in Rust, so a call crosses the FFI boundary exactly once (#284).
- **Borrowed `Cow` return.** Already-ASCII input returns the original `str`
  object via a borrowed `Cow`, with no allocation (#277 lever 4).
- **Zero-copy UTF-8 extraction.** Input is read with `PyUnicode_AsUTF8AndSize`
  on the abi3-py310 floor — no intermediate copy (#277 lever 1).
- **Atomic no-replacements flag.** The common case (no registered replacements)
  is a single atomic load (`Ordering::Acquire`, paired with the `Release` store
  in the mutators), skipping the replacement-registry lock entirely
  (`src/tables/mod.rs`).
- **GIL released across batch loops.** List inputs release the GIL around the
  pure-Rust compute loop, so multiple Python threads run their Rust work in
  parallel (#70).
- **Range-dispatch before the table.** CJK and Hangul ranges dispatch directly
  to their dedicated romanisers, skipping a probe of the general table
  (`src/transliterate.rs`).

## Integrity checklist

What this page does to keep its numbers honest:

- Comparator versions are pinned and hash-locked
  (`requirements/bench.txt`, installed with `--require-hashes`).
- Measurement is interleaved; noise cancels in the ratio; medians are reported.
- Published absolutes are bucketed by CPU microarchitecture and recorded on the
  public `perf-results` branch with a full fingerprint.
- Our numbers are rounded down; comparators' numbers are rounded up.
- Executed assertions use loose floors with the margin policy stated above.
- Reproduction is one install + one command (below).

What this page does **not** claim:

- No cross-hardware absolute comparisons. A ns figure on one machine says
  nothing about another.
- No "fastest possible" claim. disarm is faster than the pure-Python
  comparators measured here, for the workloads measured here — nothing broader.
- No claims about workloads not measured on this page.
- No transliterate-axis comparison against ftfy (it is a normaliser).

## Reproducing these numbers

```bash
# Install disarm with the pinned, hash-locked comparator set
pip install disarm[bench]

# Short-string ratios (interleaved, median-of-7), per script
python benchmarks/bench_ratio.py

# Unidecode's own four-cell benchmark
python benchmarks/bench_unidecode_own.py

# Document-scale throughput vs Unidecode/text-unidecode/anyascii
python benchmarks/bench_vs_unidecode.py

# Record the environment fingerprint your numbers belong to
python scripts/perf_fingerprint.py --json
```

The executed blocks on this page are run in CI by the Sybil doc-test harness
(#154); the `benchmarks/` scripts produce the recorded figures that the prose
cites. To regenerate this page's recorded absolutes, run the benchmarks on a
tuned machine (`python -m pyperf system tune` on Linux) and append the
fingerprinted record to the `perf-results` branch.
