# What we're looking for

We'd love your help, especially with:

- **Domain-specific extensions and new use cases.** disarm is a kit of canonicalization
  and transliteration building blocks. If you work in a domain we haven't designed
  for — a library catalog, a moderation pipeline, an IDN registrar check, a search
  index, a data-cleaning ETL step, a linguistics workflow — and disarm *almost* does
  what you need, tell us. The most valuable feature requests come from real workflows
  we hadn't pictured. Use the **💡 Extension idea / new use case** issue form.
- **Language profiles.** Profiles apply sparse overrides on top of the default table
  (e.g. German `ü` → `ue`). Adding or refining a profile for a language you know well
  is a high-value, self-contained contribution. See
  [Language support](https://docs.disarm.dev/user-guide/language-support.html).
- **A new language binding** (distinct from a profile above). disarm's pure-Rust core
  is wrapped per programming-language ecosystem — Ruby is live; Node, Go, Java, PHP, and
  R are planned (#43–#48). A binding for an ecosystem you know well is high-value, but it
  must *feel native* to that language, not be a re-export of the Rust/Python API. Read
  [BINDINGS.md](../BINDINGS.md) — the per-binding definition of done — and use
  `bindings/ruby/` as the template before you start.
- **Coverage requests.** A confusable pair, a script, or a code point we don't yet map
  is a *known limitation* (see the [Threat Model](../THREAT_MODEL.md)), not a vulnerability —
  but it is exactly how this layer improves. Use the **🗺️ Coverage / confusable-gap**
  issue form; a single missing pair is a perfectly good issue.
- **Genuine feature requests and fixes.** Bug reports with a minimal reproduction, and
  PRs that come with a test, are always welcome.

If you're not sure whether an idea fits, open an issue and ask. We would rather
discuss a half-formed idea than have you not raise it.

## Reporting bugs and requesting features

Please use the [issue forms](https://github.com/raeq/disarm/issues/new/choose) — they
ask for the few things we need to act on a report (a version, a minimal reproduction,
expected vs. actual output). A report we can reproduce in under a minute gets fixed far
faster than one we have to interrogate.

**Security issues are different:** do **not** open a public issue. Follow
[SECURITY.md](../SECURITY.md) for private disclosure, and read the
[Threat Model](../THREAT_MODEL.md) first — it defines precisely what counts as a
vulnerability versus an out-of-scope limitation.
