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

/// Zero-width / invisible formatting codepoints (soft hyphen U+00AD is excluded: it is
/// legitimate hyphenation).
const INVISIBLE: &[char] = &[
    '\u{200B}', '\u{200C}', '\u{200D}', '\u{2060}', '\u{2061}', '\u{2062}', '\u{2063}', '\u{FEFF}',
];
/// Bidi overrides (LRO/RLO): never legitimate in normal text.
const BIDI_OVERRIDE: &[char] = &['\u{202D}', '\u{202E}'];
/// Bidi overrides + isolates. Plain embeddings (LRE/RLE/PDF) and bare directional marks
/// are common in benign RTL and social text, so they are not flagged.
const BIDI_FMT: &[char] = &[
    '\u{202D}', '\u{202E}', '\u{2066}', '\u{2067}', '\u{2068}', '\u{2069}',
];
/// Wrapping punctuation trimmed from token edges (NOT the leet symbols @ $ |).
const WRAP: &[char] = &[
    '"', '.', ',', ';', ':', '?', '!', '(', ')', '[', ']', '{', '}', '<', '>', '\u{AB}', '\u{BB}',
    '\u{201C}', '\u{201D}', '\u{2018}', '\u{2019}', '`', '\u{2014}', '\u{2026}', '\'', ' ', '\t',
];
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
        '1' => Some('i'),
        '3' => Some('e'),
        '4' | '@' => Some('a'),
        '5' | '$' => Some('s'),
        '7' => Some('t'),
        '9' => Some('g'),
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
    let letters: Vec<char> = tok.chars().filter(|c| c.is_alphabetic()).collect();
    !letters.is_empty() && letters.iter().filter(|c| c.is_ascii()).count() * 2 >= letters.len()
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
    let seps = core
        .chars()
        .filter(|c| matches!(*c, '.' | '_' | '-'))
        .count();
    let letters: Vec<char> = core.chars().filter(|c| c.is_alphabetic()).collect();
    // dense: seps >= max(2, 0.6*(letters-1)); integer form is 5*seps >= 3*(letters-1)
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
            // letters on both sides. Every other invisible (ZWSP, word joiner,
            // BOM, …) is never legitimate inside a word, so any letter neighbour
            // — including accented Latin — is enough.
            let joiner = c == '\u{200C}' || c == '\u{200D}';
            let neighbour = |slice: &[char]| {
                if joiner {
                    slice.iter().any(char::is_ascii_alphabetic)
                } else {
                    slice.iter().copied().any(char::is_alphabetic)
                }
            };
            if neighbour(&chars[..i]) && neighbour(&chars[i + 1..]) {
                return Some(mk(AnomalyKind::Invisible, codepoint(c)));
            }
        }
        if let Some(c) = tok.chars().find(|c| BIDI_OVERRIDE.contains(c)) {
            return Some(mk(AnomalyKind::Bidi, codepoint(c)));
        }
        if is_majority_latin(tok) {
            if let Some(c) = tok.chars().find(|c| BIDI_FMT.contains(c)) {
                return Some(mk(AnomalyKind::Bidi, codepoint(c)));
            }
        }
        if is_zalgo(tok, ZALGO_THRESHOLD) {
            return Some(mk(
                AnomalyKind::Zalgo,
                "stacked combining marks".to_string(),
            ));
        }
        let core = tok.trim_matches(|c: char| WRAP.contains(&c));
        let core_lower = core.to_lowercase();
        if core.chars().count() >= 2 && !UNITS.contains(&core_lower.as_str()) {
            let scripts = detect_scripts(core);
            let has_latin = scripts.contains(&"Latin");
            let has_cyr_grk = scripts.iter().any(|s| *s == "Cyrillic" || *s == "Greek");
            if has_latin && has_cyr_grk {
                return Some(mk(AnomalyKind::MixedScript, scripts.join(" and ")));
            }
        }
    }

    let core = tok.trim_matches(|c: char| WRAP.contains(&c));
    if core.chars().count() < 2 {
        return None;
    }

    let has_sym = core
        .chars()
        .any(|c| c.is_ascii_digit() || matches!(c, '@' | '$' | '|'));
    if has_sym && !is_ordinal_or_time(core) {
        let base = base_ascii(core);
        if let Some(d) = leet_demangle(core) {
            // reject a real word with a trailing literal number (Power5 -> power); keep
            // interior substitutions (ab0ut) and short leet (th3 -> the): trust base at len>=4
            let literal =
                base.len() >= 4 && lexicon.contains(base.as_str()) && is_word_plus_trailing(core);
            if base.len() >= 2 && !literal && d.chars().count() >= 3 && d != base {
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
    let mut findings = Vec::new();
    for (start, tok) in split_tokens(text) {
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
    AnomalyReport {
        anomalous: !findings.is_empty(),
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

    // ── bidi ────────────────────────────────────────────────────────────────

    #[test]
    fn bidi_fires_on_override_and_trojan_isolate() {
        let l = lex(&[]);
        assert!(has_anomalies("user\u{202E}txt.exe", &l)); // RLO override
        assert!(has_anomalies("ab\u{2066}cd", &l)); // isolate inside a majority-Latin token
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
    fn mixed_script_spares_cjk_units_and_single_scripts() {
        let l = lex(&[]);
        assert!(!has_anomalies("漢字 mixed with text", &l)); // Han + Latin, not Cyr/Greek
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
    fn leet_spares_literal_numbers() {
        let l = lex(&["power", "covid"]);
        assert!(!has_anomalies("the win32 api and mp3 file", &l));
        assert!(!has_anomalies("Power5 chip", &l)); // word + trailing literal number
        assert!(!has_anomalies("covid19 update", &l));
        assert!(!has_anomalies("on the 21st at 3pm", &l)); // ordinal + time
    }

    // ── segmentation ────────────────────────────────────────────────────────

    #[test]
    fn segmentation_fires_on_dense_single_letter_splits() {
        let l = lex(&["viagra"]);
        assert!(has_anomalies("buy v.i.a.g.r.a now", &l));
        assert!(has_anomalies("v_i_a_g_r_a", &l));
    }

    #[test]
    fn segmentation_spares_hyphenated_words() {
        let l = lex(&["viagra"]);
        assert!(!has_anomalies("a 6-foot-6 player", &l)); // multi-letter parts
        assert!(!has_anomalies("send an e-mail today", &l)); // a single separator
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
