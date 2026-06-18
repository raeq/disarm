# Architecture: Security & Hostname Validation

How disarm defends against Unicode-based attacks in hostnames, filenames, and user-supplied text.

## Threat model

Unicode introduces attack surfaces that don't exist in ASCII-only systems:

- **Homoglyph spoofing**: Cyrillic `а` (U+0430) and Latin `a` (U+0061) are visually identical. An attacker registers `pаypal.com` (Cyrillic а) to impersonate `paypal.com`.
- **Mixed-script confusion**: combining characters from multiple scripts in a single label to create plausible-looking but fraudulent domains.
- **Confusable sequences**: characters from one script that look like characters from another, even when not mixed within a single label.
- **Path traversal**: `../../etc/passwd` or dot-sequence tricks in filenames.
- **Reserved name injection**: Windows reserved names like `NUL`, `CON`, `AUX` embedded in filenames.

## Hostname safety: multi-stage canonicalization

`is_suspicious_hostname()` implements a conservative check that flags anything suspicious rather than trying to determine benign intent. The pipeline:

1. **NFKC normalization**: compatibility decomposition + canonical composition. This collapses fullwidth Latin, circled letters, and other visual variants to their base forms before analysis.
2. **Per-label script detection**: each dot-separated label is analyzed independently via `detect_scripts()`. A label with characters from multiple scripts is flagged as mixed-script.
3. **Mixed-script flagging (conservative, #254)**: *any* label drawing on more than one script (excluding Common/Inherited) is flagged — not a curated set of high-risk pairs. This fails closed: benign combinations (e.g. Latin+CJK) are flagged alongside spoofing ones, so callers wanting a more permissive policy inspect the `mixed_script`/`scripts` fields.
4. **Confusable detection**: each label is checked via `is_confusable()`, which probes the TR39 confusable table for characters that map to different Latin equivalents.
5. **Canonical form generation**: `normalize_confusables()` produces a Latin-canonical form that reveals what the hostname "looks like" to a Latin-script reader.

The function returns both a boolean `suspicious` verdict and a `HostnameAnalysis` object with full diagnostic information (detected scripts, mixed-script flag, confusable flag, canonical form). A `False` result is not a safety guarantee — it asserts no problem was *found*, not that the host is safe; callers should implement their own policy on top of disarm's detection.

**Design tradeoff**: the check is deliberately conservative. A fully-Cyrillic domain like `яндекс.ру` is not flagged as suspicious by the mixed-script rule (it's single-script), but a domain with even one Cyrillic character mixed into an otherwise-Latin label is flagged. False positives are preferred over false negatives in this security context.

## Confusable normalization

The confusable table is a PHF map of ~6,000 Unicode characters to their Latin visual equivalents, derived from Unicode TR39. `normalize_confusables()` replaces each confusable character with its Latin equivalent; `is_confusable()` performs an early-return scan that stops at the first confusable character found.

Both functions are O(n) in the length of the input with O(1) per-character PHF lookup and zero allocation beyond the output string.

## Filename sanitization security

`sanitize_filename()` applies multiple defense layers:

1. **Path traversal removal**: strips `/`, `\`, and collapses `..` sequences.
2. **Platform-specific illegal character removal**: Windows-banned characters (`<`, `>`, `:`, `"`, `|`, `?`, `*`) on universal and Windows platforms.
3. **Dot-sequence collapsing**: multiple consecutive dots are collapsed to a single dot, preventing `...` tricks.
4. **Reserved name prefixing**: Windows reserved names (NUL, CON, PRN, AUX, COM1–COM9, LPT1–LPT9) are detected and prefixed with `_`.
5. **Post-truncation reserved name check**: after `max_length` truncation, the result is re-checked against reserved names. If truncation created a reserved name (e.g., `NULtra.txt` truncated to 3 bytes becomes `NUL`), the `_` prefix is re-applied.
6. **Empty result fallback**: if sanitization removes all characters, a default name is substituted.

The reserved-name check examines the stem (before the first dot) and compares case-insensitively. The post-truncation check was added to fix a bug where truncation could create a valid-looking but dangerous filename.

## Script detection

`detect_scripts()` classifies each character in a string by its Unicode script property, returning a deduplicated list of script names. This is the foundation for mixed-script detection in both `is_suspicious_hostname()` and the standalone `is_mixed_script()` predicate.

Script deduplication uses a `HashSet<&str>` to maintain O(1) per-character insertion while preserving first-seen ordering in the output vector. This replaced an earlier O(n²) implementation that scanned the output vector for duplicates.

## Precompiled security pipelines

The `canonicalize` preset composes the security-relevant transforms into a single pipeline: NFKC normalization → confusable normalization → bidi stripping → whitespace collapse. This is the recommended entry point for security-sensitive text processing where the goal is to canonicalize Unicode content by neutralizing homoglyph spoofing, removing dangerous bidi overrides, and collapsing invisible characters.

The `canonicalize_strict` preset extends this approach for web application input: NFKC normalization → strip bidi → strip zero-width → strip control → strip zalgo (capping combining marks at 2 per base character) → confusable normalization → whitespace collapse, while preserving the original script (no transliteration). It is the recommended entry point for *normalizing* user-submitted form data, comments, and API payloads. Note: this is input Unicode normalization, not output sanitization — it provides no XSS/injection protection, so still encode at the output sink (see [Threat Model](https://github.com/raeq/disarm/blob/main/THREAT_MODEL.md)).

## Zalgo detection

The `is_zalgo()` predicate detects excessive combining mark stacking by walking the NFD decomposition and counting consecutive combining marks per base character. The default threshold of 3 marks is safe for all legitimate scripts — Vietnamese `ệ` (the most combining-mark-heavy legitimate character in common use) has exactly 2 marks in NFD. The `strip_zalgo()` function caps marks at a configurable limit (default: 2), preserving legitimate diacritics while removing abuse.
