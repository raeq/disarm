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

/// Zero-width / invisible formatting codepoints (soft hyphen U+00AD is excluded: it is
/// legitimate hyphenation).
const INVISIBLE: &[char] = &[
    '\u{200B}', '\u{200C}', '\u{200D}', '\u{2060}', '\u{2061}', '\u{2062}', '\u{2063}', '\u{FEFF}',
];
/// Bidi overrides (LRO/RLO): never legitimate in normal text.
const BIDI_OVERRIDE: &[char] = &['\u{202D}', '\u{202E}'];
/// Bidi isolates (LRI/RLI/FSI/PDI). Plain embeddings (LRE/RLE/PDF) and bare directional
/// marks are common in benign RTL and social text, so they are not flagged. The overrides
/// (U+202D/U+202E) are handled first by [`BIDI_OVERRIDE`], so they are not re-listed here.
const BIDI_ISOLATES: &[char] = &['\u{2066}', '\u{2067}', '\u{2068}', '\u{2069}'];
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
    /// A letter-for-symbol substitution decoding to a common word (`fr33` -> `free`).
    Leet,
    /// Dense separators splitting single letters into a real word (`v.i.a.g.r.a`).
    Segmentation,
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
            AnomalyKind::Leet => "leet",
            AnomalyKind::Segmentation => "segmentation",
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
            AnomalyKind::Leet => {
                format!("{:?} decodes to the word {:?}", self.token, self.detail)
            }
            AnomalyKind::Segmentation => {
                format!("{:?} splits the word {:?}", self.token, self.detail)
            }
        }
    }
}

/// Structured result, parallel to [`crate::hostname::HostnameAnalysis`].
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

    // ASCII fast-path: the invisible / bidi / zalgo / mixed-script branches can only fire
    // above U+007F, so a pure-ASCII token skips every script and zalgo call.
    if !tok.is_ascii() {
        let chars: Vec<char> = tok.chars().collect();
        for (i, &c) in chars.iter().enumerate() {
            if !INVISIBLE.contains(&c) {
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
        if let Some(&c) = chars.iter().find(|c| BIDI_OVERRIDE.contains(c)) {
            return Some(mk(AnomalyKind::Bidi, codepoint(c)));
        }
        // Spare isolates only in tokens that are majority non-Latin-script (legit RTL):
        // flag an isolate when the token has any ASCII-Latin letter (majority-Latin) OR
        // has no letters at all (digits/punct only, e.g. `12<isolate>34`).
        if is_majority_latin(tok) || has_no_letters(tok) {
            if let Some(&c) = chars.iter().find(|c| BIDI_ISOLATES.contains(c)) {
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

/// True if any whitespace token carries out-of-place characters that disguise a real word.
///
/// Reports a technical fact and leaves the malicious-or-not judgement to the caller.
/// `lexicon` is a set of common words for the language being protected (used only by the
/// leet and segmentation branches).
#[must_use]
pub fn has_anomalies(text: &str, lexicon: &HashSet<String>) -> bool {
    split_tokens(text)
        .into_iter()
        .any(|(start, tok)| classify(tok, start, lexicon).is_some())
}

/// Full analysis: every finding with its span and a plain-language reason. Parallel to
/// [`crate::hostname::HostnameAnalysis`].
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

    fn lex(words: &[&str]) -> HashSet<String> {
        words.iter().map(|w| (*w).to_string()).collect()
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
