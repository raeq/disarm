//! Layer 1 (pure-Rust core): TR39 confusable folding. No pyo3.
//!
//! The PyO3 shims for these functions live in `src/py/confusables.rs`; the
//! idiomatic crates.io surface is `crate::api::{normalize_confusables,
//! is_confusable}`. This module is the algorithm, returning the native
//! [`crate::ErrorRepr`] (never a `PyErr`).
//!
//! These fns are `pub(crate)` while [`crate::ErrorRepr`] is `pub(crate)` (avoiding a
//! private-in-public leak). They are promoted to `pub` together with the opaque
//! public `Error` in the first fallible-module extraction sub-PR (#38).

use crate::tables;
/// Whether a *detection* should ignore `ch` because it is printable ASCII (#957).
///
/// `"` (U+0022), `` ` `` (U+0060) and `|` (U+007C) are TR39 confusable **sources**: the
/// bundled table folds them to `''`, `'` and `l`. That is correct for the fold and
/// deliberate — #725 records the three rows and which surfaces apply them — but it made
/// `is_confusable` return `true` for any quoted sentence or JSON document. Measured over
/// this repository's own prose: 588 of 1,342 pure-ASCII lines.
///
/// So the rows stay in the fold and stop counting as detections. The rule is the whole
/// printable range rather than those three code points, so a row added to the table later
/// cannot quietly turn ordinary punctuation into a detection; `printable_ascii_is_not_a_detection`
/// in the tests below sweeps U+0021–U+007E to hold that.
///
/// **This is not the ASCII fast path #252 O6.1 rejected.** That one would have skipped
/// ASCII in `normalize_confusables`, where it is wrong precisely because the fold does
/// rewrite these three. The fold is untouched here.
///
/// Tested before the table probe rather than after, so ASCII text — the common case for a
/// screen — pays a range check instead of a PHF lookup per character.
#[inline]
fn skipped_by_detection(ch: char) -> bool {
    ch.is_ascii_graphic()
}

/// The three digit policies, as a type rather than a string (#646 §2).
///
/// `digit_policy` was a `&str` on one public function and nowhere else, so
/// `Step::Confusables` could not carry it and no preset could express the setting. As a
/// `Copy` enum it lives on the step, which is where the decision in
/// `docs/architecture/prototype-policy.md` §3 puts it: the policy is a property of the
/// fold, not of one function's signature.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(crate) enum DigitPolicy {
    /// disarm's reading: a non-Latin digit folds to the ASCII digit, so a number in
    /// running prose stays a number. The default, and what every preset used before the
    /// step could express anything else.
    Numeric,
    /// Upstream TR39's: most non-Latin digits fold to a Latin letter (Devanagari zero →
    /// `o`). Correct for an identifier skeleton, ruinous for a field carrying a number.
    Tr39,
    /// Leave the numeral in its own script (#648).
    Preserve,
}

/// Safety bound on the confusables fixed-point loop, shared by the owned and borrowing
/// forms. Far above the observed maximum; the `debug_assert` on the way out catches any
/// future table change that regresses convergence.
const MAX_CONFUSABLE_PASSES: usize = 8;

/// Validate the `digit_policy` parameter (#561).
///
/// `"numeric"` (default) keeps disarm's reading: a non-Latin digit folds to the ASCII
/// digit, so a number in running prose stays a number. `"tr39"` selects upstream's, which
/// folds most of them to a Latin letter (Devanagari zero → `o`) — correct for an
/// identifier skeleton, where the only job is to make two confusable identifiers collide.
/// Three of the 47 divergent rows do not land on a letter: `٠` and `۰` fold to `.`, and
/// `𑣣` folds to the two characters `rn`. A skeleton feeding a label- or path-shaped key
/// has to allow for that extra `.`.
fn validate_digit_policy(digit_policy: &str) -> Result<(), crate::ErrorRepr> {
    DigitPolicy::from_token(digit_policy).map(|_| ())
}

impl DigitPolicy {
    /// The one place the wire token maps to the enum.
    ///
    /// The `&str` and enum forms of the fold grew up separately — `normalize_confusables_cow`
    /// compares tokens, `normalize_confusables_into` matches variants — so the accepted set
    /// was written twice. `validate_digit_policy` now delegates here, which makes a new
    /// policy one edit rather than two that can disagree.
    ///
    /// # Errors
    ///
    /// [`crate::ErrorRepr::InvalidDigitPolicy`] naming the offending token.
    /// The token `from_token` accepts for this value; what `steps()` reports (#646).
    pub(crate) fn as_token(self) -> &'static str {
        match self {
            Self::Numeric => "numeric",
            Self::Tr39 => "tr39",
            Self::Preserve => "preserve",
        }
    }

    pub(crate) fn from_token(token: &str) -> Result<Self, crate::ErrorRepr> {
        match token {
            "numeric" => Ok(Self::Numeric),
            "tr39" => Ok(Self::Tr39),
            "preserve" => Ok(Self::Preserve),
            _ => Err(crate::ErrorRepr::InvalidDigitPolicy {
                got: token.to_owned(),
            }),
        }
    }
}

/// Resolve one character under the chosen digit policy (#561).
///
/// `tr39_digits` is `digit_policy == "tr39" && target_script == "latin"`: the override set
/// is generated from the **Latin** table and its values are TR39's Latin targets, so it is
/// meaningless — and actively wrong — for any other target. Consulting it under
/// `target_script = "cyrillic"` would emit a Latin letter into a Cyrillic skeleton, and
/// would invent folds for sources the Cyrillic table deliberately has no row for.
///
/// The override map is consulted only when that flag is set. The numeric path therefore
/// costs one predictable, loop-invariant `bool` test per lookup and never touches the
/// override map — not literally free, but the branch predicts perfectly and the map probe
/// (the part that would actually cost something) is skipped entirely. Splitting the fold
/// into two loops to remove the test was considered and rejected: it duplicates the
/// borrow-on-no-op logic for a branch that is already free in practice.
///
/// `preserve_digits` is the third policy (#648) and needs no table of its own. "The digit
/// rows" are exactly the rows whose target is one ASCII digit, which the bundled map
/// already states, so the set is read off the live table instead of duplicated beside it
/// — and therefore cannot drift from it. The two tables disagree about which sources
/// those are (157 rows in the Latin map, 66 in the Cyrillic, neither a subset of the
/// other), so a separate file would have had to be per-target as well.
#[inline]
fn lookup_with_policy(
    map: Option<tables::ConfusableMap>,
    ch: char,
    tr39_digits: bool,
    preserve_digits: bool,
) -> Option<&'static str> {
    if tr39_digits {
        if let Some(over) = crate::tables::confusable_digit_tr39_override(ch) {
            return Some(over);
        }
    }
    let hit = map.and_then(|m| m.get(&ch).copied())?;
    if preserve_digits && hit.len() == 1 && hit.as_bytes()[0].is_ascii_digit() {
        return None;
    }
    Some(hit)
}

/// Validate the `target_script` parameter.
///
/// Supported values: `"latin"`, `"cyrillic"`, `"arabic"`, `"hebrew"` (#792).
///
/// This list and the `match` below are the same list written twice, so they are checked
/// against each other: `crate::api::TargetScript` enumerates the supported values, and
/// `every_target_script_variant_validates` asserts each variant passes here and that
/// nothing outside it does.
fn validate_target_script(target_script: &str) -> Result<(), crate::ErrorRepr> {
    match target_script {
        "latin" | "cyrillic" | "arabic" | "hebrew" => Ok(()),
        _ => Err(crate::ErrorRepr::InvalidTargetScript {
            got: target_script.to_owned(),
        }),
    }
}

/// Replace Unicode confusable homoglyphs with target-script equivalents.
///
/// The public fold/detect entrypoints compose each base + combining-mark cluster at
/// lookup time (#475/#477, see [`crate::compose`]) so a *decomposed* homoglyph (`і`
/// U+0456 + combining diaeresis U+0308) reaches the bundled table's *precomposed*
/// entry (`ї` U+0457 → `i`) instead of mapping only the base and leaving the mark —
/// otherwise the recovery is evadable, and detection flips, by sending the decomposed
/// form. Compose-only (never decompose), so a composition-excluded presentation form
/// (`שׂ` U+FB2B) keeps its own table entry, and the result is invariant to the input's
/// normal form. The preset-internal `normalize_confusables_into` stays pure — the
/// presets canonicalize their own input upstream.
///
/// # NFKC interaction warning
/// Compose-at-lookup applies only **canonical** composition, never **NFKC**
/// (compatibility) mappings. NFKC must not be added: ~31 codepoints in the TR39
/// confusables table conflict with NFKC mappings (e.g. ſ U+017F: TR39→f but NFKC→s).
/// Canonical composition is safe because it never applies a compatibility mapping. If
/// NFKC is ever needed, `gen_confusables.py` must filter entries where the TR39 target
/// differs from `unicodedata.normalize('NFKC', chr(cp))`.
/// See: <https://paultendo.github.io/posts/unicode-confusables-nfkc-conflict/>
///
/// # Valid `target_script` values
/// `"latin"`, `"cyrillic"`, `"arabic"` or `"hebrew"` (#792). Any other value returns
/// [`crate::ErrorRepr`].
pub(crate) fn normalize_confusables(
    text: &str,
    target_script: &str,
    digit_policy: &str,
) -> Result<String, crate::ErrorRepr> {
    // Owned wrapper over the borrowing fixed-point form, which is where the loop and its
    // rationale live. `_fixed_cow` borrows on a no-op (#352), so pure-ASCII or
    // already-folded input never allocates a rebuilt string — only this final owned
    // conversion copies a borrow.
    Ok(normalize_confusables_fixed_cow(text, target_script, digit_policy)?.into_owned())
}

/// Borrowing form of [`normalize_confusables`] (#352): returns `Cow::Borrowed`
/// when `text` contains no confusable for the target (the common case), so a
/// no-op never allocates. A single pass — it only starts building an owned
/// string at the first character that actually folds.
pub(crate) fn normalize_confusables_cow<'a>(
    text: &'a str,
    target_script: &str,
    digit_policy: &str,
) -> Result<std::borrow::Cow<'a, str>, crate::ErrorRepr> {
    use std::borrow::Cow;

    validate_target_script(target_script)?;
    validate_digit_policy(digit_policy)?;
    let map = tables::resolve_confusable_map(target_script);
    // Resolved once, not per character: the default path must not pay for the option.
    // Latin-only: the override set carries TR39's *Latin* targets, so it must never be
    // consulted for another target script (see `lookup_with_policy`).
    let tr39_digits = digit_policy == "tr39" && target_script == "latin";
    // Unlike `tr39`, this is target-agnostic: it declines to fold a digit at all, so
    // there is no Latin-target restriction to honour.
    let preserve_digits = digit_policy == "preserve";

    // #475/#477: a base + combining-mark cluster (or a conjoining Hangul jamo run, #483)
    // must fold as its precomposed form. Compose-at-lookup can only change something when
    // such input is present, so gate on that: it is folded into an owned buffer, while
    // input with neither (the common case — ASCII, CJK, precomposed letters) falls
    // through to the single-pass borrow-on-no-op path, which never allocates on a no-op.
    // ASCII can carry neither a combining mark nor a conjoining jamo, so skip the
    // `needs_composition` char-decode scan on it entirely (M-3) — `is_ascii` is a cheap
    // byte scan that short-circuits on the first non-ASCII byte, so non-ASCII pays ~nothing
    // extra, but pure-ASCII input no longer runs a second full trie-lookup pass.
    if !text.is_ascii() && crate::compose::needs_composition(text) {
        let mut out = String::with_capacity(text.len());
        for (ch, _) in crate::compose::composed(text) {
            match lookup_with_policy(map, ch, tr39_digits, preserve_digits) {
                Some(replacement) => out.push_str(replacement),
                None => out.push(ch),
            }
        }
        return Ok(Cow::Owned(out));
    }

    for (i, ch) in text.char_indices() {
        if let Some(replacement) = lookup_with_policy(map, ch, tr39_digits, preserve_digits) {
            // First fold found: copy the borrowed prefix, then fold the rest.
            let mut out = String::with_capacity(text.len());
            out.push_str(&text[..i]);
            out.push_str(replacement);
            for ch in text[i + ch.len_utf8()..].chars() {
                match lookup_with_policy(map, ch, tr39_digits, preserve_digits) {
                    Some(replacement) => out.push_str(replacement),
                    None => out.push(ch),
                }
            }
            return Ok(Cow::Owned(out));
        }
    }
    Ok(Cow::Borrowed(text))
}

/// [`normalize_confusables_cow`] iterated to a fixed point (#522) — the borrowing form
/// of [`normalize_confusables`], and the one every public surface must call.
///
/// Confusable folding and canonical composition expose work for each other in *both*
/// directions, so one pass is not stable:
///   * a fold can expose a composition — `¥`+◌̀ folds to `Y`+◌̀, which composes to `Ỳ`;
///   * a composition can expose a *new* fold — `Ҫ`+◌̧ composes to `Ç`, itself a
///     confusable that folds to `C`.
///
/// Re-running `_cow` (which composes-at-lookup on its input each pass) until the output
/// stops changing makes the result idempotent by construction, and complete: the loop can
/// only exit once no char folds, i.e. `is_confusable` is false. That holds under `numeric`
/// and `tr39`. Under `preserve` the digit rows never fold, by design (#648), and
/// `is_confusable`, which takes no policy, still flags them (the Lean model in
/// `formal/lean/Confusables`, F2). That completeness is the
/// point — #586 was the Layer-2 API calling the single-pass form, so `normalize` returned
/// strings that `is_confusable` still flagged, and the five non-Python bindings all
/// inherited it.
///
/// Most input settles in two or three passes. A fold cycle takes one pass per mark:
/// `C` with U+0327 composes to `Ç`, which folds back to `C`, ready for the next
/// cedilla, so a stack of nine outlasts [`MAX_CONFUSABLE_PASSES`] (found by the nightly
/// fuzz run). Input still changing at the cap goes to [`converge_slow`], which finishes
/// it span by span and skips a cycle's repeats: a few passes, not one per mark.
///
/// Borrows on a no-op exactly as `_cow` does (#352): input with nothing to fold is
/// already a fixed point, so the common case still never allocates.
pub(crate) fn normalize_confusables_fixed_cow<'a>(
    text: &'a str,
    target_script: &str,
    digit_policy: &str,
) -> Result<std::borrow::Cow<'a, str>, crate::ErrorRepr> {
    let mut cur = match normalize_confusables_cow(text, target_script, digit_policy)? {
        // Borrowed ⇒ nothing folded ⇒ the input is already a fixed point (the common case).
        std::borrow::Cow::Borrowed(s) => return Ok(std::borrow::Cow::Borrowed(s)),
        std::borrow::Cow::Owned(s) => s,
    };
    for _ in 0..MAX_CONFUSABLE_PASSES {
        match normalize_confusables_cow(&cur, target_script, digit_policy)? {
            std::borrow::Cow::Borrowed(_) => return Ok(std::borrow::Cow::Owned(cur)),
            std::borrow::Cow::Owned(next) if next == cur => {
                return Ok(std::borrow::Cow::Owned(cur));
            }
            std::borrow::Cow::Owned(next) => cur = next,
        }
    }
    let tr39_digits = digit_policy == "tr39" && target_script == "latin";
    converge_slow(
        cur,
        &fold_pass(target_script, digit_policy),
        &folds(target_script, tr39_digits, digit_policy == "preserve"),
    )
    .map(std::borrow::Cow::Owned)
}

/// A run of one combining mark at least this long loses the same number of copies to a
/// pass at every length ([`skip_cycle`]). Composition takes at most three marks into a
/// starter, since no character's NFD is longer than four, and the excluded-composition
/// map can touch only a run's first and last copy. Eight leaves copies between them.
const CYCLE_RUN_MIN: usize = 8;

/// The fold's own pass, for [`converge_slow`].
fn fold_pass<'p>(
    target_script: &'p str,
    digit_policy: &'p str,
) -> impl Fn(&str) -> Result<String, crate::ErrorRepr> + 'p {
    move |text| Ok(normalize_confusables_cow(text, target_script, digit_policy)?.into_owned())
}

/// Whether the fold rewrites `ch`, under the policy flags `normalize_confusables_cow`
/// and `normalize_confusables_into` resolve.
fn folds(target_script: &str, tr39_digits: bool, preserve_digits: bool) -> impl Fn(char) -> bool {
    let map = tables::resolve_confusable_map(target_script);
    move |ch| lookup_with_policy(map, ch, tr39_digits, preserve_digits).is_some()
}

/// Finish a presets loop of the confusable fold and then `form`, `normalize_into` style,
/// which its cap of passes did not settle. The presets and the pipeline iterate the
/// fold that way, rather than through compose-at-lookup, and meet the same cycles.
pub(crate) fn converge_fold_then_normalize(
    text: String,
    target_script: &str,
    digit_policy: DigitPolicy,
    form: &str,
) -> Result<String, crate::ErrorRepr> {
    let tr39_digits = digit_policy == DigitPolicy::Tr39 && target_script == "latin";
    let preserve_digits = digit_policy == DigitPolicy::Preserve;
    let pass = |text: &str| {
        let mut folded = String::with_capacity(text.len());
        normalize_confusables_into(text, target_script, digit_policy, &mut folded)?;
        let mut out = String::with_capacity(folded.len());
        crate::normalize::normalize_into(&folded, form, &mut out)?;
        Ok(out)
    };
    converge_slow(
        text,
        &pass,
        &folds(target_script, tr39_digits, preserve_digits),
    )
}

/// Can a span begin at `ch`? It starts a unit ([`crate::compose::starts_unit`]), and so
/// does the first character of its compatibility decomposition: U+FF9E starts a unit,
/// and NFKC turns it into U+3099, which composes with the character before.
fn cuts_before(ch: char) -> bool {
    let mut first = None;
    unicode_normalization::char::decompose_compatible(ch, |c| {
        first.get_or_insert(c);
    });
    crate::compose::starts_unit(ch) && first.is_some_and(crate::compose::starts_unit)
}

/// The fixed point of `pass` from `text`, which a capped loop of it did not settle.
///
/// Only a fold cycle keeps a string changing that long, and each pass over the whole
/// string would cost its full length, once per mark. So the string is cut before every
/// character a span can begin at ([`cuts_before`]): no cluster, Hangul syllable or
/// compatibility decomposition crosses a cut, and every fold output starts a unit, so
/// each span folds on its own as it does in place. The spans converge one at a time, and
/// the whole is checked with one more pass.
///
/// `folds` says whether the pass's fold rewrites a character, for [`skip_cycle`].
pub(crate) fn converge_slow(
    mut text: String,
    pass: &dyn Fn(&str) -> Result<String, crate::ErrorRepr>,
    folds: &dyn Fn(char) -> bool,
) -> Result<String, crate::ErrorRepr> {
    for _ in 0..MAX_CONFUSABLE_PASSES {
        let mut next = String::with_capacity(text.len());
        let mut start = 0;
        for (i, ch) in text.char_indices().skip(1) {
            if cuts_before(ch) {
                next.push_str(&converge_span(&text[start..i], pass, folds)?);
                start = i;
            }
        }
        next.push_str(&converge_span(&text[start..], pass, folds)?);
        if pass(&next)? == next {
            return Ok(next);
        }
        text = next;
    }
    debug_assert!(false, "the confusable fold did not converge: {text:?}");
    Ok(text)
}

/// The fixed point of `pass` on one span, skipping the repeats of a fold cycle
/// ([`skip_cycle`]).
fn converge_span(
    span: &str,
    pass: &dyn Fn(&str) -> Result<String, crate::ErrorRepr>,
    folds: &dyn Fn(char) -> bool,
) -> Result<String, crate::ErrorRepr> {
    let mut cur = span.to_owned();
    // Every pass that changes the span without a cycle to skip takes a mark or folds a
    // character, so the span's length bounds them.
    for _ in 0..=cur.chars().count() + MAX_CONFUSABLE_PASSES {
        let next = pass(&cur)?;
        if next == cur {
            return Ok(cur);
        }
        cur = match skip_cycle(&cur, &next, pass, folds)? {
            Some(skipped) => skipped,
            None => next,
        };
    }
    debug_assert!(false, "the confusable fold did not converge: {cur:?}");
    Ok(cur)
}

/// `text` as runs of one character: `(char, count)`.
fn runs(text: &str) -> Vec<(char, usize)> {
    let mut out: Vec<(char, usize)> = Vec::new();
    for ch in text.chars() {
        match out.last_mut() {
            Some((c, n)) if *c == ch => *n += 1,
            _ => out.push((ch, 1)),
        }
    }
    out
}

fn from_runs(runs: &[(char, usize)]) -> String {
    runs.iter()
        .flat_map(|&(c, n)| std::iter::repeat_n(c, n))
        .collect()
}

/// When the pass `prev` → `next` is a fold cycle eating a run of marks, the string the
/// cycle leaves once the run is down to [`CYCLE_RUN_MIN`]: the passes in between are
/// skipped.
///
/// The pass must have removed `d` copies of one mark `m` from one run and changed nothing
/// else, with at least [`CYCLE_RUN_MIN`] copies left. `m` has a nonzero combining class,
/// is its own NFKD and does not fold. Then, for any length `x` of that run of at least
/// [`CYCLE_RUN_MIN`], a pass maps the string to `P' m^(x - c) S'`, with `P'`, `S'` and
/// `c` the same at every `x`:
///
/// * canonical ordering keeps the copies together, and composition takes at most three
///   of them, a prefix, into the starter; the first copy it leaves blocks the rest, and
///   blocks nothing a copy would not;
/// * the excluded-composition map of compose-at-lookup can take only the run's first or
///   last copy, since no key holds a character twice in a row;
/// * the fold leaves every copy alone.
///
/// That holds for every pass [`converge_slow`] is given: compose-at-lookup then the
/// fold; the fold then NFC or NFKC; and `skeleton_key`'s case fold, fold and NFKC.
/// `folds` then covers a case fold as well.
///
/// Where `P'` ends is checked, not assumed: one more pass, on `prev` with the run one
/// copy longer, must give `next` with the run one copy longer. Then the insertion point
/// lies inside the run, and a pass at any length `x` gives `next`'s shape with `x - d`
/// copies, so the cycle is applied as many times as that holds at once.
fn skip_cycle(
    prev: &str,
    next: &str,
    pass: &dyn Fn(&str) -> Result<String, crate::ErrorRepr>,
    folds: &dyn Fn(char) -> bool,
) -> Result<Option<String>, crate::ErrorRepr> {
    use unicode_normalization::char::{canonical_combining_class, decompose_compatible};

    let (before, mut after) = (runs(prev), runs(next));
    if before.len() != after.len() {
        return Ok(None);
    }
    let mut changed = before
        .iter()
        .zip(&after)
        .enumerate()
        .filter(|(_, (b, a))| b != a);
    let Some((run, (&(mark, was), &(still, left)))) = changed.next() else {
        return Ok(None);
    };
    let taken = was.saturating_sub(left);
    if changed.next().is_some()
        || mark != still
        || taken == 0
        || taken >= CYCLE_RUN_MIN
        || left < CYCLE_RUN_MIN
    {
        return Ok(None);
    }
    let mut own_nfkd = true;
    decompose_compatible(mark, |c| own_nfkd &= c == mark);
    if canonical_combining_class(mark) == 0 || !own_nfkd || folds(mark) {
        return Ok(None);
    }

    let mut longer = before;
    longer[run].1 += 1;
    let probe = pass(&from_runs(&longer))?;
    after[run].1 += 1;
    if probe != from_runs(&after) {
        return Ok(None);
    }
    // Each pass needs `CYCLE_RUN_MIN` copies going in: skip every pass that has them.
    let passes = (left - CYCLE_RUN_MIN) / taken + 1;
    after[run].1 = left - passes * taken;
    Ok(Some(from_runs(&after)))
}

/// In-place form of [`normalize_confusables`] writing into `out` (cleared
/// first), so the pipeline can reuse one buffer across steps (#236 item 7).
pub(crate) fn normalize_confusables_into(
    text: &str,
    target_script: &str,
    digit_policy: DigitPolicy,
    out: &mut String,
) -> Result<(), crate::ErrorRepr> {
    validate_target_script(target_script)?;
    out.clear();
    out.reserve(text.len());

    // Resolve the confusables map once (#236 / #233 review item) instead of
    // re-dispatching `target_script` for every character. `validate_target_script`
    // above guarantees `Some`. There is deliberately no ASCII fast path: the
    // latin table maps ASCII source code points (U+007C `|`→`l`, U+0022 `"`→`''`,
    // U+0060 `` ` ``→`'`), so ASCII input is not identity even for `target="latin"`.
    let map = tables::resolve_confusable_map(target_script);

    // The policy is applied here rather than assumed (#646 §2). Until this took a
    // `DigitPolicy` it did a bare map lookup, so `Step::Confusables` — and through it
    // every preset — was pinned to `numeric` while the public `normalize_confusables`
    // could be told otherwise. Two call paths into the same fold, one of which could not
    // express the security-relevant setting.
    let tr39_digits = digit_policy == DigitPolicy::Tr39 && target_script == "latin";
    let preserve_digits = digit_policy == DigitPolicy::Preserve;

    for ch in text.chars() {
        match lookup_with_policy(map, ch, tr39_digits, preserve_digits) {
            Some(replacement) => out.push_str(replacement),
            None => out.push(ch),
        }
    }

    Ok(())
}

// ── Coverage introspection (#563) ────────────────────────────────────────────────
//
// `find_untranslatable` has existed for transliteration since #184; there was no
// confusables analogue, so the only way to ask "which sources go uncovered?" was to
// rebuild the capability outside the library against a cached copy of the upstream
// file. A defender needs the answer because that set is precisely where an adaptive
// attacker moves: a tool at 0.949 per-source coverage is not 95% safe, it is one query
// away from the other 5%.

/// Every upstream confusable source the bundled `target_script` table does not map,
/// sorted by codepoint.
///
/// # Valid `target_script` values
/// `"latin"`, `"cyrillic"`, `"arabic"` or `"hebrew"` (#792). Any other value returns
/// [`crate::ErrorRepr`].
pub(crate) fn unmapped_confusables(target_script: &str) -> Result<Vec<char>, crate::ErrorRepr> {
    validate_target_script(target_script)?;
    Ok(tables::unmapped_confusable_sources(target_script))
}

/// Scan `text` for characters upstream marks as confusable that the bundled
/// `target_script` table does **not** fold, as `(char, byte_offset)` in order of
/// appearance — the confusables analogue of `find_untranslatable`.
///
/// Composes at lookup exactly as the fold does (#475/#477/#483), so a decomposed
/// homoglyph whose *precomposed* form is mapped is correctly reported as covered
/// rather than as a gap. Each report is a character of the caller's `text` at its own
/// offset ([`crate::compose::input_char_at`]), never one of the composed intermediate.
///
/// # Valid `target_script` values
/// `"latin"`, `"cyrillic"`, `"arabic"` or `"hebrew"` (#792). Any other value returns
/// [`crate::ErrorRepr`].
pub(crate) fn find_unmapped_confusables(
    text: &str,
    target_script: &str,
) -> Result<Vec<(char, usize)>, crate::ErrorRepr> {
    validate_target_script(target_script)?;
    let map = tables::resolve_confusable_map(target_script);

    let mut out = Vec::new();
    // Always iterate through `composed`: it is identity on input with nothing to
    // compose, and going through one path keeps this scan and the fold in lockstep by
    // construction. A character is a gap iff the fold would leave it alone AND upstream
    // considers it confusable — the second half is what separates "disarm does not
    // touch this" from "disarm cannot neutralize this".
    for (ch, offset) in crate::compose::composed(text) {
        let mapped = map.is_some_and(|m| m.contains_key(&ch));
        if !mapped && tables::is_upstream_confusable_source(ch) {
            out.push((crate::compose::input_char_at(text, offset, ch), offset));
        }
    }
    Ok(out)
}

/// Every **mapped** confusable in `text`, with its byte offset and its fold target (#737).
///
/// The mirror of [`find_unmapped_confusables`]: the two read the same table from opposite
/// sides. That one answers *"what would survive the fold?"* — exposure. This one answers
/// *"what did the fold change, and to what?"* — evidence.
///
/// `is_confusable` returns a bare `bool` and `normalize_confusables` returns the folded
/// string; neither says **where**. A caller that wants to highlight the impersonated
/// character, or log which one it was, had to diff the two strings and hope the fold was
/// length-preserving, which it is not (`ﬁ` -> `fi`).
///
/// Offsets are anchored in the caller's `text`, and iterate through `composed` for the
/// same reason the sibling does: one path keeps this scan and the fold in lockstep by
/// construction. The character reported is the input's at that offset
/// ([`crate::compose::input_char_at`]); the target is the fold of what the scan looked up.
///
/// # Valid `target_script` values
/// `"latin"`, `"cyrillic"`, `"arabic"` or `"hebrew"` (#792). Any other value returns
/// [`crate::ErrorRepr`].
pub(crate) fn find_confusables(
    text: &str,
    target_script: &str,
    allowed_scripts: &[&str],
) -> Result<Vec<(char, usize, &'static str)>, crate::ErrorRepr> {
    validate_target_script(target_script)?;
    let allowed = canonical_scripts(allowed_scripts)?;
    let map = tables::resolve_confusable_map(target_script);

    let mut out = Vec::new();
    for (ch, offset) in crate::compose::composed(text) {
        if skipped_by_detection(ch) {
            continue;
        }
        if let Some(target) = map.and_then(|m| m.get(&ch)) {
            if !allowed.is_empty() && is_allowed(ch, &allowed) {
                continue;
            }
            out.push((
                crate::compose::input_char_at(text, offset, ch),
                offset,
                *target,
            ));
        }
    }
    Ok(out)
}

/// Whether `ch` belongs to a script the caller declared legitimate (#900).
///
/// **`Common` and `Inherited` are never allowed, whatever the caller passes**, and that
/// is what keeps this from costing recall. The characters that carry a spoof without
/// belonging to any script — `ℐ` U+2110, `Ⅰ` U+2160, `𝐈` U+1D408, the mathematical
/// alphanumerics — all resolve to `Common` here, so no declaration can suppress them.
/// A caller who says "Cyrillic is legitimate" exempts Cyrillic letters and nothing else.
fn is_allowed(ch: char, allowed: &[&'static str]) -> bool {
    let script = crate::scripts::detect_char_script(ch);
    if script == "Common" || script == "Inherited" {
        return false;
    }
    allowed.contains(&script)
}

/// Resolve caller-supplied script names to their canonical spelling, case-insensitively.
///
/// `detect_scripts` returns `Cyrillic`; `target_script` on this same function takes
/// `cyrillic`. Rather than make the caller remember which parameter wants which, both
/// spellings are accepted here and resolved against [`crate::metadata::SCRIPTS`].
///
/// # Errors
///
/// [`crate::ErrorRepr::UnknownScript`] naming the first unrecognised entry.
fn canonical_scripts(names: &[&str]) -> Result<Vec<&'static str>, crate::ErrorRepr> {
    names
        .iter()
        .map(|name| {
            crate::metadata::SCRIPTS
                .iter()
                .find(|known| known.eq_ignore_ascii_case(name))
                .copied()
                .ok_or_else(|| crate::ErrorRepr::UnknownScript {
                    got: (*name).to_owned(),
                })
        })
        .collect()
}

/// True if text contains any characters confusable with target-script characters.
///
/// # Valid `target_script` values
/// `"latin"`, `"cyrillic"`, `"arabic"` or `"hebrew"` (#792). Any other value returns
/// [`crate::ErrorRepr`].
pub(crate) fn is_confusable(text: &str, target_script: &str) -> Result<bool, crate::ErrorRepr> {
    validate_target_script(target_script)?;

    // #475/#477: detect on the compose-at-lookup form so a decomposed homoglyph can't
    // evade detection (a composed `ç` is confusable; its decomposed `c`+cedilla
    // otherwise is not). See [`crate::compose`].
    let map = tables::resolve_confusable_map(target_script);
    for (ch, _) in crate::compose::composed(text) {
        // #957: the range check comes first, so ASCII text skips the table probe entirely.
        if skipped_by_detection(ch) {
            continue;
        }
        if map.is_some_and(|m| m.contains_key(&ch)) {
            return Ok(true);
        }
    }
    Ok(false)
}

#[cfg(test)]
mod tests {
    /// #849 review: the doc comment on `validate_target_script` still said
    /// `"latin"`/`"cyrillic"` after #792 added two more. The list is written twice — once
    /// as the `match` arms here, once as `TargetScript`'s variants — so hold them together
    /// rather than relying on both being edited.
    /// #957: the rule, swept. Printable ASCII is never a detection, whatever the table
    /// gains later — the three rows that exist today are `"`, `` ` `` and `|`.
    #[test]
    fn printable_ascii_is_not_a_detection() {
        // Every supported target, not just Latin: `skipped_by_detection` is target-agnostic
        // and the contract is stated that way, so a table gained for another script must
        // not start reporting quoted prose either (#960 review).
        for target in crate::api::TargetScript::ALL {
            for cp in 0x21u32..0x7Fu32 {
                let ch = char::from_u32(cp).expect("ASCII is always a scalar value");
                let s = ch.to_string();
                assert!(
                    !is_confusable(&s, target.as_str()).unwrap(),
                    "U+{cp:04X} {ch:?} is reported as confusable for {target:?}"
                );
                assert!(
                    find_confusables(&s, target.as_str(), &[])
                        .unwrap()
                        .is_empty(),
                    "U+{cp:04X} {ch:?} is located as confusable for {target:?}"
                );
            }
        }
    }

    /// Both halves. #725 keeps the three rows in the fold; #957 stops them being
    /// detections. Asserting only the second would pass if the rows had been deleted,
    /// which is the fix #957 explicitly did not ask for.
    #[test]
    fn the_fold_still_rewrites_what_the_detector_ignores() {
        for (source, folded) in [('|', "l"), ('"', "''"), ('`', "'")] {
            let s = source.to_string();
            assert_eq!(
                normalize_confusables(&s, "latin", "numeric").unwrap(),
                folded
            );
            assert!(!is_confusable(&s, "latin").unwrap());
        }
    }

    /// The skip must not become a way of turning the detector off.
    #[test]
    fn a_homoglyph_beside_ascii_punctuation_is_still_detected() {
        assert!(is_confusable("say \"p\u{0430}ypal\"", "latin").unwrap());
        let hits = find_confusables("say \"p\u{0430}ypal\"", "latin", &[]).unwrap();
        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0].0, '\u{0430}');
    }

    #[test]
    fn every_target_script_variant_validates() {
        for variant in crate::api::TargetScript::ALL {
            assert!(
                validate_target_script(variant.as_str()).is_ok(),
                "TargetScript::{variant:?} ({:?}) is not accepted by validate_target_script",
                variant.as_str(),
            );
        }
    }

    /// The third copy of the same list: the error message (#888).
    ///
    /// It read `"target_script must be 'latin' or 'cyrillic'"` and stayed that way when
    /// #792 added Arabic and Hebrew — naming two of the four values it accepts, on all
    /// three entry points. A caller who trusted it could not discover the two targets
    /// that cycle existed to add.
    ///
    /// The two tests around this one hold the validator and the enum together; nothing
    /// held the message. It is now derived from `TargetScript::ALL`, and this asserts the
    /// derivation names every accepted token and nothing else — so a fifth target updates
    /// the message by construction rather than by someone remembering.
    #[test]
    fn the_error_message_names_exactly_the_accepted_scripts() {
        // A `got` value that is not itself a script name, so the absence checks below
        // cannot trip over the rejected value being echoed back.
        let message = crate::ErrorRepr::InvalidTargetScript {
            got: "klingon".to_owned(),
        }
        .to_string();
        for variant in crate::api::TargetScript::ALL {
            let quoted = format!("'{}'", variant.as_str());
            assert!(
                message.contains(&quoted),
                "the error does not name the accepted script {quoted}: {message:?}",
            );
        }
        // And nothing it does not accept — including the three largest unsupported
        // targets in the table, which is what makes the list informative rather than
        // decorative (#888).
        for absent in ["'greek'", "'han'", "'hangul'"] {
            assert!(
                !message.contains(absent),
                "the error names {absent}, which is not accepted: {message:?}",
            );
        }
        assert!(
            message.contains("got 'klingon'"),
            "the error must still report the offending value: {message:?}",
        );
    }

    /// And the other direction: the validator must not accept a token the type cannot
    /// express, or the enum stops being the definition of what is supported.
    #[test]
    fn the_validator_accepts_nothing_outside_the_enum() {
        let known: Vec<&str> = crate::api::TargetScript::ALL
            .iter()
            .map(|v| v.as_str())
            .collect();
        for candidate in [
            "greek", "klingon", "Latin", "LATIN", "", "arabic ", "hebrew\n", "han",
        ] {
            if known.contains(&candidate) {
                continue;
            }
            assert!(
                validate_target_script(candidate).is_err(),
                "validate_target_script accepted {candidate:?}, which TargetScript cannot \
                 express",
            );
        }
    }

    /// Tier-3 exhaustive gate for the fold/compose idempotency invariant (#522).
    ///
    /// The `\PC*` proptest below is a *random* walk, so the specific two-code-point
    /// adjacency that breaks idempotency — a confusable base immediately followed by a
    /// combining mark that composes with the *folded* base — is astronomically unlikely
    /// to be generated, and indeed slipped through 1000-case runs until one unlucky CI
    /// seed hit `¥\u{340}`. The bug class is *local* (base + mark), so it is bounded and
    /// deterministically enumerable: cross every confusable source code point with every
    /// combining mark and assert both invariants hold for every pair. This caught 61
    /// residual failures that the one-shot recompose missed. `#[ignore]` (Tier 3): ~9M
    /// pairs, a few seconds in release — too slow for per-PR CI, run pre-release.
    #[test]
    #[ignore = "exhaustive: ~9M (confusable × mark) pairs; run in Tier 3 / pre-release"]
    fn exhaustive_fold_compose_idempotent_and_complete() {
        use unicode_normalization::char::is_combining_mark;
        let marks: Vec<char> = (0u32..=0x0010_FFFF)
            .filter_map(char::from_u32)
            .filter(|&c| is_combining_mark(c))
            .collect();
        for script in ["latin", "cyrillic"] {
            let map = tables::resolve_confusable_map(script).unwrap();
            for &base in map.keys() {
                for &m in &marks {
                    let s: String = [base, m].iter().collect();
                    let once = normalize_confusables(&s, script, "numeric").unwrap();
                    let twice = normalize_confusables(&once, script, "numeric").unwrap();
                    assert_eq!(
                        once, twice,
                        "not idempotent: base U+{:04X} + mark U+{:04X} ({script})",
                        base as u32, m as u32
                    );
                    assert!(
                        !is_confusable(&once, script).unwrap(),
                        "residual confusable after normalize: base U+{:04X} + mark U+{:04X} ({script}) → {once:?}",
                        base as u32, m as u32
                    );
                }
            }
        }
    }
    use super::*;

    #[test]
    fn test_normalize_confusables_cyrillic() {
        // Cyrillic 'а' (U+0430) → Latin 'a'
        let result = normalize_confusables("\u{0430}", "latin", "numeric").unwrap();
        assert_eq!(result, "a");
    }

    #[test]
    fn test_normalize_confusables_passthrough() {
        let result = normalize_confusables("hello", "latin", "numeric").unwrap();
        assert_eq!(result, "hello");
    }

    #[test]
    fn test_normalize_confusables_empty() {
        let result = normalize_confusables("", "latin", "numeric").unwrap();
        assert_eq!(result, "");
    }

    #[test]
    fn test_is_confusable_true() {
        // Cyrillic 'а' is confusable with Latin 'a'
        assert!(is_confusable("\u{0430}", "latin").unwrap());
    }

    #[test]
    fn test_is_confusable_false() {
        assert!(!is_confusable("hello", "latin").unwrap());
    }

    #[test]
    fn test_is_confusable_empty() {
        assert!(!is_confusable("", "latin").unwrap());
    }

    #[test]
    fn fold_and_detect_are_form_invariant() {
        // #475/#477: compose-at-lookup, so a decomposed homoglyph folds/detects the
        // same as its precomposed form. `ї` (U+0457) → "i"; NFD is `і` + U+0308.
        use unicode_normalization::UnicodeNormalization;
        for ch in ['\u{0457}', '\u{00E7}', '\u{03AF}', '\u{0625}'] {
            let nfc: String = std::iter::once(ch).collect();
            let nfd: String = std::iter::once(ch).nfd().collect();
            assert_ne!(nfc, nfd, "{ch:?} must actually decompose for this test");
            assert_eq!(
                normalize_confusables(&nfc, "latin", "numeric").unwrap(),
                normalize_confusables(&nfd, "latin", "numeric").unwrap(),
                "fold not form-invariant on {ch:?}"
            );
            assert_eq!(
                is_confusable(&nfc, "latin").unwrap(),
                is_confusable(&nfd, "latin").unwrap(),
                "detection not form-invariant on {ch:?}"
            );
        }
    }

    #[test]
    fn nfc_form_preserves_existing_output() {
        // Already-NFC / ASCII input is unchanged by compose-at-lookup (mark-free gate).
        assert_eq!(
            normalize_confusables("\u{0430}ll", "latin", "numeric").unwrap(),
            "all"
        );
        assert_eq!(
            normalize_confusables("hello", "latin", "numeric").unwrap(),
            "hello"
        );
    }

    #[test]
    fn composition_excluded_presentation_form_is_form_invariant() {
        // #477/#481: the input is never decomposed (the #478 regression class), so a bare
        // presentation form `שׂ` U+FB2B passes through unchanged. Its decomposition `ש`
        // U+05E9 + sin dot U+05C2 now *composes* to U+FB2B via the widening map (#481)
        // rather than staying split, so both forms agree on U+FB2B — form-invariant, and
        // neither is a Latin confusable, so both pass through to the same scalar.
        assert_eq!(
            normalize_confusables("\u{FB2B}", "latin", "numeric").unwrap(),
            "\u{FB2B}"
        );
        assert_eq!(
            normalize_confusables("\u{05E9}\u{05C2}", "latin", "numeric").unwrap(),
            "\u{FB2B}"
        );
    }

    #[test]
    fn test_validate_target_script_latin_ok() {
        assert!(validate_target_script("latin").is_ok());
    }

    #[test]
    fn test_validate_target_script_cyrillic_ok() {
        assert!(validate_target_script("cyrillic").is_ok());
    }

    #[test]
    fn test_validate_target_script_invalid() {
        assert!(validate_target_script("greek").is_err());
        assert!(validate_target_script("").is_err());
        assert!(validate_target_script("Latin").is_err()); // case-sensitive
        assert!(validate_target_script("Cyrillic").is_err()); // case-sensitive
    }

    #[test]
    fn test_normalize_confusables_mixed_long() {
        // String with confusable Cyrillic chars interspersed with ASCII
        let input = "h\u{0435}ll\u{043E} w\u{043E}rld"; // Cyrillic е and о
        let result = normalize_confusables(input, "latin", "numeric").unwrap();
        // Cyrillic е→e, о→o
        assert_eq!(result, "hello world");
    }

    #[test]
    fn test_normalize_confusables_nfc_vs_nfd() {
        // Confusable lookup operates on individual codepoints; NFC and NFD
        // should both work (combining marks aren't confusable targets).
        let nfc = "\u{00e9}"; // é as single codepoint
        let result = normalize_confusables(nfc, "latin", "numeric").unwrap();
        // é is not a confusable — it should pass through unchanged
        assert_eq!(result, nfc);
    }

    #[test]
    fn normalize_confusables_idempotent_when_fold_and_compose_interact() {
        // #522 regression, both interaction directions.
        //
        // (a) a fold exposes a composition. `¥` (U+00A5) folds to `Y`, carrying a combining
        //     grave (U+0340, which canonically decomposes to U+0300). The cluster composes
        //     to `¥`+U+0300 (yen has no precomposed grave); folding `¥`→`Y` leaves `Y`+U+0300,
        //     which composes to `Ỳ` (U+1EF2) — a non-confusable, so that is the fixed point.
        let once = normalize_confusables("\u{a5}\u{340}", "latin", "numeric").unwrap();
        assert_eq!(once, "\u{1ef2}"); // Ỳ
        assert_eq!(
            normalize_confusables(&once, "latin", "numeric").unwrap(),
            once
        );

        // (b) a composition exposes a *new* fold. `Ҫ` (U+04AA) folds to `C`, carrying a
        //     combining cedilla (U+0327); `C`+cedilla composes to `Ç` (U+00C7) — which is
        //     *itself* a confusable that folds to `C`. Only iterating to a fixed point
        //     reaches `C`; a single recompose would stop at the still-confusable `Ç`.
        let once = normalize_confusables("\u{04AA}\u{0327}", "latin", "numeric").unwrap();
        assert_eq!(once, "C");
        assert_eq!(
            normalize_confusables(&once, "latin", "numeric").unwrap(),
            once
        );
        assert!(!is_confusable(&once, "latin").unwrap());
    }

    /// The fixed point taken one pass at a time with no cap: what the fold must equal.
    fn fixed_point_by_passes(text: &str, script: &str, policy: &str) -> String {
        let mut cur = text.to_owned();
        loop {
            let next = normalize_confusables_cow(&cur, script, policy)
                .unwrap()
                .into_owned();
            if next == cur {
                return cur;
            }
            cur = next;
        }
    }

    /// The nightly fuzz run's input, as the `confusables` target decodes it: `Ҫ` folds
    /// to `C`, and then each pass composes one of the eight cedillas into `Ç` and folds
    /// it back to `C`. The loop gave up after eight passes with one cedilla left, so the
    /// fold was not idempotent and its output was still confusable.
    #[test]
    fn a_fold_cycle_converges_past_the_pass_cap() {
        let text = "A. \u{FFFD}\u{FFFD}\u{3AA}\u{4AA}\u{327}\u{32A}\u{327}\u{327}\u{327}\
                    \u{327}\u{32A}\u{327}\u{327}\u{327}\u{32C}\u{FFFD}\u{F37C}\u{FFFD}\
                    \u{FFFD}\u{F37C}\u{FFFD}\u{FFFD}";
        let once = normalize_confusables(text, "latin", "numeric").unwrap();
        assert_eq!(
            once,
            "A. \u{FFFD}\u{FFFD}\u{3AA}C\u{32A}\u{32A}\u{32C}\u{FFFD}\u{F37C}\u{FFFD}\
             \u{FFFD}\u{F37C}\u{FFFD}\u{FFFD}"
        );
        assert_eq!(once, fixed_point_by_passes(text, "latin", "numeric"));
        assert_eq!(
            normalize_confusables(&once, "latin", "numeric").unwrap(),
            once
        );
        assert!(!is_confusable(&once, "latin").unwrap());
    }

    /// `skip_cycle` jumps over passes; the result must be the one the passes reach. The
    /// three cycles the tables hold ([`every_fold_cycle_is_a_self_loop`]), plus a
    /// precomposed and a cross-script way in, at run lengths either side of
    /// `CYCLE_RUN_MIN` and the pass cap, with context the skip must carry unchanged: a
    /// mark of a higher class after the run, a second run the first one blocks, a
    /// spacing mark that starts a run of its own, and a second cluster.
    #[test]
    fn skipping_a_fold_cycle_matches_the_pass_by_pass_fixed_point() {
        let cycles = [
            ('C', '\u{327}'),
            ('c', '\u{327}'),
            ('i', '\u{309}'),
            ('\u{C7}', '\u{327}'),
            ('\u{4AA}', '\u{327}'),
        ];
        for (base, mark) in cycles {
            for n in 0..40 {
                let run: String = std::iter::repeat_n(mark, n).collect();
                for text in [
                    format!("{base}{run}"),
                    format!("x{base}{run}\u{301}\u{32A}y"),
                    format!("{base}{run}\u{328}{run}"),
                    format!("{base}{run}\u{9BE}{run}"),
                    format!("{base}{run} {base}{run}{run}\u{301}"),
                ] {
                    for policy in ["numeric", "tr39", "preserve"] {
                        assert_eq!(
                            normalize_confusables(&text, "latin", policy).unwrap(),
                            fixed_point_by_passes(&text, "latin", policy),
                            "{text:?} ({policy})"
                        );
                    }
                }
            }
        }
    }

    /// The presets' and the pipeline's form of the loop, the fold then a normal form, must
    /// reach the fixed point its passes reach too.
    #[test]
    fn the_presets_slow_path_matches_their_passes() {
        let cycles = [('C', '\u{327}'), ('c', '\u{327}'), ('i', '\u{309}')];
        for (base, mark) in cycles {
            for n in [0, 7, 8, 9, 17, 39] {
                let run: String = std::iter::repeat_n(mark, n).collect();
                for text in [
                    format!("{base}{run}"),
                    format!("x{base}{run}\u{301}\u{32A}y {base}{run}{run}"),
                    format!("{base}{run}\u{9BE}{run}\u{FF9E}"),
                ] {
                    for policy in [
                        DigitPolicy::Numeric,
                        DigitPolicy::Tr39,
                        DigitPolicy::Preserve,
                    ] {
                        for form in ["NFC", "NFKC"] {
                            let mut want = text.clone();
                            loop {
                                let mut folded = String::new();
                                normalize_confusables_into(&want, "latin", policy, &mut folded)
                                    .unwrap();
                                let mut next = String::new();
                                crate::normalize::normalize_into(&folded, form, &mut next).unwrap();
                                if next == want {
                                    break;
                                }
                                want = next;
                            }
                            let got =
                                converge_fold_then_normalize(text.clone(), "latin", policy, form)
                                    .unwrap();
                            assert_eq!(got, want, "{text:?} ({policy:?}, {form})");
                        }
                    }
                }
            }
        }
    }

    /// One pass per mark would make this quadratic: 200,000 passes over 400 KB.
    #[test]
    fn a_long_mark_stack_folds_in_a_few_passes() {
        let cedillas = format!("C{}", "\u{327}".repeat(200_000));
        assert_eq!(
            normalize_confusables(&cedillas, "latin", "numeric").unwrap(),
            "C"
        );
        let two = format!("{cedillas} i{}", "\u{309}".repeat(200_000));
        assert_eq!(
            normalize_confusables(&two, "latin", "numeric").unwrap(),
            "C i"
        );
    }

    /// A fold cycle that took two passes to come round would change the string in two
    /// places, or change the starter, and `skip_cycle` would not recognize it: the fold
    /// would still converge, one pass per mark. So every cycle in the graph of "a mark
    /// composes onto this fold output, and the result folds to that one" must be a self
    /// loop. These are the ones the tables hold.
    #[test]
    fn every_fold_cycle_is_a_self_loop() {
        use std::collections::{BTreeMap, BTreeSet};
        use unicode_normalization::char::canonical_combining_class;
        use unicode_normalization::UnicodeNormalization;

        let marks: Vec<char> = (0u32..=0x10_FFFF)
            .filter_map(char::from_u32)
            .filter(|&c| canonical_combining_class(c) > 0)
            .collect();
        let mut self_loops = Vec::new();
        for script in ["latin", "cyrillic", "arabic", "hebrew"] {
            let map = tables::resolve_confusable_map(script).unwrap();
            let starters: BTreeSet<char> = map
                .entries()
                .filter_map(|(_, value)| value.chars().last())
                .collect();
            let mut edges: BTreeMap<char, BTreeSet<char>> = BTreeMap::new();
            for &v in &starters {
                for &m in &marks {
                    let composed: Vec<char> = [v, m].into_iter().nfc().collect();
                    let [x] = composed[..] else { continue };
                    let Some(w) = map.get(&x).and_then(|value| value.chars().last()) else {
                        continue;
                    };
                    if w == v {
                        self_loops.push((script, v, m));
                    } else {
                        edges.entry(v).or_default().insert(w);
                    }
                }
            }
            // Kahn's algorithm: an acyclic graph empties.
            let mut indegree: BTreeMap<char, usize> = BTreeMap::new();
            for (&v, ws) in &edges {
                indegree.entry(v).or_default();
                for &w in ws {
                    *indegree.entry(w).or_default() += 1;
                }
            }
            let mut ready: Vec<char> = indegree
                .iter()
                .filter(|&(_, &n)| n == 0)
                .map(|(&v, _)| v)
                .collect();
            let mut removed = 0;
            while let Some(v) = ready.pop() {
                removed += 1;
                for w in edges.get(&v).into_iter().flatten() {
                    let n = indegree.get_mut(w).unwrap();
                    *n -= 1;
                    if *n == 0 {
                        ready.push(*w);
                    }
                }
            }
            assert_eq!(removed, indegree.len(), "a longer fold cycle ({script})");
        }
        assert_eq!(
            self_loops,
            [
                ("latin", 'C', '\u{327}'),
                ("latin", 'c', '\u{327}'),
                ("latin", 'i', '\u{309}'),
            ]
        );
    }

    /// `skip_cycle` assumes a pass takes fewer than `CYCLE_RUN_MIN - 2` copies of a run:
    /// at most one less than the longest canonical decomposition by composition, and two
    /// more at the ends.
    #[test]
    fn the_cycle_run_minimum_clears_what_one_pass_can_take() {
        use unicode_normalization::UnicodeNormalization;
        let longest = (0u32..=0x10_FFFF)
            .filter_map(char::from_u32)
            .map(|c| std::iter::once(c).nfd().count())
            .max()
            .unwrap();
        assert_eq!(longest, 4);
        assert!(CYCLE_RUN_MIN > (longest - 1) + 2);
    }

    /// `converge_slow` folds span by span. That is the whole-string fold only if what a
    /// span folds to never joins the span before it. A span's output starts with a table
    /// value, or with the NFC of the character that starts it, grown by composition. So
    /// every table value, every such NFC, and every primary composite built on a
    /// character that starts a unit must start one.
    #[test]
    fn a_span_folds_as_it_does_in_place() {
        use crate::compose::starts_unit;
        use unicode_normalization::UnicodeNormalization;
        for script in ["latin", "cyrillic", "arabic", "hebrew"] {
            let map = tables::resolve_confusable_map(script).unwrap();
            for (&key, value) in map.entries() {
                let first = value.chars().next().unwrap();
                assert!(starts_unit(first), "U+{:04X} ({script})", key as u32);
            }
        }
        for c in (0u32..=0x10_FFFF).filter_map(char::from_u32) {
            if starts_unit(c) {
                let first = std::iter::once(c).nfc().next().unwrap();
                assert!(starts_unit(first), "NFC of U+{:04X}", c as u32);
            }
            let nfd: Vec<char> = std::iter::once(c).nfd().collect();
            if nfd.len() > 1 && starts_unit(nfd[0]) && nfd.into_iter().nfc().eq(std::iter::once(c))
            {
                assert!(starts_unit(c), "composite U+{:04X}", c as u32);
            }
        }
    }

    #[test]
    fn confusable_table_values_are_non_empty() {
        // The fold never deletes content because every table value is non-empty — a
        // lookup always yields at least one output char. Asserted directly over the
        // tables (deterministic), replacing the former char-count proptest which no
        // longer holds once fold∘compose iterates to a fixed point (#522).
        for script in ["latin", "cyrillic"] {
            let map = tables::resolve_confusable_map(script).unwrap();
            for (&key, &value) in map.entries() {
                assert!(
                    !value.is_empty(),
                    "empty confusable mapping for U+{:04X} ({script})",
                    key as u32
                );
            }
        }
    }

    // ── Property-based tests ─────────────────────────────────────────

    mod proptest_properties {
        use super::*;
        use proptest::prelude::*;

        proptest! {
            #![proptest_config(ProptestConfig::with_cases(1000))]

            /// Normalizing confusables is idempotent: applying it twice
            /// yields the same result as applying it once. It holds because the
            /// fold iterates to a fixed point (#522), not because of the table's
            /// shape: 35 Latin rows map to a non-ASCII value (U+0101 to U+00E3),
            /// and three ASCII characters are sources themselves (#725). The Lean
            /// model in `formal/lean/Confusables` proves idempotence from
            /// convergence alone.
            #[test]
            fn normalize_confusables_idempotent(s in "\\PC*") {
                let once = normalize_confusables(&s, "latin", "numeric").unwrap();
                let twice = normalize_confusables(&once, "latin", "numeric").unwrap();
                prop_assert_eq!(&once, &twice,
                    "normalize_confusables is not idempotent on: {:?}", s);
            }

            /// After normalizing confusables, is_confusable must return false.
            /// This is the completeness invariant: if the table is self-consistent,
            /// no confusable characters survive normalization.
            #[test]
            fn normalized_is_not_confusable(s in "\\PC*") {
                let normalized = normalize_confusables(&s, "latin", "numeric").unwrap();
                let still_confusable = is_confusable(&normalized, "latin").unwrap();
                prop_assert!(!still_confusable,
                    "is_confusable returned true after normalize_confusables on: {:?} → {:?}",
                    s, normalized);
            }

            /// The fold never *annihilates* content: non-empty input yields non-empty
            /// output. A stronger char-count guarantee (`result >= composed input`) no
            /// longer holds since #522 — iterating fold∘compose to a fixed point can
            /// legitimately shorten the string (`Ҫ`+◌̧ → `Ç` → `C`, the cedilla absorbed
            /// then discarded because completeness forces the confusable `Ç` to fold to
            /// `C`). The "no table value is empty" guarantee that underpinned the old
            /// count check is asserted directly and deterministically by
            /// [`confusable_table_values_are_non_empty`].
            #[test]
            fn fold_never_annihilates_content(s in "\\PC+") {
                let result = normalize_confusables(&s, "latin", "numeric").unwrap();
                prop_assert!(!result.is_empty(),
                    "non-empty input {:?} normalized to empty", s);
            }

            /// normalize_confusables output is always valid UTF-8 (trivially
            /// true since we return String, but this catches memory corruption).
            #[test]
            fn normalize_confusables_valid_utf8(s in "\\PC*") {
                let result = normalize_confusables(&s, "latin", "numeric").unwrap();
                // If this compiles and doesn't panic, the result is valid UTF-8.
                let _ = result.len(); // forces evaluation
            }
        }
    }
}

/// The TR39 prototype classes disarm's table deliberately keeps apart (#650).
///
/// `confusables_to_latin.tsv` maps every member of the capital-I family to `I` — fullwidth
/// `Ｉ`, math `𝓘`, Cyrillic `І`, Greek `Ι`, Cherokee `Ꮥ` all arrive there. TR39 goes one
/// step further and puts `I`, `l` and `1` in a single class, with `O` and `0` in another.
/// disarm stops short on purpose: those last merges are between *ASCII* characters, so
/// they cost nothing to spot and everything to apply — `paypaI` and `paypal` become one
/// token, and so do `SKU-100` and `SKU-1O0`.
///
/// This applies that last step, for the one caller that wants it: a key whose only job is
/// to make two confusable identifiers collide, and whose output is never displayed.
///
/// **It must run on cased text.** Applied before a case fold the letter half costs six
/// collision groups in the 235,976 entries of `/usr/share/dict/words`; applied after, when
/// `I ≡ l` has become `i ≡ l`, it costs 264 — `boiling`/`bolling`, `doit`/`dolt`,
/// `ail`/`all`. A factor of 44, and the reason this is a separate builder rather than a
/// flag on `catalog_key`, which folds case at step 3 and cannot be reordered (#419).
///
/// The digit half rides on [`DigitPolicy::Tr39`], which is the same reading it already
/// selects elsewhere — non-Latin digits fold toward letters, "correct for an identifier
/// skeleton, ruinous for a field carrying a number". Under `Numeric` and `Preserve` the
/// digits stay digits and only the letter half applies.
pub(crate) fn prototype_fold_into(input: &str, digits: DigitPolicy, out: &mut String) -> bool {
    let fold_digits = matches!(digits, DigitPolicy::Tr39);
    // Nothing here is multi-byte, so a scan for the sources is exact and cheap.
    let hit = input
        .bytes()
        .any(|b| b == b'I' || (fold_digits && (b == b'1' || b == b'0')));
    if !hit {
        return false;
    }
    out.clear();
    out.reserve(input.len());
    for c in input.chars() {
        out.push(match c {
            // TR39's prototype for the I-family is `l`, not `I`.
            'I' => 'l',
            '1' if fold_digits => 'l',
            '0' if fold_digits => 'O',
            other => other,
        });
    }
    true
}

#[cfg(test)]
mod prototype_fold_tests {
    use super::*;

    fn fold(s: &str, d: DigitPolicy) -> String {
        let mut out = String::new();
        if prototype_fold_into(s, d, &mut out) {
            out
        } else {
            s.to_owned()
        }
    }

    /// The letter half is unconditional; the digit half is not.
    #[test]
    fn the_two_halves_are_separately_gated() {
        for policy in [DigitPolicy::Numeric, DigitPolicy::Preserve] {
            assert_eq!(
                fold("paypaI", policy),
                "paypal",
                "letter half is unconditional"
            );
            assert_eq!(fold("SKU-1O0", policy), "SKU-1O0", "digits untouched");
        }
        assert_eq!(fold("paypaI", DigitPolicy::Tr39), "paypal");
        assert_eq!(fold("SKU-1O0", DigitPolicy::Tr39), "SKU-lOO");
    }

    /// The borrow signal must be exact: `false` means the caller keeps its input.
    #[test]
    fn it_reports_whether_it_changed_anything() {
        let mut out = String::new();
        assert!(!prototype_fold_into("paypal", DigitPolicy::Tr39, &mut out));
        assert!(!prototype_fold_into(
            "no digits here",
            DigitPolicy::Numeric,
            &mut out
        ));
        assert!(!prototype_fold_into(
            "SKU-100",
            DigitPolicy::Numeric,
            &mut out
        ));
        assert!(prototype_fold_into("SKU-100", DigitPolicy::Tr39, &mut out));
        assert!(prototype_fold_into(
            "paypaI",
            DigitPolicy::Numeric,
            &mut out
        ));
    }

    /// Lowercase `o` is NOT in the O class here, because this runs before the case fold
    /// that merges it with `O` anyway. Adding it would be the 264-collision version.
    #[test]
    fn lowercase_o_is_left_alone() {
        assert_eq!(fold("book", DigitPolicy::Tr39), "book");
        assert_eq!(fold("BOOK", DigitPolicy::Tr39), "BOOK");
    }

    /// Non-ASCII passes through untouched — the confusables fold ran before this.
    #[test]
    fn non_ascii_is_not_this_steps_business() {
        assert_eq!(fold("Ω→café", DigitPolicy::Tr39), "Ω→café");
    }
}
