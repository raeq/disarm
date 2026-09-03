# Derived deterministic identifiers

disarm's key builders name three uses — search index, library catalog, collation — and
`find_key_collisions` names a fourth, registry admission. A fifth is common and had no
map: a **derived deterministic identifier**, where a value is normalized, hashed, and the
digest becomes the handle. Idempotency keys, cache keys, dedup-on-insert, content
addressing and canonical-request signing (AWS SigV4, HTTP Message Signatures) all have
this shape.

It differs from the four disarm covers in one way that changes the advice: the caller
never sees the two values side by side. There is no batch. A request arrives, gets keyed,
and either matches a stored digest or does not — so both failure directions are silent,
and they are opposite:

- **under-normalize** → two spellings of one intent hash apart → the retry executes twice
- **over-normalize** → two distinct values hash together → a real second request is
  suppressed and the first one's result is returned

## What each key does to each variation class

Both tables are rendered by `tests/test_derived_identifiers.py` from its registry, one
pair of inputs per row, and that test fails when this page drifts from what the build
does. `<-` marks a cell the use case cannot take.

**Must merge** — same order, spelled two ways:

| class | `fold_case` | `search_key` | `catalog_key` | `canonicalize` | `canonicalize_strict` | `normalize_confusables` | `skeleton_key` |
|---|---|---|---|---|---|---|---|
| NFC vs NFD | distinct `<-` | merge | merge | merge | merge | merge | merge |
| fullwidth digits | distinct `<-` | merge | merge | merge | merge | distinct `<-` | merge |
| fullwidth letters | distinct `<-` | merge | merge | merge | merge | distinct `<-` | merge |
| case | merge | merge | merge | distinct `<-` | distinct `<-` | distinct `<-` | merge |
| zero-width space | distinct `<-` | merge | merge | merge | merge | distinct `<-` | merge |
| soft hyphen | distinct `<-` | merge | merge | merge | merge | distinct `<-` | merge |
| RLO control | distinct `<-` | merge | merge | merge | merge | distinct `<-` | merge |
| Cyrillic homoglyph | distinct `<-` | merge | merge | merge | merge | merge | merge |
| NBSP for space | distinct `<-` | merge | merge | merge | merge | distinct `<-` | merge |
| edge whitespace | distinct `<-` | merge | merge | merge | merge | distinct `<-` | merge |
| duplicated marks | distinct `<-` | merge | merge | merge | merge | distinct `<-` | distinct `<-` |
| tag characters | distinct `<-` | merge | merge | merge | merge | distinct `<-` | merge |
| variation selector | distinct `<-` | merge | merge | merge | merge | distinct `<-` | merge |
| ligature | merge | merge | merge | merge | merge | merge | merge |
| sharp s | merge | merge | merge | distinct `<-` | distinct `<-` | distinct `<-` | merge |

**Must not merge** — distinct values:

| class | `fold_case` | `search_key` | `catalog_key` | `canonicalize` | `canonicalize_strict` | `normalize_confusables` | `skeleton_key` |
|---|---|---|---|---|---|---|---|
| accent (`resume`/`résumé`) | distinct | merge `<-` | merge `<-` | distinct | distinct | distinct | distinct |
| digit system (`1`/`١`) | distinct | merge `<-` | merge `<-` | merge `<-` | merge `<-` | merge `<-` | merge `<-` |
| vulgar fraction (`1/2`/`½`) | distinct | merge `<-` | merge `<-` | merge `<-` | merge `<-` | distinct | merge `<-` |
| circled digits (`100.00`/`①⓪⓪.⓪⓪`) | distinct | merge `<-` | merge `<-` | merge `<-` | merge `<-` | distinct | merge `<-` |
| romanization (`Война`/`Voyna`) | distinct | merge `<-` | merge `<-` | distinct | distinct | distinct | distinct |
| case-significant id (`SKU-a`/`SKU-A`) | merge `<-` | merge `<-` | merge `<-` | distinct | distinct | distinct | merge `<-` |

## Reading the matrix

No column is clean, and the columns fail in different directions.

`search_key` and `catalog_key` merge every row of the second table. That is what they are
for — a search index *wants* `résumé` and `resume` to be one entry — and it is exactly
what an idempotency key cannot have: a real second order for `résumé` is answered with
the first order's receipt.

`canonicalize` is the closest. It misses two of the fifteen must-merge classes (case and
sharp s, both of which it leaves alone on purpose), and its three must-not-merge failures
are all one thing: **it changes the value of a number**.

```python
from disarm import canonicalize

assert canonicalize("amount-١") == "amount-1"  # U+0661 ARABIC-INDIC DIGIT ONE
assert canonicalize("qty-½") == "qty-1/2"
assert canonicalize("①⓪⓪.⓪⓪") == "100.00"
```

`①⓪⓪.⓪⓪` → `100.00` and `½` → `1/2` are NFKC, the first step of the preset; `١` → `1`
is the confusable fold's default digit policy. Nothing in the matrix is a bug in any
builder: every cell is right for the use the builder is named for. The gap is that this
use has no builder, and a caller choosing one today is choosing by its name.

`skeleton_key` is a spoof key. It exists to make confusable identifiers collide, so it
merges four of the six distinct values by design, and its output is never for display.

### `digit_policy` rescues a numeral only where a fold is what changes it

`"preserve"` (#648) is the setting that leaves `١` alone, and it holds on the three
builders whose own fold is what would change the digit — `canonicalize`,
`canonicalize_strict` and `strip_obfuscation` — since #896 threaded the policy through the
core (until then the Python pre-pass kept the numeral and the preset's own fold folded it,
which was #949). On `search_key`, `catalog_key` and `sort_key` the numeral is romanized by
*transliteration*, not by the fold, and a key that maps every script to Latin cannot keep
one; `preserve` neither can nor should stop that.

```python
from disarm import canonicalize, normalize_confusables, search_key, skeleton_key

assert normalize_confusables("amount-١", digit_policy="preserve") == "amount-١"
assert skeleton_key("amount-١", digit_policy="preserve") == "amount-١"
assert canonicalize("amount-١", digit_policy="preserve") == "amount-١"
assert search_key("amount-١", digit_policy="preserve") == "amount-1"  # transliterated
```

And `½` and `①` are policy-blind either way: NFKC rewrites them before any fold runs.

## The recipe

**1. Split the key by field, and choose the failure direction per field.** A derived
identifier is usually built from several fields, and they do not want the same key.

- A free-text field — a description, a name as typed — goes on `canonicalize`. Its two
  misses (case, sharp s) are the two a retry is least likely to vary, and its failures
  are all on numbers, which this field does not carry.
- A numeric or code-like field — an amount, an order number, a SKU, a part number — goes
  on `fold_case` or on **nothing**, and is *screened* rather than folded: reject on
  `has_anomalies` instead of recovering. #650 made the same argument for `catalog_key` on
  ISBNs and part numbers; this is the second use case arriving at it, on amounts and
  order numbers.
- Never key a field where accent or digit system carries meaning on `search_key` or
  `catalog_key`. Both merge every distinct value above.

**2. Check at write time, do not recompute.** `is_canonical` answers "is this value
already the form my key would produce" without building the key (#730). A value that is
*not* its own canonical form is a second spelling arriving; rejecting it keeps the stored
handle bound to one representation, where silently recomputing defends only the
comparison and lets the second form keep circulating.

```python
from disarm import is_canonical

assert is_canonical("amount-1", preset="canonicalize")
assert not is_canonical("amount-١", preset="canonicalize")
```

**3. Name which direction you accepted.** Under-normalizing costs a duplicate execution;
over-normalizing costs a suppressed one. For a payment the second is worse; for a cache
the first is. The matrix tells you which cells you are buying with each builder, and the
choice is the caller's, per field.

## Non-goals

- Changing what any key builder merges. Every cell above is correct for the use the
  builder is named for; the gap was a sixth use with no guidance, not five with wrong
  answers.
- A hashing or identifier-generation API. Choosing the digest, the salt and the truncation
  is the caller's, and disarm's contribution ends at the normalized string.

## Where this came from

Auditing disarm against CN122268567A, a deterministic-idempotency patent whose "business
unique key" is `BusinessType:SubjectID:param1=val1:...`, sorted by code point,
percent-encoded per RFC 3986, then HMAC-SHA256'd — and which specifies no Unicode
normalization at all. The question was what disarm would tell someone building it. The
answer was "seven functions, no map"; this page is the map.
