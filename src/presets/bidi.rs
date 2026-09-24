//! `strip_bidi`: the UAX #9 formatting characters, the soft hyphen and the deprecated
//! format controls.

use crate::invisibles;

/// Strip dangerous bidirectional override and formatting characters
/// that `collapse_whitespace` does not handle.
///
/// Character list follows UAX #9 (Unicode Bidirectional Algorithm) §3.3.2
/// "Explicit Directional Formatting Characters" plus the soft hyphen
/// (frequently abused to split security keywords invisibly).
///
/// Covers: soft hyphen (U+00AD), Arabic Letter Mark (U+061C),
/// bidi marks (U+200E–U+200F), bidi embeddings/overrides (U+202A–U+202E),
/// bidi isolates (U+2066–U+2069), deprecated format controls (U+206A–U+206F),
/// and interlinear annotation marks (U+FFF9–U+FFFB).
pub(crate) fn strip_bidi(text: &str) -> String {
    let mut out = String::new();
    strip_bidi_into(text, &mut out);
    out
}

/// In-place form of [`strip_bidi`] (#236 item 7).
pub(crate) fn strip_bidi_into(text: &str, out: &mut String) {
    out.clear();
    // Every bidi/format target is >= U+00AD, so pure-ASCII input passes through
    // unchanged — skip the per-char filter entirely (review D-3). Guarded by
    // `strip_bidi_has_no_ascii_targets`.
    if text.is_ascii() {
        out.push_str(text);
        return;
    }
    out.reserve(text.len()); // filter's size_hint lower bound is 0
    out.extend(text.chars().filter(|&ch| !is_bidi_or_format(ch)));
}

#[inline]
pub(super) fn is_bidi_or_format(ch: char) -> bool {
    // ── UAX #9 §3.3.2 bidi formatting characters ───────
    // Defined once, in `crate::scripts::is_bidi_control`, so this set and the
    // hostname screen (#603) cannot drift apart.
    if crate::scripts::is_bidi_control(ch) {
        return true;
    }

    // ── Soft hyphen ─────────────────────────────────────
    // Not a bidi char per se, but invisible and used to split keywords.
    if ch == '\u{00AD}' {
        return true;
    }

    // ── Deprecated format controls + interlinear annotation (#67.2) ──
    // U+206A–U+206F (deprecated: symmetric/digit shaping, inhibit join) and
    // U+FFF9–U+FFFB (interlinear annotation anchor/separator/terminator) are
    // invisible/format characters; strip them here too so strip_bidi /
    // strip_format don't leave them behind (they were previously only handled
    // as transliteration-table entries). Defined in `invisibles`, not here, so the
    // anomaly detector reads the same set this strip deletes (Finding 1 of the Lean
    // model in `formal/lean/Detection`).
    invisibles::is_deprecated_or_annotation_format(ch)
}
