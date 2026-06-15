//! `strip_log_injection` — neutralize log-injection at the log-line sink.
//!
//! A character-level, stateless transform that makes untrusted text safe to
//! *write* as a log line: it replaces the structure-breaking and terminal-control
//! characters that let an attacker forge log records (CRLF / NEL / LS / PS),
//! corrupt parsers (NUL / C0 / C1 controls), or hijack a terminal that `cat`s the
//! log (ANSI escape introducers / DEL).
//!
//! **Scope (see `THREAT_MODEL.md`).** This owns the log-store/parser and
//! operator-terminal sinks. It does **not** make a log line safe to render in an
//! HTML log viewer (Kibana/Grafana/etc.) — that is stored / second-order XSS and
//! is the *viewer's* output-encoding responsibility (use `escape_html` there).
//! It performs **no** HTML/JS/SQL escaping and is **not** a defense against
//! logging-framework interpolation (log4shell `${jndi:...}`), which is an
//! evaluation flaw, not a character-level one. It does no NFKC / confusable
//! folding, so it preserves the message's meaning and does not unmask
//! metacharacters.
//!
//! Layer 1 (pure-Rust core): no pyo3. Shim in `src/py/log_injection.rs`;
//! crates.io surface is `crate::api::strip_log_injection`.
//!
//! **Anti-recursion invariant.** The diagnostic logger (`tl_trace_content!`,
//! #208) dogfoods [`strip_log_injection_str`] to neutralize the samples it
//! emits. Nothing in this module may therefore emit a `tl_*!` / `log::` record:
//! a logger that sanitized its own line by calling code that logs would recurse.
//! `tests/log_injection_no_recursion.rs` enforces this with a source scan.

use std::borrow::Cow;

/// Whether `c` is a character `strip_log_injection` neutralizes.
///
/// Tab (`\t`, a C0 control) is kept only when `keep_tab` is set; the arm is
/// ordered before the C0 range so the flag wins.
#[inline]
fn is_log_injection_char(c: char, keep_tab: bool) -> bool {
    if c == '\t' {
        return !keep_tab;
    }
    matches!(c,
        '\u{0000}'..='\u{001F}'   // C0 controls (incl. CR, LF, NUL, ESC)
        | '\u{007F}'              // DEL
        | '\u{0080}'..='\u{009F}' // C1 controls (incl. NEL U+0085, CSI U+009B)
        | '\u{2028}' | '\u{2029}' // line / paragraph separators
    )
}

/// Pure core: replace every neutralized character with `replacement`.
///
/// Returns `Cow::Borrowed` when the input contains no neutralized character (the
/// common all-printable line) — an allocation-free pass-through. The check scans
/// `chars()` rather than taking an `isascii()`/byte shortcut because the
/// neutralized set includes non-ASCII code points (NEL U+0085, LS U+2028,
/// PS U+2029, C1 controls): a clean *non-ASCII* line (e.g. `café`) must still
/// pass through, and those scalars cannot be detected from a single byte. ANSI
/// sequences
/// are neutralized by replacing their *introducer* (ESC / the C1 CSI), leaving
/// the inert, audit-visible residue (`[31m`) as printable text; full CSI/OSC
/// sequences are not parsed (that would be stateful and fragile).
pub(crate) fn strip_log_injection_str<'a>(
    text: &'a str,
    replacement: &str,
    keep_tab: bool,
) -> Cow<'a, str> {
    if !text.chars().any(|c| is_log_injection_char(c, keep_tab)) {
        return Cow::Borrowed(text);
    }
    let mut out = String::with_capacity(text.len());
    for c in text.chars() {
        if is_log_injection_char(c, keep_tab) {
            out.push_str(replacement);
        } else {
            out.push(c);
        }
    }
    Cow::Owned(out)
}

/// Validate a `strip_log_injection` `replacement`: it must contain none of the
/// characters this call neutralizes, or the "no raw CR/LF/ESC in output" and
/// idempotency guarantees would not hold.
pub(crate) fn validate_log_replacement(
    replacement: &str,
    keep_tab: bool,
) -> Result<(), crate::ErrorRepr> {
    if let Some(c) = replacement
        .chars()
        .find(|&c| is_log_injection_char(c, keep_tab))
    {
        return Err(crate::ErrorRepr::InvalidLogReplacement {
            codepoint: c as u32,
        });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn strip(s: &str) -> String {
        strip_log_injection_str(s, "\u{FFFD}", false).into_owned()
    }

    #[test]
    fn neutralizes_crlf_and_nul() {
        assert_eq!(strip("a\r\nb\0c"), "a\u{FFFD}\u{FFFD}b\u{FFFD}c");
    }

    #[test]
    fn neutralizes_ansi_introducer_leaving_residue() {
        // ESC (U+001B) → replacement; the trailing `[31m` survives as inert text.
        assert_eq!(strip("\u{1B}[31mred"), "\u{FFFD}[31mred");
    }

    #[test]
    fn neutralizes_nel_ls_ps_and_c1() {
        assert_eq!(
            strip("a\u{0085}b\u{2028}c\u{2029}d\u{009B}e"),
            "a\u{FFFD}b\u{FFFD}c\u{FFFD}d\u{FFFD}e"
        );
    }

    #[test]
    fn neutralizes_del() {
        assert_eq!(strip("a\u{7F}b"), "a\u{FFFD}b");
    }

    #[test]
    fn tab_neutralized_by_default_kept_when_opted_in() {
        assert_eq!(strip("a\tb"), "a\u{FFFD}b");
        assert_eq!(
            strip_log_injection_str("a\tb", "\u{FFFD}", true).into_owned(),
            "a\tb"
        );
    }

    #[test]
    fn clean_line_borrows() {
        assert!(matches!(
            strip_log_injection_str("plain ascii line", "\u{FFFD}", false),
            Cow::Borrowed(_)
        ));
        // Printable non-ASCII (and HTML metacharacters) are preserved.
        assert!(matches!(
            strip_log_injection_str("café <b>&amp;</b> ☕", "\u{FFFD}", false),
            Cow::Borrowed(_)
        ));
    }

    #[test]
    fn preserves_html_metacharacters() {
        // Must NOT escape — it makes no HTML-viewer-safety claim (#307 carve-out).
        let s = "<script>alert(1)</script> & \"x\"";
        assert_eq!(strip(s), s);
    }

    #[test]
    fn idempotent() {
        let s = "a\r\nb\u{1B}\tc";
        let once = strip(s);
        assert_eq!(strip(&once), once);
    }

    #[test]
    fn output_has_no_raw_cr_lf_esc() {
        let s = "x\r\n\u{1B}\u{0085}\u{2028}y";
        let out = strip(s);
        assert!(!out.contains(['\r', '\n', '\u{1B}']));
    }
}
