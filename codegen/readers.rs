//! The TSV readers: every source table under `src/tables/data/` is parsed here.

use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

/// Parse an uppercase hex code point, panicking with file context on error.
pub(crate) fn parse_hex(hex: &str, path: &Path) -> u32 {
    u32::from_str_radix(hex.trim(), 16)
        .unwrap_or_else(|e| panic!("Bad hex '{hex}' in {}: {e}", path.display()))
}

// ─── Data readers ────────────────────────────────────────────────────

/// Read a `start\tend` hex range TSV (the shape `generate_range_set` consumes) as a
/// sorted, binary-searchable list. Used for build-time property lookups that ship no
/// runtime table of their own (#757).
///
/// Distinct from [`read_char_str_tsv`] below, which reads the `HEX_CODEPOINT\tvalue` map
/// shape. Two columns either way, but the second is a bound rather than a value.
pub(crate) fn read_range_tsv(path: &Path) -> Vec<(u32, u32)> {
    let content = fs::read_to_string(path)
        .unwrap_or_else(|e| panic!("Failed to read {}: {e}", path.display()));
    let mut rows: Vec<(u32, u32)> = Vec::new();
    for line in content.lines() {
        let t = line.trim();
        if t.is_empty() || t.starts_with('#') {
            continue;
        }
        let mut it = t.split('\t');
        let start = parse_hex(it.next().unwrap_or(""), path);
        let end = parse_hex(it.next().unwrap_or(""), path);
        rows.push((start, end));
    }
    rows.sort_unstable();
    rows
}

/// Read a TSV file with lines of `HEX_CODEPOINT\tvalue`.
/// Skips blank lines and lines starting with `#`.
pub(crate) fn read_char_str_tsv(path: &Path) -> BTreeMap<u32, String> {
    let content = fs::read_to_string(path)
        .unwrap_or_else(|e| panic!("Failed to read {}: {e}", path.display()));
    let mut map = BTreeMap::new();
    for line in content.lines() {
        let trimmed = line.trim_start();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }
        // Lines without a tab map to the empty string.
        // Don't trim the value — trailing spaces may be significant (e.g., U+30FB → " ").
        let (hex, value) = trimmed
            .split_once('\t')
            .unwrap_or_else(|| (trimmed.trim_end(), ""));
        let cp = u32::from_str_radix(hex.trim(), 16).unwrap_or_else(|e| {
            panic!("Bad hex '{hex}' in {}: {e}", path.display());
        });
        // Unescape Rust-style escapes from the extracted data
        map.insert(cp, unescape_rust_str(value));
    }
    map
}

/// Extract the upstream `confusables.txt` version from a confusables TSV header (#560).
///
/// The generator writes the provenance on line 1, e.g.
/// `# Unicode UTS#39 confusables.txt 17.0.0, folded to Latin, ...`. This parses the
/// `17.0.0` out of it and panics if the header no longer has that shape, so a generator
/// change that drops the version fails the build instead of silently freezing the const
/// at a stale value.
pub(crate) fn read_confusables_version(path: &Path) -> String {
    const MARKER: &str = "# Unicode UTS#39 confusables.txt ";

    let content = fs::read_to_string(path)
        .unwrap_or_else(|e| panic!("Failed to read {}: {e}", path.display()));
    let header = content.lines().next().unwrap_or_else(|| {
        panic!("{}: file is empty; expected a header line", path.display());
    });
    let rest = header.strip_prefix(MARKER).unwrap_or_else(|| {
        panic!(
            "{}: header line does not start with {MARKER:?} (got {header:?}). \
             scripts/gen_confusables.py owns this line; if its format changed, update \
             `read_confusables_version` in codegen/readers.rs in the same commit.",
            path.display()
        )
    });
    let version: String = rest
        .chars()
        .take_while(|c| c.is_ascii_digit() || *c == '.')
        .collect();

    // Require a dotted numeric version with at least two components. `confusables.txt`
    // releases are `major.minor.patch` (17.0.0); accept two-component forms too rather
    // than over-fitting, but reject an empty or malformed run outright.
    let parts: Vec<&str> = version.split('.').collect();
    assert!(
        parts.len() >= 2
            && parts
                .iter()
                .all(|p| !p.is_empty() && p.bytes().all(|b| b.is_ascii_digit())),
        "{}: expected a dotted numeric version after {MARKER:?}, got {version:?} \
         (from header {header:?})",
        path.display()
    );
    version
}

/// Read a TSV file with lines of `key\tvalue` (string keys).
pub(crate) fn read_str_str_tsv(path: &Path) -> Vec<(String, String)> {
    let content = fs::read_to_string(path)
        .unwrap_or_else(|e| panic!("Failed to read {}: {e}", path.display()));
    let mut entries = Vec::new();
    for line in content.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let (key, value) = line.split_once('\t').unwrap_or_else(|| {
            panic!("Bad line in {}: {line}", path.display());
        });
        entries.push((key.to_string(), value.to_string()));
    }
    entries
}

/// Read a file with one hex codepoint per line (set entries).
pub(crate) fn read_char_set_tsv(path: &Path) -> Vec<u32> {
    let content = fs::read_to_string(path)
        .unwrap_or_else(|e| panic!("Failed to read {}: {e}", path.display()));
    let mut entries = Vec::new();
    for line in content.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let cp = u32::from_str_radix(line, 16).unwrap_or_else(|e| {
            panic!("Bad hex '{line}' in {}: {e}", path.display());
        });
        entries.push(cp);
    }
    entries
}

/// Unescape Rust string escapes in TSV data values.
/// Handles `\"`, `\\`, `\n`, `\r`, `\t`, and `\u{XXXX}` Unicode escapes.
fn unescape_rust_str(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut chars = s.chars().peekable();
    while let Some(ch) = chars.next() {
        if ch == '\\' {
            match chars.peek() {
                Some(&'u') => {
                    chars.next(); // consume 'u'
                    assert!(
                        chars.peek() == Some(&'{'),
                        "Malformed \\u escape in TSV: expected '{{' after \\u"
                    );
                    chars.next(); // consume '{'

                    // Collect hex digits up to the closing brace, asserting it is
                    // actually present — `take_while` would silently accept a
                    // truncated `\u{XXXX` (no closing '}') by consuming to EOL.
                    let mut hex = String::new();
                    let mut closed = false;
                    for c in chars.by_ref() {
                        if c == '}' {
                            closed = true;
                            break;
                        }
                        hex.push(c);
                    }
                    assert!(
                        closed,
                        "Malformed \\u escape in TSV: missing closing '}}' (got '\\u{{{hex}')"
                    );
                    let cp = u32::from_str_radix(&hex, 16).unwrap_or_else(|e| {
                        panic!("Invalid hex in \\u{{...}} escape: '{hex}': {e}");
                    });
                    let c = char::from_u32(cp).unwrap_or_else(|| {
                        panic!("Invalid Unicode scalar value: U+{cp:04X}");
                    });
                    out.push(c);
                }
                Some(&'"') => {
                    chars.next();
                    out.push('"');
                }
                Some(&'\\') => {
                    chars.next();
                    out.push('\\');
                }
                Some(&'n') => {
                    chars.next();
                    out.push('\n');
                }
                Some(&'r') => {
                    chars.next();
                    out.push('\r');
                }
                Some(&'t') => {
                    chars.next();
                    out.push('\t');
                }
                None => out.push('\\'),
                Some(&other) => {
                    chars.next();
                    out.push('\\');
                    out.push(other);
                }
            }
        } else {
            out.push(ch);
        }
    }
    out
}
