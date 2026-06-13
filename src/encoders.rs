//! Context-explicit output encoders — terminal functions, **not** pipeline steps.
//!
//! Output encoding must happen at the sink, with the sink context known, exactly
//! once. A pipeline is context-free and position-blind by design, so these
//! encoders are deliberately *not* exposed as `TextPipeline`/`PROFILES` steps:
//! baking an encoder into a pipeline invites double-encoding, wrong-context
//! escaping, and storing pre-escaped text. They are correct encoders for
//! *specific* sinks — see `THREAT_MODEL.md`. disarm remains *not* a
//! context-aware auto-escaper.

use std::borrow::Cow;

use pyo3::prelude::*;
use pyo3::types::PyString;

/// Escape the five HTML metacharacters for element-body / quoted-attribute
/// context: `&`→`&amp;`, `<`→`&lt;`, `>`→`&gt;`, `"`→`&quot;`, `'`→`&#x27;`.
///
/// Pure `&str` core (no Python). Returns `Cow::Borrowed` when nothing needs
/// escaping, so the FFI wrapper can hand back the original object zero-copy.
pub fn escape_html_str(s: &str) -> Cow<'_, str> {
    if !s
        .bytes()
        .any(|b| matches!(b, b'&' | b'<' | b'>' | b'"' | b'\''))
    {
        return Cow::Borrowed(s);
    }
    let mut out = String::with_capacity(s.len() + 16);
    for ch in s.chars() {
        match ch {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&#x27;"),
            c => out.push(c),
        }
    }
    Cow::Owned(out)
}

/// Escape the five HTML metacharacters for element-body (PCDATA) and
/// quoted-attribute context.
///
/// `&`→`&amp;`, `<`→`&lt;`, `>`→`&gt;`, `"`→`&quot;`, `'`→`&#x27;` (hex
/// apostrophe; widely safe). Everything else passes through unchanged.
///
/// Correct for HTML **element-body and quoted-attribute** context (the five-char
/// set, with both quotes, covers both). **Not** correct inside `<script>` /
/// `<style>`, unquoted attributes, URL / `href` / `src` attributes, or HTML
/// comments — there, HTML-entity escaping is insufficient or actively corrupting
/// (entities are not decoded inside `<script>`, so `&lt;` renders literally).
/// Encode once, at the output sink.
///
/// Fast path: input with no metacharacter returns the original object
/// (zero-copy), consistent with the transliterate fast path (#277).
#[pyfunction]
#[pyo3(signature = (text,))]
pub fn _escape_html<'py>(text: &Bound<'py, PyString>) -> PyResult<Bound<'py, PyString>> {
    let s = text.to_cow()?;
    match escape_html_str(&s) {
        // Nothing to escape → hand back the original object (refcount bump,
        // no string copy). The common case for already-clean text.
        Cow::Borrowed(_) => Ok(text.clone()),
        Cow::Owned(escaped) => Ok(PyString::new(text.py(), &escaped)),
    }
}

const UPPER_HEX: &[u8; 16] = b"0123456789ABCDEF";

/// RFC 3986 §2.3 unreserved characters: `ALPHA / DIGIT / "-" / "." / "_" / "~"`.
#[inline]
fn is_unreserved(b: u8) -> bool {
    b.is_ascii_alphanumeric() || matches!(b, b'-' | b'.' | b'_' | b'~')
}

/// `pchar` (RFC 3986 §3.3) minus pct-encoded and `/`: unreserved + sub-delims +
/// `:` `@`. The safe set for a single path **segment**.
#[inline]
fn keep_segment(b: u8) -> bool {
    is_unreserved(b)
        || matches!(
            b,
            b'!' | b'$'
                | b'&'
                | b'\''
                | b'('
                | b')'
                | b'*'
                | b'+'
                | b','
                | b';'
                | b'='
                | b':'
                | b'@'
        )
}

/// A full **path**: `pchar` plus `/` (so multiple segments survive).
#[inline]
fn keep_path(b: u8) -> bool {
    keep_segment(b) || b == b'/'
}

/// **query** / **form** encode a *value* to embed: keep only unreserved, so
/// reserved characters (`&`, `=`, `+`, …) cannot break out of the component.
#[inline]
fn keep_value(b: u8) -> bool {
    is_unreserved(b)
}

fn percent_encode_into(text: &str, keep: fn(u8) -> bool, space_to_plus: bool, out: &mut String) {
    for &b in text.as_bytes() {
        if space_to_plus && b == b' ' {
            out.push('+');
        } else if keep(b) {
            out.push(b as char);
        } else {
            out.push('%');
            out.push(UPPER_HEX[(b >> 4) as usize] as char);
            out.push(UPPER_HEX[(b & 0x0f) as usize] as char);
        }
    }
}

/// Percent-encode `text` for a named URL component. Pure `&str` core (no
/// Python). Returns `None` for an unrecognized component name.
pub fn percent_encode_str(text: &str, component: &str) -> Option<String> {
    let (keep, space_to_plus): (fn(u8) -> bool, bool) = match component {
        "path" => (keep_path, false),
        "segment" => (keep_segment, false),
        "query" => (keep_value, false),
        "form" => (keep_value, true),
        _ => return None,
    };
    let mut out = String::with_capacity(text.len());
    percent_encode_into(text, keep, space_to_plus, &mut out);
    Some(out)
}

/// Percent-encode `text` for a named URL component (RFC 3986).
///
/// **Not ASCII-closed:** the input is UTF-8 encoded first, then every byte
/// outside the component's safe set becomes `%XX` (`é` → `%C3%A9`). Output is
/// pure ASCII. The safe set differs by component, so `component` is required:
///
/// - `path` — unreserved + sub-delims + `:` `@` + `/` (a whole path)
/// - `segment` — `path` without `/` (a single path segment)
/// - `query` — unreserved only (a query *value*; reserved chars are encoded)
/// - `form` — `query` plus `application/x-www-form-urlencoded` space → `+`
///
/// Percent-encoding is **not** a defense against `javascript:` / `data:` scheme
/// injection or open redirects — those are URL-*construction* concerns, out of
/// scope. Encode once, at the output sink.
#[pyfunction]
#[pyo3(signature = (text, *, component))]
pub fn _percent_encode(text: &str, component: &str) -> PyResult<String> {
    percent_encode_str(text, component).ok_or_else(|| {
        crate::InvalidArgumentError::new_err(format!(
            "unknown percent-encode component {component:?}; expected one of: \
             'path', 'segment', 'query', 'form'"
        ))
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn escape_html_metacharacters() {
        assert_eq!(
            escape_html_str("<script>alert(1)</script>"),
            "&lt;script&gt;alert(1)&lt;/script&gt;"
        );
        assert_eq!(escape_html_str("a & b"), "a &amp; b");
        assert_eq!(escape_html_str("say \"hi\""), "say &quot;hi&quot;");
        assert_eq!(escape_html_str("it's"), "it&#x27;s");
    }

    #[test]
    fn escape_html_passthrough_borrows() {
        // Non-metacharacters (incl. non-ASCII) untouched, and borrowed (no alloc).
        assert!(matches!(
            escape_html_str("café 北京"),
            Cow::Borrowed("café 北京")
        ));
        // `&` is itself escaped, so a pre-existing entity is re-escaped
        // (not idempotent, by design): `&lt;` → `&amp;lt;`.
        assert_eq!(escape_html_str("&lt;"), "&amp;lt;");
    }

    #[test]
    fn escape_html_not_idempotent_by_design() {
        assert_eq!(escape_html_str("&"), "&amp;");
        assert_eq!(escape_html_str("&amp;"), "&amp;amp;");
    }

    #[test]
    fn percent_encode_unreserved_untouched() {
        assert_eq!(
            percent_encode_str("AZaz09-._~", "query").unwrap(),
            "AZaz09-._~"
        );
    }

    #[test]
    fn percent_encode_query_encodes_reserved() {
        assert_eq!(
            percent_encode_str("a&b=c+d", "query").unwrap(),
            "a%26b%3Dc%2Bd"
        );
    }

    #[test]
    fn percent_encode_form_space_to_plus() {
        assert_eq!(percent_encode_str("a b+c", "form").unwrap(), "a+b%2Bc");
    }

    #[test]
    fn percent_encode_utf8_bytes() {
        assert_eq!(percent_encode_str("é", "query").unwrap(), "%C3%A9");
    }

    #[test]
    fn percent_encode_segment_vs_path() {
        assert_eq!(percent_encode_str("a/b", "segment").unwrap(), "a%2Fb");
        assert_eq!(percent_encode_str("a/b", "path").unwrap(), "a/b");
    }

    #[test]
    fn percent_encode_output_is_ascii() {
        assert!(percent_encode_str("Москва ☕", "form").unwrap().is_ascii());
    }

    #[test]
    fn percent_encode_unknown_component_is_none() {
        assert!(percent_encode_str("x", "nonsense").is_none());
    }
}
