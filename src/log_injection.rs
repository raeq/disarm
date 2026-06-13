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

use std::borrow::Cow;

use pyo3::prelude::*;
use pyo3::types::PyString;

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
/// common all-printable line) — an allocation-free pass-through. ANSI sequences
/// are neutralized by replacing their *introducer* (ESC / the C1 CSI), leaving
/// the inert, audit-visible residue (`[31m`) as printable text; full CSI/OSC
/// sequences are not parsed (that would be stateful and fragile).
pub fn strip_log_injection_str<'a>(
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

/// Neutralize log-injection / terminal-control characters in `text`.
///
/// Replaces — never silently drops, so a redaction stays visible in the
/// record — every CR, LF, NEL (U+0085), LS (U+2028), PS (U+2029), NUL, C0/C1
/// control, ESC (U+001B), and DEL (U+007F) with `replacement` (default
/// U+FFFD). `\t` is **also** neutralized by default (`keep_tab=False`): a tab is
/// a field separator in TSV/logfmt logs, so keeping it would permit column
/// injection; opt back in with `keep_tab=True` for human-readable tabular logs.
///
/// Idempotent, and the output never contains a raw CR/LF/ESC. **Not** an HTML/
/// SQL output sanitizer and **not** a defense against logging-framework
/// interpolation (log4shell); it makes a log line safe to *write*, not safe to
/// later *render as HTML*. See `THREAT_MODEL.md`.
// No defaults in the FFI signature: the Python wrapper supplies them. (A
// non-ASCII default like U+FFFD in `__text_signature__` is unparseable by
// `inspect.signature`, which the stub-drift test relies on.)
#[pyfunction]
#[pyo3(signature = (text, *, replacement, keep_tab))]
pub fn _strip_log_injection<'py>(
    text: &Bound<'py, PyString>,
    replacement: &str,
    keep_tab: bool,
) -> PyResult<Bound<'py, PyString>> {
    // The "never emit a raw CR/LF/ESC" guarantee and idempotency hold only if the
    // replacement itself contains none of the characters this call neutralizes.
    if let Some(c) = replacement
        .chars()
        .find(|&c| is_log_injection_char(c, keep_tab))
    {
        return Err(crate::InvalidArgumentError::new_err(format!(
            "replacement must not contain a character this call neutralizes \
             (found U+{:04X})",
            c as u32
        )));
    }
    let s = text.to_cow()?;
    match strip_log_injection_str(&s, replacement, keep_tab) {
        // Clean line → hand back the original object (refcount bump, no copy).
        Cow::Borrowed(_) => Ok(text.clone()),
        Cow::Owned(out) => Ok(PyString::new(text.py(), &out)),
    }
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
