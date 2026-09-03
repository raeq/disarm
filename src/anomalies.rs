//! Out-of-place-character anomaly detection.
//!
//! [`has_anomalies`] reports a *technical fact*: that text carries out-of-place
//! characters that disguise a real word (a cross-script homoglyph, leet, segmentation,
//! a zero-width / bidi control, or zalgo). It claims nothing about intent — whether the
//! anomaly is malicious is the caller's judgement, exactly as [`crate::hostname`] does for
//! hostnames. [`inspect_anomalies`] returns the per-token detail.
//!
//! Built on the crate's own primitives ([`crate::scripts::detect_scripts`],
//! [`crate::zalgo::is_zalgo`]) plus a caller-supplied common-word lexicon for the leet and
//! segmentation branches; the invisible / bidi / zalgo / mixed-script branches need no
//! lexicon and are script-agnostic.

use std::collections::HashSet;

use unicode_normalization::UnicodeNormalization;

use crate::scripts::detect_scripts;
use crate::zalgo::is_zalgo;

/// Combining-mark stacking depth at which a token is treated as zalgo (matches the
/// `is_zalgo` default).
const ZALGO_THRESHOLD: usize = 3;

/// Maximum demangled length for the leet path. `nearest()` is O(n²) in allocation over the
/// demangled token, so an unbounded attacker-supplied token would be a DoS vector. Real
/// words are short; capping the leet decode at a sane bound caps the worst case without
/// affecting normal input.
const MAX_LEET_LEN: usize = 64;

/// Whether `c` is invisible *inside a word* — the set the neighbour rule below reads.
///
/// Reuses `crate::invisibles` rather than restating the ranges (#700 §1). The detector
/// having its own eight-character list is exactly how it drifted from the strip functions:
/// `strip_zero_width_chars` removed `U+2064` and `U+180E` and the detector reported the
/// same input clean, and `U+180E` sits in the Mongolian block so the token was reported as
/// `mixed_script` instead — a script the reader cannot see.
///
/// The **fillers** (#643) join it here rather than in the run rule: `ad\u{3164}min` renders
/// as `admin`, which is the single-character-inside-a-word shape the neighbour rule exists
/// for, and `U+200B` is already reported for identical attacks.
///
/// Soft hyphen and CGJ are deliberately **not** here — both have a legitimate use between
/// letters, which is precisely where the neighbour rule fires. They are carriers for the
/// run rule only, where a *sequence* of them is not legitimate under any reading.
#[inline]
fn is_invisible_in_word(c: char) -> bool {
    crate::invisibles::is_zero_width(c)
        || crate::invisibles::is_invisible_filler(c)
        // #813: invisible by Unicode property rather than by name. `pay` + `U+1D173` +
        // `pal` is the same attack as `pay` + `U+200B` + `pal` and was reported clean,
        // which is the inconsistency that makes it a defect rather than a coverage gap —
        // the argument #643 made for the fillers on the line above.
        || crate::invisibles::is_default_ignorable_format(c)
}

/// Soft hyphen — legitimate hyphenation between letters, so it is a run-rule carrier only.
const SOFT_HYPHEN: char = '\u{00AD}';
/// Combining Grapheme Joiner — legitimate between letters (it blocks normalization), so
/// likewise run-rule only.
const CGJ: char = '\u{034F}';

/// How many consecutive carriers of each class it takes to fire on their own, with no
/// letter beside them (#700 §2).
///
/// The neighbour rule is right for one zero-width space hiding inside a word: the letter
/// next to it is what makes it suspicious. It is wrong for a *run*, which is the shape a
/// pasted payload has — a run standing between two spaces has no letter in its token, so
/// it could not fire even for a character that was in the table. `"Hello "` plus 21 tag
/// characters spelling `tracked-by:acct-99213` plus `" world"` reported clean while
/// `strip_tags` removed the whole thing.
///
/// The thresholds differ because the classes do. A single tag character is not ordinary
/// anything — nothing legitimate emits one outside a subdivision flag, which is allowed
/// for separately. A single variation selector after a base is ordinary emoji
/// presentation, so two is the floor. Zero-width runs need the loosest floor: eight, well
/// above any orthography and well below the sixteen it takes to smuggle two ASCII letters.
///
/// The Private Use Area (#812) takes four. It is a run rule and not a neighbour rule for
/// the reason `strip_format` keeps the block at all: a single PUA code point beside a
/// letter is an icon-font glyph, which is ordinary in UI strings — so the floor has to sit
/// above one, unlike the tag block where nothing legitimate emits even one. Four is the
/// shortest run that no icon font produces and that still catches the shape
/// `canonicalize` was already deleting silently.
const RUN_THRESHOLD_TAG: usize = 1;
const RUN_THRESHOLD_VARIATION_SELECTOR: usize = 2;
const RUN_THRESHOLD_ZERO_WIDTH: usize = 8;
const RUN_THRESHOLD_PRIVATE_USE: usize = 4;

/// The carrier classes the run rule counts, each with its own floor.
#[derive(Clone, Copy, PartialEq, Eq)]
enum Carrier {
    Tag,
    VariationSelector,
    ZeroWidth,
    /// #812: `canonicalize` strips the Private Use Area and the detector said nothing, so
    /// a guardrail screening with `has_anomalies` passed exactly what the comparison
    /// presets had decided was not text.
    PrivateUse,
}

impl Carrier {
    fn of(c: char) -> Option<Self> {
        if crate::invisibles::is_tag(c) {
            Some(Self::Tag)
        } else if crate::invisibles::is_variation_selector(c) {
            Some(Self::VariationSelector)
        } else if is_invisible_in_word(c) || c == SOFT_HYPHEN || c == CGJ {
            Some(Self::ZeroWidth)
        } else if crate::invisibles::is_pua(c) {
            Some(Self::PrivateUse)
        } else {
            None
        }
    }

    fn threshold(self) -> usize {
        match self {
            Self::Tag => RUN_THRESHOLD_TAG,
            Self::VariationSelector => RUN_THRESHOLD_VARIATION_SELECTOR,
            Self::ZeroWidth => RUN_THRESHOLD_ZERO_WIDTH,
            Self::PrivateUse => RUN_THRESHOLD_PRIVATE_USE,
        }
    }
}
/// Bidi overrides (LRO/RLO): never legitimate in normal text.
const BIDI_OVERRIDE: &[char] = &['\u{202D}', '\u{202E}'];
/// Bidi isolates (LRI/RLI/FSI/PDI). Plain embeddings (LRE/RLE/PDF) and bare directional
/// marks are common in benign RTL and social text, so they are not flagged. The overrides
/// (U+202D/U+202E) are handled first by [`BIDI_OVERRIDE`], so they are not re-listed here.
const BIDI_ISOLATES: &[char] = &['\u{2066}', '\u{2067}', '\u{2068}', '\u{2069}'];
/// Bidi *embeddings*: LRE/RLE and their terminator PDF. Held to the same
/// majority-Latin condition as the isolates above (#643).
///
/// `bidi_spares_marks_and_embeddings` documented that condition — "an LRE..PDF embedding
/// around RTL text (no Latin majority) is benign" — and did not implement it: an
/// embedding was spared unconditionally, so `\u{202B}if (isAdmin) { grant(); }\u{202C}`
/// reported clean. That is the Trojan Source construction with the older embedding
/// operators in place of the isolates, and the comment already said it was not meant to
/// be spared. Bare `LRM`/`RLM` stay spared, which is the part that is clearly right —
/// they carry no scope and are common in benign social text.
const BIDI_EMBEDDINGS: &[char] = &['\u{202A}', '\u{202B}', '\u{202C}'];
/// Bare right-to-left directional marks: `RLM` and `ALM` (#741).
///
/// Spared outright until now, on the false-positive grounds `docs/user-guide/
/// anomaly-detection.md` states — "bare directional marks; LRE..PDF embeddings (RTL text,
/// hashtags)". Measured against UAX #9 with `unicode-bidi`, two of them still reorder
/// rendered text inside otherwise pure-Latin prose:
///
/// ```text
/// Transfer <RLM>100 200 300 to Bob   renders   Transfer 300 200 100 to Bob
/// acct <ALM>4321-9876                renders   acct 9876-4321
/// ```
///
/// That is Boucher et al., *Bad Characters* (arXiv:2106.09898v2) Table I, reached with a
/// control the detector did not report. `LRM` is **not** here: the same measurement found
/// it produced no reordering over any carrier tried, so the finding is `RLM` and `ALM`,
/// not "the spared set is wrong".
const BIDI_RTL_MARKS: &[char] = &['\u{200F}', '\u{061C}'];

/// Enclosing marks (`Me`) — the complete category, 13 code points (#724).
///
/// One mark per base is below every threshold disarm has: `is_zalgo` fires above three,
/// `strip_zalgo` keeps two (#429's decision, and the right one — Vietnamese `ệ` is two
/// marks in NFD), so `I\u{20DD}g\u{20DD}n\u{20DD}o\u{20DD}r\u{20DD}e\u{20DD}` was clean
/// at every surface while `strip_obfuscation` removed it.
///
/// The **count** was the only thing measured, and for an enclosing mark the *category* is
/// the whole signal: no `Me` mark is an accent, and nothing legitimate encircles every
/// letter of a word.
const ENCLOSING_MARKS: &[char] = &[
    '\u{0488}', '\u{0489}', '\u{1ABE}', '\u{20DD}', '\u{20DE}', '\u{20DF}', '\u{20E0}', '\u{20E2}',
    '\u{20E3}', '\u{20E4}', '\u{A670}', '\u{A671}', '\u{A672}',
];
/// Fewest folding characters before a wholly non-ASCII token is called a disguise (#815).
///
/// Below this sit IPA fragments and linguistic notation — `\u{026a}\u{0274}` is two
/// characters and a real transcription. A disguised identifier is not.
const MIN_WHOLLY_CONFUSABLE: usize = 4;

/// A token with NO ASCII letter whose every character imitates one (#815).
///
/// #633's gate reports a `confusable` only when the word also carries an ASCII letter,
/// which is what keeps `\u{041F}\u{0440}\u{0438}\u{0432}\u{0435}\u{0442}` clean and is a
/// gate worth having — #907 records what happens when a surface treats legitimate
/// non-Latin text as something to rewrite.
///
/// It inverts, though. Substituting one letter of `instructions` for its small capital
/// trips the detector and substituting all twelve silences it, because the last ASCII
/// letter leaves with the last substitution. A word where *every* character imitates a
/// Latin letter is more suspicious than a half-converted one, not less.
///
/// Four conditions, and the fourth is the whole difference between "a word in another
/// script" and "Latin letters wearing a disguise":
///
/// 1. every non-space character folds to an ASCII **letter**, which also rules out any
///    ASCII letter, since none of the table's three ASCII sources (#725) is one,
/// 2. at least [`MIN_WHOLLY_CONFUSABLE`] of them,
/// 3. the token's script is Latin, or it has none at all,
/// 4. and it is not wholly drawn from a block where a whole token is ordinary text.
///
/// `\u{041C}\u{043E}\u{0441}\u{043A}\u{0432}\u{0430}` passes the first three — every
/// Cyrillic letter here folds to ASCII — and fails the fourth. The "no script" arm is for
/// the negative enclosed letters, which are category `So` and belong to no script while
/// still spelling a word.
///
/// Measured before shipping: 4 hits across the 23,135-row key-stability corpus, every one
/// an attack string, and 0 across 235,976 entries of `/usr/share/dict/words`.
fn is_wholly_confusable_word(part: &str) -> bool {
    let core: Vec<char> = part.chars().filter(|c| !c.is_whitespace()).collect();
    if core.len() < MIN_WHOLLY_CONFUSABLE {
        return false;
    }
    // No explicit "contains no ASCII letter" check: the table has three ASCII sources
    // (#725) and none is a letter, so an ASCII letter fails the fold test below and the
    // check would be redundant. Mutation testing is what showed that — deleting it left
    // every test passing, which is the only honest reason to know.
    let folds_to_letter = |c: char| {
        crate::tables::lookup_confusable(c, "latin")
            .is_some_and(|t| t.len() == 1 && t.chars().all(|f| f.is_ascii_alphabetic()))
    };
    if !core.iter().copied().all(folds_to_letter) {
        return false;
    }
    // #722 section 2 spared seven blocks under #633's NHK argument: a detector that fires
    // on ordinary text written wholly in one of them is a detector a caller switches off.
    // That argument is real for three of them and contested for the rest, so this rule
    // takes the three rather than the list.
    //
    // A Japanese broadcaster IS written in fullwidth forms, an SI unit IS one CJK
    // Compatibility glyph, a numero sign IS Letterlike. Nothing else spells those. But
    // Phonetic Extensions and Enclosed Alphanumeric Supplement are where the disguised
    // English words live, and sparing a block because it CAN hold ordinary text is what
    // let the finished attack through in the first place.
    //
    // IPA is the false positive this risks, and the length floor answers it: a
    // transcription short enough to be wholly non-ASCII is shorter than
    // MIN_WHOLLY_CONFUSABLE. Measured at 0 hits across 235,976 dictionary words and 0
    // across the key-stability corpus's natural word forms.
    if core.iter().copied().all(ordinary_as_a_whole_token) {
        return false;
    }
    let scripts = detect_scripts(part);
    scripts.is_empty() || scripts == ["Latin"]
}

/// The three blocks of [`whole_token_compat_is_ordinary`] where a whole token really is
/// ordinary text and nothing else spells it (#815).
fn ordinary_as_a_whole_token(ch: char) -> bool {
    matches!(ch,
        '\u{FF00}'..='\u{FFEF}'      // Halfwidth and Fullwidth Forms
        | '\u{3300}'..='\u{33FF}'    // CJK Compatibility
        | '\u{2100}'..='\u{214F}'    // Letterlike Symbols
    )
}

/// Wrapping punctuation trimmed from token edges (NOT the leet symbols @ $ |).
const WRAP: &[char] = &[
    '"', '.', ',', ';', ':', '?', '!', '(', ')', '[', ']', '{', '}', '<', '>', '\u{AB}', '\u{BB}',
    '\u{201C}', '\u{201D}', '\u{2018}', '\u{2019}', '`', '\u{2014}', '\u{2026}', '\'', ' ', '\t',
];
/// CJK script names: legitimately mixed with Latin in ordinary text (annotations,
/// product names, mixed-language prose), so they are exempt from the mixed-script branch.
///
/// **Wider than the UTS #39 §5.1 augmented sets, on purpose** (#776).
/// [`crate::scripts::is_mixed_script`] resolves those sets exactly, so it calls Latin
/// beside Japanese mixed — a *label* doing that is the shape the rule exists to catch.
/// This detector runs over prose, where a Japanese sentence carrying a product name in
/// Latin is ordinary text, so it exempts the combination as well. The two answers differ
/// for `例えa` and that is a policy, recorded in
/// `tests/test_augmented_script_sets.py::test_the_detector_stays_wider_on_purpose`.
const CJK_SCRIPTS: &[&str] = &["Han", "Hiragana", "Katakana", "Hangul", "Bopomofo"];

/// Legitimate spoof-looking unit symbols (lowercased), exempt from the mixed-script branch.
const UNITS: &[&str] = &[
    "kω", "mω", "gω", "µf", "nf", "pf", "µm", "µs", "µg", "µa", "µv", "å", "ω", "°c", "°f",
];

/// The kind of anomaly a [`Finding`] records.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum AnomalyKind {
    /// A zero-width / invisible formatting codepoint inside a Latin word.
    Invisible,
    /// A bidi override, or a bidi control inside a majority-Latin token (Trojan Source).
    Bidi,
    /// Excessive stacked combining marks.
    Zalgo,
    /// One token mixing Latin with Cyrillic or Greek (a Latin homoglyph).
    MixedScript,
    /// One token mixing strong left-to-right and strong right-to-left *letters*
    /// (no `U+202x` override — that is [`Bidi`](Self::Bidi)), which can visually
    /// reorder under the Unicode Bidi Algorithm — the "BiDi Swap" precondition.
    BidiMixed,
    /// A letter-for-symbol substitution decoding to a common word (`fr33` -> `free`).
    Leet,
    /// Dense separators splitting single letters into a real word (`v.i.a.g.r.a`).
    Segmentation,
    /// A non-whitespace control character (`NUL`, `ESC`, `BEL`, `DEL`, the C1 block).
    ///
    /// Never legitimate in text, and the introducer for terminal-escape injection
    /// (CVE-2008-2383, CVE-2019-9535) and leading-blank blocklist bypass
    /// (CVE-2023-24329). The whitespace-class controls — TAB, LF, VT, FF, CR, the
    /// information separators `U+001C`–`U+001F`, NEL — are excluded: they are real
    /// separators that [`crate::api::collapse_whitespace`] folds to a space,
    /// so flagging them would fire on ordinary multi-line text (#612).
    Control,
    /// A token spelled partly in a Unicode **compatibility** form and partly in ASCII —
    /// `ａdmin`, `ｅxample.com`, `＜script＞` — which NFKC folds to a different string.
    ///
    /// `canonicalize` performs that fold as its first step, so the whole class was
    /// neutralized and reported clean (#633). The mixed spelling is the signal: nobody
    /// writes half a word in fullwidth. A token that is *wholly* in a compatibility form
    /// (`ｐａｙｐａｌ`, `ＮＨＫ`, `１９９５年`) is deliberately not flagged — see the
    /// branch in `classify` for why.
    CompatFold,
    /// A token where the **confusable fold** — not NFKC — produces ASCII the input did
    /// not contain: `pɑypal` (`U+0251`), `gıthub` (`U+0131`), `ord∶end` (`U+2236`).
    ///
    /// `canonicalize` has two ASCII-producing steps and [`CompatFold`](Self::CompatFold)
    /// reported only the first. The second is the largest body of data disarm ships, and
    /// the aggregate detector never consulted it: `is_confusable("pɑypal")` was `true`,
    /// `canonicalize` returned `paypal`, and `has_anomalies` said `false`. The slice with
    /// no compatibility decomposition is also single-script, so
    /// [`MixedScript`](Self::MixedScript) cannot see it either (#737).
    ///
    /// It covers the punctuation half too (#719): `U+2236 RATIO` has no decomposition at
    /// all and reaches `:` only through the fold, so a token could gain a delimiter with
    /// nothing to report it. 232 code points reach ASCII by the fold alone, 76 of them
    /// producing one of `: = % & ? # / \`.
    ///
    /// Gated exactly as `CompatFold` is — the token must also carry an ASCII letter — so
    /// `Привет` and `Ελλάδα` do not fire. Every letter in them folds to Latin, and
    /// flagging that is the whole-legitimate-non-Latin-web over-flagging #545 removed
    /// from `is_suspicious_hostname`.
    Confusable,
    /// A token whose base characters carry **enclosing marks** (`Me`) — `I⃝g⃝n⃝o⃝r⃝e⃝`.
    ///
    /// Its own kind rather than a `Zalgo` finding, because it is a different fact: not
    /// "too many marks" but "a mark whose category is never an accent". One per base is
    /// below every threshold disarm has — `is_zalgo` fires above three and `strip_zalgo`
    /// keeps two — so the whole class was clean at every surface while `strip_obfuscation`
    /// removed it, and `canonicalize`'s accent preservation (correct for `café` and
    /// `Việt`) preserved this too (#724).
    ///
    /// Keycap sequences are exempt: `1️⃣` is `1` + `U+FE0F` + `U+20E3`, and the variation
    /// selector is what makes it an RGI keycap rather than a bare enclosing mark — the
    /// same shape as the subdivision-flag allowlist. Cyrillic `Me` on a Cyrillic base is
    /// exempt too; `U+0488` is historic Cyrillic notation, not a disguise.
    EnclosingMark,
    /// A token drawing digits from more than one decimal numbering system — UTS #39 §5.3
    /// *Mixed Numbers*.
    ///
    /// `1٢۳４५` reads as `12345` and is five systems; `12٣` is two and was clean at every
    /// surface. Digits carry the script of nothing, so
    /// [`MixedScript`](Self::MixedScript) cannot see the common shape — a token that is
    /// mostly ASCII with one substituted digit is one script to every other check here.
    ///
    /// A single system is never flagged however unusual it looks: `٢٠٢٤` is a year.
    MixedNumbers,
    /// A base carrying the **same stacking mark twice** — UTS #39 5.4's first
    /// optional-detection rule, *"forbid sequences of the same nonspacing mark"*.
    ///
    /// Its own kind rather than a [`Zalgo`](Self::Zalgo) finding, for the reason #724
    /// gave for [`EnclosingMark`](Self::EnclosingMark): a different fact, not "too many
    /// marks" but "the same mark twice", which no count reaches — two is below
    /// `is_zalgo`'s threshold by construction.
    ///
    /// It is not removable by the cap either. `strip_zalgo` keeps up to
    /// `DEFAULT_MAX_MARKS` per position, so a duplicate survives canonicalization
    /// whatever the cap is set to: a base with two acutes does not canonicalize to the
    /// same string as the same base with one. Two spellings a reader sees as one word
    /// produce different keys, and nothing reported it (#835).
    ///
    /// Restricted to marks of **nonzero combining class**, which is #842's discriminator:
    /// a class-0 mark is positioned by the renderer rather than stacked, and a repeated
    /// Indic matra or Thai vowel is an orthography question rather than this one. The
    /// `Me` half of the same UTS #39 rule is [`EnclosingMark`](Self::EnclosingMark),
    /// which #724 already triggers on two.
    DuplicateMark,
}

impl AnomalyKind {
    /// The lowercase token name.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            AnomalyKind::Invisible => "invisible",
            AnomalyKind::Bidi => "bidi",
            AnomalyKind::Zalgo => "zalgo",
            AnomalyKind::MixedScript => "mixed_script",
            AnomalyKind::BidiMixed => "bidi_mixed",
            AnomalyKind::Leet => "leet",
            AnomalyKind::Segmentation => "segmentation",
            AnomalyKind::Control => "control",
            AnomalyKind::CompatFold => "compat_fold",
            AnomalyKind::Confusable => "confusable",
            AnomalyKind::EnclosingMark => "enclosing_mark",
            AnomalyKind::MixedNumbers => "mixed_numbers",
            AnomalyKind::DuplicateMark => "duplicate_mark",
        }
    }
}

/// One reason a token is anomalous. `start`/`end` are byte offsets into the input text.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Finding {
    /// Which branch fired.
    pub kind: AnomalyKind,
    /// The offending whitespace token, as it appeared.
    pub token: String,
    /// Byte offset of the token start in the input.
    pub start: usize,
    /// Byte offset of the token end in the input.
    pub end: usize,
    /// Evidence: the codepoint, the scripts, or the decoded word.
    pub detail: String,
}

impl Finding {
    /// A plain-language sentence describing the finding.
    #[must_use]
    pub fn reason(&self) -> String {
        match self.kind {
            AnomalyKind::Invisible => {
                format!(
                    "{:?} contains an invisible character ({})",
                    self.token, self.detail
                )
            }
            AnomalyKind::Bidi => format!(
                "{:?} contains a bidirectional control character ({})",
                self.token, self.detail
            ),
            AnomalyKind::Zalgo => {
                format!(
                    "{:?} is overloaded with combining marks (zalgo)",
                    self.token
                )
            }
            AnomalyKind::MixedScript => format!("{:?} mixes {}", self.token, self.detail),
            AnomalyKind::BidiMixed => format!(
                "{:?} mixes left-to-right and right-to-left letters ({}), which can visually reorder",
                self.token, self.detail
            ),
            AnomalyKind::Leet => {
                format!("{:?} decodes to the word {:?}", self.token, self.detail)
            }
            AnomalyKind::Segmentation => {
                format!("{:?} splits the word {:?}", self.token, self.detail)
            }
            AnomalyKind::Control => {
                format!("{:?} contains the control character {}", self.token, self.detail)
            }
            AnomalyKind::CompatFold => format!(
                "{:?} mixes a compatibility form with ASCII and folds to {}",
                self.token, self.detail
            ),
            AnomalyKind::Confusable => {
                format!("{:?} contains a confusable: {}", self.token, self.detail)
            }
            AnomalyKind::EnclosingMark => format!(
                "{:?} carries enclosing marks that hide the base text: {}",
                self.token, self.detail
            ),
            AnomalyKind::MixedNumbers => format!(
                "{:?} mixes digits from {} (UTS #39 Mixed Numbers)",
                self.token, self.detail
            ),
            AnomalyKind::DuplicateMark => format!(
                "{:?} repeats the same combining mark ({}), which renders as one",
                self.token, self.detail
            ),
        }
    }
}

/// Structured result, parallel to [`crate::api::HostnameAnalysis`].
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AnomalyReport {
    /// Whether any token tripped (the same value [`has_anomalies`] returns).
    pub anomalous: bool,
    /// The kinds that fired, in order of first appearance.
    pub kinds: Vec<AnomalyKind>,
    /// Every finding, with span and detail.
    pub findings: Vec<Finding>,
    /// The first finding's reason, or `None`.
    pub reason: Option<String>,
}

/// Shortest decode the *near-miss* sub-path will consider (#825).
///
/// The leet branch has two sub-paths: the decode is a lexicon word, or the decode is one
/// edit from one. The first has a floor of three. The second carried `>= 6` from #393
/// with no comment, and `leet_sub` maps `'1'` to `'i'` rather than `'l'` — correctly, but
/// it means a `1`-for-`l` substitution never decodes *exactly* and can only ever be
/// caught by the second path. Below the floor that path does not run, so the whole
/// substitution class went unreported on short targets: `l0gin` was caught and `1ogin`
/// was not, same brand, same five letters, one digit each.
///
/// Five rather than six or three, and the number is measured rather than chosen. Over 65
/// ordinary digit-bearing tokens (`mp3`, `k8s`, `sha1`, `i18n`, `rtx4090`, …) against a
/// 234k-word lexicon, and 8 single-substitution brand spoofs:
///
/// | floor | false positives / 65 | spoofs caught / 8 |
/// |------:|---------------------:|------------------:|
/// | 3     | 22                   | 8                 |
/// | 4     | 12                   | 8                 |
/// | **5** | **5**                | **7**             |
/// | 6     | 4                    | 3                 |
///
/// Six caught three of eight. Five costs exactly one more false positive than six —
/// `top10`, whose decode `topio` is one edit from a word — and more than doubles the
/// spoofs caught. Four costs eight more to gain one (`1yft`, four letters), which is the
/// wrong side of the knee.
///
/// The issue argued the floor should go entirely, on the grounds that the exact path
/// already fires below it and produces false positives anyway. The measurement does not
/// support that: the exact path contributes 4 of the 65, and removing the floor takes the
/// total to 22. The floor is doing work — it was just set three positions too high.
const NEAR_MISS_MIN_LEN: usize = 5;

fn leet_sub(c: char) -> Option<char> {
    match c {
        '0' => Some('o'),
        '1' | '!' => Some('i'),
        '2' => Some('z'),
        '3' => Some('e'),
        '4' | '@' => Some('a'),
        '5' | '$' => Some('s'),
        '6' | '9' => Some('g'),
        '7' | '+' => Some('t'),
        '8' => Some('b'),
        '|' => Some('l'),
        _ => None,
    }
}

fn codepoint(c: char) -> String {
    format!("U+{:04X}", c as u32)
}

fn base_ascii(s: &str) -> String {
    s.chars()
        .filter(char::is_ascii_alphabetic)
        .map(|c| c.to_ascii_lowercase())
        .collect()
}

/// Undo leet only if every non-letter is a letter-substitute (apostrophes skipped); else
/// `None`. The literal-number guard: `win32` -> `None` (the `2` maps to no letter).
fn leet_demangle(s: &str) -> Option<String> {
    let mut out = String::new();
    for c in s.chars() {
        if c.is_alphabetic() {
            out.extend(c.to_lowercase());
        } else if let Some(m) = leet_sub(c) {
            out.push(m);
        } else if c == '\'' || c == '\u{2019}' {
            // skip apostrophes so contractions decode (d0n't -> dont)
        } else {
            return None;
        }
    }
    Some(out)
}

fn is_majority_latin(tok: &str) -> bool {
    // Single pass with two integer counters (no Vec allocation): count alphabetic
    // letters and how many of them are ASCII (Latin).
    let mut letters = 0usize;
    let mut ascii = 0usize;
    for c in tok.chars() {
        if c.is_alphabetic() {
            letters += 1;
            if c.is_ascii() {
                ascii += 1;
            }
        }
    }
    letters != 0 && ascii * 2 >= letters
}

/// True if `tok` carries no alphabetic letters at all (digits/punct only).
fn has_no_letters(tok: &str) -> bool {
    !tok.chars().any(char::is_alphabetic)
}

/// `^\d+(st|nd|rd|th|am|pm)$`, case-insensitive (ordinals and times are literal).
fn is_ordinal_or_time(s: &str) -> bool {
    let lower = s.to_ascii_lowercase();
    for suf in ["st", "nd", "rd", "th", "am", "pm"] {
        if let Some(num) = lower.strip_suffix(suf) {
            if !num.is_empty() && num.chars().all(|c| c.is_ascii_digit()) {
                return true;
            }
        }
    }
    false
}

/// `^[A-Za-z]+[0-9@$|]+$`: a word followed only by trailing digits/symbols.
fn is_word_plus_trailing(s: &str) -> bool {
    let mut chars = s.chars().peekable();
    let mut letters = 0usize;
    while let Some(&c) = chars.peek() {
        if c.is_ascii_alphabetic() {
            chars.next();
            letters += 1;
        } else {
            break;
        }
    }
    if letters == 0 {
        return false;
    }
    let mut tail = 0usize;
    for c in chars {
        if c.is_ascii_digit() || matches!(c, '@' | '$' | '|') {
            tail += 1;
        } else {
            return false;
        }
    }
    tail > 0
}

/// A single-edit neighbour of `d` that is in the lexicon (`dealz` -> `deals`).
fn nearest(d: &str, lexicon: &HashSet<String>) -> Option<String> {
    let chars: Vec<char> = d.chars().collect();
    let n = chars.len();
    for i in 0..n {
        let mut s = String::with_capacity(n.saturating_sub(1));
        s.extend(chars[..i].iter().copied());
        s.extend(chars[i + 1..].iter().copied());
        if lexicon.contains(s.as_str()) {
            return Some(s);
        }
    }
    for i in 0..=n {
        for c in b'a'..=b'z' {
            let ch = c as char;
            let mut ins = String::with_capacity(n + 1);
            ins.extend(chars[..i].iter().copied());
            ins.push(ch);
            ins.extend(chars[i..].iter().copied());
            if lexicon.contains(ins.as_str()) {
                return Some(ins);
            }
            if i < n {
                let mut sub = String::with_capacity(n);
                sub.extend(chars[..i].iter().copied());
                sub.push(ch);
                sub.extend(chars[i + 1..].iter().copied());
                if lexicon.contains(sub.as_str()) {
                    return Some(sub);
                }
            }
        }
    }
    None
}

/// Blocks where a token spelled *wholly* in a compatibility form is ordinary text (#722).
///
/// #633 exempted the whole-token case with a sound argument about one block: `ｐａｙｐａｌ`
/// is indistinguishable by character class from `ＮＨＫ`, and a detector that fires on
/// `ＮＨＫ` is one a CJK-facing caller switches off entirely. The exemption was then
/// applied to *every* compatibility form, including blocks where no `ＮＨＫ` exists — so
/// 652 Mathematical Alphanumeric code points spell a whole word that `canonicalize` folds
/// to plain ASCII and the detector reported clean.
///
/// The list is the blocks where the argument actually holds:
///
/// - Halfwidth and Fullwidth Forms — `ＮＨＫ`, `Ｑ＆Ａ`, the #633 case itself
/// - CJK Compatibility — `㎏`, `㎞`, ordinary units
/// - Letterlike Symbols — `№`, `℡`
/// - Phonetic Extensions and IPA Extensions — an IPA transcription is a whole token
/// - Enclosed Alphanumeric Supplement — regional indicators, handled elsewhere
///
/// Mathematical Alphanumeric Symbols and Enclosed Alphanumerics are deliberately absent:
/// a formula variable is not a word, and `ⓟⓐⓨⓟⓐⓛ` is not prose. Those are #722 §2's two
/// starting blocks.
fn whole_token_compat_is_ordinary(ch: char) -> bool {
    matches!(ch,
        '\u{FF00}'..='\u{FFEF}'      // Halfwidth and Fullwidth Forms
        | '\u{3300}'..='\u{33FF}'    // CJK Compatibility
        | '\u{2100}'..='\u{214F}'    // Letterlike Symbols
        | '\u{0250}'..='\u{02AF}'    // IPA Extensions
        | '\u{1D00}'..='\u{1D7F}'    // Phonetic Extensions
        | '\u{1D80}'..='\u{1DBF}'    // Phonetic Extensions Supplement
        | '\u{1F100}'..='\u{1F1FF}'  // Enclosed Alphanumeric Supplement
    )
}

/// The first stacking mark that appears twice in a row on one base (#835).
///
/// Compared over NFD. Canonical ordering sorts a base's marks by combining class, so two
/// copies of one mark end up adjacent however they were typed — the same property that
/// makes `strip_zalgo`'s per-class count un-evadable by interleaving (#842).
///
/// Nonzero combining class only, which is #842's discriminator: a class-0 mark is
/// positioned by the renderer rather than stacked, so a repeated Indic matra or Thai
/// vowel is an orthography question and not this one.
///
/// A run is bounded by any non-mark, so `a` + acute + `b` + acute is two bases carrying
/// one mark each and is not a finding.
fn duplicate_stacking_mark(tok: &str) -> Option<char> {
    use unicode_normalization::char::{canonical_combining_class, is_combining_mark};
    use unicode_normalization::UnicodeNormalization;

    let mut previous: Option<char> = None;
    for ch in tok.nfd() {
        if is_combining_mark(ch) && canonical_combining_class(ch) != 0 {
            if previous == Some(ch) {
                return Some(ch);
            }
            previous = Some(ch);
        } else {
            previous = None;
        }
    }
    None
}

/// The ASCII a confusable fold introduces that the input did not have (#719, #737).
///
/// Returns `(source, target)` for the first such character, so `Finding::detail` can name
/// the impersonated letter the way `mixed_script` names the two scripts.
///
/// The fold is `canonicalize`'s *second* ASCII-producing step and nothing reported it.
/// `pɑypal` folded to `paypal` while `has_anomalies` said clean, and the slice with no
/// compatibility decomposition is single-script, so `mixed_script` could not see it
/// either. `U+2236 RATIO` is the punctuation half: no decomposition at all, reaching `:`
/// only through the fold.
fn folded_confusable(tok: &str) -> Option<(char, &'static str)> {
    fn ascii_target(c: char) -> Option<&'static str> {
        // Only a fold that *lands* in ASCII matters: the point is that the output carries
        // a character the input did not, which is what a downstream comparison sees.
        crate::tables::lookup_confusable(c, "latin").filter(|t| t.is_ascii())
    }
    tok.chars().find_map(|c| {
        if c.is_ascii() {
            return None;
        }
        if let Some(target) = ascii_target(c) {
            return Some((c, target));
        }
        // The composed case, which #719 calls the subtle one: `U+00BD` NFKC-decomposes to
        // `1⁄2`, whose middle character is `U+2044` and is NOT ASCII — so the `CompatFold`
        // gate above is false — and the `/` appears only when the fold reaches that
        // `U+2044` one step later. Neither step alone sees it; the composition does.
        c.nfkc()
            .find(|f| !f.is_ascii() && ascii_target(*f).is_some())
            .and_then(|f| ascii_target(f).map(|target| (c, target)))
    })
}
/// Enclosing marks in `tok` that are not part of a legitimate sequence (#724 §2).
///
/// Two exemptions, both narrow and both measured rather than assumed:
///
/// - **Keycaps.** `1️⃣` is `1` + `U+FE0F` + `U+20E3`, and the variation selector is what
///   makes it an RGI keycap rather than a bare enclosing mark — the same distinction
///   `crate::invisibles` draws for a subdivision flag. A `U+20E3` with no `U+FE0F` before
///   it is not a keycap.
/// - **Cyrillic.** `U+0488`, `U+0489`, `U+A670`-`U+A672` are historic Cyrillic notation.
///   On a Cyrillic base they are orthography; on a Latin one they are a disguise.
///
/// Two are required rather than one. A single enclosing mark on a single base is a
/// character someone may have typed; encircling *every* letter of a word is not something
/// any orthography does, and that is the shape #724 measures.
fn enclosing_marks(tok: &str) -> Vec<char> {
    const KEYCAP: char = '\u{20E3}';
    const VS16: char = '\u{FE0F}';
    let chars: Vec<char> = tok.chars().collect();
    let mut out = Vec::new();
    for (i, &c) in chars.iter().enumerate() {
        if !ENCLOSING_MARKS.contains(&c) {
            continue;
        }
        if c == KEYCAP && i > 0 && chars[i - 1] == VS16 {
            continue;
        }
        // The base is the last character before it that is not a combining mark of any
        // kind — not merely the last non-*enclosing* one. An intervening `U+0301` would
        // otherwise be read as the base, and `а\u{301}\u{488}` reported.
        //
        // And the script comes from `detect_char_script`, the one resolver, rather than
        // from a hand-written range: the first draft listed `U+0400-04FF` and
        // `U+A640-A69F` and so missed Cyrillic Supplement and Extended-C, reporting
        // ordinary `\u{501}\u{488}` and `\u{1C80}\u{488}`. Restating a range that the
        // library already resolves is the failure #774 was about.
        let base_is_cyrillic = chars[..i]
            .iter()
            .rev()
            .find(|b| !unicode_normalization::char::is_combining_mark(**b))
            .is_some_and(|b| crate::scripts::detect_char_script(*b) == "Cyrillic");
        if base_is_cyrillic {
            continue;
        }
        out.push(c);
    }
    out
}

/// `tok` trimmed by `WRAP` **minus** the characters that are also leet substitutes (#726).
///
/// `!`, `(` and `)` sit in both sets. Trimming them off the token edge before the leet
/// decode is right when they are punctuation (`4dm1n!`) and wrong when they are the
/// substitution (`!gn0r3` -> `ignore`). Position cannot tell those apart; the lexicon can,
/// so this is the second attempt and runs only after the trimmed decode has missed.
fn leet_edge_core(tok: &str) -> &str {
    tok.trim_matches(|c: char| WRAP.contains(&c) && leet_sub(c).is_none() && c != '(' && c != ')')
}

/// Whether `c` separates the letters of a segmented word (#750, #720).
///
/// Was three characters — `.`, `_`, `-` — while Unicode has two whole general categories
/// for joining parts of one word. Measured over `c<SEP>o<SEP>n<SEP>f<SEP>i<SEP>r<SEP>m`,
/// the exact shape this branch is documented to catch, **16 of the 36 joiners were silent
/// on every path**, and two of those are sharper than silence: `canonicalize` actively
/// rewrites `U+2E40` and `U+30A0` to `=`, which was not in the recognised set either, so
/// the fold moved the attack from one unrecognised separator to another.
///
/// `U+2010 HYPHEN` is the real typographic hyphen and `U+002D HYPHEN-MINUS` is the ASCII
/// one. They render identically, and the branch fired on one and not the other.
///
/// Derived from the general category by `scripts/gen_word_joiners.py` rather than curated,
/// so a Unicode release that adds a dash cannot leave a hole. The exotic spaces are here
/// too (#720): `is_token_boundary` declines to consume them precisely so this branch can
/// see them.
#[inline]
fn is_segment_separator(c: char) -> bool {
    crate::tables::is_word_joiner(c) || (c.is_whitespace() && !is_token_boundary(c))
}

/// A word split by an exotic space, rejoined into a lexicon word (#720).
///
/// `seg_word` above answers a different question: *dense* single-letter splitting, where
/// `v.i.a.g.r.a` is a finding because five separators sit between six letters. A word
/// broken **once** — `Ign\u{200A}ore` — never reaches that gate and should not; the shape
/// is not density but a separator that has no business inside a word at all.
///
/// The discrimination is the lexicon, and it is the only thing that works here. Every
/// candidate looks identical to `collapse_whitespace`, which folds them all to `U+0020`:
///
/// ```text
/// Ign<U+200A>ore    -> "ignore"     in the lexicon      -> fragmentation
/// Mr.<U+00A0>Smith  -> "mr.smith"   not a word          -> clean
/// 10<U+00A0>km      -> "10km"       not a word          -> clean
/// Hello<U+00A0>мир  -> "helloмир"   not a word          -> clean
/// ```
///
/// This is the word-fragmentation subtype of arXiv:2508.14070v1 §3, whose generator uses
/// `U+200A`; it measured 0/10 neutralized and 0/10 detected, the only structural subtype
/// where both columns were zero and the input is still plainly legible.
///
/// A letter is required on **both** sides of at least one removed space, so a trailing or
/// leading one — which is a space doing its job — cannot trip it.
fn space_fragmented_word(core: &str, lexicon: &HashSet<String>) -> Option<String> {
    let chars: Vec<char> = core.chars().collect();
    let mut word_internal = false;
    let mut joined = String::with_capacity(core.len());
    for (i, &c) in chars.iter().enumerate() {
        if c.is_whitespace() && !is_token_boundary(c) {
            let before = chars[..i]
                .iter()
                .next_back()
                .is_some_and(|p| p.is_alphabetic());
            let after = chars[i + 1..]
                .iter()
                .next()
                .is_some_and(|n| n.is_alphabetic());
            if before && after {
                word_internal = true;
            }
            continue;
        }
        joined.extend(c.to_lowercase());
    }
    if !word_internal || joined.chars().count() < 4 {
        return None;
    }
    lexicon.contains(joined.as_str()).then_some(joined)
}

/// Dense single-letter segmentation (`v.i.a.g.r.a`), not a lone hyphen or `6-foot-6`.
fn seg_word(core: &str, lexicon: &HashSet<String>) -> Option<String> {
    // Collapse runs of consecutive separators before counting, so padding (`v-.-i-.-a...`)
    // cannot inflate the separator count to game the density ratio: each run counts once.
    let mut seps = 0usize;
    let mut prev_sep = false;
    for c in core.chars() {
        let is_sep = is_segment_separator(c);
        if is_sep && !prev_sep {
            seps += 1;
        }
        prev_sep = is_sep;
    }
    // #752: DEMANGLE the non-letters rather than dropping them. `p.4.s.s.w.0.r.d` used to
    // reassemble as `psswrd` — `4` and `0` are not `is_alphabetic`, so they were silently
    // discarded — and neither that nor `p.a.s.s.w.0.r.d`'s `passwrd` is in any lexicon.
    // One substituted character was enough to defeat both branches that each catch its
    // halves: the leet branch fails because `core` still holds the separators, and this
    // one failed because it threw the substitute away. Every substitutable position in
    // `password` — `a`, both `s`, and `o`, the four letters `leet_sub` has an inverse for
    // — screened clean.
    let letters: Vec<char> = core
        .chars()
        .filter(|c| !is_segment_separator(*c))
        .filter_map(|c| {
            if c.is_alphabetic() {
                Some(c)
            } else {
                leet_sub(c)
            }
        })
        .collect();
    // Dense single-letter splitting: require seps >= 2 AND 5*seps >= 3*(letters-1).
    if seps < 2 || 5 * seps < 3 * letters.len().saturating_sub(1) {
        return None;
    }
    for part in core.split(is_segment_separator) {
        if part.chars().count() > 1 && part.chars().any(char::is_alphabetic) {
            return None;
        }
    }
    let word: String = letters.iter().flat_map(|c| c.to_lowercase()).collect();
    if word.chars().count() >= 4 && lexicon.contains(word.as_str()) {
        Some(word)
    } else {
        None
    }
}

/// The longest carrier run in `chars` that reaches its class's threshold (#700 §2, §4).
///
/// Returns `(class-representative code point, run length)`. Reports the **run**, not one
/// character of it: a finding whose detail names `U+200B` when sixteen are in sequence
/// understates the input, and the count is what tells a caller this was a payload rather
/// than a stray character.
///
/// A well-formed emoji subdivision flag is skipped whole (#700 §3). `U+1F3F4` plus tag
/// letters plus `U+E007F` is a flag when the letters decode to one of the three RGI
/// payloads, and the tags channel wearing a flag base otherwise — a distinction
/// `crate::invisibles` already draws, and which is reused rather than restated so the
/// detector and the stripper cannot disagree.
fn carrier_run(chars: &[char]) -> Option<(char, usize)> {
    let mut i = 0;
    let mut best: Option<(char, usize)> = None;
    while i < chars.len() {
        if let Some(len) = crate::invisibles::subdivision_flag_len(&chars[i..]) {
            i += len;
            continue;
        }
        let Some(class) = Carrier::of(chars[i]) else {
            i += 1;
            continue;
        };
        let start = i;
        while i < chars.len() && Carrier::of(chars[i]) == Some(class) {
            i += 1;
        }
        let len = i - start;
        // An explicit match rather than `is_none_or` (Rust 1.82; the crate's MSRV is
        // 1.81) or `map_or(true, ..)`, which clippy rewrites back into `is_none_or`.
        let longer = match best {
            None => true,
            Some((_, best_len)) => len > best_len,
        };
        if len >= class.threshold() && longer {
            best = Some((chars[start], len));
        }
    }
    best
}

fn classify(tok: &str, start: usize, lexicon: &HashSet<String>) -> Option<Finding> {
    let end = start + tok.len();
    let mk = |kind: AnomalyKind, detail: String| Finding {
        kind,
        token: tok.to_string(),
        start,
        end,
        detail,
    };

    // `core` (token with wrapping punctuation trimmed) is needed by both the mixed-script
    // branch and the leet/segmentation branches; compute it once.
    let core = tok.trim_matches(|c: char| WRAP.contains(&c));

    // Non-whitespace controls (#612). Checked BEFORE the ASCII fast-path below, because
    // NUL, ESC, BEL and DEL are all ASCII — a pure-ASCII token skips that whole block, so
    // a check placed inside it would never see the vectors this exists for.
    //
    // Presence, not position. #612 framed this as an "edge" question because it started
    // from whitespace trimming, but a control hides things wherever it sits: the last
    // character of `"malicious\u{1b}\\"` is a backslash, so an edge-only rule would call
    // that token clean while the escape introducer sits one place in.
    //
    // The whitespace-class controls are excluded via `is_fold_whitespace` — TAB, LF, VT,
    // FF, CR, `U+001C`-`U+001F` and NEL are real separators that `collapse_whitespace`
    // folds to a space, and flagging them would fire on ordinary multi-line text. That is
    // the same split `strip_control_chars` has drawn since #433, reused rather than
    // restated so the two cannot drift.
    if let Some(c) = tok
        .chars()
        .find(|&c| c.is_control() && !crate::whitespace::is_fold_whitespace(c))
    {
        return Some(mk(AnomalyKind::Control, codepoint(c)));
    }

    // ASCII fast-path: the invisible / bidi / zalgo / mixed-script branches can only fire
    // above U+007F, so a pure-ASCII token skips every script and zalgo call.
    if !tok.is_ascii() {
        // Mixed numbers — UTS #39 §5.3 (#777). Inside the fast path, not before it: a
        // pure-ASCII token carries only ASCII digits and so cannot mix systems, and the
        // shape this exists for — `12\u{0663}`, ASCII beside Arabic-Indic — is not pure
        // ASCII, so it reaches here anyway. An earlier version ran the scan on every
        // token and paid a walk plus a binary search per digit for nothing (#865 review).
        //
        // Two or more systems, not "any non-ASCII digit". `\u{0662}\u{0660}\u{0662}\u{0664}`
        // is a year written entirely in Arabic-Indic digits and is ordinary text; `12\u{0663}`
        // is not, and it was clean at every surface — `is_mixed_script` sees one script
        // because digits carry the script of nothing, and nothing looked at numbering
        // systems at all.
        let systems = crate::digits::system_count(tok);
        if systems > 1 {
            return Some(mk(
                AnomalyKind::MixedNumbers,
                format!("{systems} decimal numbering systems"),
            ));
        }

        let chars: Vec<char> = tok.chars().collect();
        for (i, &c) in chars.iter().enumerate() {
            if !is_invisible_in_word(c) {
                continue;
            }
            // ZWJ/ZWNJ are legitimate joiners in many non-Latin scripts (Arabic,
            // Indic) and in emoji sequences, so for them require ASCII-Latin
            // letters on BOTH sides. Every other invisible (ZWSP, word joiner,
            // BOM, …) is never legitimate inside or at the edge of a word, so a
            // single letter neighbour on EITHER side — including accented Latin —
            // is enough (catches word-edge `paypal<ZWSP>` and leading `<BOM>paypal`).
            let joiner = c == '\u{200C}' || c == '\u{200D}';
            let letter = |slice: &[char]| {
                if joiner {
                    slice.iter().any(char::is_ascii_alphabetic)
                } else {
                    slice.iter().copied().any(char::is_alphabetic)
                }
            };
            let before = letter(&chars[..i]);
            let after = letter(&chars[i + 1..]);
            let fire = if joiner {
                before && after
            } else {
                before || after
            };
            if fire {
                return Some(mk(AnomalyKind::Invisible, codepoint(c)));
            }
        }
        // #700 §2: a run fires on its own, with no letter beside it.
        //
        // Checked after the neighbour rule, which matters only for the classes the two
        // share: a lone ZWSP inside a word reports as `U+200B` rather than `U+200B \u{d7}1`.
        // Tags and variation selectors are NOT in `is_invisible_in_word`, so they only
        // ever reach this branch — a single tag character reports as `U+E0074 \u{d7}1`,
        // which is correct: its threshold is 1 precisely because one of them is already
        // an anomaly.
        if let Some((c, len)) = carrier_run(&chars) {
            return Some(mk(
                AnomalyKind::Invisible,
                format!("{} \u{d7}{len}", codepoint(c)),
            ));
        }
        if let Some(&c) = chars.iter().find(|c| BIDI_OVERRIDE.contains(c)) {
            return Some(mk(AnomalyKind::Bidi, codepoint(c)));
        }
        // Spare isolates and embeddings only in tokens that are majority non-Latin-script
        // (legit RTL): flag one when the token has any ASCII-Latin letter (majority-Latin)
        // OR has no letters at all (digits/punct only, e.g. `12<isolate>34`).
        if is_majority_latin(tok) || has_no_letters(tok) {
            if let Some(&c) = chars
                .iter()
                .find(|c| BIDI_ISOLATES.contains(c) || BIDI_EMBEDDINGS.contains(c))
            {
                return Some(mk(AnomalyKind::Bidi, codepoint(c)));
            }
            // #741 §2: the narrower, higher-precision predicate the measurement suggests
            // — a spared mark immediately preceding a run of European numbers. That is
            // the construction that reorders, and it fires on neither RTL prose nor a
            // hashtag, which is why the mark is not simply added to the list above.
            //
            // The carrier is always a number run: an account number, an amount, a date.
            // Each group keeps its internal digits and the groups swap places, which is
            // what makes the rendering stay plausible.
            if let Some(i) = chars.iter().position(|c| BIDI_RTL_MARKS.contains(c)) {
                if chars.get(i + 1).is_some_and(char::is_ascii_digit) {
                    return Some(mk(AnomalyKind::Bidi, codepoint(chars[i])));
                }
            }
        }
        // #724: checked BEFORE the count-based zalgo rule, because it is a different fact
        // and the count never reaches that threshold — one mark per base is below it by
        // construction.
        let enclosing = enclosing_marks(tok);
        if enclosing.len() >= 2 {
            return Some(mk(
                AnomalyKind::EnclosingMark,
                format!("{} \u{d7}{}", codepoint(enclosing[0]), enclosing.len()),
            ));
        }
        if is_zalgo(tok, ZALGO_THRESHOLD) {
            return Some(mk(
                AnomalyKind::Zalgo,
                "stacked combining marks".to_string(),
            ));
        }
        // #835, UTS #39 5.4: the same stacking mark twice on one base. AFTER the zalgo
        // rule, unlike the enclosing-mark rule above it. #724 could go first because one
        // enclosing mark per base is below every count threshold by construction, so the
        // two rules can never both fire. A repeat has no such bound — four identical
        // acutes are a repeat AND a stack — and putting this first made every zalgo
        // finding report as `duplicate_mark` instead, since heavy stacks repeat. Zalgo is
        // the louder fact about that token; this rule is for the repeats no count reaches.
        if let Some(dup) = duplicate_stacking_mark(tok) {
            return Some(mk(AnomalyKind::DuplicateMark, codepoint(dup)));
        }
        // #702: per WORD, not per token. `IT-специалист` reported `Latin and Cyrillic` —
        // byte-for-byte the finding `раypal` produces — because a hyphen did not end a
        // token. The attack works by putting two scripts inside one word; a hyphen,
        // an underscore, a slash or an exotic space is a boundary, and a boundary is
        // exactly what the attack cannot have.
        for part in word_parts(core) {
            let part_lower = part.to_lowercase();
            if part.chars().count() < 2 || UNITS.contains(&part_lower.as_str()) {
                continue;
            }
            let scripts = detect_scripts(part);
            // Direction conflict (#412): a single token mixing strong-LTR and
            // strong-RTL *letters* (no U+202x override — that is the `Bidi` kind)
            // can visually reorder under the Bidi Algorithm ("BiDi Swap"). This is
            // the precise, reorder-capable subset of mixed-script, and it also
            // catches non-Latin RTL mixes (e.g. Cyrillic+Hebrew) the Latin-anchored
            // `mixed_script` rule below cannot see. Checked first so the more
            // specific kind wins.
            if crate::scripts::has_bidi_letter_conflict(part) {
                return Some(mk(AnomalyKind::BidiMixed, scripts.join(" and ")));
            }
            let has_latin = scripts.contains(&"Latin");
            // Flag Latin mixed with ANY non-Latin, non-CJK script (Cyrillic, Greek,
            // Armenian, Cherokee, Coptic, …). CJK (Han/Kana/Hangul/Bopomofo) is exempt
            // because mixing it with Latin is legitimate in ordinary text.
            let has_other = scripts
                .iter()
                .any(|s| *s != "Latin" && !CJK_SCRIPTS.contains(s));
            if has_latin && has_other {
                return Some(mk(AnomalyKind::MixedScript, scripts.join(" and ")));
            }
        }

        // Compatibility fold (#633): the token changes under NFKC *and* also carries
        // ASCII alphanumerics — so it is spelled half in a compatibility form and half
        // in ASCII (`ａdmin`, `ｅxample.com`, `＜script＞alert(1)`). Nobody writes half a
        // word in fullwidth. `canonicalize` folds this as its very first step, so until
        // now the entire class was neutralized and reported clean, which is the
        // asymmetry #603/#605/#610/#612 each closed for a different character class.
        //
        // TWO GATES, and both are load-bearing.
        //
        // 1. The token must carry an ASCII **letter**. Ordinary Japanese typography
        //    changes under NFKC too — `ＮＨＫ`, `Ｑ＆Ａ`, `１９９５年`, `ＣＤ－ＲＯＭ`,
        //    `全角１２３`, `Ｔシャツ` — and none of them carries one, so none fires.
        //
        //    A letter, not an alphanumeric: the squared CJK units fold to ASCII and so
        //    pass gate 2, and a digit beside them is ordinary — `10㎏` folds to `10kg`,
        //    `5㎞` to `5km`, `3㎡` to `3m2`. 125 code points in U+3000–U+33FF fold to
        //    ASCII, so an alphanumeric gate opens a whole false-positive class that
        //    gate 2 cannot see (review on #652). The disguise case is a *word* spelled
        //    half in a compatibility form, and a word has letters.
        // 2. Some non-ASCII character must fold TO ASCII. This one was added after the
        //    first draft fired on `kΩ µF resistor`, caught by
        //    `mixed_script_spares_cjk_units_and_single_scripts`: U+2126 OHM SIGN folds
        //    to Greek `Ω` and
        //    U+00B5 MICRO SIGN to Greek `μ`, so both changed under NFKC while disguising
        //    nothing. A compatibility form is only a disguise when what it folds to is
        //    the ASCII someone else is comparing against — which is exactly the attack
        //    and exactly not the unit symbol.
        //
        // Measured with both gates: every mixed-form attack shape caught, 0 of 16
        // legitimate samples flagged — the Japanese corpus, the Greek-folding unit
        // symbols, and the squared CJK units.
        //
        // The 3 it does not catch are a token spelled WHOLLY in a compatibility form
        // (`ｐａｙｐａｌ`, `Ｈｅｌｌｏ`, `１２３`), and that is deliberate rather than a
        // gap: by character class those are indistinguishable from `ＮＨＫ`, and nothing
        // available here separates them. A detector that fired on `ＮＨＫ` is one a
        // CJK-facing caller would switch off entirely — which would cost the mixed case
        // as well, so the narrow rule protects the coverage it does have.
        //
        // Cheap test first: the ASCII scan is a byte walk, the NFKC comparison is not.
        // Both live inside the non-ASCII block because ASCII is already NFKC-normalized,
        // so a pure-ASCII token can never fire — pinned by
        // `ascii_is_nfkc_stable_so_the_fast_path_is_safe`, the check #612 needed and
        // did not have.
        // Whitespace is excluded from the trigger (#720). Every exotic `Zs` folds to
        // `U+0020` under NFKC, so once `is_token_boundary` stopped consuming them this
        // branch fired on `Mr.\u{00A0}Smith` and `10\u{00A0}km`. A space folding to a space
        // is not what #633 describes — "spelled half in a compatibility form and half in
        // ASCII", the shape nobody writes on purpose. It is a space.
        //
        // #722: the whole-token exemption is now per BLOCK. It exists to protect `ＮＨＫ`,
        // and was applied to twelve blocks including ones where no `ＮＨＫ` exists — 652
        // Mathematical Alphanumeric code points spell a word that folds to plain ASCII.
        // A token with no ASCII letter still fires when every compatibility character in
        // it comes from a block where a whole-token spelling is not ordinary text.
        // Per WORD, for the reason #702 gives: `IT-специалист` is two words with a
        // boundary between them, and every Cyrillic letter folds to Latin. Judging the
        // whole token would report `Сбербанк-Online` and every IDN URL, which is the
        // over-flagging P16 removed from the mixed-script branch a moment ago.
        //
        // `detail` stays the whole token's NFKC fold (#722 §4), so a caller still sees
        // `paypal` rather than a fragment.
        for part in word_parts(tok) {
            let has_ascii_letter = part.chars().any(|c| c.is_ascii_alphabetic());
            let compat: Vec<char> = part
                .chars()
                .filter(|c| !c.is_ascii() && c.nfkc().all(|f| f.is_ascii()))
                .collect();
            // ALL, not ANY. With `any`, one fullwidth character exempted the whole word:
            // `\u{1D41A}\u{FF41}` mixes a Mathematical Alphanumeric with a fullwidth `a`,
            // folds to `aa`, and reported clean. The exemption reads "this word is
            // ordinary text in a block where a whole-token spelling is ordinary" — a word
            // drawing on two compatibility blocks is not that, whichever blocks they are.
            let spared =
                !has_ascii_letter && compat.iter().copied().all(whole_token_compat_is_ordinary);
            if !compat.is_empty() && !spared {
                return Some(mk(AnomalyKind::CompatFold, tok.nfkc().collect::<String>()));
            }
        }
    }

    if core.chars().count() < 2 {
        return None;
    }

    // Symbols that gate the leet path: digits plus the non-digit letter-substitutes the
    // demangler understands (`@ $ | ! +`). `!`/`+`/`@`/`$`/`|` are interior here — leading
    // or trailing `!` (and the other WRAP chars) were already stripped into `core`.
    // #726: `!` is in `WRAP` *and* in the leet alphabet, and `(`/`)` are the second case —
    // in `WRAP` and forming `()` -> `o`. `core` is trimmed before this branch runs, so a
    // leet word whose first or last character is one of them lost it before the decode and
    // the shortened result missed the lexicon: `1gn0r3` was caught, `!gn0r3` was clean, and
    // `$ystem` — a substitute NOT in `WRAP` — was caught. The two roles are not separable
    // by position, but they are separable by outcome: trim, decode, and on a miss retry
    // with the edges kept. The retry runs second, so the trim keeps doing its real job —
    // `4dm1n!` decodes on the first pass and that trailing `!` is punctuation.
    //
    // Per word, for the same reason as the mixed-script branch: `fr33` and `m0n3y` each
    // decode, and an exotic space between them no longer ends the token (#720), so a
    // whole-token decode would fail on a pair that used to be two tokens. A narrower
    // split than `word_parts` — see `leet_parts`.
    for source in [core, leet_edge_core(tok)] {
        for core in leet_parts(source) {
            let has_sym = core
                .chars()
                .any(|c| c.is_ascii_digit() || matches!(c, '@' | '$' | '|' | '!' | '+'));
            // 4.1: cap the token length BEFORE decoding, so neither the O(n) `leet_demangle`
            // allocation nor the O(n²) `nearest()` path can be driven by an unbounded
            // attacker-supplied token (the decode is never longer than the token itself).
            if has_sym && core.chars().count() <= MAX_LEET_LEN {
                // 7.1: compute the leet decode first so the ordinal/time scan only runs when a
                // decode actually exists.
                if let Some(d) = leet_demangle(core) {
                    if !is_ordinal_or_time(core) {
                        let base = base_ascii(core);
                        // reject a real word with a trailing literal number (Power5 -> power); keep
                        // interior substitutions (ab0ut) and short leet (th3 -> the): trust base at
                        // len>=4
                        let literal = base.chars().count() >= 4
                            && lexicon.contains(base.as_str())
                            && is_word_plus_trailing(core);
                        if base.chars().count() >= 2
                            && !literal
                            && d.chars().count() >= 3
                            && d != base
                        {
                            if lexicon.contains(d.as_str()) {
                                return Some(mk(AnomalyKind::Leet, d));
                            }
                            if d.chars().count() >= NEAR_MISS_MIN_LEN {
                                if let Some(near) = nearest(&d, lexicon) {
                                    return Some(mk(AnomalyKind::Leet, near));
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // #720: the separator set gains the exotic spaces. This branch is the one built for
    // "a real word broken up by separators", and it is the only place in the library that
    // can tell `Ign\u{200A}ore` from `Mr.\u{00A0}Smith` — because it asks the lexicon
    // whether the fragments spell a word. `collapse_whitespace` has no lexicon and folds
    // both to `U+0020`, which is right for display and is why the answer lives here.
    //
    // The token is used whole, NOT `word_parts`: the separators are the evidence.
    if core.chars().any(is_segment_separator) {
        if let Some(word) = seg_word(core, lexicon) {
            return Some(mk(AnomalyKind::Segmentation, word));
        }
        if let Some(word) = space_fragmented_word(core, lexicon) {
            return Some(mk(AnomalyKind::Segmentation, word));
        }
    }

    // #719, #737: the SECOND ASCII-producing step in `canonicalize`. Same two gates as
    // `CompatFold` — an ASCII letter in the word, and a non-ASCII character folding *to*
    // ASCII — so #633's false-positive analysis carries over unchanged and `Привет` (no
    // ASCII letter) stays clean.
    //
    // LAST, because it is the least specific rule that fires without a lexicon. Nearly
    // every within-word joiner folds to ASCII — `U+2E40` to `=`, `U+2010` to `-` — so
    // running it earlier would relabel `c⹀o⹀n⹀f⹀i⹀r⹀m` as a confusable and lose the
    // segmentation finding, which names the reassembled word. When there is no word,
    // `confusable` is still the right answer and still fires.
    if !tok.is_ascii() {
        for part in word_parts(tok) {
            // #815: no ASCII letter is not automatically clean. A token where EVERY
            // character imitates a Latin letter is the finished form of the attack this
            // branch exists to catch, and #633's gate went quiet on exactly that.
            if !part.chars().any(|c| c.is_ascii_alphabetic()) && !is_wholly_confusable_word(part) {
                continue;
            }
            // The same `UNITS` exemption the mixed-script branch takes. `µF` folds to
            // `uF` and `kΩ` keeps its omega, and both are ordinary technical text — the
            // micro sign IS how a microfarad is written. Caught by
            // `unit_symbols_fold_to_greek_and_are_not_a_disguise`, which existed for
            // exactly this and is why the exemption is reused rather than re-derived.
            if UNITS.contains(&part.to_lowercase().as_str()) {
                continue;
            }
            if let Some((source, target)) = folded_confusable(part) {
                return Some(mk(
                    AnomalyKind::Confusable,
                    format!("{source} (U+{:04X}) folds to {target}", source as u32),
                ));
            }
        }
    }

    None
}

/// Whitespace that ends a token — the *structural* kind (#720).
///
/// Deliberately narrower than `char::is_whitespace`, which is what it used to be. Every
/// exotic `Zs` separator is whitespace by that test, so `Ign\u{200A}ore` was not one
/// suspicious token but two ordinary ones, `Ign` and `ore` — neither a word, so nothing
/// fired, and no widening of the carrier table could have changed it because the
/// separator was consumed before classification began. That is the word-fragmentation
/// subtype of arXiv:2508.14070v1 §3, and it measured 0/10 detected.
///
/// The exotic spaces now stay *inside* the token, where `seg_word` can ask the question
/// that actually separates an attack from typography: do the fragments spell a real word?
/// `collapse_whitespace` still folds them to `U+0020` — see the module docs on why
/// deleting them there would be wrong.
///
/// `U+0085 NEL`, `U+2028` and `U+2029` stay boundaries: they are line breaks, not spaces.
#[inline]
fn is_token_boundary(c: char) -> bool {
    c.is_ascii_whitespace() || matches!(c, '\u{000B}' | '\u{0085}' | '\u{2028}' | '\u{2029}')
}

/// Split `s` into *words* for the branches that ask a per-word question (#702, #720).
///
/// A token is not a word. `split_tokens` bounds on structural whitespace, so
/// `IT-специалист` arrives as one token and `detect_scripts` reported
/// `Latin and Cyrillic` — the same kind and the same detail as `раypal`, which is the
/// attack. `раypal` works *because* the two scripts sit inside one word with no boundary
/// to hide behind; `IT-специалист` is two words and the hyphen is the boundary.
///
/// The set is the punctuation that joins words rather than forming them, plus the exotic
/// spaces `is_token_boundary` no longer consumes — `Hello\u{00A0}мир` is two words and must
/// not read as a mixed-script one.
///
/// The apostrophe is deliberately **absent**, though #702 §1 lists it: `leet_demangle`
/// skips apostrophes so contractions decode, and splitting on one turns `d0n't` into
/// `d0n` and `t`, neither of which decodes to anything. None of the six measured false
/// positives uses an apostrophe, so the set stays exactly what the evidence needs.
///
/// Deliberately NOT used by the `segmentation` branch, which needs the separators intact:
/// `v.i.a.g.r.a` is a finding precisely because they are inside one token.
fn word_parts(s: &str) -> impl Iterator<Item = &str> {
    s.split(|c: char| c.is_whitespace() || matches!(c, '-' | '_' | '/' | ':' | '@' | ','))
        .filter(|p| !p.is_empty())
}

/// Word parts for the **leet** branch: the exotic spaces only (#720).
///
/// The joining punctuation `word_parts` splits on is the leet payload here, not a
/// boundary — `@` and `$` and `|` are letter-substitutes the demangler understands, so
/// `p@ss` is one word and splitting it yields `p` and `ss`, neither of which decodes.
/// The apostrophe is skipped by `leet_demangle` for the same reason, so `d0n't` decodes
/// to `dont`.
///
/// What this does need is the exotic spaces, because `is_token_boundary` no longer
/// consumes them: `fr33\u{00A0}m0n3y` used to arrive as two tokens and would otherwise now
/// arrive as one that decodes to nothing.
fn leet_parts(s: &str) -> impl Iterator<Item = &str> {
    s.split(|c: char| c.is_whitespace())
        .filter(|p| !p.is_empty())
}

fn split_tokens(text: &str) -> Vec<(usize, &str)> {
    let mut out = Vec::new();
    let mut start: Option<usize> = None;
    for (i, c) in text.char_indices() {
        if is_token_boundary(c) {
            if let Some(s) = start.take() {
                out.push((s, &text[s..i]));
            }
        } else if start.is_none() {
            start = Some(i);
        }
    }
    if let Some(s) = start {
        out.push((s, &text[s..]));
    }
    out
}

/// Build a lexicon set for [`has_anomalies`] / [`inspect_anomalies`], lowercasing
/// each entry.
///
/// The detector decodes and **lowercases** candidate words before looking them up
/// (`fr33` → `free`, `V.I.A.G.R.A` → `viagra`), so the lexicon must be lowercase too;
/// a title-cased wordlist like `["Free"]` would otherwise silently miss `fr33`. Build
/// the set through this helper (the bindings do) so the lowercasing is automatic.
///
/// Accepts any iterable of string-like items (`String`, `&str`, `&String`,
/// `Cow<str>`, …), so callers holding borrowed data need not pre-allocate owned
/// `String`s just to build the set.
#[must_use]
pub fn lexicon<I, S>(words: I) -> HashSet<String>
where
    I: IntoIterator<Item = S>,
    S: AsRef<str>,
{
    words
        .into_iter()
        .map(|s| s.as_ref().to_lowercase())
        .collect()
}

/// True if any whitespace token carries out-of-place characters that disguise a real word.
///
/// Reports a technical fact and leaves the malicious-or-not judgement to the caller.
/// `lexicon` is a set of common words for the language being protected (used only by the
/// leet and segmentation branches). Entries must be **lowercase** — build it with
/// [`lexicon`] so the lowercasing matches the detector's lowercased lookups.
#[must_use]
pub fn has_anomalies(text: &str, lexicon: &HashSet<String>) -> bool {
    split_tokens(text)
        .into_iter()
        .any(|(start, tok)| classify(tok, start, lexicon).is_some())
}

/// Full analysis: every finding with its span and a plain-language reason. Parallel to
/// [`crate::api::HostnameAnalysis`].
#[must_use]
pub fn inspect_anomalies(text: &str, lexicon: &HashSet<String>) -> AnomalyReport {
    let tokens = split_tokens(text);
    #[cfg(feature = "log")]
    let token_count = tokens.len();
    let mut findings = Vec::new();
    for (start, tok) in tokens {
        if let Some(f) = classify(tok, start, lexicon) {
            findings.push(f);
        }
    }
    let mut kinds: Vec<AnomalyKind> = Vec::new();
    for f in &findings {
        if !kinds.contains(&f.kind) {
            kinds.push(f.kind);
        }
    }
    let reason = findings.first().map(Finding::reason);
    let anomalous = !findings.is_empty();
    // Metadata only — input length, token/finding counts, and the result flag.
    // Never log input text, tokens, or decoded words.
    tl_debug!(
        "inspect_anomalies: in_bytes={} tokens={} findings={} anomalous={}",
        text.len(),
        token_count,
        findings.len(),
        anomalous,
    );
    AnomalyReport {
        anomalous,
        kinds,
        findings,
        reason,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// `is_wholly_confusable_word` must hold on its own terms, not only where it is called.
    ///
    /// Its one caller already checks "no ASCII letter", so nothing observable through
    /// `inspect_anomalies` covers the helper's own behaviour. A private helper that is
    /// only correct because of its caller is one refactor away from being wrong.
    ///
    /// The ASCII case is asserted here too, and holds for a reason worth stating: an
    /// ASCII letter has no confusable row, so the fold test rejects it without a separate
    /// check.
    #[test]
    fn wholly_confusable_word_holds_on_its_own_terms() {
        // An ASCII letter disqualifies it — via the fold test, not a separate guard.
        assert!(!is_wholly_confusable_word(
            "\u{1D18}\u{1D00}ss\u{1D21}\u{1D0F}\u{0280}\u{1D05}"
        ));
        // Every character must fold to an ASCII letter.
        assert!(!is_wholly_confusable_word(
            "\u{1D18}\u{1D00}\u{4E2D}\u{1D05}"
        ));
        // The length floor.
        assert!(!is_wholly_confusable_word("\u{1D00}\u{1D05}\u{1D0D}"));
        // A word in another script is not a disguise, however well it folds.
        assert!(!is_wholly_confusable_word(
            "\u{041C}\u{043E}\u{0441}\u{043A}\u{0432}\u{0430}"
        ));
        // …and the thing it is for.
        assert!(is_wholly_confusable_word(
            "\u{1D18}\u{1D00}\u{A731}\u{A731}\u{1D21}\u{1D0F}\u{0280}\u{1D05}"
        ));
    }

    // ── Compatibility fold (#633) ───────────────────────────────────

    /// The premise of putting the branch inside the non-ASCII block. ASCII is already
    /// in NFKC normal form, so a pure-ASCII token can never fold — which is what makes
    /// skipping the check on the fast path safe. #612's `control` kind was placed the
    /// other way round and had to move; this asserts the premise instead of assuming it.
    #[test]
    fn ascii_is_nfkc_stable_so_the_fast_path_is_safe() {
        use unicode_normalization::UnicodeNormalization;
        for cp in 0u32..0x80 {
            let s = char::from_u32(cp).unwrap().to_string();
            assert!(
                s.nfkc().eq(s.chars()),
                "ASCII U+{cp:04X} is not NFKC-stable"
            );
        }
    }

    #[test]
    fn a_token_half_in_fullwidth_is_flagged() {
        for (tok, folds_to) in [
            ("\u{FF1C}script\u{FF1E}", "<script>"),
            ("\u{FF41}dmin", "admin"),
            ("\u{FF45}xample.com", "example.com"),
        ] {
            let r = inspect_anomalies(tok, &HashSet::new());
            assert_eq!(r.kinds, vec![AnomalyKind::CompatFold], "{tok:?}");
            assert_eq!(r.findings[0].detail, folds_to);
        }
    }

    /// The false-positive gate, and the reason the rule is narrow. Every one of these
    /// changes under NFKC and every one is ordinary Japanese typography; none carries an
    /// ASCII alphanumeric, so none fires.
    #[test]
    fn ordinary_fullwidth_typography_is_not_flagged() {
        for tok in [
            "\u{FF2E}\u{FF28}\u{FF2B}",                         // ＮＨＫ
            "\u{FF31}\u{FF06}\u{FF21}",                         // Ｑ＆Ａ
            "\u{FF11}\u{FF19}\u{FF19}\u{FF15}\u{5E74}",         // １９９５年
            "\u{FF23}\u{FF24}\u{FF0D}\u{FF32}\u{FF2F}\u{FF2D}", // ＣＤ－ＲＯＭ
        ] {
            assert!(
                inspect_anomalies(tok, &HashSet::new()).kinds.is_empty(),
                "{tok:?} was flagged"
            );
        }
    }

    /// MEASURED LIMIT, and a decision rather than a gap: a token spelled WHOLLY in a
    /// compatibility form is indistinguishable by character class from `ＮＨＫ`. A
    /// detector that fired on it would fire on ordinary Japanese too, and a CJK-facing
    /// caller would switch the whole thing off — costing the mixed case as well.
    #[test]
    fn a_token_wholly_in_fullwidth_is_deliberately_not_flagged() {
        for tok in [
            "\u{FF50}\u{FF41}\u{FF59}\u{FF50}\u{FF41}\u{FF4C}", // ｐａｙｐａｌ
            "\u{FF11}\u{FF12}\u{FF13}",                         // １２３
        ] {
            assert!(
                inspect_anomalies(tok, &HashSet::new()).kinds.is_empty(),
                "{tok:?}"
            );
        }
    }

    /// The second gate, and the reason it exists. A first draft required only "changes
    /// under NFKC", which fired on `kΩ µF resistor` — U+2126 OHM SIGN folds to Greek `Ω`
    /// and U+00B5 MICRO SIGN to Greek `μ`. Both change, neither disguises any ASCII, and
    /// the existing `mixed_script` unit test caught it. A compatibility form is only a
    /// disguise when it folds to the ASCII someone else compares against.
    #[test]
    fn unit_symbols_fold_to_greek_and_are_not_a_disguise() {
        for tok in [
            "k\u{2126}",
            "\u{B5}F",
            "\u{B5}s",
            "100\u{2126}",
            // And the squared CJK units, which DO fold to ASCII and so clear gate 2 —
            // gate 1's letter requirement is the only thing keeping them out
            // (review on #652). `10㎏` -> `10kg`, `5㎞` -> `5km`, `3㎡` -> `3m2`.
            "10\u{338F}",
            "5\u{339E}",
            "3\u{33A1}",
            "100\u{339C}",
        ] {
            assert!(
                inspect_anomalies(tok, &HashSet::new()).kinds.is_empty(),
                "{tok:?} was flagged"
            );
        }
    }

    /// The rule is not fullwidth-specific: any compatibility form counts, which is why
    /// the ligature is caught by the same branch.
    #[test]
    fn other_compatibility_forms_count_too() {
        let r = inspect_anomalies("\u{FB01}le", &HashSet::new()); // ﬁle
        assert_eq!(r.kinds, vec![AnomalyKind::CompatFold]);
        assert_eq!(r.findings[0].detail, "file");
    }

    fn lex(words: &[&str]) -> HashSet<String> {
        words.iter().map(|w| (*w).to_string()).collect()
    }

    #[test]
    fn lexicon_lowercases_so_title_cased_wordlists_match() {
        // `lexicon()` folds case, so a title-cased wordlist still matches the
        // detector's lowercased decoded words (regression: `{"Free"}` missed `fr33`).
        let title = lexicon(["Free".to_string(), "Viagra".to_string()]);
        assert!(title.contains("free") && title.contains("viagra"));
        assert!(has_anomalies("get fr33 now", &title)); // leet
        assert!(has_anomalies("v.i.a.g.r.a", &title)); // segmentation
                                                       // a raw (un-folded) set is the caller's responsibility and does NOT match:
        assert!(!has_anomalies("get fr33 now", &lex(&["Free"])));
    }

    #[test]
    fn flags_homoglyph_leet_and_clears_clean() {
        let l = lex(&["free", "viagra"]);
        assert!(has_anomalies("get fr33 now", &l));
        assert!(has_anomalies("payp\u{0430}l", &l)); // Cyrillic a
        assert!(!has_anomalies("the win32 api and mp3 file", &l));
        assert!(!has_anomalies("perfectly clean sentence", &l));
    }

    #[test]
    fn reports_reason_and_span() {
        let l = lex(&["free"]);
        let r = inspect_anomalies("get fr33", &l);
        assert!(r.anomalous);
        assert_eq!(r.kinds, vec![AnomalyKind::Leet]);
        assert_eq!(r.findings[0].detail, "free");
    }

    // ── invisible ───────────────────────────────────────────────────────────

    #[test]
    fn invisible_fires_inside_a_latin_word() {
        let l = lex(&[]);
        assert!(has_anomalies("pay\u{200B}pal", &l)); // zero-width space
        assert!(has_anomalies("he\u{200C}llo", &l)); // ZWNJ between Latin letters
                                                     // a never-legitimate invisible (ZWSP) fires even between accented Latin
                                                     // letters that carry no ASCII letter
        assert!(has_anomalies("\u{00E9}\u{200B}\u{00E0}", &l)); // é ZWSP à
    }

    #[test]
    fn invisible_spares_emoji_and_non_latin_joiners() {
        let l = lex(&[]);
        // emoji ZWJ sequence — no ASCII letter on either side of the joiner
        assert!(!has_anomalies(
            "\u{1F468}\u{200D}\u{1F469}\u{200D}\u{1F467}",
            &l
        ));
        // ZWJ between Arabic letters is legitimate joining, not an anomaly
        assert!(!has_anomalies(
            "\u{0643}\u{062A}\u{200D}\u{0627}\u{0628}",
            &l
        ));
        // soft hyphen is legitimate hyphenation, not flagged
        assert!(!has_anomalies("encyclo\u{00AD}pedia", &l));
    }

    #[test]
    fn invisible_fires_at_word_edges_for_never_legit_codepoints() {
        // 3.3: never-legitimate invisibles (everything except the joiners) need a letter on
        // EITHER side, so trailing/leading placements are caught.
        let l = lex(&[]);
        assert!(has_anomalies("paypal\u{200B}", &l)); // trailing ZWSP
        assert!(has_anomalies("\u{FEFF}paypal", &l)); // leading BOM
        assert!(has_anomalies("paypal\u{2060}", &l)); // trailing word joiner
                                                      // but a joiner (ZWJ/ZWNJ) at an edge still needs letters on both sides:
        assert!(!has_anomalies("paypal\u{200D}", &l)); // trailing ZWJ alone — not flagged
        assert!(!has_anomalies("\u{200C}paypal", &l)); // leading ZWNJ alone — not flagged
    }

    // ── bidi ────────────────────────────────────────────────────────────────

    #[test]
    fn bidi_fires_on_override_and_trojan_isolate() {
        let l = lex(&[]);
        assert!(has_anomalies("user\u{202E}txt.exe", &l)); // RLO override
        assert!(has_anomalies("ab\u{2066}cd", &l)); // isolate inside a majority-Latin token
    }

    #[test]
    fn bidi_fires_on_isolate_in_letterless_token() {
        // 2.3: an isolate in a token with no letters at all (digits/punct only) is flagged;
        // previously `is_majority_latin` was false for zero-letter tokens so this slipped.
        let l = lex(&[]);
        assert!(has_anomalies("12\u{2066}34", &l));
    }

    #[test]
    fn bidi_spares_marks_and_embeddings() {
        let l = lex(&[]);
        // bare directional marks (LRM/RLM) are common and benign
        assert!(!has_anomalies("hello\u{200F}world", &l));
        // an LRE..PDF embedding around RTL text (no Latin majority) is benign
        assert!(!has_anomalies(
            "\u{202B}\u{0639}\u{0631}\u{0628}\u{064A}\u{202C}",
            &l
        ));
        // #643: the Latin-majority half of that sentence was never implemented, so the
        // same embedding around SOURCE CODE was spared too — the Trojan Source
        // construction with the older operators in place of the isolates.
        assert!(has_anomalies("\u{202B}if(isAdmin){grant();}\u{202C}", &l));
    }

    // ── zalgo ───────────────────────────────────────────────────────────────

    #[test]
    fn zalgo_fires_but_spares_normal_accents() {
        let l = lex(&[]);
        assert!(has_anomalies("z\u{0301}\u{0301}\u{0301}\u{0301}algo", &l));
        assert!(!has_anomalies("café résumé naïve", &l));
    }

    // ── mixed_script ────────────────────────────────────────────────────────

    #[test]
    fn mixed_script_fires_on_latin_plus_cyrillic_or_greek() {
        let l = lex(&[]);
        assert!(has_anomalies("payp\u{0430}l", &l)); // Cyrillic а
        assert!(has_anomalies("Vi\u{03B1}gra", &l)); // Greek α among Latin
    }

    #[test]
    fn mixed_script_fires_on_latin_plus_any_non_cjk_script() {
        // 3.1: Latin mixed with ANY non-Latin, non-CJK script is flagged, not just Cyr/Greek.
        let l = lex(&[]);
        assert!(has_anomalies("payp\u{0561}l", &l)); // Armenian а (U+0561) among Latin
        assert!(has_anomalies("Chero\u{13A0}kee", &l)); // Cherokee letter among Latin
        assert!(has_anomalies("Co\u{2C81}pt", &l)); // Coptic letter among Latin
    }

    #[test]
    fn mixed_script_spares_cjk_units_and_single_scripts() {
        let l = lex(&[]);
        // CJK mixed WITH Latin in the SAME token stays exempt (annotations, product names):
        assert!(!has_anomalies("漢字api", &l)); // Han + Latin in one token
        assert!(!has_anomalies("カナkana", &l)); // Katakana + Latin
        assert!(!has_anomalies("한글text", &l)); // Hangul + Latin
        assert!(!has_anomalies("漢字 mixed with text", &l)); // Han + Latin (separate tokens)
        assert!(!has_anomalies("kΩ µF resistor", &l)); // legitimate unit symbols
        assert!(!has_anomalies("Москва Россия", &l)); // pure Cyrillic
    }

    // ── bidi_mixed (#412) ─────────────────────────────────────────────────────

    #[test]
    fn bidi_mixed_fires_on_ltr_plus_rtl_token() {
        let l = lex(&[]);
        // Latin + Hebrew in one token reorders under the Bidi Algorithm. Reported
        // as the precise `bidi_mixed` kind, not the generic `mixed_script`.
        let r = inspect_anomalies("varonis\u{05D5}", &l);
        assert!(r.anomalous);
        assert_eq!(r.kinds, vec![AnomalyKind::BidiMixed]);
    }

    #[test]
    fn bidi_mixed_catches_non_latin_rtl_mix_missed_by_mixed_script() {
        let l = lex(&[]);
        // Cyrillic + Hebrew: no Latin, so the Latin-anchored mixed_script rule
        // cannot see it — but it is still a direction conflict.
        let r = inspect_anomalies("\u{0430}\u{05D5}\u{05DD}", &l);
        assert!(r.anomalous);
        assert_eq!(r.kinds, vec![AnomalyKind::BidiMixed]);
    }

    #[test]
    fn bidi_mixed_does_not_fire_on_same_direction_mix() {
        let l = lex(&[]);
        // Latin + Cyrillic are both LTR — no direction conflict, still mixed_script.
        let r = inspect_anomalies("payp\u{0430}l", &l);
        assert_eq!(r.kinds, vec![AnomalyKind::MixedScript]);
        // A single-direction RTL token is clean.
        assert!(!has_anomalies("\u{05D0}\u{05EA}\u{05E8}", &l)); // all Hebrew
    }

    // ── leet ────────────────────────────────────────────────────────────────

    #[test]
    fn leet_decodes_substitutions_to_words() {
        let l = lex(&["free", "about", "the", "dont", "pass"]);
        assert!(has_anomalies("get fr33 stuff", &l));
        assert!(has_anomalies("talk ab0ut it", &l)); // interior substitution
        assert!(has_anomalies("th3 answer", &l)); // short decode
        assert!(has_anomalies("d0n't", &l)); // apostrophe skipped
        assert!(has_anomalies("p@ss", &l)); // @ -> a, $-style symbols
    }

    #[test]
    fn leet_decodes_extended_substitutions() {
        // 3.2: the unambiguous additions !->i, +->t, 6->g, 8->b, 2->z extend the catch set.
        let l = lex(&["friend", "table", "ghost", "abuse"]);
        assert!(has_anomalies("fr!end", &l)); // ! -> i
        assert!(has_anomalies("+able", &l)); // + -> t
        assert!(has_anomalies("6host", &l)); // 6 -> g
        assert!(has_anomalies("a8use", &l)); // 8 -> b
                                             // genuinely-unmapped symbols still abort the decode (no wildcard skipping):
        assert!(!has_anomalies("fr%end", &l)); // % maps to nothing
        assert!(!has_anomalies("ta#le", &l)); // # maps to nothing
    }

    #[test]
    fn leet_spares_literal_numbers() {
        let l = lex(&["power", "covid"]);
        assert!(!has_anomalies("the win32 api and mp3 file", &l));
        assert!(!has_anomalies("Power5 chip", &l)); // word + trailing literal number
        assert!(!has_anomalies("covid19 update", &l));
        assert!(!has_anomalies("on the 21st at 3pm", &l)); // ordinal + time
    }

    #[test]
    fn leet_skips_overlong_tokens() {
        // 4.1: a demangled token longer than MAX_LEET_LEN skips the O(n^2) nearest() path.
        let l = lex(&["free"]);
        let long = "3".repeat(100); // decodes to 100x 'e'
        assert!(!has_anomalies(&long, &l));
        // a normal-length leet token is unaffected:
        assert!(has_anomalies("fr33", &l));
    }

    // ── segmentation ────────────────────────────────────────────────────────

    #[test]
    fn segmentation_fires_on_dense_single_letter_splits() {
        let l = lex(&["viagra"]);
        assert!(has_anomalies("buy v.i.a.g.r.a now", &l));
        assert!(has_anomalies("v_i_a_g_r_a", &l));
    }

    #[test]
    fn segmentation_collapses_separator_padding() {
        // 2.2: runs of consecutive separators collapse to one before counting density, so
        // padding cannot inflate the ratio. The padded single-letter split is still caught
        // (collapse does not break genuine detection), and the multi-letter-part rejection
        // is untouched, so the collapse never manufactures a false positive.
        let l = lex(&["viagra"]);
        assert!(has_anomalies("v-.-i-.-a-.-g-.-r-.-a", &l)); // padded, still flagged
                                                             // padding around multi-letter parts is still spared (not single-letter splitting):
        assert!(!has_anomalies("via---gra", &l));
    }

    // ── reports / parity ──────────────────────────────────────────────────────

    #[test]
    fn clean_text_reports_nothing() {
        let l = lex(&["free", "viagra"]);
        let r = inspect_anomalies("a perfectly ordinary sentence", &l);
        assert!(!r.anomalous);
        assert!(r.kinds.is_empty());
        assert!(r.findings.is_empty());
        assert!(r.reason.is_none());
    }

    #[test]
    fn inspect_records_span_kind_and_reason() {
        let l = lex(&["paypal"]);
        let r = inspect_anomalies("log in to payp\u{0430}l today", &l);
        assert_eq!(r.kinds, vec![AnomalyKind::MixedScript]);
        let f = &r.findings[0];
        assert_eq!(f.kind, AnomalyKind::MixedScript);
        assert_eq!(&f.token, "payp\u{0430}l");
        // the span points at the offending token in the original text
        assert_eq!(&"log in to payp\u{0430}l today"[f.start..f.end], f.token);
        assert!(r.reason.unwrap().contains("Latin"));
    }

    #[test]
    fn has_anomalies_matches_inspect() {
        let l = lex(&["free", "viagra", "paypal"]);
        for s in [
            "get fr33",
            "payp\u{0430}l",
            "v.i.a.g.r.a",
            "perfectly clean text",
            "user\u{202E}txt",
        ] {
            assert_eq!(has_anomalies(s, &l), inspect_anomalies(s, &l).anomalous);
        }
    }
}
