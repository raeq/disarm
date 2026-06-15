# Threat Model

This document defines what disarm's security-relevant features are intended to do,
what they are explicitly **not** intended to do, and — critically — how we distinguish a
**vulnerability** from a **known limitation**. Read it before relying on disarm in a
security context, and before reporting a "bypass."

## Positioning

disarm provides **building blocks for adversarial-text defense** — it is a
**defense-in-depth layer, not a complete control**. It performs deterministic,
table-driven Unicode canonicalization (TR39 confusable mapping, bidi/zalgo/zero-width
stripping, NFKC, mixed-script and hostname analysis). It makes **no guarantee** that any
class of attack is fully neutralized.

disarm is a pure, in-process text-transformation library: no network access, no
filesystem writes, no code execution, no runtime dependencies.

The opt-in `log` feature (#208) does not change this: emission is the consuming
binding's *sink* (disarm itself still does no I/O), and default-level records
(ERROR/WARN/INFO/DEBUG) carry only metadata — lengths, language, mode, flags,
counts, durations, and `Error::code` — **never** the input or output text.
Content samples are reachable only via the louder `log-content` feature at TRACE,
truncated by the same 80-byte `truncate_error_text` cap used for error messages.

**disarm is an *input-normalization* layer, not an *output sanitizer*.** It neutralizes
character-level Unicode manipulation; it does **not** make text safe to emit into any
execution or markup context. It performs no HTML/attribute/JS/URL/CSS escaping, no SQL or
shell quoting, and does not strip or encode `<`, `>`, `&`, `"`, `'`. Defending those sinks
is **context-dependent output encoding** — the same byte is safe in one context and
dangerous in another — which can only be done correctly at the point of output, where the
sink is known. Use your framework's auto-escaping (e.g. templating autoescape, JSX),
a dedicated HTML sanitizer (e.g. DOMPurify) for rich HTML, and parameterized queries for
SQL. disarm runs *before* those, as the Unicode layer they do not cover; it never replaces
them. See the XSS / injection and metacharacter-unmasking items under *Out of scope*.

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
| `strip_obfuscation` / `security_clean` / `normalize_user_input` | Compose the above in a fixed order. The output is "more canonical," not "safe." |
| `is_suspicious_hostname` | Flag **mixed-script** labels and labels containing bundled-table confusables. A not-suspicious result asserts no problem was *found*, not that the host is safe. |
| `normalize` (NFC/NFD/NFKC/NFKD), `fold_case` | Standard Unicode normalization / full case folding for the bundled Unicode data version. |
| `escape_html` | HTML entity escaping of the five metacharacters (`& < > " '`) for element-body / quoted-attribute context. |
| `percent_encode` | RFC 3986 percent-encoding of a value for a named URL component (`path`/`segment`/`query`/`form`). |
| `strip_log_injection` | Replace CR/LF/NEL/LS/PS, NUL, C0/C1 controls, ESC, and DEL (optionally `\t`) with a replacement, making untrusted text safe to *write* as a log line. |

**Documented invariants** (these we *do* stand behind, and treat failures as bugs):

- Output is idempotent: `f(f(x)) == f(x)` for each transform and the composed pipelines.
- After `normalize_confusables(text, target)`, the output contains no code point that the
  **bundled** table maps to `target`.
- Transliteration output is ASCII (enforced at compile time).
- No transform panics on any input. The confusable / normalization / bidi-stripping
  transforms are table-driven and linear-time (no regex). `unsafe` is forbidden
  crate-wide (`unsafe_code = "forbid"`). (Note: `slugify` accepts a *caller-supplied*
  separator regex — bounded by an input-size cap — which is the one regex path and is not
  part of the security transforms; see the DoS item under *Out of scope*.)

> **Output encoders are the narrow, context-pinned exception to "disarm is not an output
> sanitizer."** `escape_html` and `percent_encode` are *terminal* encoders, applied at the
> output sink **exactly once**, with the sink context stated by the caller. They are not made
> "safe" by composing them with normalization, and disarm is still **not** a context-aware
> auto-escaper: `escape_html` is wrong inside `<script>`/unquoted-attr/URL contexts, and
> `percent_encode` does not vet `javascript:`/`data:` schemes or open redirects. Run them at
> output, after (not instead of) the input-normalization layer.

> **`strip_log_injection` owns the log-record and operator-terminal sinks, not the log
> *viewer*.** It neutralizes the character-level vectors (CRLF record forging, NUL/control
> corruption, ANSI/DEL terminal hijack) but makes **no** HTML-viewer-safety claim: when a
> log is rendered in an HTML dashboard (Kibana/Grafana), attacker text is stored/second-order
> XSS that the *viewer* must output-encode (`escape_html`). It preserves `< > &` precisely so
> nothing mistakes it for viewer-safe output, does no NFKC/confusable folding, and does not
> address logging-framework interpolation (log4shell `${jndi:...}`).

## Out of scope — by design, not bugs

These are **known limitations**. A "bypass" that relies on any of them is expected
behavior, not a vulnerability:

- **Confusables not in the bundled TR39 table.** The table is a finite, versioned subset
  of Unicode confusables. Characters outside it — including the official Unicode
  `confusables.txt` entries disarm does not bundle, and entirely novel/ML-discovered
  homoglyphs (e.g. Deng et al.'s 8,000+) — are **not** mapped. Normalization is
  enumerate-the-known; it cannot canonicalize the unknown.
- **Whole-script / single-script spoofs.** A string composed *entirely* of one non-Latin
  script that visually reads as Latin (e.g. an all-Cyrillic word) is **not mixed-script**
  and may contain no table confusable; `is_suspicious_hostname` and `is_mixed_script` will not
  flag it. Whole-script confusable detection is not implemented.
- **Multi-character confusables.** Sequences confusable as a *group* rather than
  per-character — e.g. `rn` → `m`, `cl` → `d`, `vv` → `w` — are not detected or folded.
  Mapping is single-code-point only.
- **Unicode-version skew.** Bundled tables (confusables, CaseFolding, scripts) track a
  specific Unicode version. Code points added in later versions are unmapped until the
  data is updated. The bundled version is recorded in the release.
- **Semantic / meaning-level attacks.** Prompt injection, social engineering, or any
  attack that does not depend on character-level visual/format manipulation.
- **Injection attacks — XSS, HTML, SQL, shell, template, header.** disarm does **not**
  escape, encode, quote, or strip the metacharacters these attacks use. Pure-ASCII payloads
  such as `<script>alert(1)</script>` or `' OR 1=1 --` pass through every transform
  **unchanged** (every Unicode transform is a no-op on ASCII). Preventing injection is the
  job of context-appropriate output encoding at the sink, not of input normalization;
  disarm is not, and cannot be, a substitute. A preset named `normalize_user_input` performs
  Unicode hygiene only — the name predates this clarification; treat its output as
  normalized, **not** as injection-safe.
- **Metacharacter unmasking via NFKC (important).** NFKC normalization — step 1 of
  `security_clean` and `normalize_user_input` — maps fullwidth and compatibility lookalikes
  to their ASCII originals **by design** (that is how fullwidth-bypass evasion is collapsed):
  `＜script＞` (U+FF1C…U+FF1E) → `<script>`, `＆`→`&`, `＂`→`"`, `／`→`/`. A consequence is
  that disarm's output can contain *live* ASCII metacharacters that the input had only in a
  masked, non-actionable form. This is correct normalization, **not** a vulnerability — but
  it means disarm output is, if anything, **more** important to context-encode on the way
  out, never less. Do not treat normalized text as closer to injection-safe than the raw
  input; it is not.
- **Completeness or "safety" guarantees of any kind.** disarm reduces a specific,
  enumerated attack surface. It does not certify that processed text is safe to trust.
- **Denial of service guarantees.** We aim for linear-time behavior and test for it, but
  do not guarantee resource bounds for adversarial inputs in all configurations. As of
  0.6.0 the library imposes **no input-size cap** on its transforms — bounding untrusted
  input size is the caller's responsibility (the only remaining limit guards
  `register_replacements` output amplification). This includes the raw-bytes decode path
  (`detect_encoding` / `decode_to_utf8`), which has no size bound; it is fuzzed and tested
  for no-panic and linear behavior on hostile bytes (#78), but a caller accepting
  arbitrarily large byte buffers must bound them itself.
- **Linguistic correctness** of transliteration (context-free romanization is lossy for
  CJK/Indic/abjad — that is a quality property, not a security property).

## Vulnerability vs. known limitation

**We will treat as a security vulnerability** a case where disarm fails to do what this
document says it does — for example:

- `normalize_confusables(text, target)` emits a code point the **bundled** table maps to
  `target`;
- a documented bidi/zero-width code point is not stripped by the relevant function;
- an idempotence/fixed-point invariant is violated;
- a panic, crash, memory-safety issue, or super-linear blowup on some input;
- `is_suspicious_hostname` fails to flag a label despite a bundled-table confusable or a
  mixed-script condition it claims to detect.

**We will treat as a known limitation (not a vulnerability)** any "bypass" that depends on
an *Out of scope* item above — most commonly a confusable that is simply not in the bundled
table. Such reports are nonetheless **welcome as coverage/enhancement requests**:
expanding the bundled mapping data is exactly how this layer improves.

## Background and evidence

The scope above is grounded in the literature, not asserted:

- **Table-driven normalization is a layer, not a solution.** On *real* phishing text,
  1:1 confusable-database lookup restores only ~35% of visually-perturbed words, versus
  ~96% for a context-aware character model (Lee et al., *BitAbuse*, 2025). disarm is the
  fast, deterministic first layer — not the whole defense.
- **The confusable space is unbounded and mostly outside any standard.** Deng et al.
  (2020) used deep learning to find 8,000+ homoglyphs. Measured against disarm's bundled
  data: of their ~4,859 *letter* homoglyphs, only ~11% appear in the official TR39
  `confusables.txt` at all — the rest are novel. A TR39-derived tool **cannot** canonicalize
  what TR39 does not list. (Their released set is code-points only, so this measures
  recognition, not target-correctness.)
- **The dominant real-world threat is the one disarm covers well.** Holgers et al.
  (USENIX 2006) found registered homograph domains are overwhelmingly **single-character,
  Latin** substitutions (85–88%), with IDN/Unicode a smaller but growing share. disarm's
  single-letter Latin confusable coverage of UTS#39 is complete and gated in CI
  (`tests/test_confusable_coverage.py`); `is_suspicious_hostname` addresses the mixed-script/IDN
  case. Multi-character (`rn`→`m`) and whole-script spoofs remain out of scope (above).

References: Holgers, Watson & Gribble, "Cutting through the Confusion," USENIX 2006 ·
Deng, Linsky & Wright, "Weaponizing Unicodes with Deep Learning," 2020 (arXiv:2010.04382) ·
Lee et al., "BitAbuse," 2025 (arXiv:2502.05225) · Unicode UTS#39.

## Reporting

See [SECURITY.md](SECURITY.md) for private disclosure. When in doubt, report it — we would
rather triage a known limitation than miss a real invariant failure.
