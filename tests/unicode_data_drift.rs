//! #717: the other two floating dependencies that carry Unicode data into a verdict.
//!
//! `tests/normalization_ucd_drift.rs` exists because `unicode-normalization = "0.1"` is a
//! floating requirement, so a `cargo update` can move Unicode data with no disarm code
//! change. Two more dependencies have that property and had no gate:
//!
//! | dependency | declared | carries |
//! |---|---|---|
//! | `unicode-segmentation` | `"1"` | UAX #29 grapheme tables — `grapheme_len`, `terminal_width`, the boundaries `slugify` cuts on, the mark runs `is_zalgo` counts |
//! | `idna` | `"1"` | UTS #46 mapping and validation — every `xn--` label `is_suspicious_hostname` decodes |
//!
//! `idna` is the one that reaches a security verdict: `src/hostname.rs` runs every ACE
//! label through `idna::domain_to_unicode`, so the UTS #46 mapping decides what the script
//! and confusable analysis ever sees. A moved table would change hostname answers for the
//! same registry entries and the suite would stay green.
//!
//! The two need different mechanisms, because `idna` publishes no version constant at all.
//! For `unicode-segmentation` the crate exports the answer and the documented row can
//! simply be checked, as the normalization gate does. For `idna` this freezes **behaviour**
//! instead — the version string is the artifact, the behaviour is the thing being
//! protected — which also avoids the failure in #708, where a gate stayed green because it
//! compared two things that drifted together. A literal snapshot cannot drift with the
//! crate.

const PROVENANCE: &str = include_str!("../docs/provenance.md");

// ── unicode-segmentation: the crate publishes the answer ─────────────────────

/// `(17, 0, 0)` rendered the way the documentation writes it.
fn segmentation_version() -> String {
    let (major, minor, patch) = unicode_segmentation::UNICODE_VERSION;
    format!("{major}.{minor}.{patch}")
}

/// The one `docs/provenance.md` row that is about grapheme segmentation.
///
/// Scoped to the row rather than the file, for the reason the normalization gate gives:
/// several rows state a version and today most of them state the same number, so a
/// whole-file `contains` would keep passing with this row left stale.
fn segmentation_row() -> &'static str {
    PROVENANCE
        .lines()
        .find(|line| line.contains("unicode-segmentation"))
        .expect("docs/provenance.md has no `unicode-segmentation` row")
}

#[test]
fn provenance_states_the_resolved_segmentation_version() {
    let version = segmentation_version();
    assert!(
        segmentation_row().contains(&version),
        "docs/provenance.md's grapheme-segmentation row does not state {version}, which is \
         what `unicode-segmentation` resolves to now.\n\nrow: {}\n\nA `cargo update` moved \
         the UAX #29 tables. Update the row (and #645's constant, if it exists by then).",
        segmentation_row()
    );
}

// ── idna: no version constant, so freeze the behaviour ───────────────────────

/// UTS #46 outcomes whose movement would change a hostname verdict.
///
/// Frozen literals, measured against `idna` 1.1.0 / `icu_properties_data` 2.3.0. Chosen to
/// span the parts of UTS #46 that move independently of each other:
///
/// - punycode decoding, including a whole-script confusable and a mixed-script spoof;
/// - **case mapping**, both on an ACE label and on a Unicode one — the part that moves
///   independently of normalization, which is why #717 asks for it specifically;
/// - the compatibility folds that manufacture ASCII a caller never typed (`①` → `1`,
///   `Ⅻ` → `xii`, `℡` → `tel`) — the class `canonicalize`'s two ASCII-producing steps are
///   about, arriving here through a different door;
/// - the `ß` deviation, where UTS #46 transitional and non-transitional disagree.
const UTS46: &[(&str, &str)] = &[
    // punycode → the label the confusable analysis actually sees
    (
        "xn--80ak6aa92e.com",
        "\u{430}\u{440}\u{440}\u{4cf}\u{435}.com",
    ),
    ("xn--pple-43d.com", "\u{430}pple.com"),
    ("xn--e1awd7f.com", "\u{435}\u{440}\u{456}\u{441}.com"),
    ("xn--nxasmm1c.gr", "\u{3b2}\u{3cc}\u{3bb}\u{3bf}\u{3c2}.gr"),
    ("xn--mgbh0fb.eg", "\u{645}\u{62b}\u{627}\u{644}.eg"),
    ("xn--zckzah.jp", "\u{30c6}\u{30b9}\u{30c8}.jp"),
    ("xn--fiqs8s", "\u{4e2d}\u{56fd}"),
    // case mapping — on the ACE spelling and on the Unicode one
    ("XN--PPLE-43D.COM", "\u{430}pple.com"),
    ("ExAmPlE.COM", "example.com"),
    ("B\u{fc}cher.de", "b\u{fc}cher.de"),
    // compatibility folds that produce ASCII the caller never typed
    ("\u{2460}.com", "1.com"),
    ("\u{216b}.com", "xii.com"),
    ("\u{2121}.com", "tel.com"),
    // the ß deviation: non-transitional keeps it, and both spellings agree
    ("xn--fa-hia.de", "fa\u{df}.de"),
    ("fa\u{df}.de", "fa\u{df}.de"),
];

#[test]
fn uts46_behaviour_has_not_moved() {
    let mut moved = Vec::new();
    for (input, expected) in UTS46 {
        let (got, errors) = idna::domain_to_unicode(input);
        if errors.is_err() {
            moved.push(format!("{input:?} now fails validation (was {expected:?})"));
        } else if got != *expected {
            moved.push(format!("{input:?} -> {got:?}, was {expected:?}"));
        }
    }
    assert!(
        moved.is_empty(),
        "UTS #46 behaviour moved under `idna`:\n  {}\n\n`idna` publishes no version \
         constant, so this snapshot is the gate. A change here means `cargo update` moved \
         the ICU4X data behind `is_suspicious_hostname`, and the same registry entries now \
         decode differently. Re-measure, decide whether the new answers are right, then \
         update this table and the `idna` row in docs/provenance.md.",
        moved.join("\n  ")
    );
}

#[test]
fn the_snapshot_can_fail() {
    // A frozen table that cannot fail is a comment. This proves the comparison is live.
    let (got, _) = idna::domain_to_unicode("xn--pple-43d.com");
    assert_ne!(got, "not-what-idna-returns.com");
    assert_eq!(got, "\u{430}pple.com");
}

#[test]
fn provenance_names_the_resolved_idna_artifacts() {
    let row = PROVENANCE
        .lines()
        .find(|line| line.contains("UTS&nbsp;#46 mapping"))
        .expect("docs/provenance.md has no UTS #46 row");
    for token in ["idna", "icu_properties_data"] {
        assert!(
            row.contains(token),
            "the UTS #46 row must name `{token}` — it pins a crate version because `idna` \
             publishes no Unicode version.\n\nrow: {row}"
        );
    }
}
