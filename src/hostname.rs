use unicode_normalization::UnicodeNormalization;

use crate::{confusables, invisibles, scripts};

/// Every invisible class a hostname label may not legitimately contain (#605, #610).
///
/// The union of the zero-width set with the four class predicates
/// [`invisibles::is_tag`], [`invisibles::is_variation_selector`],
/// [`invisibles::is_noncharacter`] and [`invisibles::is_pua`].
///
/// RFC 5892 puts the four classes #610 added in DISALLOWED outright, which is what
/// justifies folding PUA and the variation selectors in here — both have legitimate
/// uses in ordinary text, so a general-text detector needs a separate argument for
/// them. The zero-width set is not uniformly disallowed: `U+200C`/`U+200D` are
/// CONTEXTJ, permitted in the specific joining contexts RFC 5892 Appendix A.1/A.2
/// describe. This screen flags them anyway (#605), because a spoof screen has no
/// reason to honour a context rule it cannot verify, and that is a deliberate policy
/// rather than a reading of the RFC.
///
/// Deliberately excludes the UAX #9 bidi controls: those are
/// [`scripts::is_bidi_control`] and are reported through `bidi_control` (#603), so the
/// two predicates partition the space rather than overlap.
fn is_invisible_in_hostname(ch: char) -> bool {
    invisibles::is_zero_width(ch)
        || invisibles::is_tag(ch)
        || invisibles::is_variation_selector(ch)
        || invisibles::is_noncharacter(ch)
        || invisibles::is_pua(ch)
}

/// Check if a bracketed string is a valid IPv6 literal per RFC 3986 §3.2.2.
///
/// Requires: starts with `[`, ends with `]`, content contains `:`,
/// only hex digits / colons / dots / `%` (zone ID), and no more than 7 colons.
fn is_ipv6_literal(normalized: &str) -> bool {
    if !(normalized.starts_with('[') && normalized.ends_with(']')) {
        return false;
    }
    let inner = &normalized[1..normalized.len() - 1];
    if inner.is_empty() || !inner.contains(':') {
        return false;
    }
    // Validate colon count on the address portion (before any zone ID).
    let addr_part = match inner.find('%') {
        Some(pos) => &inner[..pos],
        None => inner,
    };
    let colon_count = addr_part.chars().filter(|&c| c == ':').count();
    if colon_count > 7 {
        return false;
    }
    // A valid literal has at most one zone-ID delimiter (`%`); more than one is
    // malformed. Bounding it keeps a crafted `[::1%a%b...]` from being waved
    // through as an IP and thereby skipping homoglyph analysis. (C5)
    if inner.bytes().filter(|&b| b == b'%').count() > 1 {
        return false;
    }
    inner
        .as_bytes()
        .iter()
        .all(|&b| b.is_ascii_hexdigit() || b == b':' || b == b'.' || b == b'%')
}

/// Findings from a hostname homoglyph analysis.
///
/// Reports factual findings; it claims nothing about absolute safety. A
/// `suspicious == false` result is not a safety certificate (see
/// [`is_suspicious_hostname`]).
#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct HostnameAnalysis {
    /// Whether the hostname is flagged suspicious overall.
    pub(crate) suspicious: bool,
    /// Scripts detected across all labels, in order of first appearance.
    pub(crate) scripts: Vec<String>,
    /// Whether any single label mixes characters from more than one script.
    pub(crate) mixed_script: bool,
    /// Whether any label contains a confusable mapping to a Latin character.
    pub(crate) has_confusables: bool,
    /// Whether the decoded hostname mixes strong LTR and strong RTL characters
    /// (Bidi-reorder / "BiDi Swap" precondition). Folded into `suspicious`.
    pub(crate) bidi_conflict: bool,
    /// Whether the decoded hostname contains a UAX #9 bidi control character
    /// (#603). Disjoint from `bidi_conflict`, which reads only strong-direction
    /// letters. Folded into `suspicious`, and stripped from `canonical`.
    pub(crate) bidi_control: bool,
    /// Whether the decoded hostname contains a zero-width or invisible-format
    /// character (#605). Disjoint from `bidi_control`. Folded into `suspicious`,
    /// and stripped from `canonical`.
    pub(crate) has_invisible: bool,
    /// Whether any label carried a Unicode compatibility form before normalization
    /// (#709). Matches the `compat_fold` anomaly kind from #633, and is the only
    /// field computed from the *raw* input: the NFKC that opens this analysis
    /// destroys the evidence, so `ｇoogle.com` reached the per-label checks already
    /// spelled `google.com` and screened clean while `inspect_anomalies` on the same
    /// string returned `['compat_fold']`.
    ///
    /// The predicate is RFC 5892 §2.1's, applied per code point: a character `c`
    /// where `toNFKC(c) != c` is DISALLOWED in an IDN label, so there is no
    /// legitimate hostname to protect and this folds into `suspicious` on the same
    /// footing as `bidi_control` and `has_invisible`. Tested per character rather
    /// than "NFKC changed the label", which would fire on decomposed input that is
    /// entirely valid (`한국.kr` written with conjoining jamo).
    pub(crate) compat_fold: bool,
    /// Whether the labels span more than one distinct script (Common/Inherited
    /// excluded). Broader than `bidi_conflict`; NOT folded into `suspicious`.
    pub(crate) cross_label_script: bool,
    /// Per-label resolved scripts, left to right (Common/Inherited excluded).
    pub(crate) label_scripts: Vec<Vec<String>>,
    /// Whether any label is a whole-script confusable (#545): single-script,
    /// non-Latin, with a confusable skeleton that is entirely Latin. A graded
    /// SIGNAL, not a verdict — it fires on short non-Latin ccTLDs (`ру`→`py`) and
    /// on real words whose every letter is a confusable (`оса`→`oca`) — so it is
    /// deliberately NOT folded into `suspicious` (see the `is_suspicious_hostname`
    /// docs). The precise caller policy is
    /// `label_whole_script_confusable[non-TLD label] ∧ Latin TLD`.
    pub(crate) whole_script_confusable: bool,
    /// Per-label whole-script-confusable flags, parallel to `label_scripts`.
    pub(crate) label_whole_script_confusable: Vec<bool>,
    /// The Latin-normalized (canonical) form of the hostname.
    pub(crate) canonical: String,
}

/// Detect whether a hostname is *suspicious* for Unicode homoglyph spoofing.
///
/// `xn--` (ACE) labels are decoded to their Unicode form via UTS#46 before
/// analysis, so the on-the-wire IDN homograph attack is examined rather than
/// passed through as inert ASCII (#63). A malformed ACE label is treated as
/// suspicious (fail closed).
///
/// A hostname is flagged **suspicious** if:
/// - Any single label contains characters from more than one script
///   (mixed-script), excluding Common/Inherited (digits, punctuation,
///   combining marks). This is conservative and fails closed (#254): it flags
///   benign combinations (e.g. Latin + CJK) as well as spoofing ones — a caller
///   wanting a more permissive policy can inspect the `mixed_script`/`scripts`
///   fields.
/// - Any label contains a character confusable with a Latin character. This is an
///   *any-character* screen, so it flags essentially every hostname containing a
///   non-Latin letter (the most frequent Cyrillic and Greek letters are TR39
///   confusables) — legitimate ones (`москва.рф`) as well as spoofs. `suspicious`
///   is therefore a **maximally conservative screen**, not a precise verdict.
/// - The decoded hostname mixes strong left-to-right and strong right-to-left
///   characters (`bidi_conflict`, #412) — the "BiDi Swap" reorder precondition,
///   which `mixed_script` misses because the mixing is *across* labels. The
///   broader `cross_label_script` fact is exposed but deliberately NOT folded in
///   (it fires on benign IDN ccTLDs like `google.рф`).
/// - The decoded hostname contains a UAX #9 bidi control character (`bidi_control`,
///   #603) — an override, embedding, isolate or directional mark. This is disjoint
///   from `bidi_conflict`: the latter reads strong-direction *letters* and is blind
///   to `paypal<U+202E>moc.evil.com`. IDNA2008 disallows every character in the set,
///   so the screen fails closed on all of them; they are also stripped from
///   `canonical` so it cannot carry an override into a caller's display path.
/// - An ACE label fails to decode, or a confusable check errors (fail closed)
///
/// **Whole-script confusables (#545).** `whole_script_confusable` (and the
/// per-label `label_whole_script_confusable`) name the fact that discriminates a
/// whole-script spoof (`аррӏе.com` → skeleton `apple.com`, every letter a
/// confusable) from a genuine non-Latin domain (`москва.рф`, whose `м`/`к`/`в`
/// survive the skeleton). It is a graded **signal, not a verdict**, and is
/// deliberately NOT folded into `suspicious`: on its own it fires on short
/// non-Latin ccTLDs (`ру`→`py`) and on real words that happen to skeleton to Latin
/// (`оса`→`oca`). The precise, low-false-positive policy is caller-side —
/// `label_whole_script_confusable[non-TLD label] ∧ (TLD is Latin/ASCII)` — because
/// separating the last two classes needs registrable-boundary (TLD) context, which
/// this library leaves to the caller, plus a caller-supplied protected-name list
/// for the irreducible `оса`-style case.
///
/// Returns a tuple of (is_suspicious, analysis).
///
/// **A `false` (not-suspicious) result is NOT a safety guarantee.** It means
/// only that no mixed-script label and no confusable *from the bundled TR39
/// table* was found. Confusables outside the bundled table are not detected and
/// will report not-suspicious. Base allow/deny decisions on the granular
/// `scripts` / `mixed_script` / `has_confusables` / `whole_script_confusable`
/// fields plus your own policy — a detector can attest the *presence* of a
/// problem, never the *absence* of all problems.
/// [`is_suspicious_hostname`] with the #562 contraction rules selectable.
///
/// `contractions` folds ASCII digraphs that can impersonate a single letter — `rn`→`m`,
/// `vv`→`w`, `cl`→`d` — into the canonical form, so `arnazon.com` canonicalizes to
/// `amazon.com`. Off by default and deliberately confined to this path: unconditional
/// contraction is worse than none (it breaks `earnings`, `turnip`, `born`), and a
/// hostname is the one place where the threat model justifies the false positives and
/// there is no running prose to corrupt.
/// The IDNA label separators (UTS #46 §4): FULL STOP plus the three code points UTS #46
/// treats as equivalent to it.
///
/// Splitting on `'.'` alone would read a fullwidth or ideographic stop as label *content*.
/// The NFKC that used to open this function did that job by rewriting them, but it also
/// pre-empted the UTS #46 mapping the analysis is supposed to run on: NFKC turns `ϲ`
/// U+03F2 into `ς` U+03C2, where UTS #46 maps it to `σ` U+03C3. The label reaching the
/// confusable check was then neither spelling's real form — `ϲ.com` resolved to `ς.com`
/// and its own ACE spelling `xn--4xa.com` to `o.com`. Splitting on the separators
/// directly lets the raw label reach `domain_to_unicode` intact (#714).
fn is_label_separator(c: char) -> bool {
    matches!(c, '.' | '\u{FF0E}' | '\u{3002}' | '\u{FF61}')
}

/// Remove every invisible-in-a-hostname character from `label`, recording whether any
/// were there (#605, widened by #610).
///
/// Stripped BEFORE script analysis rather than later on the joined hostname: `U+FEFF`
/// sits in the Arabic Presentation Forms block, `U+180E` in the Mongolian block and
/// `U+FDD0` in the Arabic Presentation Forms range, so leaving them in makes
/// `detect_scripts` report a script the reader cannot see and `mixed_script` fire on an
/// ASCII-looking host. Stripping first means nothing downstream — scripts, mixed_script,
/// confusables, canonical — ever sees them.
///
/// RFC 5892 puts the four classes #610 added in DISALLOWED outright, so a hostname
/// carrying one is malformed whatever its intent and the screen fails closed. That is why
/// PUA and the variation selectors are included here but would need a separate argument in
/// a general-text detector, where both have legitimate uses. ZWNJ/ZWJ are the exception:
/// CONTEXTJ, so conditionally permitted. Flagging them is a policy choice (#605), not
/// something the RFC settles. The tag block is the ASCII-smuggling channel:
/// `U+E0061`-`U+E007A` spell arbitrary Latin invisibly, so returning them in `canonical`
/// would launder the payload.
///
/// Called on both sides of the UTS #46 mapping (#714): the mapping's IGNORED disposition
/// deletes half this set silently, so a check placed only after it can never fire on a
/// literal spelling; and a punycode label can decode into one, which a check placed only
/// before it would miss. `retain` edits in place and only runs when something is actually
/// there to remove, so the clean path neither allocates nor rescans.
fn strip_invisibles(label: &mut String, found: &mut bool) {
    if label.chars().any(is_invisible_in_hostname) {
        *found = true;
        label.retain(|c| !is_invisible_in_hostname(c));
    }
}

/// RFC 5892 §2.1's DISALLOWED derivation, per code point (#709).
///
/// A character whose NFKC form is not itself is disallowed in an IDN label, so this is
/// the whole test — no ASCII-alphabetic gate like `src/anomalies.rs`'s. That gate exists
/// there to keep `ＮＨＫ` out of a general-text report; on hostname-shaped input it is
/// already void (the TLD supplies the ASCII) and there is no registrable name to protect.
///
/// Per *character*, not "NFKC changed the label": the label-level form fires on
/// decomposed input that is entirely legitimate, such as `한국.kr` written with
/// conjoining jamo, where every individual code point is NFKC-stable.
fn has_compat_form(label: &str) -> bool {
    label.chars().any(|c| {
        let mut folded = c.nfkc();
        folded.next() != Some(c) || folded.next().is_some()
    })
}

pub(crate) fn is_suspicious_hostname_opts(
    hostname: &str,
    contractions: bool,
) -> (bool, HostnameAnalysis) {
    // NFKC is still applied for the IPv6-literal test below, which is a *structural*
    // question (does this parse as `[::1]`) that fullwidth digits and colons can dress
    // up. It is deliberately NOT applied to the labels: see `is_label_separator`.
    let normalized: String = hostname.nfkc().collect();

    // IPv6 literals (e.g. "[::1]", "[2001:db8::1]") are not IDN hostnames and
    // cannot be visually spoofed via homoglyph attacks. Report them as
    // not-suspicious without running the script/confusable analysis.
    if is_ipv6_literal(&normalized) {
        return (
            false,
            HostnameAnalysis {
                suspicious: false,
                scripts: Vec::new(),
                mixed_script: false,
                has_confusables: false,
                bidi_conflict: false,
                bidi_control: false,
                has_invisible: false,
                compat_fold: false,
                cross_label_script: false,
                label_scripts: Vec::new(),
                whole_script_confusable: false,
                label_whole_script_confusable: Vec::new(),
                canonical: normalized,
            },
        );
    }

    // 2. Split on dots to check each label
    let mut suspicious = false;
    let mut all_scripts: Vec<&str> = Vec::new();
    let mut seen_scripts: std::collections::HashSet<&str> = std::collections::HashSet::new();
    let mut has_mixed = false;
    let mut has_confusables = false;
    let mut has_invisible = false;
    // #709: read off the RAW label, inside the loop. Every other field is computed after
    // the UTS #46 mapping and the NFKC, which is what makes them work and also what erases
    // this evidence: by the per-label checks `ｇoogle` is already `google`,
    // `is_confusable` correctly returns false, and nothing reports what the mapping ate.
    // `analysis.canonical` differing from the input was the analysis proving to itself
    // that a fold had happened while `suspicious` said clean.
    let mut compat_fold = false;
    let mut decoded_labels: Vec<String> = Vec::new();
    let mut per_label_scripts: Vec<Vec<String>> = Vec::new();
    let mut per_label_wsc: Vec<bool> = Vec::new();

    for raw_label in hostname.split(is_label_separator) {
        // Empty labels arise from leading, trailing, or consecutive dots
        // (e.g. "a..b" or "example.com.").  These are structurally
        // malformed but not a homoglyph attack vector — skip them (but keep a
        // placeholder so the canonical form preserves dot structure).
        if raw_label.is_empty() {
            decoded_labels.push(String::new());
            per_label_scripts.push(Vec::new());
            per_label_wsc.push(false);
            continue;
        }

        // Map EVERY label through UTS #46, not only the `xn--` ones (#714).
        //
        // #63 added this decode so an on-the-wire IDN homograph would be analysed
        // instead of passing as inert ASCII, and it did exactly that — but the mapping
        // it introduced reached only the ACE branch. A label written in literal Unicode
        // went to script and confusable analysis unmapped, so the two spellings of one
        // registered domain were two different inputs and **561 code points** got a
        // different verdict depending on which spelling the caller happened to hold:
        // `xn--58da.com` was suspicious and `ꭰꭰ.com` was clean, naming the same domain.
        // The Cherokee row is the CVE-2026-17084 one (#713): UTS #46 folds `U+AB70`
        // toward `U+13A0`, which disarm maps to `D`, so only the ACE spelling ever
        // reached the whole-script-confusable check.
        //
        // The NFKC at the top of this function is not a substitute: UTS #46's table
        // includes case folding and per-character dispositions NFKC does not perform.
        //
        // `domain_to_unicode` decodes punycode *and* applies the mapping, so one call
        // covers both spellings and the ACE/literal branch disappears. A malformed
        // label cannot be verified → fail closed, as the ACE branch already did. On
        // error the raw label is kept instead of the best-effort mapping; see below.
        // #709: per *label*, not over the whole hostname. Three of the four UTS #46
        // separators carry a compatibility decomposition — `U+FF0E` and `U+FF61` do,
        // `U+3002` does not — so a whole-string scan reported `example．com` suspicious
        // and `example。com` clean, for two spellings of one host. A separator is
        // structure, not label content, and RFC 5892 §2.1 is a statement about what may
        // appear *in a label*.
        //
        // Read before the mapping for the same reason it is read before NFKC: UTS #46
        // maps the compatibility repertoire away (or rejects it as DISALLOWED), so a
        // check placed after it can never fire. An ACE label is pure ASCII and so
        // NFKC-stable by construction; a compatibility form smuggled inside punycode is
        // caught by the decode below, which rejects DISALLOWED code points outright.
        if has_compat_form(raw_label) {
            compat_fold = true;
        }

        // The invisible strip below runs FIRST, on the raw label, because UTS #46 gives
        // ZWSP, the word joiner, U+FEFF, U+180E and the variation selectors the IGNORED
        // disposition: the mapping deletes them silently, and mapping before the check
        // made `has_invisible` unreachable for every literal spelling of #605's own set.
        // It runs again afterwards because a punycode label can decode *into* one.
        let mut label = raw_label.to_string();
        strip_invisibles(&mut label, &mut has_invisible);

        let (mapped, result) = idna::domain_to_unicode(&label);
        if result.is_err() {
            // The returned string is a best-effort form carrying `U+FFFD`, which is worse
            // to analyse than the input and would launder into `canonical`. Keep the raw
            // label — NFKC-folded, so an unmappable label still canonicalizes as
            // readably as it did before UTS #46 reached this branch — and let the flag
            // carry the verdict.
            suspicious = true;
            label = label.nfkc().collect();
        } else {
            label = mapped.nfkc().collect();
        }
        // Second pass: a punycode label can decode into an invisible the raw scan above
        // could not see.
        strip_invisibles(&mut label, &mut has_invisible);

        decoded_labels.push(label.clone());

        // Check scripts in this (decoded) label
        let label_scripts = scripts::detect_scripts(&label);
        per_label_scripts.push(label_scripts.iter().map(|s| (*s).to_string()).collect());

        // Whole-script-confusable for this label (#545): single-script, non-Latin,
        // and the confusable skeleton is entirely Latin. `detect_scripts` already
        // drops Common/Inherited (digits, hyphen, combining marks), so a skeleton
        // resolving to exactly `["Latin"]` means every non-neutral character folded
        // to Latin. This is a graded SIGNAL, deliberately NOT folded into
        // `suspicious` — it fires on short non-Latin ccTLDs (`ру`→`py`) and on real
        // words whose every letter is a confusable (`оса`→`oca`). See the fn docs
        // for the precise `wsc(non-TLD) ∧ Latin-TLD` caller policy.
        let label_wsc = label_scripts.len() == 1 && label_scripts[0] != "Latin" && {
            // "numeric" (#561): hostname analysis keeps disarm's digit reading. Selecting
            // the TR39 policy here would silently change what `is_suspicious_hostname`
            // flags, which is a security-behaviour change and belongs in its own issue.
            let skeleton = confusables::normalize_confusables(&label, "latin", "numeric")
                .unwrap_or_else(|_| label.clone());
            matches!(scripts::detect_scripts(&skeleton).as_slice(), ["Latin"])
        };
        per_label_wsc.push(label_wsc);

        // Track all scripts seen (O(1) dedup via HashSet)
        for s in &label_scripts {
            if seen_scripts.insert(s) {
                all_scripts.push(s);
            }
        }

        // Mixed-script within a single label is suspicious. Conservative policy
        // (#254): any label drawing on two or more scripts is flagged. The
        // former rule only flagged the four Latin-paired high-risk combinations
        // (Cyrillic/Greek/Armenian/Cherokee + Latin), so a label mixing *two
        // non-Latin* scripts with no Latin confusable mapping — e.g. Greek +
        // Cyrillic — set `mixed_script = true` yet was reported not-suspicious.
        // That contradicted this function's documented "flag anything
        // suspicious" contract and failed open on a real spoofing vector.
        // Callers needing a more permissive policy (e.g. allowing Latin + CJK)
        // can read the `mixed_script` and `scripts` fields and decide for
        // themselves; the boolean here fails closed.
        if label_scripts.len() > 1 {
            has_mixed = true;
            suspicious = true;
        }

        // Check confusables in this label. Fail CLOSED (#67.1): if the check
        // errors we cannot prove the label clean, so flag it as suspicious
        // rather than silently degrading to "not confusable". The target
        // ("latin") is a fixed, always-supported script, so the underlying
        // Result is in practice always `Ok`; the `Err` arm is defensive.
        match confusables::is_confusable(&label, "latin") {
            Ok(true) => {
                has_confusables = true;
                suspicious = true;
            }
            Ok(false) => {}
            Err(_) => {
                suspicious = true;
            }
        }
    }

    // Generate canonical Latin form from the decoded labels.
    let mut decoded_hostname = decoded_labels.join(".");

    // Direction conflict (#412): the decoded hostname mixes strong-LTR and
    // strong-RTL characters — the "BiDi Swap" precondition. Computed on the same
    // decoded codepoints, with no U+202x override involved. Fold it into the
    // verdict (it is precise and rare in legitimate hostnames). `cross_label_script`
    // (more than one script across labels) is the broader, noisier fact — it
    // fires on benign IDN ccTLDs (`google.рф`), so it is exposed but NOT folded.
    let bidi_conflict = scripts::has_bidi_conflict(&decoded_hostname);
    let cross_label_script = all_scripts.len() > 1;
    if bidi_conflict {
        suspicious = true;
    }

    // Bidi CONTROL characters (#603): U+202A-U+202E, U+2066-U+2069, U+200E/U+200F,
    // U+061C. `bidi_conflict` above reads strong-direction *letters* only, so it is
    // blind to `paypal<RLO>moc.evil.com` — the best-known bidi spoof there is. Every
    // one of these is DISALLOWED by IDNA2008 (RFC 5892), so a hostname carrying one
    // is malformed whatever its intent, and the screen can fail closed on the whole
    // set with no legitimate-use tradeoff. The ACE path already rejects them via
    // `idna::domain_to_unicode`; this covers the literal-Unicode label, which reaches
    // the pass-through arm above and was never inspected.
    //
    // Strip them before canonicalization too, so `canonical` cannot carry an override
    // into a caller's display path — the sharper half of #603: a caller who screened the
    // name, was told it was clean, and then rendered `canonical` rendered the spoof.
    // `retain` edits in place and only runs when something is actually there to remove,
    // so the clean path (every real hostname) neither allocates nor rescans.
    let bidi_control = scripts::has_bidi_control(&decoded_hostname);
    if bidi_control {
        suspicious = true;
        decoded_hostname.retain(|c| !scripts::is_bidi_control(c));
    }

    // #605: folded into the verdict for the same reason as #603 — IDNA2008 disallows
    // the whole set, so a hostname carrying one is malformed whatever its intent. The
    // characters were already removed per label above.
    if has_invisible {
        suspicious = true;
    }

    // #709: folded on the same #603 / #605 / #610 precedent. RFC 5892 §2.1 derives
    // DISALLOWED for every code point NFKC rewrites, so the whole set is malformed in a
    // hostname whatever its intent and there is no legitimate case to protect. The threat
    // is a blocklist bypass rather than a lookalike: `ｅvil.com` is absent from a blocked
    // set, screens clean, and resolves to `evil.com`.
    if compat_fold {
        suspicious = true;
    }

    // Hostname analysis keeps the NUMERIC digit policy (#561): a spoofed label is judged
    // on what a reader sees, and a Devanagari zero reads as a zero. The TR39 skeleton
    // policy is for benchmark comparison, not for this verdict.
    let canonical = confusables::normalize_confusables(&decoded_hostname, "latin", "numeric")
        .unwrap_or(decoded_hostname);
    // #562: contraction runs AFTER the cross-script fold, so a label carrying both a
    // Cyrillic homoglyph and an ASCII digraph (`аrnazon`) resolves both. Applied per
    // label so a digraph can never form across a dot — the `r` ending one label and the
    // `n` starting the next are not adjacent glyphs to a reader.
    let canonical = if contractions {
        canonical
            .split('.')
            .map(|label| crate::contraction::contract(label).into_owned())
            .collect::<Vec<_>>()
            .join(".")
    } else {
        canonical
    };

    // Aggregate: any label is a whole-script confusable. Graded signal (§545 §5.1);
    // NOT folded into `suspicious`.
    let whole_script_confusable = per_label_wsc.iter().any(|&b| b);

    (
        suspicious,
        HostnameAnalysis {
            suspicious,
            scripts: all_scripts.into_iter().map(String::from).collect(),
            mixed_script: has_mixed,
            has_confusables,
            bidi_conflict,
            bidi_control,
            has_invisible,
            compat_fold,
            cross_label_script,
            label_scripts: per_label_scripts,
            whole_script_confusable,
            label_whole_script_confusable: per_label_wsc,
            canonical,
        },
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_clean_hostname_not_suspicious() {
        let (suspicious, details) = is_suspicious_hostname_opts("paypal.com", false);
        assert!(!suspicious);
        assert!(!details.has_confusables);
        assert!(!details.mixed_script);
    }

    #[test]
    fn test_cyrillic_spoof() {
        // Cyrillic а and р mixed with Latin
        let (suspicious, details) = is_suspicious_hostname_opts("\u{0440}\u{0430}ypal.com", false);
        assert!(suspicious);
        assert!(details.has_confusables);
        assert!(details.mixed_script);
        assert_eq!(details.canonical, "paypal.com");
    }

    #[test]
    fn test_full_cyrillic_domain() {
        // Fully Cyrillic domain (Yandex): not mixed-script. `suspicious` is true only
        // via the any-character confusable screen (#545), not a real spoof — so the
        // verdict is no longer discarded, it is explained by the whole-script signal.
        let (_, d) = is_suspicious_hostname_opts("яндекс.ру", false);
        assert!(!d.mixed_script);
        // Known graded-signal FP: the `яндекс` label is NOT whole-script-confusable
        // (я, д survive the skeleton), but the short Cyrillic ccTLD `ру` skeletons to
        // Latin `py`, so it IS — and the top-level (any-label) bool therefore fires.
        // The caller's `wsc(non-TLD) ∧ latin-TLD` policy clears it: the only wsc label
        // is the TLD, and the TLD is Cyrillic, not Latin.
        assert_eq!(d.label_whole_script_confusable, vec![false, true]);
        assert!(
            d.whole_script_confusable,
            "top-level bool over-fires on the `ру` ccTLD — the documented graded-signal FP"
        );
    }

    #[test]
    fn test_whole_script_confusable_attack() {
        // аррӏе.com: an all-Cyrillic label whose every letter is a confusable — the
        // skeleton is `apple`. The non-TLD label is whole-script-confusable and the
        // TLD is Latin, so both the field and the caller policy flag it.
        let (_, d) =
            is_suspicious_hostname_opts("\u{0430}\u{0440}\u{0440}\u{04CF}\u{0435}.com", false);
        assert!(d.whole_script_confusable);
        assert_eq!(d.label_whole_script_confusable, vec![true, false]);
        assert_eq!(d.canonical, "apple.com");
    }

    #[test]
    fn test_whole_script_confusable_legit_domains_not_flagged() {
        // Genuine non-Latin domains: at least one letter in every label survives the
        // Latin skeleton, so NO label is whole-script-confusable. (Cyrillic, Greek,
        // Hebrew, and mixed Han+Hiragana all covered.)
        for host in [
            "\u{043C}\u{043E}\u{0441}\u{043A}\u{0432}\u{0430}.\u{0440}\u{0444}", // москва.рф
            "\u{043F}\u{043E}\u{0447}\u{0442}\u{0430}.\u{0440}\u{0444}",         // почта.рф
            "\u{03B1}\u{03B8}\u{03AE}\u{03BD}\u{03B1}.gr", // αθήνα.gr (ή survives)
            "\u{05D0}\u{05EA}\u{05E8}.\u{05E7}\u{05D5}\u{05DD}", // אתר.קום
            "\u{4F8B}\u{3048}.jp",                         // 例え.jp (mixed-script label)
        ] {
            let (_, d) = is_suspicious_hostname_opts(host, false);
            assert!(
                !d.whole_script_confusable,
                "{host:?} must not be whole-script-confusable, got {:?}",
                d.label_whole_script_confusable
            );
        }
    }

    #[test]
    fn test_whole_script_confusable_known_fp_osa() {
        // оса.рф ("wasp"): the `оса` label skeletons to Latin `oca`, so it IS
        // whole-script-confusable — an IRREDUCIBLE false positive at the label level
        // (signal-identical to а spoof; only a caller-supplied protected-name list can
        // separate them). Pinned deliberately. The caller's `wsc(non-TLD) ∧ latin-TLD`
        // policy still clears the full domain because the `.рф` TLD is Cyrillic.
        let (_, d) =
            is_suspicious_hostname_opts("\u{043E}\u{0441}\u{0430}.\u{0440}\u{0444}", false);
        assert_eq!(d.label_whole_script_confusable, vec![true, false]);
        assert!(d.whole_script_confusable);
        assert!(!d.mixed_script);
    }

    #[test]
    fn test_whole_script_confusable_spoof_under_cyrillic_tld() {
        // аррӏе.рф: a Cyrillic spoof label under a Cyrillic ccTLD. The label IS
        // whole-script-confusable, but the documented caller policy `wsc(non-TLD) ∧
        // latin-TLD` does NOT flag it — correctly, since it is not claiming to be a
        // Latin-web brand. A documented policy choice, verified here.
        let (_, d) = is_suspicious_hostname_opts(
            "\u{0430}\u{0440}\u{0440}\u{04CF}\u{0435}.\u{0440}\u{0444}",
            false,
        );
        assert!(d.label_whole_script_confusable[0]);
        // The TLD label `рф` is not Latin, so a `wsc(non-TLD) ∧ latin-TLD` caller
        // policy evaluates false even though the field is set.
        assert_ne!(d.label_scripts.last().unwrap(), &vec!["Latin".to_string()]);
    }

    #[test]
    fn test_mixed_non_latin_scripts_suspicious() {
        // #254: a label mixing two *non-Latin* scripts (Cyrillic я + Greek ψ)
        // with no Latin confusable mapping used to set mixed_script=true yet
        // report not-suspicious, because the old rule only flagged Latin-paired
        // high-risk combinations. The conservative policy now flags any
        // mixed-script label as suspicious.
        let (suspicious, details) = is_suspicious_hostname_opts("\u{044F}\u{03C8}.com", false);
        assert!(suspicious, "mixed Cyrillic+Greek label must be suspicious");
        assert!(details.mixed_script);
        // The mixed-script rule — not the confusable check — is what catches
        // this: neither character maps to a Latin confusable.
        assert!(
            !details.has_confusables,
            "neither я nor ψ is a Latin confusable; the mixed-script rule must \
             be what flags this label"
        );
        assert!(details.scripts.iter().any(|s| s == "Cyrillic"));
        assert!(details.scripts.iter().any(|s| s == "Greek"));
    }

    #[test]
    fn test_punycode_non_homograph_not_suspicious() {
        // xn--n3h.com decodes to ☃.com (a snowman) — a single-script non-Latin
        // label, not a homoglyph spoof, so it is correctly reported
        // not-suspicious. The point of #63 is that the label is now *decoded and
        // analysed*, not that every xn-- label is flagged.
        let (suspicious, _) = is_suspicious_hostname_opts("xn--n3h.com", false);
        assert!(!suspicious);
    }

    #[test]
    fn test_punycode_homograph_suspicious() {
        // #63: the on-the-wire ACE form of a Cyrillic homograph must be decoded
        // and flagged. Build the xn-- form of a Cyrillic "apple" spoof, then
        // assert is_suspicious_hostname flags it (it used to pass as safe ASCII).
        let spoof = "\u{0430}\u{0440}\u{0440}\u{04CF}\u{0435}"; // аррӏе (Cyrillic)
        let ace = idna::domain_to_ascii(spoof).expect("encode Cyrillic spoof to ACE");
        assert!(
            ace.starts_with("xn--"),
            "expected an xn-- label, got {ace:?}"
        );
        let hostname = format!("{ace}.com");
        let (suspicious, details) = is_suspicious_hostname_opts(&hostname, false);
        assert!(
            suspicious,
            "Cyrillic homograph in ACE form {hostname:?} must be suspicious"
        );
        assert!(details.has_confusables);
    }

    #[test]
    fn test_ipv6_loopback_not_suspicious() {
        let (suspicious, details) = is_suspicious_hostname_opts("[::1]", false);
        assert!(!suspicious);
        assert!(!details.mixed_script);
        assert!(!details.has_confusables);
    }

    #[test]
    fn test_ipv6_full_not_suspicious() {
        let (suspicious, details) = is_suspicious_hostname_opts("[2001:db8::1]", false);
        assert!(!suspicious);
        assert!(details.scripts.is_empty());
    }

    // ── #412: bidi-direction conflict ────────────────────────────────────────

    #[test]
    fn test_bidi_swap_hostname_flags_direction_conflict() {
        // "varonis.com.ו.קום": Latin subdomain stacked on a Hebrew (RTL) domain —
        // the BiDi-Swap shape. mixed_script stays false (each label is single
        // script), but bidi_conflict fires and drives suspicious=true.
        let (suspicious, d) =
            is_suspicious_hostname_opts("varonis.com.\u{05D5}.\u{05E7}\u{05D5}\u{05DD}", false);
        assert!(suspicious);
        assert!(
            d.bidi_conflict,
            "LTR+RTL across labels must set bidi_conflict"
        );
        assert!(d.cross_label_script);
        assert!(!d.mixed_script, "no single label is mixed-script");
        assert_eq!(d.label_scripts.len(), 4);
        assert_eq!(d.label_scripts[0], vec!["Latin".to_string()]);
        assert_eq!(d.label_scripts[3], vec!["Hebrew".to_string()]);
    }

    #[test]
    fn test_bidi_conflict_intra_label() {
        // The intra-label case: "varonisו.com" — one label mixes Latin + Hebrew.
        let (suspicious, d) = is_suspicious_hostname_opts("varonis\u{05D5}.com", false);
        assert!(suspicious);
        assert!(d.bidi_conflict);
    }

    #[test]
    fn test_benign_idn_cctld_no_direction_conflict() {
        // "google.рф": Latin label under a Cyrillic ccTLD. Both scripts are LTR,
        // so there is NO direction conflict (cross_label_script is true but does
        // not flip suspicious on its own).
        let (_, d) = is_suspicious_hostname_opts("google.\u{0440}\u{0444}", false);
        assert!(!d.bidi_conflict);
        assert!(d.cross_label_script);
    }

    #[test]
    fn test_all_rtl_hostname_no_direction_conflict() {
        // "אתר.קום": a legitimately all-Hebrew domain — single direction (RTL),
        // so bidi_conflict is false and cross_label_script is false.
        let (_, d) =
            is_suspicious_hostname_opts("\u{05D0}\u{05EA}\u{05E8}.\u{05E7}\u{05D5}\u{05DD}", false);
        assert!(!d.bidi_conflict);
        assert!(!d.cross_label_script);
    }

    #[test]
    fn test_ascii_hostname_no_new_signals() {
        let (suspicious, d) = is_suspicious_hostname_opts("example.com", false);
        assert!(!suspicious);
        assert!(!d.bidi_conflict);
        assert!(!d.cross_label_script);
        assert_eq!(
            d.label_scripts,
            vec![vec!["Latin".to_string()], vec!["Latin".to_string()]]
        );
    }

    #[test]
    fn bidi_controls_are_flagged_and_stripped_from_canonical() {
        // #603: every UAX #9 bidi control must flag, and none may survive into
        // `canonical` — a caller who renders that field would render the spoof.
        for c in [
            '\u{200E}', '\u{200F}', '\u{061C}', '\u{202A}', '\u{202B}', '\u{202C}', '\u{202D}',
            '\u{202E}', '\u{2066}', '\u{2067}', '\u{2068}', '\u{2069}',
        ] {
            let host = format!("paypal{c}moc.evil.com");
            let (suspicious, d) = is_suspicious_hostname_opts(&host, false);
            assert!(suspicious, "U+{:04X} must flag suspicious", c as u32);
            assert!(d.bidi_control, "U+{:04X} must set bidi_control", c as u32);
            assert!(
                !d.canonical.contains(c),
                "U+{:04X} must not survive into canonical (got {:?})",
                c as u32,
                d.canonical
            );
        }
    }

    #[test]
    fn bidi_control_is_disjoint_from_bidi_conflict() {
        // The two fields answer different questions (#599). The RLO spoof has a
        // control and no conflict; the "BiDi Swap" has a conflict and no control.
        let (_, rlo) = is_suspicious_hostname_opts("paypal\u{202E}moc.evil.com", false);
        assert!(rlo.bidi_control && !rlo.bidi_conflict);

        let (_, swap) =
            is_suspicious_hostname_opts("varonis.com.\u{05D5}.\u{05E7}\u{05D5}\u{05DD}", false);
        assert!(swap.bidi_conflict && !swap.bidi_control);
    }

    #[test]
    fn clean_hostname_sets_no_bidi_control() {
        for host in [
            "paypal.com",
            "\u{043C}\u{043E}\u{0441}\u{043A}\u{0432}\u{0430}.\u{0440}\u{0444}",
            "example.co.uk",
        ] {
            let (_, d) = is_suspicious_hostname_opts(host, false);
            assert!(!d.bidi_control, "{host} must not set bidi_control");
            assert_eq!(
                d.canonical
                    .chars()
                    .filter(|c| crate::scripts::is_bidi_control(*c))
                    .count(),
                0
            );
        }
    }

    #[test]
    fn test_bidi_conflict_on_decoded_punycode() {
        // xn--9db.xn--9dbq2a decodes to Hebrew ו.קום — all-RTL after decode, so
        // bidi_conflict is false, exactly as for the literal Hebrew form.
        let (_, d) = is_suspicious_hostname_opts("xn--9db.xn--9dbq2a", false);
        assert!(!d.bidi_conflict);
    }
}
