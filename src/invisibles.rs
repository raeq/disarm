//! Layer 1 (pure-Rust core): stripping of invisible and non-interchange code
//! point classes that survive NFKC and the existing zero-width/bidi passes
//! (#413). No pyo3.
//!
//! These are the "ASCII smuggling" surface — Unicode Tags and variation
//! selectors weaponized as covert channels into LLMs (2024–25) — plus the
//! adjacent non-interchange classes (Combining Grapheme Joiner, noncharacters,
//! Private Use Area). The crates.io surface is
//! `crate::api::{strip_tags, strip_variation_selectors, strip_noncharacters, strip_pua}`.
//!
//! None of this is a blanket delete: a well-formed emoji **subdivision flag**
//! (`U+1F3F4` + tag letters + `U+E007F`, e.g. the Scotland flag) is preserved,
//! and a rendering-context policy keeps the emoji/text presentation selectors
//! `U+FE0E`/`U+FE0F` after a base character.

/// Per-preset policy for [`strip_invisible_classes`].
#[derive(Clone, Copy)]
pub(crate) struct StripPolicy {
    /// Strip Private Use Area code points. Comparison presets do; the rendering
    /// preset (`display_clean`) preserves them (private agreement / icon fonts).
    pub strip_pua: bool,
    /// Keep `U+FE0E`/`U+FE0F` (text/emoji presentation selectors) when they
    /// follow a base character — a rendering-context carve-out. Comparison
    /// presets strip every variation selector.
    pub keep_presentation_vs: bool,
}

/// Unicode Tags block (`U+E0000`–`U+E007F`) — the "ASCII smuggling" channel.
#[inline]
pub(crate) fn is_tag(ch: char) -> bool {
    matches!(ch, '\u{E0000}'..='\u{E007F}')
}

/// Tag *letters* `U+E0061`–`U+E007A` — the payload of an emoji tag sequence.
#[inline]
fn is_tag_letter(ch: char) -> bool {
    matches!(ch, '\u{E0061}'..='\u{E007A}')
}

/// Variation selectors: VS1–VS16 (`U+FE00`–`U+FE0F`) and the Variation
/// Selectors Supplement VS17–VS256 (`U+E0100`–`U+E01EF`).
#[inline]
pub(crate) fn is_variation_selector(ch: char) -> bool {
    matches!(ch, '\u{FE00}'..='\u{FE0F}' | '\u{E0100}'..='\u{E01EF}')
}

/// Unicode noncharacters: `U+FDD0`–`U+FDEF` and the last two code points of
/// every plane (`U+FFFE`/`U+FFFF`, `U+1FFFE`/`U+1FFFF`, … `U+10FFFE`/`U+10FFFF`).
/// Permanently reserved, invalid for open interchange (Core Spec §23.7).
#[inline]
pub(crate) fn is_noncharacter(ch: char) -> bool {
    let cp = ch as u32;
    matches!(cp, 0xFDD0..=0xFDEF) || (cp & 0xFFFF) >= 0xFFFE
}

/// Private Use Area: BMP (`U+E000`–`U+F8FF`), plane 15 (`U+F0000`–`U+FFFFD`),
/// plane 16 (`U+100000`–`U+10FFFD`). Renders as arbitrary, font-defined glyphs.
#[inline]
pub(crate) fn is_pua(ch: char) -> bool {
    matches!(ch, '\u{E000}'..='\u{F8FF}' | '\u{F0000}'..='\u{FFFFD}' | '\u{100000}'..='\u{10FFFD}')
}

/// Combining Grapheme Joiner — invisible; blocks normalization/collation and so
/// splits a confusable/denylisted run while staying unseen.
const CGJ: char = '\u{034F}';

/// Emoji flag base (`U+1F3F4` WAVING BLACK FLAG) and tag terminator
/// (`U+E007F` CANCEL TAG).
const FLAG_BASE: char = '\u{1F3F4}';
const CANCEL_TAG: char = '\u{E007F}';

/// Called with `chars` positioned just after a [`FLAG_BASE`]. If a well-formed
/// emoji subdivision flag tail follows — one or more tag letters terminated by a
/// single [`CANCEL_TAG`] — consume it and return it (letters + terminator) so the
/// caller can re-emit the whole flag. Otherwise consume only the tag letters
/// (which are stray smuggling payload, dropped) and return `None`, leaving the
/// non-tag character that ended the run in the iterator. Streams over the input
/// with at most a small buffer for the tail — no `Vec<char>` of the whole string.
/// The complete set of RGI emoji subdivision-flag payloads — the ASCII the tag
/// letters decode to (England / Scotland / Wales). These are the *only*
/// well-formed `U+1F3F4` + tag-letters + `U+E007F` sequences; any other tail is
/// the Tags "ASCII smuggling" channel wearing a flag base, so it is stripped
/// (review D-6). Bounding to the region-subtag *shape* alone would still pass a
/// ≤6-letter lowercase payload; matching the exact allowlist closes the channel.
const VALID_SUBDIVISION_FLAGS: [&str; 3] = ["gbeng", "gbsct", "gbwls"];

fn consume_flag_tail(chars: &mut std::iter::Peekable<std::str::Chars<'_>>) -> Option<String> {
    let mut tail = String::new();
    let mut decoded = String::new();
    while let Some(&c) = chars.peek() {
        if is_tag_letter(c) {
            tail.push(c);
            // Tag letters U+E0061..=U+E007A decode to ASCII a..z.
            if let Some(ascii) = char::from_u32(c as u32 - 0xE0000) {
                decoded.push(ascii);
            }
            chars.next();
        } else {
            break;
        }
    }
    if chars.peek() == Some(&CANCEL_TAG) && VALID_SUBDIVISION_FLAGS.contains(&decoded.as_str()) {
        tail.push(CANCEL_TAG);
        chars.next();
        Some(tail)
    } else {
        None
    }
}

/// A character that a presentation selector may legitimately follow in the
/// rendering carve-out: a base that survives **every** downstream strip
/// `strip_format` runs after this one (control, zero-width, and the
/// whitespace/blank-render fold). Keeping a VS after a base that a later stage
/// removes orphans the selector, so a second pass strips it and the preset is
/// not idempotent (post-0.11 review D-2). Reject those bases here.
#[inline]
fn is_presentation_base(ch: char) -> bool {
    !ch.is_whitespace()
        && !ch.is_control()
        && !crate::whitespace::is_blank_render(ch)
        && !crate::whitespace::is_zero_width(ch)
}

/// Public helper: strip the Unicode Tags block, **preserving** well-formed emoji
/// subdivision flag sequences (`U+1F3F4` … `U+E007F`).
pub(crate) fn strip_tags(text: &str) -> String {
    // Fast path: every tag-block character and the flag base is non-ASCII.
    if text.is_ascii() {
        return text.to_string();
    }
    let mut out = String::with_capacity(text.len());
    let mut chars = text.chars().peekable();
    while let Some(ch) = chars.next() {
        if ch == FLAG_BASE {
            out.push(FLAG_BASE);
            if let Some(tail) = consume_flag_tail(&mut chars) {
                out.push_str(&tail); // a valid flag: re-emit its tag sequence
            }
            continue;
        }
        if !is_tag(ch) {
            out.push(ch);
        }
    }
    out
}

/// Public helper: strip every variation selector (VS1–VS256).
pub(crate) fn strip_variation_selectors(text: &str) -> String {
    text.chars()
        .filter(|&c| !is_variation_selector(c))
        .collect()
}

/// Public helper: strip every Unicode noncharacter.
pub(crate) fn strip_noncharacters(text: &str) -> String {
    text.chars().filter(|&c| !is_noncharacter(c)).collect()
}

/// Public helper: strip every Private Use Area code point.
pub(crate) fn strip_pua(text: &str) -> String {
    text.chars().filter(|&c| !is_pua(c)).collect()
}

/// Strip the #413 invisible / non-interchange classes in a single pass,
/// according to `policy`. Always strips: stray Tags-block characters (keeping
/// valid flag sequences), the Combining Grapheme Joiner, and noncharacters.
/// Variation selectors and Private Use Area are governed by `policy`.
// Returning form is now used only by the `_legacy` preset oracles and this
// module's unit tests; the presets call `strip_invisible_classes_into`. The
// extension-module clippy build has no test target, so without this it reads as
// dead. Reassessed in the #453 cleanup task.
#[allow(dead_code)]
pub(crate) fn strip_invisible_classes(text: &str, policy: StripPolicy) -> String {
    let mut out = String::new();
    strip_invisible_classes_into(text, policy, &mut out);
    out
}

/// `strip_invisible_classes`, writing into a caller-owned buffer (ping-pong form).
/// Clears `out` first, like every other `*_into` leaf.
pub(crate) fn strip_invisible_classes_into(text: &str, policy: StripPolicy, out: &mut String) {
    out.clear();
    // Fast path: every class handled here (tags, CGJ, noncharacters, PUA,
    // variation selectors, the flag base) is non-ASCII, so ASCII passes through.
    if text.is_ascii() {
        out.push_str(text);
        return;
    }
    out.reserve(text.len());
    let mut chars = text.chars().peekable();
    while let Some(ch) = chars.next() {
        // Emoji subdivision flag: preserve the whole well-formed sequence.
        if ch == FLAG_BASE {
            out.push(FLAG_BASE);
            if let Some(tail) = consume_flag_tail(&mut chars) {
                out.push_str(&tail);
            }
            continue;
        }
        if is_tag(ch) || ch == CGJ || is_noncharacter(ch) {
            continue;
        }
        if policy.strip_pua && is_pua(ch) {
            continue;
        }
        if is_variation_selector(ch) {
            // Rendering carve-out: keep VS15/VS16 directly after a base.
            let keep = policy.keep_presentation_vs
                && matches!(ch, '\u{FE0E}' | '\u{FE0F}')
                && out.chars().next_back().is_some_and(is_presentation_base);
            if keep {
                out.push(ch);
            }
            continue;
        }
        out.push(ch);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn comparison() -> StripPolicy {
        StripPolicy {
            strip_pua: true,
            keep_presentation_vs: false,
        }
    }
    fn rendering() -> StripPolicy {
        StripPolicy {
            strip_pua: false,
            keep_presentation_vs: true,
        }
    }

    #[test]
    fn classifiers_cover_the_ranges() {
        assert!(is_tag('\u{E0001}') && is_tag('\u{E0050}') && is_tag('\u{E007F}'));
        assert!(!is_tag('\u{1F3F4}')); // the flag base is not a tag char
        assert!(is_variation_selector('\u{FE00}') && is_variation_selector('\u{FE0F}'));
        assert!(is_variation_selector('\u{E0100}') && is_variation_selector('\u{E01EF}'));
        assert!(
            is_noncharacter('\u{FDD0}')
                && is_noncharacter('\u{FFFE}')
                && is_noncharacter('\u{FFFF}')
        );
        assert!(is_noncharacter('\u{1FFFE}') && is_noncharacter('\u{10FFFF}'));
        assert!(is_noncharacter('\u{FDEF}')); // FDEF is the last noncharacter in the range
        assert!(!is_noncharacter('\u{FDF0}')); // FDF0 is assigned (Arabic), not a noncharacter
        assert!(
            is_pua('\u{E000}') && is_pua('\u{F8FF}') && is_pua('\u{F0000}') && is_pua('\u{100000}')
        );
        assert!(!is_pua('a'));
    }

    #[test]
    fn strips_tag_smuggling_payload() {
        // "hi" + tag-encoded "PWN"
        let payload: String = "hi"
            .chars()
            .chain(
                "PWN"
                    .chars()
                    .map(|c| char::from_u32(0xE0000 + c as u32).unwrap()),
            )
            .collect();
        assert_eq!(strip_tags(&payload), "hi");
        assert_eq!(strip_invisible_classes(&payload, comparison()), "hi");
    }

    #[test]
    fn fixes_deprecated_language_tag() {
        // U+E0001 LANGUAGE TAG must be stripped (the #413 "E0001 survives" defect).
        assert_eq!(strip_tags("hi\u{E0001}bye"), "hibye");
    }

    #[test]
    fn preserves_well_formed_emoji_flag() {
        // Scotland flag: U+1F3F4 + gbsct (tag letters) + U+E007F.
        let scotland = "\u{1F3F4}\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}";
        assert_eq!(strip_tags(scotland), scotland);
        assert_eq!(strip_invisible_classes(scotland, comparison()), scotland);
        // …but a malformed tag run (no terminator) after the flag is stripped.
        let bad = "\u{1F3F4}\u{E0067}\u{E0062}"; // no CANCEL TAG
        assert_eq!(strip_tags(bad), "\u{1F3F4}");
    }

    #[test]
    fn rejects_flag_base_with_non_subdivision_tag_payload() {
        // Review D-6: a well-*shaped* sequence (flag base + tag letters +
        // terminator) whose payload is not a real RGI subdivision (England /
        // Scotland / Wales) is the Tags smuggling channel, and must be stripped
        // to the bare flag base — not preserved.
        // "pwn" tag-encoded: U+E0070 U+E0077 U+E006E, then CANCEL TAG.
        let smuggled = "\u{1F3F4}\u{E0070}\u{E0077}\u{E006E}\u{E007F}";
        assert_eq!(strip_tags(smuggled), "\u{1F3F4}");
        assert_eq!(strip_invisible_classes(smuggled, comparison()), "\u{1F3F4}");
        // Wales (gbwls) is a real subdivision flag and is preserved.
        let wales = "\u{1F3F4}\u{E0067}\u{E0062}\u{E0077}\u{E006C}\u{E0073}\u{E007F}";
        assert_eq!(strip_tags(wales), wales);
    }

    #[test]
    fn variation_selector_policy() {
        // Comparison: strip every VS (VS2 and VS17).
        assert_eq!(
            strip_invisible_classes("g\u{FE01}data", comparison()),
            "gdata"
        );
        assert_eq!(
            strip_invisible_classes("g\u{E0100}data", comparison()),
            "gdata"
        );
        // Rendering: keep VS15/VS16 after a base, strip the rest.
        assert_eq!(
            strip_invisible_classes("\u{2764}\u{FE0F}", rendering()),
            "\u{2764}\u{FE0F}"
        );
        assert_eq!(
            strip_invisible_classes("g\u{FE01}data", rendering()),
            "gdata"
        ); // VS2 still stripped
           // A leading VS16 (no base) is stripped even in rendering context.
        assert_eq!(strip_invisible_classes("\u{FE0F}x", rendering()), "x");
    }

    #[test]
    fn strips_cgj_noncharacters_and_pua() {
        assert_eq!(
            strip_invisible_classes("ad\u{034F}min", comparison()),
            "admin"
        );
        assert_eq!(
            strip_invisible_classes("a\u{FFFE}b\u{FDD0}c", comparison()),
            "abc"
        );
        assert_eq!(strip_noncharacters("a\u{FFFF}b"), "ab");
        assert_eq!(strip_pua("a\u{E000}b\u{F0000}c"), "abc");
        // Rendering preserves PUA.
        assert_eq!(
            strip_invisible_classes("a\u{E000}b", rendering()),
            "a\u{E000}b"
        );
    }

    #[test]
    fn idempotent() {
        let s = "hi\u{E0001}\u{FE01}ad\u{034F}min\u{FFFE}\u{E000}";
        let once = strip_invisible_classes(s, comparison());
        assert_eq!(once, strip_invisible_classes(&once, comparison()));
    }

    #[test]
    fn strip_invisible_classes_into_matches_returning() {
        let mut out = String::new();
        for s in [
            "",
            "abc",
            "a\u{200D}b",
            "\u{1F3F4}\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}",
            "x\u{E0041}y",
            "z\u{FE0F}",
        ] {
            strip_invisible_classes_into(s, comparison(), &mut out);
            assert_eq!(
                out,
                strip_invisible_classes(s, comparison()),
                "comparison: {s:?}"
            );
            strip_invisible_classes_into(s, rendering(), &mut out);
            assert_eq!(
                out,
                strip_invisible_classes(s, rendering()),
                "rendering: {s:?}"
            );
        }
        // Buffer reuse: a previous non-empty value must be fully overwritten.
        out.push_str("STALE");
        strip_invisible_classes_into("abc", comparison(), &mut out);
        assert_eq!(out, "abc");
    }
}
