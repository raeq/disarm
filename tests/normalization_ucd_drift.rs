//! #642: the documented normalization UCD version cannot drift away from the
//! crate that actually implements it.
//!
//! `Cargo.toml` declares `unicode-normalization = "0.1"`, a floating requirement,
//! so a `cargo update` can move the bundled Unicode data with no disarm code
//! change at all. Three places state that version in prose — `docs/provenance.md`,
//! the `api::normalize` rustdoc, and the Python `normalize` docstring — and every
//! one of them would keep claiming the old number.
//!
//! The crate exports the answer as a `pub const`, so the claim can simply be
//! checked. A `cargo update` that moves the data now fails here rather than
//! shipping three stale sentences.

use unicode_normalization::UNICODE_VERSION;

const PROVENANCE: &str = include_str!("../docs/provenance.md");
const RUST_DOC: &str = include_str!("../src/api/text.rs");
const PYTHON_DOC: &str = include_str!("../python/disarm/_api.py");

/// `(17, 0, 0)` rendered the way the documentation writes it.
fn version() -> String {
    let (major, minor, patch) = UNICODE_VERSION;
    format!("{major}.{minor}.{patch}")
}

/// Flatten doc-comment prefixes and line wrapping so a version that straddles a
/// line break still reads as adjacent to the word before it.
fn flatten(source: &str) -> String {
    source
        .lines()
        .map(|line| line.trim().trim_start_matches("///").trim())
        .collect::<Vec<_>>()
        .join(" ")
}

/// The one `docs/provenance.md` row that is about normalization.
///
/// Scoped to the row rather than the file on purpose: the confusables row states
/// a version too, and today it happens to be the same number — so a whole-file
/// `contains` would keep passing with the normalization row left stale.
fn provenance_row() -> &'static str {
    PROVENANCE
        .lines()
        .find(|line| line.contains("unicode-normalization"))
        .expect("docs/provenance.md has no `unicode-normalization` row")
}

#[test]
fn provenance_row_states_the_crate_version() {
    let version = version();
    let row = provenance_row();
    assert!(
        row.contains(&version),
        "docs/provenance.md's normalization row does not name UCD {version}.\n\
         The crate moved; the row did not. Row was:\n  {row}"
    );
}

#[test]
fn the_rustdoc_states_the_crate_version() {
    let version = version();
    let wanted = format!("UCD {version}");
    assert!(
        flatten(RUST_DOC).contains(&wanted),
        "src/api/text.rs does not document {wanted} for `normalize`. \
         `unicode-normalization` moved and the rustdoc did not follow."
    );
}

#[test]
fn the_python_docstring_states_the_crate_version() {
    let version = version();
    let wanted = format!("UCD {version}");
    assert!(
        flatten(PYTHON_DOC).contains(&wanted),
        "python/disarm/_api.py does not document {wanted} for `normalize`. \
         `unicode-normalization` moved and the docstring did not follow."
    );
}

#[test]
fn the_three_surfaces_do_not_disagree_with_each_other() {
    // Cheap belt-and-braces: a fix applied to one file and forgotten in another
    // would pass two of the three tests above and leave the docs inconsistent.
    let version = version();
    let stated = [
        ("docs/provenance.md", provenance_row().contains(&version)),
        ("src/api/text.rs", flatten(RUST_DOC).contains(&version)),
        (
            "python/disarm/_api.py",
            flatten(PYTHON_DOC).contains(&version),
        ),
    ];
    let missing: Vec<&str> = stated
        .iter()
        .filter(|(_, found)| !found)
        .map(|(name, _)| *name)
        .collect();
    assert!(
        missing.is_empty(),
        "UCD {version} is documented in some places and not others; missing from {missing:?}"
    );
}
