//! Layer 2 (part of [`crate::api`]) — cross-script confusable folding, script /
//! reverse / hostname analysis, and filename / encoding / log-injection safety.

use crate::Error;
use std::borrow::Cow;

// ── Confusables (TR39) ──────────────────────────────────────────────────────

/// Target script for confusable folding (see [`normalize_confusables`]).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[non_exhaustive]
pub enum TargetScript {
    /// Fold confusables onto their Latin prototypes (the common case).
    Latin,
    /// Fold confusables onto their Cyrillic prototypes.
    Cyrillic,
}

impl TargetScript {
    /// The lowercase token the underlying tables are keyed by.
    /// The canonical string token for this value (the inverse of its `FromStr`,
    /// and what `Display` prints).
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            TargetScript::Latin => "latin",
            TargetScript::Cyrillic => "cyrillic",
        }
    }
}

impl std::fmt::Display for TargetScript {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

impl std::str::FromStr for TargetScript {
    type Err = Error;

    /// Parse `"latin"` / `"cyrillic"`.
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "latin" => Ok(Self::Latin),
            "cyrillic" => Ok(Self::Cyrillic),
            _ => Err(Error::from(crate::ErrorRepr::InvalidTargetScript {
                got: s.to_owned(),
            })),
        }
    }
}

/// Replace Unicode confusable homoglyphs with their `target`-script prototypes
/// (TR39). Characters with no mapping pass through unchanged.
///
/// The input is canonically recomposed (NFC) before folding (#475, in the Layer-1
/// core), so the fold is invariant to the input's normal form — a decomposed
/// homoglyph (`і` + combining diaeresis) folds the same as its composed `ї`, instead
/// of leaving the mark and letting an attacker evade the fold by decomposing.
///
/// The fold iterates to a fixed point (#522/#586), so the result is idempotent —
/// `f(f(x)) == f(x)` — and complete: [`is_confusable`] is always false for the output.
/// One pass is not enough, because folding and canonical composition expose work for
/// each other in both directions (`¥`+◌̀ → `Y`+◌̀ → `Ỳ`, and `Ҫ`+◌̧ → `Ç` → `C`).
/// Completeness is what makes the result usable as a comparison skeleton.
///
/// Returns `Cow::Borrowed` when the input is already NFC and nothing folds (zero
/// allocation), `Cow::Owned` otherwise. Infallible: a [`TargetScript`] is always a
/// supported script.
#[must_use]
pub fn normalize_confusables(text: &str, target: TargetScript) -> Cow<'_, str> {
    normalize_confusables_with(text, target, DigitPolicy::Numeric)
}

/// How the fold treats non-Latin **digits** (#561).
///
/// disarm and upstream TR39 disagree on 45 rows, and both readings are defensible. The
/// divergence used to be fixed in the table with no way to select the other side, which
/// read as a defect to anyone scoring disarm against a TR39-derived benchmark.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Default)]
#[non_exhaustive]
pub enum DigitPolicy {
    /// A non-Latin digit folds to the ASCII **digit** — `०` → `0`. The default, and the
    /// right reading for prose: a Devanagari zero in running text is a zero, and turning
    /// it into a letter corrupts the number.
    #[default]
    Numeric,
    /// Upstream TR39's targets, which fold most of these digits to a Latin **letter** — `०` →
    /// `o`, `೦` → `O`, `١` → `l`. Correct for an identifier *skeleton*, whose only job is
    /// to make two confusable identifiers collide; it does not care whether the collision
    /// target reads sensibly. Select this when comparing against a TR39-derived benchmark.
    ///
    /// The override rows are generated from the Latin table and carry TR39's
    /// Latin-script targets, so this policy applies to [`TargetScript::Latin`] only;
    /// with any other target it is a no-op and the fold behaves exactly as
    /// [`DigitPolicy::Numeric`].
    Tr39,
    /// Leave the digit alone — `०` stays `०`, `٥` stays `٥` (#648).
    ///
    /// The other two policies both *rewrite* a non-Latin numeral, and neither leaves the
    /// script intact: `Numeric` produces `२०२४` → `२0२४` and `Tr39` produces `२०२४` →
    /// `२o२४`. Both are mixed-script numerals, which is neither the original nor a clean
    /// fold. This is the third answer — decline to map the digit rows and fold everything
    /// else as usual.
    ///
    /// "The digit rows" are the rows whose target is a single ASCII digit, read from the
    /// bundled table itself rather than from a separate list, so the set cannot drift
    /// from the map it describes. Unlike [`DigitPolicy::Tr39`] this applies under every
    /// target script, because declining to fold is not a Latin-specific act.
    Preserve,
}

impl DigitPolicy {
    /// The canonical token (`"numeric"` / `"tr39"`) the bindings pass across the boundary.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            DigitPolicy::Numeric => "numeric",
            DigitPolicy::Tr39 => "tr39",
            DigitPolicy::Preserve => "preserve",
        }
    }
}

impl std::str::FromStr for DigitPolicy {
    type Err = Error;

    /// Parse `"numeric"` / `"tr39"` / `"preserve"`.
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "numeric" => Ok(Self::Numeric),
            "tr39" => Ok(Self::Tr39),
            "preserve" => Ok(Self::Preserve),
            _ => Err(Error::from(crate::ErrorRepr::InvalidDigitPolicy {
                got: s.to_owned(),
            })),
        }
    }
}

impl std::fmt::Display for DigitPolicy {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

/// [`normalize_confusables`] with an explicit [`DigitPolicy`].
///
/// Kept as a separate entry point rather than a third parameter on
/// [`normalize_confusables`]: that function is the crate's most-used security primitive,
/// and the policy is a rarely-exercised option, so widening it would tax every call site
/// for something almost none of them set.
///
/// ```
/// use disarm::api::{normalize_confusables_with, DigitPolicy, TargetScript};
///
/// // Devanagari zeros. Numeric keeps the number; tr39 makes the skeleton collide.
/// let spoof = "g\u{0966}\u{0966}gle";
/// assert_eq!(
///     normalize_confusables_with(spoof, TargetScript::Latin, DigitPolicy::Numeric),
///     "g00gle"
/// );
/// assert_eq!(
///     normalize_confusables_with(spoof, TargetScript::Latin, DigitPolicy::Tr39),
///     "google"
/// );
/// ```
#[must_use]
pub fn normalize_confusables_with(
    text: &str,
    target: TargetScript,
    digit_policy: DigitPolicy,
) -> Cow<'_, str> {
    // The only error paths of the Layer-1 fn are unsupported target/policy *strings*;
    // neither enum can produce one, so this is unreachable.
    //
    // #586: the *fixed-point* form, not the single-pass `_cow`. Folding and canonical
    // composition expose work for each other, so one pass can return output that
    // `is_confusable` still flags — and every non-Python binding reaches the API through
    // here, so a single pass made the same call answer differently per language. Borrows
    // on a no-op exactly as `_cow` does, so the common case still never allocates.
    crate::confusables::normalize_confusables_fixed_cow(
        text,
        target.as_str(),
        digit_policy.as_str(),
    )
    .expect("TargetScript and DigitPolicy always map to supported tokens")
}

/// True if `text` contains any character confusable with a `target`-script
/// character (TR39).
///
/// Detection runs on the canonically recomposed (NFC) form (#475, in the Layer-1
/// core), so it cannot be evaded by decomposing the homoglyph (which would otherwise
/// flip a composed `ç` from detected to not-detected). Infallible: a [`TargetScript`]
/// is always a supported script.
#[must_use]
pub fn is_confusable(text: &str, target: TargetScript) -> bool {
    crate::confusables::is_confusable(text, target.as_str())
        .expect("TargetScript always maps to a supported target script")
}

// ── Coverage introspection (#563) ────────────────────────────────────────────

/// An upstream confusable source the bundled table does not fold, located in the
/// input — an element of [`find_unmapped_confusables`].
///
/// Mirrors [`Untranslatable`](crate::api::Untranslatable), the transliteration
/// analogue, field for field.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[non_exhaustive]
pub struct UnmappedConfusable {
    /// The unmapped character.
    pub ch: char,
    /// Its byte offset in the input string.
    pub offset: usize,
}

/// Every confusable source in the bundled upstream `confusables.txt` that disarm's
/// `target` table does **not** fold, sorted by codepoint.
///
/// Read this as *exposure*, not as a score. The set is where an adaptive attacker
/// goes once the mapped sources stop working, which is why the number matters more
/// than a per-source coverage percentage measured on a static corpus.
///
/// Most of the set is out of scope rather than missing: a source that folds to a
/// non-Latin target has no business in the to-Latin table. Cross-reference
/// [`CONFUSABLES_VERSION`](crate::api::CONFUSABLES_VERSION) and `docs/provenance.md`
/// before reading a given codepoint as a defect.
///
/// The result is derived from the same PHF the fold uses, so it cannot drift from
/// the table's actual behaviour. Allocates on every call — it is an introspection
/// entry point, not a hot path; hoist it if you need it per-request.
///
/// # The set includes five ASCII characters
/// For [`TargetScript::Latin`] the residue contains `%`, `0`, `1`, `I` and `m`. That
/// is not a bug and not an oversight. TR39 is a *skeleton* transform: it reduces `m`
/// to `rn`, `I` and `1` to `l`, and `0` to `O`, so those five are sources in the
/// upstream file. disarm does not apply those rows, because folding a legitimate ASCII
/// `m` to `rn` corrupts prose — see the digit-policy and contraction issues.
///
/// The consequence is that a per-input scan over ordinary English **will** report the
/// letter `m`. Nothing here filters it out: this API answers "what does the table not
/// fold", and a coverage report that quietly drops rows reads as coverage it does not
/// have. Filter on your own threat model at the call site.
#[must_use]
pub fn unmapped_confusables(target: TargetScript) -> Vec<char> {
    // A `TargetScript` value can never name an unsupported script.
    crate::confusables::unmapped_confusables(target.as_str())
        .expect("TargetScript always maps to a supported target script")
}

/// Scan `text` for characters upstream marks as confusable that disarm's `target`
/// table does not fold — the confusables analogue of
/// [`Transliterate::find_untranslatable`](crate::api::Transliterate::find_untranslatable).
///
/// Returns one [`UnmappedConfusable`] per occurrence, in order of appearance.
/// Composition runs exactly as it does in the fold (#475/#477/#483), so a
/// *decomposed* homoglyph whose precomposed form is mapped counts as covered rather
/// than as a gap — otherwise the report would disagree with what
/// [`normalize_confusables`] actually does. Offsets anchor to the caller's `text`,
/// never to the composed intermediate.
///
/// This is what turns the global exposure set above into something answerable against
/// your own traffic.
///
/// ```
/// use disarm::api::{find_unmapped_confusables, normalize_confusables, TargetScript};
///
/// // Cyrillic а IS folded, so it is not a gap.
/// assert!(find_unmapped_confusables("p\u{0430}ypal", TargetScript::Latin).is_empty());
/// assert_eq!(normalize_confusables("p\u{0430}ypal", TargetScript::Latin), "paypal");
/// ```
#[must_use]
pub fn find_unmapped_confusables(text: &str, target: TargetScript) -> Vec<UnmappedConfusable> {
    crate::confusables::find_unmapped_confusables(text, target.as_str())
        .expect("TargetScript always maps to a supported target script")
        .into_iter()
        .map(|(ch, offset)| UnmappedConfusable { ch, offset })
        .collect()
}

// ── Reverse transliteration (romanized Latin → native script) ────────────────

/// Language for [`reverse_transliterate`] — the scripts disarm ships reverse
/// tables for.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[non_exhaustive]
pub enum ReverseLang {
    /// Greek (`el`).
    Greek,
    /// Russian (`ru`).
    Russian,
    /// Ukrainian (`uk`).
    Ukrainian,
}

impl ReverseLang {
    /// The canonical language-code token (the inverse of its `FromStr`, and what
    /// `Display` prints): `"el"` / `"ru"` / `"uk"`.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            ReverseLang::Greek => "el",
            ReverseLang::Russian => "ru",
            ReverseLang::Ukrainian => "uk",
        }
    }
}

impl std::fmt::Display for ReverseLang {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

impl std::str::FromStr for ReverseLang {
    type Err = Error;

    /// Parse `"el"` / `"ru"` / `"uk"`.
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "el" => Ok(Self::Greek),
            "ru" => Ok(Self::Russian),
            "uk" => Ok(Self::Ukrainian),
            _ => Err(Error::from(crate::ErrorRepr::InvalidReverseLang {
                got: s.to_owned(),
            })),
        }
    }
}

/// Convert romanized Latin `text` back to its native script with greedy
/// longest-match scanning (digraphs/trigraphs like `shch` → щ); unmatched
/// characters pass through.
///
/// Infallible: a [`ReverseLang`] always has a reverse table.
#[must_use]
pub fn reverse_transliterate(text: &str, lang: ReverseLang) -> String {
    crate::reverse::reverse_transliterate_impl(text, lang.as_str())
}

/// The languages that support [`reverse_transliterate`], as lowercase codes.
#[must_use]
pub fn reverse_langs() -> Vec<String> {
    crate::reverse::reverse_langs()
}

// ── Script detection ─────────────────────────────────────────────────────────

/// Unicode scripts present in `text`, in order of first appearance (Common /
/// Inherited excluded). Names are stable UCD script identifiers (e.g. `"Latin"`).
#[must_use]
pub fn detect_scripts(text: &str) -> Vec<&'static str> {
    crate::scripts::detect_scripts(text)
}

/// True if `text` mixes characters from more than one script (excluding Common /
/// Inherited) — a homoglyph-spoofing signal.
#[must_use]
pub fn is_mixed_script(text: &str) -> bool {
    crate::scripts::is_mixed_script(text)
}

/// True if `text` contains both strong left-to-right and strong right-to-left
/// characters — the precondition for Unicode Bidi display-reordering (UAX #9),
/// and the structural signal behind "BiDi Swap"-style spoofs.
///
/// Unlike a bidi-override (`U+202x`) check, this fires on the *real letters*
/// (e.g. an LTR brand label beside an RTL domain, `varonis.com.ו.קום`), where no
/// override is present and override-stripping is a no-op. Latin/Cyrillic/Greek/
/// CJK/… are left-to-right; Hebrew/Arabic/Syriac/Thaana/N'Ko are right-to-left;
/// digits, punctuation and combining marks are neutral and never create a
/// conflict on their own. A `false` result is **not** a safety guarantee.
///
/// # This is not the RLO check (#599)
///
/// Because it reads letters, it is structurally blind to the `U+202x` overrides.
/// `"invoice\u{202E}gpj.exe"` — the classic extension spoof — returns `false`
/// here. The two conditions are **disjoint**: a string can satisfy either, both,
/// or neither.
///
/// | input | `has_bidi_conflict` | [`inspect_anomalies`] kind |
/// |---|---|---|
/// | `"invoice\u{202E}gpj.exe"` | `false` | `bidi` |
/// | `"varonis.com.\u{05D5}"` | `true` | `bidi_mixed` |
///
/// To cover an override instead: detect it with [`inspect_anomalies`] (kind
/// `bidi`), and remove it with [`strip_bidi`]. Note [`strip_bidi`] does **not**
/// close this function's case — on a real-letter conflict it returns the input
/// unchanged, because there is no format character to remove.
///
/// [`inspect_anomalies`]: crate::api::inspect_anomalies
/// [`strip_bidi`]: crate::api::strip_bidi
#[must_use]
pub fn has_bidi_conflict(text: &str) -> bool {
    crate::scripts::has_bidi_conflict(text)
}

/// How disarm's auto-language detection resolved a string — returned by
/// [`inspect_auto_lang`] for diagnostics / explainability.
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub struct AutoLangInspection {
    /// The primary non-Latin script detected, if any (e.g. `"Cyrillic"`).
    pub script: Option<String>,
    /// The language auto-detection chose, if any (e.g. `"ru"`).
    pub chosen_lang: Option<String>,
    /// Why that choice was made (`"discriminator"`, `"script_default"`,
    /// `"unambiguous_script"`, `"latin_discriminator"`, `"no_detection"`).
    pub reason: String,
    /// The discriminator characters that drove the choice, if any.
    pub discriminators_hit: Vec<String>,
}

/// Explain how auto-language detection resolves `text` (which script, which
/// language, and why) — for diagnostics, not the hot path.
#[must_use]
pub fn inspect_auto_lang(text: &str) -> AutoLangInspection {
    let (script, chosen_lang, reason, discriminators_hit) = crate::scripts::inspect_auto_lang(text);
    AutoLangInspection {
        script: script.map(str::to_owned),
        chosen_lang,
        reason: reason.to_owned(),
        discriminators_hit,
    }
}

// ── Hostname homoglyph safety ────────────────────────────────────────────────

/// Findings from a hostname homoglyph analysis — returned by
/// [`is_suspicious_hostname`].
///
/// Reports factual findings; it claims nothing about absolute safety. A
/// `suspicious == false` result is **not** a safety certificate (see
/// [`is_suspicious_hostname`]).
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub struct HostnameAnalysis {
    /// The overall verdict — this is what [`is_suspicious_hostname`] keys on.
    /// **`false` is not a safety guarantee** (see the function docs); weigh the
    /// granular fields below against your own policy.
    pub suspicious: bool,
    /// Scripts detected across all labels, in order of first appearance
    /// (Common / Inherited excluded), as stable UCD script identifiers.
    pub scripts: Vec<String>,
    /// Whether any single label mixes characters from more than one script.
    pub mixed_script: bool,
    /// Whether any label contains a character confusable with a Latin one.
    ///
    /// Read **after** the UTS #46 mapping and the NFKC that open this analysis, so it
    /// cannot see a compatibility form by construction: `ｇoogle.com` is already
    /// `google.com` by the time this field is computed, and `false` here is the correct
    /// answer — after mapping there is no confusable left. A caller who sees
    /// [`canonical`](Self::canonical) differ from the input while this stays `false` is
    /// looking at [`compat_fold`](Self::compat_fold), not at a defect (#709).
    pub has_confusables: bool,
    /// Whether the decoded hostname mixes strong left-to-right and strong
    /// right-to-left characters — the precondition for Bidi display-reordering
    /// ("BiDi Swap"). This is folded into [`suspicious`](Self::suspicious).
    pub bidi_conflict: bool,
    /// Whether the decoded hostname contains a UAX #9 bidi control character —
    /// an override (`U+202D`/`U+202E`), embedding (`U+202A`–`U+202C`), isolate
    /// (`U+2066`–`U+2069`) or directional mark (`U+200E`/`U+200F`/`U+061C`) (#603).
    ///
    /// Disjoint from [`bidi_conflict`](Self::bidi_conflict), which reads strong-direction
    /// *letters* only and is therefore blind to `paypal\u{202E}moc.evil.com`. IDNA2008
    /// (RFC 5892) disallows every character in the set, so this is folded into
    /// [`suspicious`](Self::suspicious) and the characters are stripped from
    /// [`canonical`](Self::canonical).
    pub bidi_control: bool,
    /// Whether the decoded hostname contains an invisible character of any class
    /// (#605, widened by #610):
    ///
    /// - **zero-width** — `U+200B`–`U+200D`, `U+2060`–`U+2064`, `U+FEFF`, `U+180E`
    /// - **tag** — `U+E0000`–`U+E007F`, the ASCII-smuggling channel
    /// - **variation selector** — `U+FE00`–`U+FE0F`, `U+E0100`–`U+E01EF`
    /// - **noncharacter** — `U+FDD0`–`U+FDEF` and the last two of every plane
    /// - **private use** — `U+E000`–`U+F8FF`, plane 15 and plane 16
    ///
    /// Disjoint from [`bidi_control`](Self::bidi_control): these carry no direction at
    /// all, so neither that field nor [`bidi_conflict`](Self::bidi_conflict) can see
    /// them. RFC 5892 puts the tag, variation-selector, noncharacter and private-use
    /// classes in DISALLOWED outright, which is what justifies including private use
    /// and the variation selectors here — both have legitimate uses in ordinary text,
    /// so a general-text detector would need its own argument for them. `U+200C` and
    /// `U+200D` are the exception: CONTEXTJ, so conditionally permitted. This screen
    /// flags them anyway, which is a deliberate fail-closed policy (#605) rather than
    /// something the RFC settles. Folded into [`suspicious`](Self::suspicious); the characters are
    /// removed per label *before* any other field is computed, so they never reach
    /// [`scripts`](Self::scripts), [`mixed_script`](Self::mixed_script) or
    /// [`canonical`](Self::canonical).
    pub has_invisible: bool,
    /// Whether any label carried a Unicode **compatibility form** before normalization
    /// (#709) — fullwidth (`ｇoogle`), ligature (`ﬁle`), Roman-numeral (`Ⅰ`BM),
    /// mathematical-alphanumeric (`𝗀𝗈𝗈𝗀𝗅𝖾`), circled, superscript, and the rest of the
    /// compatibility repertoire.
    ///
    /// The predicate is RFC 5892 §2.1's, applied **per code point**: a character `c`
    /// where `toNFKC(c) != c` is DISALLOWED in an IDN label. IDNA2008 therefore
    /// disallows the whole set, exactly as it does the
    /// [`bidi_control`](Self::bidi_control) and [`has_invisible`](Self::has_invisible)
    /// classes, so this is folded into [`suspicious`](Self::suspicious) on the same
    /// footing. The threat is a blocklist bypass rather than a lookalike: `ｅvil.com` is
    /// absent from a blocked set, screens clean, and resolves to `evil.com`.
    ///
    /// Per character, not "NFKC changed the label" — the label-level form fires on
    /// decomposed input that is entirely legitimate, such as `한국.kr` written with
    /// conjoining jamo, where every individual code point is NFKC-stable.
    ///
    /// This is the one field read from the **raw** input. Every other field is computed
    /// after normalization, which is what makes them work and also what erases this
    /// evidence: before #709 `ｇoogle.com` reached the per-label checks already spelled
    /// `google.com`, so [`has_confusables`](Self::has_confusables) was correctly `false`
    /// and nothing reported what the mapping had eaten.
    ///
    /// Read per **label**, not over the whole hostname: three of the four UTS #46 label
    /// separators carry a compatibility decomposition (`U+FF0E` and `U+FF61` do, `U+3002`
    /// does not), and a separator is structure rather than label content.
    pub compat_fold: bool,
    /// Whether the labels resolve to more than one distinct script (Common /
    /// Inherited excluded). Broader and noisier than [`bidi_conflict`](Self::bidi_conflict)
    /// — it fires on benign IDN-ccTLD patterns like `google.рф` — so it is
    /// **not** folded into [`suspicious`](Self::suspicious); exposed for policy.
    pub cross_label_script: bool,
    /// Per-label resolved scripts, left to right (Common / Inherited excluded),
    /// so a caller can apply position-aware policy without re-parsing.
    pub label_scripts: Vec<Vec<String>>,
    /// Whether any label is a *whole-script confusable* (#545): single-script,
    /// non-Latin, with a confusable skeleton that is entirely Latin (e.g. Cyrillic
    /// `аррӏе` → `apple`). A graded **signal, not a verdict** — on its own it fires
    /// on short non-Latin ccTLDs (`ру`→`py`) and on real words (`оса`→`oca`), so it
    /// is **not** folded into [`suspicious`](Self::suspicious). Combine
    /// [`label_whole_script_confusable`](Self::label_whole_script_confusable) for
    /// non-TLD labels with a Latin-TLD check for the precise policy.
    pub whole_script_confusable: bool,
    /// Per-label whole-script-confusable flags, parallel to
    /// [`label_scripts`](Self::label_scripts) — lets a caller exclude the TLD label
    /// when applying the `wsc(non-TLD) ∧ Latin-TLD` policy.
    pub label_whole_script_confusable: Vec<bool>,
    /// The Latin-normalized (canonical) form of the hostname.
    pub canonical: String,
}

/// Analyze a hostname for Unicode homoglyph spoofing, returning a
/// [`HostnameAnalysis`] whose [`suspicious`](HostnameAnalysis::suspicious) field
/// is the overall verdict (alongside the granular `scripts` / `mixed_script` /
/// `has_confusables` / `canonical` findings).
///
/// **Every** label is mapped through UTS #46 before analysis, whichever spelling it
/// arrived in (#63, widened by #714): `xn--` labels are decoded from ACE, and literal
/// Unicode labels go through the same mapping table. A label that fails to map cannot be
/// verified and fails closed (suspicious). Until #714 the mapping ran on the ACE branch
/// only, so `ꭰꭰ.com` and `xn--58da.com` — the same registered domain — got different
/// verdicts, across 561 code points.
///
/// A hostname is flagged when any single label is mixed-script (conservative, #254), when
/// any label contains a Latin-confusable character, when the decoded hostname mixes
/// strong LTR and strong RTL characters (`bidi_conflict`, the "BiDi Swap" precondition,
/// #412), when a label carries a compatibility form (`compat_fold`, #709), or when a
/// label fails to map.
///
/// Infallible: the analysis runs against the fixed `"latin"` target script,
/// which is always supported.
///
/// **A `false` (not-suspicious) result is NOT a safety guarantee.** It means
/// only that no mixed-script label and no confusable *from the bundled TR39
/// table* was found. Base allow/deny decisions on the granular `scripts` /
/// `mixed_script` / `has_confusables` fields plus your own policy — a detector
/// can attest the *presence* of a problem, never the *absence* of all problems.
#[must_use]
pub fn is_suspicious_hostname(hostname: &str) -> HostnameAnalysis {
    analyze_hostname_with(hostname, false)
}

/// [`is_suspicious_hostname`] with the #562 contraction rules selectable.
///
/// `contractions = true` additionally folds ASCII digraphs that can impersonate a single
/// letter — `rn`→`m`, `vv`→`w`, `cl`→`d` — into
/// [`canonical`](HostnameAnalysis::canonical), so `arnazon.com` canonicalizes to
/// `amazon.com`.
///
/// **Off by default, and deliberately confined to hostnames.** Unconditional contraction
/// is worse than none: `rn`→`m` is right for `arnazon` and wrong for `earnings`,
/// `turnip`, `born`. A hostname is the one place where the threat model justifies those
/// false positives and where there is no running prose to corrupt. It is not reachable
/// from [`normalize_confusables`] at all.
///
/// Matching is leftmost-longest over an Aho-Corasick automaton, and applied per label so
/// a digraph can never form across a dot. The rule set is validated at build time to
/// contain no chains, which is what makes one pass a fixed point.
///
/// ```
/// use disarm::api::analyze_hostname_with;
///
/// assert_eq!(analyze_hostname_with("arnazon.com", true).canonical, "amazon.com");
/// assert_eq!(analyze_hostname_with("arnazon.com", false).canonical, "arnazon.com");
/// ```
#[must_use]
pub fn analyze_hostname_with(hostname: &str, contractions: bool) -> HostnameAnalysis {
    let (_, core) = crate::hostname::is_suspicious_hostname_opts(hostname, contractions);
    HostnameAnalysis {
        suspicious: core.suspicious,
        scripts: core.scripts,
        mixed_script: core.mixed_script,
        has_confusables: core.has_confusables,
        bidi_conflict: core.bidi_conflict,
        bidi_control: core.bidi_control,
        has_invisible: core.has_invisible,
        compat_fold: core.compat_fold,
        cross_label_script: core.cross_label_script,
        label_scripts: core.label_scripts,
        whole_script_confusable: core.whole_script_confusable,
        label_whole_script_confusable: core.label_whole_script_confusable,
        canonical: core.canonical,
    }
}

// ── Filename sanitization ────────────────────────────────────────────────────

/// Target platform whose illegal-character set and reserved-name rules drive
/// [`sanitize_filename`].
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[non_exhaustive]
pub enum Platform {
    /// The intersection of all platforms' rules (the safe default).
    Universal,
    /// Windows: the universal illegal set plus reserved device names (CON, …).
    Windows,
    /// POSIX (Linux/macOS): only `/` and NUL are illegal.
    Posix,
}

impl Platform {
    /// The canonical token (the inverse of its `FromStr`, and what `Display`
    /// prints): `"universal"` / `"windows"` / `"posix"`.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            Platform::Universal => "universal",
            Platform::Windows => "windows",
            Platform::Posix => "posix",
        }
    }
}

impl std::fmt::Display for Platform {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

impl std::str::FromStr for Platform {
    type Err = Error;

    /// Parse `"universal"` / `"windows"` / `"posix"`.
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "universal" => Ok(Self::Universal),
            "windows" => Ok(Self::Windows),
            "posix" => Ok(Self::Posix),
            _ => Err(Error::from(crate::ErrorRepr::InvalidPlatform {
                got: s.to_owned(),
            })),
        }
    }
}

/// Sanitize `text` into a filename safe for `platform`: transliterate to ASCII,
/// strip illegal characters (replacing runs with `separator`), neutralize `..`
/// traversal and reserved names, and truncate to `max_length` **bytes**
/// (extension-aware when `preserve_extension`).
///
/// `lang` selects the transliteration language (`None` = auto-detect). This is
/// the one fallible argument: an unknown language code is a runtime error
/// ([`ErrorKind::InvalidArgument`](crate::ErrorKind)); `Platform` and the
/// `usize` length make every other input infallible by construction.
///
///
/// # A safe filename is not a safe URL path segment
///
/// `%` is legal in a filename on every supported platform, so a `%` the caller typed is
/// kept: `sanitize_filename("..%2Fetc")` returns `"%2Fetc"` — the literal `..` collapsed,
/// the percent-encoded spelling of the same traversal left alone. A consumer that
/// percent-decodes the result (`Content-Disposition`, an object-storage key, a
/// static-file route) must validate *after* decoding.
///
/// What this will not do is *manufacture* one. Compatibility folding maps five code
/// points to `%` — `\u{609}`, `\u{60A}`, `\u{66A}`, `\u{FE6A}`, `\u{FF05}` — which used to
/// assemble `%2E%2E%2F` out of input containing no `%` at all (#721). The rule is now
/// exact: **`%` never appears in the output unless it appeared in the input.**
///
/// [`ErrorKind::InvalidArgument`]: crate::ErrorKind::InvalidArgument
pub fn sanitize_filename(
    text: &str,
    separator: &str,
    max_length: usize,
    platform: Platform,
    lang: Option<&str>,
    preserve_extension: bool,
) -> Result<String, Error> {
    crate::filename::sanitize_filename(
        text,
        separator,
        max_length,
        platform.as_str(),
        lang,
        preserve_extension,
    )
    .map_err(Error::from)
}

// ── Encoding detection & decoding ────────────────────────────────────────────

/// The result of [`detect_encoding`]: a detected encoding label and the
/// detector's confidence.
#[derive(Debug, Clone, PartialEq)]
#[non_exhaustive]
pub struct EncodingDetection {
    /// The detected encoding's WHATWG label (e.g. `"UTF-8"`, `"windows-1251"`).
    pub label: String,
    /// Detector confidence in `0.0..=1.0` (probabilistic — prefer explicit
    /// metadata for critical pipelines).
    pub confidence: f64,
}

/// Detect the probable character encoding of `bytes` (chardetng, Firefox's
/// detector). Detection is probabilistic — prefer explicit encoding metadata for
/// critical pipelines.
///
/// # UTF-16 (#710)
///
/// Two cases are decided *before* chardetng runs, because chardetng never produces a
/// UTF-16 label at all:
///
/// - **A BOM.** `FF FE`, `FE FF` and `EF BB BF` yield `UTF-16LE`, `UTF-16BE` and `UTF-8`
///   directly. A BOM is not a probabilistic signal. This is the same WHATWG sniff
///   [`decode_to_utf8`] performs internally, so the two agree by construction — before
///   #710 they disagreed silently, with `detect_encoding` reporting `KOI8-U` at
///   confidence 0.95 for the bytes `decode_to_utf8` read correctly as UTF-16LE.
/// - **BOM-less UTF-16 over ASCII-range text**, where every second byte is `00` and the
///   position of the NUL is the endianness. Deterministic, not a frequency guess.
///
/// **BOM-less UTF-16 outside the ASCII range is not detected.** In UTF-16LE Cyrillic the
/// high byte is `04`, not `00`, so `"Привет"` without a BOM carries no NUL and there is
/// no deterministic signal to read; guessing from script frequency would be exactly the
/// ambiguous-bytes case `THREAT_MODEL.md` scopes out. Such input decodes as a single-byte
/// encoding and yields mojibake, with no flag — supply the encoding explicitly when you
/// know the source emits BOM-less UTF-16.
#[must_use]
pub fn detect_encoding(bytes: &[u8]) -> EncodingDetection {
    let (label, confidence) = crate::encoding::detect_encoding_impl(bytes);
    EncodingDetection { label, confidence }
}

/// The result of [`decode_to_utf8`]: the decoded text and whether the decode was
/// lossy.
#[derive(Debug, Clone, PartialEq, Eq)]
#[non_exhaustive]
pub struct DecodedText {
    /// The decoded UTF-8 text.
    pub text: String,
    /// Whether U+FFFD replacement characters were inserted for undecodable bytes
    /// (always `false` after a successful `strict` decode).
    pub had_errors: bool,
}

/// Decode `bytes` to UTF-8. `encoding = None` auto-detects (rejecting a guess
/// below `min_confidence`, in `0.0..=1.0`). In `strict` mode a lossy decode is an
/// error instead of setting [`DecodedText::had_errors`].
///
/// Fails ([`ErrorKind`](crate::ErrorKind)) on an unknown, unsupported, or
/// low-confidence encoding, an out-of-range `min_confidence`, or (strict) a
/// lossy decode.
pub fn decode_to_utf8(
    bytes: &[u8],
    encoding: Option<&str>,
    min_confidence: f64,
    strict: bool,
) -> Result<DecodedText, Error> {
    crate::encoding::decode_to_utf8_impl(bytes, encoding, min_confidence, strict)
        .map(|(text, had_errors)| DecodedText { text, had_errors })
        .map_err(Error::from)
}

// ── Log-injection neutralization ─────────────────────────────────────────────

/// Neutralize log-injection / terminal-control characters in `text` so it is
/// safe to *write* as a log line: each CR, LF, NEL, LS, PS, NUL, C0/C1 control,
/// ESC, and DEL (and tab, unless `keep_tab`) is replaced with `replacement`
/// (use `""` to drop them). Returns `Cow::Borrowed` for an already-clean line.
///
/// Not an HTML/SQL sanitizer and not a defense against logging-framework
/// interpolation — encode at the *viewer's* sink for those. Fails
/// ([`ErrorKind::InvalidArgument`](crate::ErrorKind)) if `replacement` itself
/// contains a character this call neutralizes (which would break the
/// no-raw-CR/LF and idempotency guarantees).
pub fn strip_log_injection<'a>(
    text: &'a str,
    replacement: &str,
    keep_tab: bool,
) -> Result<Cow<'a, str>, Error> {
    crate::log_injection::validate_log_replacement(replacement, keep_tab).map_err(Error::from)?;
    Ok(crate::log_injection::strip_log_injection_str(
        text,
        replacement,
        keep_tab,
    ))
}

// ── Key collisions across a set (#620) ──────────────────────────────────────

/// Which reducer [`find_key_collisions`] builds its keys with.
///
/// **The choice is the policy**, and there is deliberately no default. Each
/// reducer draws a different line, and picking one for the caller would mean
/// picking their threat model for them — measured against the four collision
/// CVEs in `docs/security/cve-validation.md`:
///
/// | key | 2026-23950 | 2019-19844 | 2013-7236 | 2020-12063 |
/// |---|---|---|---|---|
/// | [`FoldCase`](Self::FoldCase) | ✓ | | | |
/// | [`SearchKey`](Self::SearchKey) | ✓ | ✓ | ✓ | ✓ |
/// | [`CatalogKey`](Self::CatalogKey) | ✓ | ✓ | ✓ | ✓ |
/// | [`Canonicalize`](Self::Canonicalize) | | ✓ | ✓ | ✓ |
/// | [`CanonicalizeStrict`](Self::CanonicalizeStrict) | | ✓ | ✓ | ✓ |
/// | [`NormalizeConfusables`](Self::NormalizeConfusables) | | ✓ | ✓ | ✓ |
///
/// A stronger reducer finds more collisions, including ones nobody attacked:
/// `search_key` collides `Muller` with `Müller` and `Ivan` with `Иван`. That is
/// not a false positive — they really are one key — it is the cost of the key you
/// chose. Pinned by `test_the_reducer_is_the_policy`.
///
/// `sort_key` is absent on purpose: a sort key exists *to* collide, since that is
/// how equal-sorting items group, so reporting its collisions would be noise
/// rather than signal.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[non_exhaustive]
pub enum KeyForm {
    /// [`crate::api::fold_case`] — full Unicode case folding. The narrowest of
    /// the six and the one CVE-2026-23950 needs: it collides `groß.txt` with
    /// `gross.txt` for a case-insensitive filesystem, and folds no homoglyphs, so
    /// a Cyrillic `а` stays Cyrillic.
    FoldCase,
    /// [`crate::api::search_key`] — the identity key. Transliterates, folds
    /// confusables, strips accents and folds case, so it collides every published
    /// pair in the table above. Reach for it when the question is "is this the
    /// same person / account / sender?".
    SearchKey,
    /// [`crate::api::catalog_key`] — the bibliographic key, at its default
    /// `strict_iso9 = false`. Same coverage as [`SearchKey`](Self::SearchKey) on
    /// the CVE rows, different romanization choices.
    CatalogKey,
    /// [`crate::api::canonicalize`] — folds homoglyphs and strips the invisible
    /// classes, and leaves `ß` alone because it is a real German letter. The
    /// complement of [`FoldCase`](Self::FoldCase) rather than a superset of it.
    Canonicalize,
    /// [`crate::api::canonicalize_strict`] — as above plus the eclipsing-mark
    /// rule (#615). Destructive for scholarly transliteration and IPA; see that
    /// function's caveat before using it as a registry key.
    CanonicalizeStrict,
    /// [`crate::api::normalize_confusables`] against
    /// [`TargetScript::Latin`](TargetScript::Latin) — the TR39 skeleton alone, no
    /// case fold and no accent strip. The narrowest homoglyph reducer.
    NormalizeConfusables,
}

impl KeyForm {
    /// The canonical token the bindings pass across the boundary.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            KeyForm::FoldCase => "fold_case",
            KeyForm::SearchKey => "search_key",
            KeyForm::CatalogKey => "catalog_key",
            KeyForm::Canonicalize => "canonicalize",
            KeyForm::CanonicalizeStrict => "canonicalize_strict",
            KeyForm::NormalizeConfusables => "normalize_confusables",
        }
    }
}

impl std::str::FromStr for KeyForm {
    type Err = Error;

    /// Parse a [`KeyForm`] token — the reducer's own function name.
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "fold_case" => Ok(Self::FoldCase),
            "search_key" => Ok(Self::SearchKey),
            "catalog_key" => Ok(Self::CatalogKey),
            "canonicalize" => Ok(Self::Canonicalize),
            "canonicalize_strict" => Ok(Self::CanonicalizeStrict),
            "normalize_confusables" => Ok(Self::NormalizeConfusables),
            _ => Err(Error::from(crate::ErrorRepr::InvalidKeyForm {
                got: s.to_owned(),
            })),
        }
    }
}

impl std::fmt::Display for KeyForm {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

pub use crate::collisions::KeyCollision;

/// Which of `values` reduce to the same identity key under `key` (#620).
///
/// Every other disarm detector is a single-string predicate, and a collision is
/// not a property of a single string — `groß.txt` is an ordinary German filename,
/// and `аdmin` is only a problem next to `admin`. This is the set-shaped
/// question: **given these names, which of them are the same name?**
///
/// That is what node-tar's `PathReservations` guard failed to ask before
/// extracting two paths in parallel (CVE-2026-23950), and what a registry has to
/// ask before accepting a second `admin` (CVE-2013-7236). Note the two want
/// opposite policies from the same answer — one refuses the batch, the other
/// refuses the registration — so this reports and decides nothing.
///
/// Reducing and grouping happen in one pass over one reducer, so the report
/// cannot disagree with the collapse it describes. A group is returned only when
/// it holds **two or more distinct inputs**; the same string twice is the same
/// name twice. Groups come back in order of the first index that participates.
///
/// `lang` reaches [`SearchKey`](KeyForm::SearchKey) and
/// [`CatalogKey`](KeyForm::CatalogKey), whose romanization is language-dependent,
/// and is ignored by the rest. Under `lang = Some("de")`, `Müller` and `Mueller`
/// are one key; under the default they are two.
///
/// # Errors
///
/// [`crate::ErrorKind::ResourceLimit`] if `values` exceeds the batch cap — the same
/// one every other batch entry point enforces, so the figure lives in one place and
/// is deliberately not repeated here — and [`crate::ErrorKind::InvalidArgument`] if a
/// reducer rejects an input.
///
/// ```
/// use disarm::api::{self, KeyForm};
/// let found = api::find_key_collisions(
///     &["groß.txt", "gross.txt", "other.txt"],
///     KeyForm::FoldCase,
///     None,
/// ).unwrap();
/// assert_eq!(found.len(), 1);
/// assert_eq!(found[0].key, "gross.txt");
/// assert_eq!(found[0].values, ["groß.txt", "gross.txt"]);
/// assert_eq!(found[0].indices, [0, 1]);
/// ```
pub fn find_key_collisions<S: AsRef<str>>(
    values: &[S],
    key: KeyForm,
    lang: Option<&str>,
) -> Result<Vec<KeyCollision>, Error> {
    let borrowed: Vec<&str> = values.iter().map(AsRef::as_ref).collect();
    crate::collisions::find_key_collisions(&borrowed, key.as_str(), lang).map_err(Error::from)
}

// ── Anomaly detection ───────────────────────────────────────────────────────

pub use crate::anomalies::{
    has_anomalies, inspect_anomalies, lexicon, AnomalyKind, AnomalyReport, Finding,
};
