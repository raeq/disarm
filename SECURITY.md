# Security Policy

translit provides **building blocks for adversarial-text defense** — it is a
defense-in-depth layer, **not a complete control**. Before relying on it in a security
context, and before reporting a "bypass," please read the
**[Threat Model](THREAT_MODEL.md)**: it defines precisely what these mechanisms do, what
is **out of scope by design**, and how we distinguish a **vulnerability** from a **known
limitation**.

## Supported versions

Security fixes are released against the latest `0.6.x` release on PyPI. Older minor
series are not maintained.

| Version | Supported |
|---------|-----------|
| 0.6.x   | Yes       |
| < 0.6   | No        |

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Report privately via GitHub
[Security Advisories](https://github.com/raeq/translit/security/advisories/new). We aim to
acknowledge within **5 business days** and to publish a fix within **30 days** for
confirmed issues. translit is maintained by a small team — if a deadline is at risk we
will say so on the advisory thread rather than go silent.

Please include:
- A description of the issue
- A minimal reproduction (input → actual output → expected output)
- Which documented behavior or invariant you believe is violated

### What makes a report actionable

translit is maintained by a small team, so a report we can **reproduce in minutes** is
the difference between a same-week fix and a thread that goes nowhere. A strong report
has a runnable reproduction (the exact input, the actual output, and the expected
output) and points at the **specific** documented invariant or mechanism in the
[Threat Model](THREAT_MODEL.md) that it violates.

AI tools are fine for finding and writing this up — but please **run the reproduction
yourself before submitting** and confirm it holds against the latest release. A
speculative "there may be a buffer overflow / use-after-free here" with no reproduction,
no triggering input, and an author who can't answer follow-up questions is not a report
we can act on, and we will close it without an extended back-and-forth. This library
forbids `unsafe` crate-wide and is exhaustively fuzzed and tested for no-panic,
linear-time behavior, so memory-safety claims in particular need a concrete trigger.

If you're not sure whether your finding is a vulnerability or an out-of-scope
limitation, that's fine — say so, and lean toward reporting. We would rather triage a
known limitation than miss a real invariant failure.

## What we treat as a vulnerability

A case where translit fails to do what the [Threat Model](THREAT_MODEL.md) says it does —
for example a documented invariant failing (`normalize_confusables` emitting a code point
the bundled table maps to the target; a documented bidi/zero-width code point not stripped;
an idempotence violation), a panic / memory-safety issue / super-linear blowup, or
`is_safe_hostname` reporting a label safe despite a condition it claims to detect.

A "bypass" that depends on an **out-of-scope** item (most commonly a confusable that is
simply not in the bundled TR39 data, a whole-script spoof, or a multi-character confusable)
is a **known limitation, not a vulnerability** — but such reports are still **welcome as
coverage/enhancement requests**. Expanding the bundled data is how this layer improves.

## Mechanisms (what is security-relevant)

translit is a pure, in-process text-transformation library: no network access, no
filesystem writes, no code execution, no runtime dependencies. Security-relevant
mechanisms — described as mechanisms, not guarantees:

- **TR39 confusable mapping** — `normalize_confusables` / `is_confusable` map characters in
  the bundled Unicode TR39 table to a target script (coverage = that table).
- **Bidi / zalgo / zero-width stripping** — remove the enumerated control, combining-mark,
  and invisible code points.
- **Hostname / IDN analysis** — `is_safe_hostname` flags mixed-script labels and
  bundled-table confusables (not whole-script spoofs).
- **Filename sanitization** — `..` / path-separator handling for safer filenames.
- **Encoding detection** — `chardetng` / `encoding_rs` (Mozilla); no arbitrary code paths.
