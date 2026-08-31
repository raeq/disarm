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
    crate::invisibles::is_zero_width(c) || crate::invisibles::is_invisible_filler(c)
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
const RUN_THRESHOLD_TAG: usize = 1;
const RUN_THRESHOLD_VARIATION_SELECTOR: usize = 2;
const RUN_THRESHOLD_ZERO_WIDTH: usize = 8;

/// The carrier classes the run rule counts, each with its own floor.
#[derive(Clone, Copy, PartialEq, Eq)]
enum Carrier {
    Tag,
    VariationSelector,
    ZeroWidth,
}

impl Carrier {
    fn of(c: char) -> Option<Self> {
        if crate::invisibles::is_tag(c) {
            Some(Self::Tag)
        } else if crate::invisibles::is_variation_selector(c) {
            Some(Self::VariationSelector)
        } else if is_invisible_in_word(c) || c == SOFT_HYPHEN || c == CGJ {
            Some(Self::ZeroWidth)
        } else {
            None
        }
    }

    fn threshold(self) -> usize {
        match self {
            Self::Tag => RUN_THRESHOLD_TAG,
            Self::VariationSelector => RUN_THRESHOLD_VARIATION_SELECTOR,
            Self::ZeroWidth => RUN_THRESHOLD_ZERO_WIDTH,
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
/// Wrapping punctuation trimmed from token edges (NOT the leet symbols @ $ |).
const WRAP: &[char] = &[
    '"', '.', ',', ';', ':', '?', '!', '(', ')', '[', ']', '{', '}', '<', '>', '\u{AB}', '\u{BB}',
    '\u{201C}', '\u{201D}', '\u{2018}', '\u{2019}', '`', '\u{2014}', '\u{2026}', '\'', ' ', '\t',
];
/// CJK script names: legitimately mixed with Latin in ordinary text (annotations,
/// product names, mixed-language prose), so they are exempt from the mixed-script branch.
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

/// Dense single-letter segmentation (`v.i.a.g.r.a`), not a lone hyphen or `6-foot-6`.
fn seg_word(core: &str, lexicon: &HashSet<String>) -> Option<String> {
    // Collapse runs of consecutive separators before counting, so padding (`v-.-i-.-a...`)
    // cannot inflate the separator count to game the density ratio: each run counts once.
    let mut seps = 0usize;
    let mut prev_sep = false;
    for c in core.chars() {
        let is_sep = matches!(c, '.' | '_' | '-');
        if is_sep && !prev_sep {
            seps += 1;
        }
        prev_sep = is_sep;
    }
    let letters: Vec<char> = core.chars().filter(|c| c.is_alphabetic()).collect();
    // Dense single-letter splitting: require seps >= 2 AND 5*seps >= 3*(letters-1).
    if seps < 2 || 5 * seps < 3 * letters.len().saturating_sub(1) {
        return None;
    }
    for part in core.split(['.', '_', '-']) {
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
        // #700 §2: a run fires on its own, with no letter beside it. Checked after the
        // neighbour rule so a single carrier inside a word still reports as itself.
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
        }
        if is_zalgo(tok, ZALGO_THRESHOLD) {
            return Some(mk(
                AnomalyKind::Zalgo,
                "stacked combining marks".to_string(),
            ));
        }
        let core_lower = core.to_lowercase();
        if core.chars().count() >= 2 && !UNITS.contains(&core_lower.as_str()) {
            let scripts = detect_scripts(core);
            // Direction conflict (#412): a single token mixing strong-LTR and
            // strong-RTL *letters* (no U+202x override — that is the `Bidi` kind)
            // can visually reorder under the Bidi Algorithm ("BiDi Swap"). This is
            // the precise, reorder-capable subset of mixed-script, and it also
            // catches non-Latin RTL mixes (e.g. Cyrillic+Hebrew) the Latin-anchored
            // `mixed_script` rule below cannot see. Checked first so the more
            // specific kind wins.
            if crate::scripts::has_bidi_letter_conflict(core) {
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
        if tok.chars().any(|c| c.is_ascii_alphabetic())
            && tok
                .chars()
                .any(|c| !c.is_ascii() && c.nfkc().all(|f| f.is_ascii()))
        {
            return Some(mk(AnomalyKind::CompatFold, tok.nfkc().collect::<String>()));
        }
    }

    if core.chars().count() < 2 {
        return None;
    }

    // Symbols that gate the leet path: digits plus the non-digit letter-substitutes the
    // demangler understands (`@ $ | ! +`). `!`/`+`/`@`/`$`/`|` are interior here — leading
    // or trailing `!` (and the other WRAP chars) were already stripped into `core`.
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
                if base.chars().count() >= 2 && !literal && d.chars().count() >= 3 && d != base {
                    if lexicon.contains(d.as_str()) {
                        return Some(mk(AnomalyKind::Leet, d));
                    }
                    if d.chars().count() >= 6 {
                        if let Some(near) = nearest(&d, lexicon) {
                            return Some(mk(AnomalyKind::Leet, near));
                        }
                    }
                }
            }
        }
    }

    if core.chars().any(|c| matches!(c, '.' | '_' | '-')) {
        if let Some(word) = seg_word(core, lexicon) {
            return Some(mk(AnomalyKind::Segmentation, word));
        }
    }

    None
}

fn split_tokens(text: &str) -> Vec<(usize, &str)> {
    let mut out = Vec::new();
    let mut start: Option<usize> = None;
    for (i, c) in text.char_indices() {
        if c.is_whitespace() {
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
