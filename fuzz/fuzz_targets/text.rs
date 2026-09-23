//! The text primitives: zalgo, display width, edit distance, whitespace and invisible
//! strips, case folding, punctuation folding, the output encoders and the log-injection
//! neutralizer.
//!
//! Properties, each proved or swept in `formal/lean/Text` or `formal/lean/Sanitizers`:
//!
//! - `strip_zalgo`: idempotent (`strip_idem`); its NFD is a subsequence of the input's NFD
//!   (`strip_sublist`); and when `is_zalgo(s, k)` is false it only normalizes
//!   (`strip_id_of_not_zalgo`). The cap itself is not checked: a class-0 mark between two
//!   runs resets the count (Text finding Z1, open), and `strip_zalgo`'s output can still
//!   be zalgo at the same threshold (Z2, open).
//! - `terminal_width`: at most 2 per grapheme (`tw_le`), the ambiguous-wide policy never
//!   narrows (`gw_amb_mono`), it is the sum of `grapheme_width` over the clusters, and
//!   printable ASCII is one column per byte.
//! - `edit_distance` is a metric (`ed_metric`) bounded by the lengths in characters.
//! - `collapse_whitespace`: idempotent, no leading, trailing or doubled space, and no
//!   whitespace but U+0020 (`collapse_nf`, `collapse_idem`).
//! - The strips are idempotent and the control and zero-width strips commute
//!   (`strips_commute`); `fold_case` and `fold_punctuation` are idempotent, and
//!   `fold_punctuation` is the identity on ASCII (`foldPunct_idem`, `foldPunct_ascii`).
//! - `escape_html` and `percent_encode` round-trip through their decoders, and
//!   `percent_encode` is ASCII (`Enc.*`).
//! - `strip_log_injection`: no neutralized character survives, idempotent
//!   (`Log.strip_clean`, `strip_idem`), and a replacement it neutralizes is refused.
//! - `grapheme_truncate` keeps at most the requested clusters and is a prefix.
#![no_main]

use arbitrary::Arbitrary;
use disarm::api::{self as d, UrlComponent};
use disarm_fuzz::{is_subsequence, nfd, split_at_choice, text_and};
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
struct Opts {
    marks: u8,
    split_a: u16,
    split_b: u16,
    component: u8,
    replacement: String,
    keep_tab: bool,
    graphemes: u8,
}

fn html_unescape(s: &str) -> String {
    s.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", "\"")
        .replace("&#x27;", "'")
        .replace("&#39;", "'")
        .replace("&amp;", "&")
}

fn percent_decode(s: &str, plus_is_space: bool) -> Vec<u8> {
    let b = s.as_bytes();
    let mut out = Vec::with_capacity(b.len());
    let mut i = 0;
    while i < b.len() {
        match b[i] {
            b'%' if i + 2 < b.len() => {
                let hex = std::str::from_utf8(&b[i + 1..i + 3]).unwrap();
                out.push(u8::from_str_radix(hex, 16).expect("well-formed %XX"));
                i += 3;
            }
            b'+' if plus_is_space => {
                out.push(b' ');
                i += 1;
            }
            c => {
                out.push(c);
                i += 1;
            }
        }
    }
    out
}

fn is_log_injection_char(c: char, keep_tab: bool) -> bool {
    if c == '\t' {
        return !keep_tab;
    }
    matches!(c, '\u{0}'..='\u{1F}' | '\u{7F}'..='\u{9F}' | '\u{2028}' | '\u{2029}')
}

fuzz_target!(|data: &[u8]| {
    let Some((s, o)) = text_and::<Opts>(data) else {
        return;
    };
    let s = s.as_str();

    // Zalgo.
    let k = usize::from(o.marks % 8);
    let stripped = d::strip_zalgo(s, k);
    assert_eq!(
        d::strip_zalgo(&stripped, k),
        stripped,
        "strip_zalgo not idempotent"
    );
    assert!(
        is_subsequence(&nfd(&stripped), &nfd(s)),
        "strip_zalgo output is not a subsequence of its input: {s:?}"
    );
    if !d::is_zalgo(s, k) {
        assert_eq!(
            nfd(&stripped),
            nfd(s),
            "not zalgo, yet strip_zalgo removed marks"
        );
    }

    // Width.
    for wide in [false, true] {
        let w = d::terminal_width(s, wide);
        assert!(
            w <= 2 * d::grapheme_len(s),
            "more than 2 columns a cluster: {s:?}"
        );
        let sum: usize = d::graphemes(s).map(|g| d::grapheme_width(g, wide)).sum();
        assert_eq!(w, sum, "terminal_width != sum of grapheme_width on {s:?}");
    }
    assert!(d::terminal_width(s, false) <= d::terminal_width(s, true));
    if s.bytes().all(|b| (0x20..0x7F).contains(&b)) {
        assert_eq!(d::terminal_width(s, false), s.len());
    }

    // Edit distance: a metric, within the length bounds.
    let (a, rest) = split_at_choice(s, o.split_a);
    let (b, c) = split_at_choice(rest, o.split_b);
    let (la, lb) = (a.chars().count(), b.chars().count());
    let ab = d::edit_distance(a, b);
    assert_eq!(ab, d::edit_distance(b, a), "not symmetric");
    assert_eq!(ab == 0, a == b, "zero exactly on equal strings");
    assert!(
        la.abs_diff(lb) <= ab && ab <= la.max(lb),
        "out of the length bounds"
    );
    assert!(
        d::edit_distance(a, c) <= ab + d::edit_distance(b, c),
        "triangle inequality: {a:?} {b:?} {c:?}"
    );

    // Whitespace.
    let collapsed = d::collapse_whitespace(s);
    assert_eq!(d::collapse_whitespace(&collapsed), collapsed);
    assert!(!collapsed.starts_with(' ') && !collapsed.ends_with(' ') && !collapsed.contains("  "));
    assert!(
        collapsed.chars().all(|c| c == ' ' || !c.is_whitespace()),
        "whitespace left: {collapsed:?}"
    );

    // Strips, folds.
    let ctrl = d::strip_control_chars(s);
    let zw = d::strip_zero_width_chars(s);
    assert_eq!(d::strip_control_chars(&ctrl), ctrl);
    assert_eq!(d::strip_zero_width_chars(&zw), zw);
    assert_eq!(
        d::strip_zero_width_chars(&ctrl),
        d::strip_control_chars(&zw),
        "strips do not commute"
    );
    for f in [
        d::strip_tags,
        d::strip_variation_selectors,
        d::strip_noncharacters,
        d::strip_pua,
    ] {
        let once = f(s);
        assert_eq!(f(&once), once);
    }
    let folded = d::fold_case(s);
    assert_eq!(
        d::fold_case(&folded),
        folded,
        "fold_case not idempotent on {s:?}"
    );
    let punct = d::fold_punctuation(s);
    assert_eq!(
        d::fold_punctuation(&punct),
        punct,
        "fold_punctuation not idempotent"
    );
    if s.is_ascii() {
        assert_eq!(punct, s);
    }

    // Encoders.
    let escaped = d::escape_html(s);
    assert!(!escaped.contains(['<', '>', '"', '\'']));
    assert_eq!(
        html_unescape(&escaped),
        s,
        "escape_html does not round-trip"
    );
    let component = [
        UrlComponent::Path,
        UrlComponent::Segment,
        UrlComponent::Query,
        UrlComponent::Form,
    ][usize::from(o.component % 4)];
    let encoded = d::percent_encode(s, component);
    assert!(encoded.is_ascii());
    assert_eq!(
        percent_decode(&encoded, component == UrlComponent::Form),
        s.as_bytes(),
        "percent_encode does not round-trip"
    );

    // Log injection.
    match d::strip_log_injection(s, &o.replacement, o.keep_tab) {
        Ok(clean) => {
            assert!(!clean.chars().any(|c| is_log_injection_char(c, o.keep_tab)));
            assert_eq!(
                d::strip_log_injection(&clean, &o.replacement, o.keep_tab).unwrap(),
                clean
            );
        }
        Err(_) => assert!(
            o.replacement
                .chars()
                .any(|c| is_log_injection_char(c, o.keep_tab)),
            "refused a clean replacement {:?}",
            o.replacement
        ),
    }

    // Graphemes.
    let n = usize::from(o.graphemes % 16);
    let cut = d::grapheme_truncate(s, n);
    assert!(s.starts_with(&cut) && d::grapheme_len(&cut) <= n);
    assert_eq!(d::grapheme_split(s).concat(), s);
});
