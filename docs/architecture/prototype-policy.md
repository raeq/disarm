# Prototype policy: the I/l/1 and O/0 class

Three issues have asked the same question from different directions: #646, #648 and
#650. Each time it was re-argued from scratch. This page is the answer, so it stops
being re-argued.

The question: **TR39 gives `I`, `l` and `1` one prototype and `O`/`0` another. disarm keeps
all five distinct. Is that a defect, and if so where does the fix belong?**

## What disarm does today

All five stay distinct under every digit policy:

| | `numeric` | `tr39` | `preserve` |
|---|---|---|---|
| `I` `l` `1` `0` `O` | `I l 1 0 O` | `I l 1 0 O` | `I l 1 0 O` |

The capital-I family folds to `I`, not to TR39's lowercase `l`:

| code point | | TR39 | disarm |
|---|---|---|---|
| `U+FF29` | FULLWIDTH CAPITAL I | `l` | `I` |
| `U+0406` | CYRILLIC CAPITAL I | `l` | `I` |
| `U+0399` | GREEK CAPITAL IOTA | `l` | `I` |
| `U+2160` | ROMAN NUMERAL ONE | `l` | `I` |
| `U+1CCDE` | OUTLINED LATIN CAPITAL I | `l` | `I` |

The last two only since #734; before that the table contradicted itself inside a block.
That fix made the family consistent. It did not close the class. `paypaI` still survives
every fold, and `search_key("paypaI")` is `paypai`, which does not meet `paypal`.

## The decision

**1. The class is in scope, and it does not belong on an existing key builder.**

The cost turns almost entirely on *where* it runs. Measured over the 235,976 entries in
`/usr/share/dict/words`, counting only merges the class creates that case folding alone
did not:

| the class applied | extra merge groups | rate |
|---|---|---|
| before case folding (`I ≡ l ≡ 1`, `O ≡ 0`) | **6** | 0.003% |
| after case folding (`i ≡ l ≡ 1`, `o ≡ 0`) | **264** | 0.112% |

A factor of 44. The six are `i/l`, `ian/lan`, `io/lo`, `ione/lone`, `iowa/lowa`,
`iowan/lowan`, five of them proper nouns beginning with a capital I. The 264 are
ordinary vocabulary: `boiling`/`bolling`, `doit`/`dolt`, `broil`/`broll`,
`silverer`/`sliverer`.

Every existing key builder is in the expensive position. `catalog_key` folds case at step
3 and only then enters the romanization core, with `Step::Confusables("latin")` sitting
inside it between transliteration and accent stripping. The order is load-bearing rather
than incidental: `src/presets.rs:1005-1009` records that folding before transliteration is
what makes the preset idempotent (#419), and `:1011-1024` records why the three inner
steps run in the order they do. Reordering to make room for this class would reintroduce
that defect.

So the class needs a position no current builder offers, which makes it a separate
builder rather than a setting on one that exists.

**2. The letter half is a reasonable default there; the digit half is not.**

They differ by orders of magnitude and should be decided separately.

The letter half (`I ≡ l`, plus the I-family) costs six collisions in a quarter of a
million words. In a key whose output is never displayed and whose only job is to make two
confusable identifiers meet, that is cheap.

The digit half (`1 ≡ l`, `0 ≡ O`) destroys identifier-shaped fields outright:

| kind | inputs | shared key |
|---|---|---|
| part number | `SKU-100`, `SKU-1O0`, `SKU-IOO`, `SKU-l00` | `sku-loo` |
| plate | `B01`, `BOI`, `BOl`, `B0I` | `bol` |
| version | `v1.0.1`, `vI.O.I`, `vl.o.l` | `vl.o.l` |
| ISBN | `978-0-13-110362-8` | `978-o-l3-llo362-8` |

A word-form corpus cannot show this, because it contains no digits. That is the same
blind spot #646 names on a different axis: a collision tax measured on Latin, Cyrillic and
Greek text could not exercise Indic or Arabic numerals either.

`catalog_key` is the worst available home for it rather than the best. Its own docstring
calls it *"a canonical deduplication key for bibliographic titles"*, and bibliographic
records carry ISBNs, ISSNs, call numbers and edition numbers.

**3. Digit policy belongs on the step, not on a function signature.**

`digit_policy` has now been asked for in three places — `normalize_confusables` (#561),
a passthrough setting (#648), and this class (#650). It currently reaches exactly one
function, and `Step::Confusables(&'static str)` carries the target script and nothing
else. A preset cannot express the security-relevant setting at all.

The policy is a property of the fold, so it belongs on the step type. Widening
`Step::Confusables` to carry it lets every preset and profile express what today only one
function can.

**4. A profile takes its policy at construction, and refuses one it cannot run.**

#646 left the profile half open. A profile is a resolved pipeline object and calling it
takes text and nothing else, so the policy is either fixed when the profile is built —
`get_pipeline("llm_guardrail", digit_policy="tr39")` — or offered on every call. It is
fixed at construction, for the reason the builders settle it the same way: the policy is
a property of the fold, chosen before any text arrives, on the call that resolves the
steps. Per call would put a security setting on the hot path of every caller who never
wanted it, and would move the call signature on every binding. The two answers agree on
where the policy lives, which is what #646 asked for. In Rust it is
`api::Pipeline::with_digit_policy`; a hand-built `TextPipeline` takes the same keyword.

Three profiles carry a confusables step — `llm_guardrail`, `normalize_web_input` and
`library_catalog_key_eu` — and on the other five a policy would never run. It is refused
at construction rather than kept: a security-relevant setting that silently does nothing
is the failure #646 was filed for. `rag_ingest` is the one a reader will reach for by
mistake; its recovery is transliteration, which runs before the fold and consumes the
characters a policy would have folded (#258).

The default reproduces every profile byte for byte, and the setting is reported through
`steps()` only when it is not the default, the way `resolve_cr` is (#937).

## What this does not decide

- **The multi-character prototypes** (`m` → `rn`, `w` → `vv`, `æ` → `ae`) stay out.
  They are expansions, and accepting them means accepting that `modern` and `rnodern` are
  one token. Leaving them out is why a fold that preserves usable text tops out near 97%.
- **No change to `catalog_key`, `search_key` or `sort_key` output.** `search_key` and
  `sort_key` have no confusables step at all; whatever recovery they show is a side effect
  of transliteration, not a fold that could be tuned.
- **The name of the new builder**, which is a separate question and subject to the naming
  rule in #654.

## Consequences

| issue | status after this page |
|---|---|
| #646 §1 — is the I-family in scope | answered: yes, in a new builder |
| #646 §2 — give `digit_policy` reach | confirmed, via the step type; the profiles take it at construction (§4) |
| #648 — `digit_policy="preserve"` | shipped independently of this |
| #650 — the builder | unblocked; this is its design note |
| #731 — derived identifiers | reinforces §2: never key a code-like field on a spoof key |

## Reproducing

Every figure above was measured on `main` at `b584918`, in the repo venv. The word-list
counts come from `/usr/share/dict/words` (235,976 entries), counting groups whose members
share a key under the class but not under case folding alone. The 81.0% / 89.7% recovery
figures quoted in #650 are from an external benchmark and are *not* reproduced here; none
of the reasoning on this page depends on them.
