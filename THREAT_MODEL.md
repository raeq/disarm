# Threat Model

This document defines what translit's security-relevant features are intended to do,
what they are explicitly **not** intended to do, and — critically — how we distinguish a
**vulnerability** from a **known limitation**. Read it before relying on translit in a
security context, and before reporting a "bypass."

## Positioning

translit provides **building blocks for adversarial-text defense** — it is a
**defense-in-depth layer, not a complete control**. It performs deterministic,
table-driven Unicode canonicalization (TR39 confusable mapping, bidi/zalgo/zero-width
stripping, NFKC, mixed-script and hostname analysis). It makes **no guarantee** that any
class of attack is fully neutralized.

translit is a pure, in-process text-transformation library: no network access, no
filesystem writes, no code execution, no runtime dependencies.

## Assets and actors

- **Asset:** the integrity of text as it enters a downstream system (classifier,
  moderation filter, search index, IDN/hostname check, catalog key, display surface).
- **Actor:** an adversary who crafts Unicode input designed to look like one thing to a
  human (or to evade a filter) while being something else to a machine.

## In scope — what these mechanisms do

Each is a *mechanism*, defined by its data and algorithm, not by an outcome promise:

| Mechanism | Definition |
|---|---|
| `normalize_confusables` / `is_confusable` | Map characters in the **bundled TR39 confusable table** to a chosen target script (Latin/Cyrillic). Coverage is exactly that table — see *Out of scope*. |
| `strip_bidi` | Remove the UAX#9 bidi formatting/isolate/override code points enumerated in the implementation. |
| `strip_zalgo` / `is_zalgo` | Remove or detect runs of combining marks above a configurable threshold. |
| zero-width / invisible stripping | Remove the enumerated zero-width and invisible code points. |
| `strip_obfuscation` / `security_clean` / `sanitize_user_input` | Compose the above in a fixed order. The output is "more canonical," not "safe." |
| `is_safe_hostname` | Flag **mixed-script** labels and labels containing bundled-table confusables. |
| `normalize` (NFC/NFD/NFKC/NFKD), `fold_case` | Standard Unicode normalization / full case folding for the bundled Unicode data version. |

**Documented invariants** (these we *do* stand behind, and treat failures as bugs):

- Output is idempotent: `f(f(x)) == f(x)` for each transform and the composed pipelines.
- After `normalize_confusables(text, target)`, the output contains no code point that the
  **bundled** table maps to `target`.
- Transliteration output is ASCII (enforced at compile time).
- No transform panics or exhibits super-linear blowup on any input (no `unsafe`, no regex
  in the core path).

## Out of scope — by design, not bugs

These are **known limitations**. A "bypass" that relies on any of them is expected
behavior, not a vulnerability:

- **Confusables not in the bundled TR39 table.** The table is a finite, versioned subset
  of Unicode confusables. Characters outside it — including the official Unicode
  `confusables.txt` entries translit does not bundle, and entirely novel/ML-discovered
  homoglyphs (e.g. Deng et al.'s 8,000+) — are **not** mapped. Normalization is
  enumerate-the-known; it cannot canonicalize the unknown.
- **Whole-script / single-script spoofs.** A string composed *entirely* of one non-Latin
  script that visually reads as Latin (e.g. an all-Cyrillic word) is **not mixed-script**
  and may contain no table confusable; `is_safe_hostname` and `is_mixed_script` will not
  flag it. Whole-script confusable detection is not implemented.
- **Unicode-version skew.** Bundled tables (confusables, CaseFolding, scripts) track a
  specific Unicode version. Code points added in later versions are unmapped until the
  data is updated. The bundled version is recorded in the release.
- **Semantic / meaning-level attacks.** Prompt injection, social engineering, or any
  attack that does not depend on character-level visual/format manipulation.
- **Completeness or "safety" guarantees of any kind.** translit reduces a specific,
  enumerated attack surface. It does not certify that processed text is safe to trust.
- **Denial of service guarantees.** We aim for linear-time behavior and test for it, but
  do not guarantee resource bounds for adversarial inputs in all configurations.
- **Linguistic correctness** of transliteration (context-free romanization is lossy for
  CJK/Indic/abjad — that is a quality property, not a security property).

## Vulnerability vs. known limitation

**We will treat as a security vulnerability** a case where translit fails to do what this
document says it does — for example:

- `normalize_confusables(text, target)` emits a code point the **bundled** table maps to
  `target`;
- a documented bidi/zero-width code point is not stripped by the relevant function;
- an idempotence/fixed-point invariant is violated;
- a panic, crash, memory-safety issue, or super-linear blowup on some input;
- `is_safe_hostname` reports a label *safe* despite a bundled-table confusable or a
  mixed-script condition it claims to detect.

**We will treat as a known limitation (not a vulnerability)** any "bypass" that depends on
an *Out of scope* item above — most commonly a confusable that is simply not in the bundled
table. Such reports are nonetheless **welcome as coverage/enhancement requests**:
expanding the bundled mapping data is exactly how this layer improves.

## Reporting

See [SECURITY.md](SECURITY.md) for private disclosure. When in doubt, report it — we would
rather triage a known limitation than miss a real invariant failure.
