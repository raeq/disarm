# Precompiled Pipelines

Ready-to-use multi-step text processing pipelines. Each is a single compiled Rust function with no pipeline construction overhead at call time.

!!! warning "Renamed in 0.11 (#430)"
    Three presets were renamed to describe their mechanism rather than imply a
    safety outcome. The old names are **deprecated aliases**, behave identically,
    and are **removed in 1.0**:

    | Old name | New name |
    |---|---|
    | `security_clean` | `canonicalize` |
    | `display_clean` | `strip_format` |
    | `normalize_user_input` | `canonicalize_strict` |

    **"1.0" here is the commercial-support milestone defined in
    [RELEASING.md](../RELEASING.md), not the next release** — per that policy disarm
    expects to stay below 1.0 for a long time, so these aliases are not going away
    imminently. See the [Upgrading guide](../upgrading.md) for the full rename history
    across versions, including the `is_safe_hostname` boolean-polarity inversion.

## canonicalize

::: disarm.canonicalize

### Pipeline steps

`resolve_deletions → policy_pre_fold → NFKC → strip bidi/format → strip invisibles (#413) → strip_control → strip_zero_width → collapse_whitespace → drop_repeated_marks → strip_zalgo (#429) → NFC → fixed point(confusables → NFC) → drop_repeated_marks`

```python
from disarm import canonicalize

assert canonicalize("ℝ𝕖𝕒𝕝 𝕥𝕖𝕩𝕥") == "Real text"
assert canonicalize("Ηello Ꮤorld") == "Hello World"
```

---

## ml_normalize

::: disarm.ml_normalize

### Pipeline steps

`resolve_deletions → NFKC → emoji→text → [transliterate] → strip_accents → emoji→text → [fold_case] → strip_control → strip_zero_width → collapse_whitespace → NFC`

```python
from disarm import ml_normalize

assert ml_normalize("Café RÉSUMÉ") == "cafe resume"
assert ml_normalize("München", lang="de") == "muenchen"
assert ml_normalize("I ❤️ Python 🐍") == "i red heart python snake"

# fold_case=False drops the case fold for a cased downstream model (#559);
# every other stage — including strip_accents — still runs.
assert ml_normalize("José Martínez", fold_case=False) == "Jose Martinez"
```

---

## catalog_key

::: disarm.catalog_key

### Pipeline steps

`resolve_deletions → policy_pre_fold → NFKC → strip_bidi → strip invisibles → fold_case → fixed point(transliterate → confusables → strip_accents) → fold_case → strip_control → strip_zero_width → collapse_whitespace`

```python
from disarm import catalog_key

assert catalog_key("  Café  RÉSUMÉ  ") == "cafe resume"
assert catalog_key("Москва", lang="ru") == "moskva"
assert catalog_key("Москва", lang="auto") == "moskva"
assert catalog_key("Müller", lang="de") == "mueller"
```

---

## strip_format

::: disarm.strip_format

### Pipeline steps

`strip_bidi` → `strip invisibles (#413, rendering policy)` → `strip_control` → `strip_zero_width` → `collapse_whitespace`

```python
from disarm import strip_format

assert strip_format("hello\x00world\u200b!") == "helloworld!"
assert strip_format("  spaced   out  ") == "spaced out"
assert strip_format("admin\u202euser") == "adminuser"
```

---

## search_key

::: disarm.search_key

### Pipeline steps

`resolve_deletions → policy_pre_fold → NFKC → strip_bidi → strip invisibles → fold_case → transliterate → strip_accents → fold_case → strip_control → strip_zero_width → collapse_whitespace`

Under `digit_policy="tr39"` or `"preserve"` the pre-fold is the whole confusable table, not only its digit rows, and the list runs until the key stops changing. See [`digit_policy` on the key builders](#digit_policy-on-the-key-builders).

```python
from disarm import search_key

assert search_key("Café RÉSUMÉ") == "cafe resume"
assert search_key("Москва", lang="ru") == "moskva"
assert search_key("ΩMEGA", lang="auto") == "omega"
```

---

## skeleton_key

::: disarm.skeleton_key

### Pipeline steps

`resolve_deletions → strip_bidi → strip invisibles → strip_control → strip_zero_width → NFKC → confusables → **prototype fold** → fixed-point(fold_case → confusables → NFKC) → collapse_whitespace`

### The class the other builders cannot reach

TR39 puts `I`, `l` and `1` in one equivalence class and `O`/`0` in another. disarm's table
stops short of both: every member of the capital-I family folds to `I` and stops there. So
`paypaI` survives every other surface intact.

```python
from disarm import canonicalize, catalog_key, skeleton_key

canonicalize("paypaI")  # 'paypaI' — unchanged
catalog_key("paypaI") == catalog_key("paypal")  # False
skeleton_key("paypaI") == skeleton_key("paypal")  # True
```

### Why a separate builder, and not a flag

The letter half costs **six** collision groups in the 235,976 entries of
`/usr/share/dict/words` — `i`/`l`, `ian`/`lan`, `io`/`lo`, `ione`/`lone`, `iowa`/`lowa`,
`iowan`/`lowan`. Five are proper nouns; `Ione`/`lone` is the only ordinary-word merge.

That price holds **only on cased text**. After a case fold, `I ≡ l` is `i ≡ l` and the same
class costs **264** groups of ordinary vocabulary: `boiling`/`bolling`, `doit`/`dolt`,
`silverer`/`sliverer`, `ail`/`all`. A factor of 44.

No existing key builder runs a confusable fold before folding case. `catalog_key` folds
case at step 3 and reaches its confusable step at step 6, and the two cannot be swapped —
fold-before-transliterate is required for idempotency (#419). Hence a builder of its own.

### `digit_policy` — the half you have to ask for

`"numeric"` (default) applies the letter half only. `"tr39"` adds `1 ≡ l` and `0 ≡ O`,
which is what an identifier skeleton wants and what a deduplication key must not have:

| kind | inputs that become one key under `tr39` |
|---|---|
| part number | `SKU-100`, `SKU-1O0`, `SKU-IOO`, `SKU-l00` |
| plate | `B01`, `BOI`, `BOl`, `B0I` |
| version | `v1.0.1`, `vI.O.I`, `vl.o.l` |
| address | `Flat 10`, `Flat IO`, `Flat lO` |

For a spoof detector that is the point. For a deduplication key over anything carrying a
part number, a version or an ISBN it destroys the field — which is why `catalog_key`, whose
docstring says *"a canonical deduplication key for bibliographic titles"*, is the worst
available home for it rather than the best.

!!! warning "Not for display"
    The output is a key. It is more destructive than any preset that forwards text, in the
    same way `canonicalize_strict` is more destructive than `canonicalize`: the more
    aggressive rule lives in the entry point whose contract says so.

---

## sort_key

::: disarm.sort_key

### Pipeline steps

`resolve_deletions → policy_pre_fold → NFKC → strip_bidi → strip invisibles → fold_case → transliterate-non-Latin → fold_case → strip_control → strip_zero_width → collapse_whitespace → drop_repeated_marks → strip_zalgo → NFC`

Like `search_key`, it runs to a fixed point under a non-default `digit_policy`.

Unlike `search_key`, `sort_key` **preserves base accented characters** so
accented and unaccented forms stay distinct and the accent survives for a
locale-aware collator. Non-Latin scripts are still folded to a consistent Latin
form; Latin letters (including accented ones) are kept verbatim, so `lang` only
affects non-Latin runs. (The key is a normalized string, not a UCA weight key —
pass it to a Unicode collator when linguistically-correct order matters.)

```python
from disarm import search_key, sort_key

# accents preserved for ordering (contrast search_key, which folds them away)
assert sort_key("Über") == "über"
assert search_key("Über") == "uber"
# a language profile never expands an accented Latin letter in a sort key
assert sort_key("Über", lang="de") == "über"
# non-Latin scripts are still folded to Latin so titles interfile
assert sort_key("Война и мир", lang="ru") == "voyna i mir"
assert sort_key("Café") == "café"
```

---

## canonicalize_strict

::: disarm.canonicalize_strict

### Pipeline steps

`resolve_deletions → policy_pre_fold → NFKC → strip_bidi → strip_zero_width → strip_control → strip invisibles (#413) → fixed point(fixed point(confusables → NFC) → strip_cross_script_marks) → drop_repeated_marks → strip_zalgo → collapse_whitespace → NFC`

```python
from disarm import canonicalize_strict

assert canonicalize_strict("Hello, world!") == "Hello, world!"
assert canonicalize_strict("p\u0430ypal") == "paypal"
assert canonicalize_strict("admin\u202euser") == "adminuser"
```

Unlike `canonicalize`, this pipeline also strips zalgo text (excessive combining mark stacking). Unlike `catalog_key`/`search_key`, it does **not** transliterate — the original script is preserved.

---

## strip_obfuscation

::: disarm.strip_obfuscation

### Pipeline steps

`resolve_deletions → policy_pre_fold → NFKC → strip_zalgo(0) → strip_bidi → strip_zero_width → strip invisibles (#413) → confusables → strip_accents → strip_control → collapse_whitespace → NFC`

```python
from disarm import strip_obfuscation

# Homoglyphs (Greek/Cyrillic) folded, bidi override removed, emoji expanded.
# The emoji is left where it stands, not named (#910): a comparison surface must not
# insert attacker-chosen words. Use `demojize()` when the name is what you want.
assert strip_obfuscation("Ηеllо\u202eWоrld \U0001f600") == "HelloWorld \U0001f600"
# Strips ALL combining marks (zalgo and accents) but preserves case.
assert strip_obfuscation("Cáfé") == "Cafe"
```

Maximum-strength deobfuscation for content moderation, anti-phishing, and spam/NLP preprocessing. Strips every combining mark (zalgo **and** accents), resolves homoglyphs by TR39 visual similarity (Cyrillic `р`→`p`, not phonetic `р`→`r`). Leaves emoji where they stand rather than naming them (#910): a comparison surface must not insert attacker-chosen words into the value being compared — use `demojize()` when the name is what you want. **Preserves case** — case is meaningful, not deception. Does **not** transliterate; chain `transliterate()` on the result if you also need phonetic romanization.

---

## PRESETS

```python
from disarm import PRESETS
```

Dict mapping preset function names to their ordered pipeline steps. Each value is a list of `(step_name, parameter)` tuples in execution order.

```python
assert PRESETS["canonicalize"] == [
    ("resolve_deletions", None),
    ("policy_pre_fold", "latin"),
    ("normalize", "NFKC"),
    ("strip_bidi", None),
    ("strip_invisibles", "comparison"),
    ("strip_control", None),
    ("strip_zero_width", None),
    ("collapse_whitespace", None),
    ("drop_repeated_marks", None),
    ("strip_zalgo", None),
    ("normalize", "NFC"),
    ("fixed_point", "confusables(latin) -> normalize(NFC)"),
    ("drop_repeated_marks", None),
]
assert PRESETS["canonicalize_strict"] == [
    ("resolve_deletions", None),
    ("policy_pre_fold", "latin"),
    ("normalize", "NFKC"),
    ("strip_bidi", None),
    ("strip_zero_width", None),
    ("strip_control", None),
    ("strip_invisibles", "comparison"),
    (
        "fixed_point",
        "fixed_point(confusables(latin) -> normalize(NFC)) -> strip_cross_script_marks",
    ),
    ("drop_repeated_marks", None),
    ("strip_zalgo", None),
    ("collapse_whitespace", None),
    ("normalize", "NFC"),
]
```

Use `PRESETS` to audit exactly which transforms a preset applies. It is a mirror of the
step lists in `src/presets.rs`, and a test reads those lists and fails when the two
differ — it drifted for a long time before that, missing steps that ran and listing one
that did not (Finding 5 of the Lean model in `formal/lean/Presets`).

Most names are the `TextPipeline` step or public function of the same name. Five are not:

| step | what it does |
|---|---|
| `policy_pre_fold` | Nothing under the default `digit_policy`. Under `"tr39"` or `"preserve"`, the whole Latin confusable fold on the raw text (#885, #896) |
| `fixed_point` | Runs the inner steps, named in its parameter, as a group until the text stops changing (bounded) |
| `drop_repeated_marks` | Drops a nonspacing mark repeated on one base (UTS #39 §5.4, #835) |
| `strip_cross_script_marks` | Drops a combining mark whose script differs from its base's (#615) |
| `prototype_fold` | `I` to `l`, and under `"tr39"` `1` to `l` and `0` to `O` (#650) |

Two properties are not steps, so the lists cannot show them: `search_key` and `sort_key`
run their whole list to a fixed point under a non-default `digit_policy`, and every preset
raises `ResourceLimitError` when a step leaves the text more than 10 MiB longer than its
input (#768). A `TextPipeline` has neither `fixed_point` nor the preset-only steps, so it
reproduces a preset only approximately.

### `digit_policy` on the key builders

On `canonicalize`, `canonicalize_strict` and `strip_obfuscation`, which fold confusables
anyway, a non-default policy changes the digit rows the fold reads. On `catalog_key`,
`search_key` and `sort_key` it does more: `policy_pre_fold` runs the **whole** confusable
table on the raw text, before transliteration, and `search_key` and `sort_key` have no
fold of their own at all under the default. So under `"tr39"` or `"preserve"` a Cyrillic
spelling of `paypal` keys as `paypal` rather than `raural`, and `search_key` and
`sort_key` rewrite `|`, `"` and `` ` `` as the other folding surfaces do.

```python
from disarm import search_key

cyrillic_paypal = "".join(map(chr, (0x440, 0x430, 0x443, 0x440, 0x430, 0x6C)))
assert search_key(cyrillic_paypal) == "raural"
assert search_key(cyrillic_paypal, digit_policy="preserve") == "paypal"
assert search_key("a|b") == "a|b"
assert search_key("a|b", digit_policy="tr39") == "alb"
```

`"preserve"` is named for what it does to numerals, not for leaving the rest of the key
alone.

!!! warning "`None` here is a parameter, not an off switch"

    A `None` in the second position means the step takes no parameter, or runs at its
    own default — the step is in the list, so it runs. This is the opposite of what
    `None` means as a `TextPipeline` keyword, where it omits the step (#958). The
    difference bites on `strip_zalgo`: `("strip_zalgo", None)` above is a live step at
    the default cap, while `TextPipeline(strip_zalgo=None)` compiles no step, and
    `TextPipeline(strip_zalgo=0)` compiles a step that strips every diacritic. See
    [`TextPipeline`](classes.md#strip_zalgo-is-a-cap-and-0-is-not-off).

---

## Policy Profiles

Named policy profiles provide pre-configured `TextPipeline` instances for common institutional and application workflows.

### get_pipeline

```python
from disarm import get_pipeline

pipe = get_pipeline("scholarly_cyrillic_iso9")
assert pipe("Москва") == "moskva"
```

Returns a fresh `TextPipeline` configured for the named profile. Raises `DisarmError` for unknown profiles.

A profile runs its steps again until the output stops changing (bounded), so calling it on
its own output returns that output. One pass was not always enough (Findings 3 and 4 of the
Lean model in `formal/lean/Presets`): the mark strip runs before the confusable fold and
before `strip_pua`, and the control and zero-width strips run after `normalize`, so
`llm_guardrail` kept a negation overlay on a symbol and then stripped it once the fold had
made the symbol a letter. A `TextPipeline` built from the same flags runs its steps once;
the two agree wherever one pass is already a fixed point, which includes every single code
point.

```python
from disarm import get_pipeline

guardrail = get_pipeline("llm_guardrail")
cent_negated = chr(0xA2) + chr(0x338)
assert guardrail(cent_negated) == "c"
assert guardrail(guardrail(cent_negated)) == "c"
```

### list_profiles

```python
from disarm import list_profiles

print(list_profiles())
# ['code_context', 'library_catalog_key_eu', 'llm_guardrail', 'ml_corpus_normalize',
#  'normalize_web_input', 'rag_ingest', 'scholarly_cyrillic_iso9', 'search_index']
```

Returns sorted list of available profile names.

### Available profiles

| Profile | Steps | Output |
|---------|-------|--------|
| `code_context` | strip_bidi → strip_control → strip_zero_width | UTF-8 |
| `scholarly_cyrillic_iso9` | NFKC → strip_plane14 → transliterate (ISO 9) → fold_case → strip_control → strip_zero_width → strip_pua → collapse_whitespace | UTF-8 |
| `library_catalog_key_eu` | NFKC → strip_plane14 → strip_accents → transliterate → confusables → fold_case → confusables → fold_case → strip_control → strip_zero_width → strip_pua → collapse_whitespace | ASCII |
| `normalize_web_input` | NFKC → confusables → strip_control → strip_zero_width → strip_pua → collapse_whitespace | UTF-8 |
| `ml_corpus_normalize` | NFKC → strip_plane14 → demojize → strip_accents → fold_case → strip_control → strip_zero_width → strip_pua → collapse_whitespace | UTF-8 (no transliteration: a script without accents keeps its letters) |
| `search_index` | NFKC → strip_plane14 → strip_accents → transliterate → fold_case → strip_control → strip_zero_width → strip_pua → collapse_whitespace | ASCII |
| `llm_guardrail` | resolve_deletions → NFKC → strip_zalgo(0) → strip_bidi → strip_plane14 → strip_accents → confusables → fold_case → confusables → fold_case → strip_control → strip_zero_width → strip_pua → collapse_whitespace | UTF-8 |
| `rag_ingest` | resolve_deletions → NFKC → strip_bidi → strip_plane14 → strip_accents → transliterate → strip_control → strip_zero_width → strip_pua → collapse_whitespace | ASCII |

Each list is what the profile's `steps` reports, and every profile runs it to a fixed point.

`llm_guardrail` hardens text against prompt-injection and homoglyph/zalgo/bidi obfuscation before it reaches an LLM (digits are never remapped to letters). `rag_ingest` canonicalizes documents for retrieval pipelines while preserving case.

!!! note "Homoglyph handling: `rag_ingest` romanizes, it does not visually-fold (#258)"
    The two guardrail profiles canonicalize homoglyphs differently, and the
    distinction matters for spoof resistance:

    - **`llm_guardrail`** runs `confusables` *without* `transliterate`, so a
      Cyrillic look-alike of "paypal" (`раураl`) is **visually folded** to
      `paypal` — it collides with the real Latin term (good for "treat the spoof
      as the word it imitates").
    - **`rag_ingest`** runs `transliterate`, which **phonetically romanizes** the
      same input to `raural` — a *distinct* key, so the spoof does not
      impersonate the real term, and legitimate non-Latin text still romanizes
      for retrieval (`Москва → Moskva`).

    These are deliberate trade-offs of the fixed step order (transliterate runs
    before confusables; running confusables first would mangle legitimate
    Cyrillic/Greek into mixed-script gibberish). Adding `confusables` to
    `rag_ingest` would be a no-op — transliterate has already consumed the
    non-Latin characters. **If you need homoglyph spoofs folded onto the term
    they imitate, use `llm_guardrail` (or a dedicated `confusables` pass), not
    `rag_ingest`.**

See [Policy Templates](../policy-templates.md) for detailed usage guidance and institutional recipes.
