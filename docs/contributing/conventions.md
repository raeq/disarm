# Conventions

Rules that apply to every change, whichever part of the tree it touches.

## Leave it better than you found it

This project follows the **Boy Scout rule** and the **broken-windows** principle:
if you touch an area and notice something broken, stale, or sub-standard — a lint
that only fires under `--all-targets`, a stale doc claim, a flaky test, a
misleading comment — **fix it as part of your change**, even if you didn't cause
it. Broken windows accumulate fast: one tolerated defect signals that defects are
acceptable, and quality erodes. A small, in-scope cleanup alongside your work is
always welcome (call it out in the PR description so reviewers can see what's
incidental). When a fix is too large to fold in, open an issue so it isn't lost.

## Naming public entry points (#654)

**A public name may describe the operation, never the outcome.** `canonicalize`,
not `clean`. `strip_bidi`, not `make_safe`. No public name may imply a safety
guarantee.

The reason is in `canonicalize`'s own docstring, which denies the guarantee a name
like `clean` would imply. NFKC unmasking makes the output *more* dangerous to emit
than the input — fullwidth `＜` folds to a live `<` — so a name promising safety
would be actively wrong rather than merely vague. `mysql_real_escape_string` is the
worked example of what happens when a name outlives its caveats.

Write the rule down here so the next `clean()` proposal meets a written rule rather
than an argument.

**One shipped name sits outside it.** `ml_normalize` is named for a use case, and
readers pick it by that use case. It is also the transform that passes bidi
controls, private-use characters and homoglyphs straight through, so it is exactly
the name the rule exists to prevent. It stays, and its docstring carries the
warning instead. Recording that the exception is known matters more than resolving
it.

## Logging rules (#208)

Diagnostic logging lives behind the opt-in `log` feature via the `tl_*!` macros
in `src/obs.rs`. Two hard rules, enforced by tests:

- **Never log content.** Default-level records (ERROR/WARN/INFO/DEBUG) carry only
  metadata — lengths, language, mode, flags, counts, durations, `Error::code` —
  never input or output text. A sentinel test (`tests/logging.rs`) fails the
  build if any default-level record contains the input. Truncated content
  samples are reachable only via `tl_trace_content!` (the `log-content` feature,
  TRACE).
- **Never log in an inner loop.** Instrument core *boundaries* only. The
  per-codepoint loop in `transliterate_impl_inner` and the per-token loop in
  `context::resolve` must contain no `tl_*!`/`log::` call — guarded by
  `tests/hot_path_guard.rs`. Variables that exist only to feed a record are
  `#[cfg(feature = "log")]`-gated so they cost nothing when the feature is off.
