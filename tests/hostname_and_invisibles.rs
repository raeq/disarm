//! The hostname screen's invisible, compatibility-form and IPv6-literal checks, and the
//! invisible-class helpers, asserted from Rust.
//!
//! cargo-mutants (#1040) found these lines asserted by nothing the Rust suite runs: the
//! hostname checks were covered only by `tests/test_hn_compat_and_mapping.py`, which the
//! Node, Ruby, Java and C bindings never run although they reach the same code. Each
//! test names the lines it pins; `docs/architecture/testing-guarantees.md` has the
//! mutation baseline and what is left of it.

use std::collections::HashSet;

use disarm::api::{
    canonicalize, decode_smuggled, has_anomalies, inspect_anomalies, is_suspicious_hostname,
    strip_format, strip_tags, strip_variation_selectors, HostnameAnalysis,
};

fn screen(host: &str) -> HostnameAnalysis {
    is_suspicious_hostname(host)
}

// -- `is_invisible_in_hostname` and `strip_invisibles` ------------------------------

/// One character of every class the hostname screen treats as invisible, each on its
/// own: a mutant that drops any one class from the union, or joins two with `&&`,
/// leaves one of these unflagged.
const INVISIBLE_ONE_OF_EACH: &[(char, &str)] = &[
    ('\u{200B}', "zero-width"),
    ('\u{E0061}', "tag"),
    ('\u{FE0F}', "variation selector"),
    ('\u{E0100}', "variation selector supplement"),
    ('\u{FDD0}', "noncharacter"),
    ('\u{E000}', "private use"),
    ('\u{F0000}', "plane-15 private use"),
    ('\u{00AD}', "default-ignorable: soft hyphen"),
    ('\u{034F}', "default-ignorable: CGJ"),
    ('\u{3164}', "default-ignorable: Hangul filler"),
    ('\u{1D173}', "default-ignorable: musical format"),
    ('\u{E0080}', "default-ignorable: unassigned tag-block tail"),
];

#[test]
fn every_invisible_class_is_flagged_and_stripped() {
    for &(ch, class) in INVISIBLE_ONE_OF_EACH {
        let host = format!("ev{ch}il.com");
        let a = screen(&host);
        assert!(a.has_invisible, "{class} U+{:04X} not flagged", ch as u32);
        assert!(a.suspicious, "{class} U+{:04X} not suspicious", ch as u32);
        // Stripped from `canonical`, and only it: the rest of the label survives.
        assert_eq!(a.canonical, "evil.com", "{class} U+{:04X}", ch as u32);
    }
}

#[test]
fn a_clean_host_is_not_flagged_invisible() {
    for host in [
        "evil.com",
        "example.org",
        "b\u{fc}cher.de",
        "xn--bcher-kva.de",
    ] {
        let a = screen(host);
        assert!(!a.has_invisible, "{host}");
        assert!(!a.canonical.is_empty(), "{host}");
    }
    // A bidi control is `bidi_control`, not `has_invisible`: the two partition the
    // default-ignorables between them.
    let a = screen("pay\u{202E}pal.com");
    assert!(a.bidi_control);
    assert!(!a.has_invisible);
}

// -- `has_compat_form` ---------------------------------------------------------------

#[test]
fn a_compatibility_form_is_folded_and_flagged() {
    // One character whose NFKC is another single character (fullwidth `g`), and one
    // whose NFKC is longer (the `fi` ligature): the two halves of the check.
    for (host, canonical) in [
        ("\u{FF47}oogle.com", "google.com"),
        ("\u{FB01}le.com", "file.com"),
        ("\u{2160}BM.com", "ibm.com"),
    ] {
        let a = screen(host);
        assert!(a.compat_fold, "{host}");
        assert!(a.suspicious, "{host}");
        assert_eq!(a.canonical, canonical, "{host}");
    }
    // NFKC-stable labels, including decomposed Hangul, are not a compatibility form.
    for host in [
        "google.com",
        "\u{1112}\u{1161}\u{11AB}.kr",
        "b\u{fc}cher.de",
    ] {
        assert!(!screen(host).compat_fold, "{host}");
    }
}

// -- `is_ipv6_literal` ---------------------------------------------------------------

/// An IPv6 literal short-circuits the analysis: nothing is split into labels.
fn is_literal(host: &str) -> bool {
    let a = screen(host);
    a.label_scripts.is_empty() && !a.suspicious
}

#[test]
fn ipv6_literals_are_recognised() {
    for host in [
        "[::1]",
        "[2001:db8::1]",
        // Seven colons, the most a literal has.
        "[1:2:3:4:5:6:7:8]",
        // One zone ID.
        "[fe80::1%1]",
        // An embedded IPv4 address.
        "[::ffff:192.0.2.1]",
    ] {
        assert!(is_literal(host), "{host} is a literal");
        assert_eq!(screen(host).canonical, host);
    }
}

#[test]
fn near_misses_are_not_ipv6_literals() {
    for host in [
        // Unbracketed on one side.
        "[::1",
        "::1]",
        // Empty, or no colon.
        "[]",
        "[abcd]",
        // Eight colons.
        "[1:2:3:4:5:6:7:8:9]",
        // Two zone-ID delimiters.
        "[fe80::1%a%b]",
        // A character no literal holds.
        "[::g]",
        "[::1/64]",
    ] {
        assert!(!is_literal(host), "{host} is not a literal");
    }
}

// -- The invisible-class helpers -----------------------------------------------------

#[test]
fn strip_variation_selectors_removes_selectors_and_only_them() {
    assert_eq!(
        strip_variation_selectors("a\u{FE0F}b\u{FE00}c\u{E0100}d\u{E01EF}"),
        "abcd"
    );
    assert_eq!(strip_variation_selectors("plain text"), "plain text");
    assert_eq!(strip_variation_selectors("\u{2764}\u{FE0F}"), "\u{2764}");
    assert_eq!(strip_variation_selectors(""), "");
}

#[test]
fn the_default_ignorable_formats_are_invisible() {
    // U+1BCA0-U+1BCA3 and U+1D173-U+1D17A: invisible by property, not by name (#813).
    for ch in ['\u{1BCA0}', '\u{1BCA3}', '\u{1D173}', '\u{1D17A}'] {
        let s = format!("pay{ch}pal");
        assert_eq!(strip_format(&s), "paypal", "U+{:04X}", ch as u32);
        assert_eq!(canonicalize(&s).unwrap(), "paypal", "U+{:04X}", ch as u32);
    }
}

#[test]
fn a_subdivision_flag_is_skipped_whole() {
    // England: U+1F3F4, the tag letters `gbeng`, U+E007F CANCEL TAG. The detector and
    // the carrier scan skip the whole sequence; one short would leave CANCEL TAG behind
    // to be read as the start of a tag run.
    let england = "\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}";
    let lexicon = HashSet::new();
    for s in [
        england.to_owned(),
        format!("{england}{england}"),
        format!("go {england} team"),
    ] {
        assert_eq!(strip_tags(&s), s, "{s:?}");
        assert!(decode_smuggled(&s).is_empty(), "{s:?}");
        assert!(!has_anomalies(&s, &lexicon), "{s:?}");
        assert!(!inspect_anomalies(&s, &lexicon).anomalous, "{s:?}");
    }
    // Not a flag: the tags channel wearing a flag base is still found.
    let fake = "\u{1F3F4}\u{E0068}\u{E0069}\u{E007F}";
    assert!(has_anomalies(fake, &lexicon));
}
