//! The sorted range and array tables the runtime binary-searches: bidi class,
//! width, emoji and script ranges, the confusable census and the decimal zeros.

use std::fmt::Write as _;
use std::fs;
use std::path::Path;

use super::readers::parse_hex;

/// Generate `BIDI_STRONG_RANGES: &[(u32, u32, u8)]` from `bidi_strong_ranges.tsv`.
/// Class encoding: 0 = strong LTR (`Bidi_Class L`), 1 = strong RTL (`R` or `AL`). A code
/// point absent from the table has no strong direction (#773).
pub(crate) fn generate_bidi_strong_ranges(tsv_path: &Path, out_path: &Path) {
    let content = fs::read_to_string(tsv_path)
        .unwrap_or_else(|e| panic!("Failed to read {}: {e}", tsv_path.display()));
    let mut rows: Vec<(u32, u32, u8)> = Vec::new();
    for line in content.lines() {
        let t = line.trim();
        if t.is_empty() || t.starts_with('#') {
            continue;
        }
        let mut it = t.split('\t');
        let start = parse_hex(it.next().unwrap_or(""), tsv_path);
        let end = parse_hex(it.next().unwrap_or(""), tsv_path);
        let class = match it.next().unwrap_or("") {
            "L" => 0u8,
            "R" => 1u8,
            other => panic!("{}: unknown bidi class {other:?}", tsv_path.display()),
        };
        rows.push((start, end, class));
    }
    rows.sort_unstable();
    let mut code = String::from("static BIDI_STRONG_RANGES: &[(u32, u32, u8)] = &[\n");
    for (s, e, c) in &rows {
        writeln!(
            code,
            "    (0x{:04X}_{:04X}, 0x{:04X}_{:04X}, {c}),",
            s >> 16,
            s & 0xFFFF,
            e >> 16,
            e & 0xFFFF
        )
        .unwrap();
    }
    code.push_str("];\n");
    fs::write(out_path, code).unwrap_or_else(|e| panic!("write {}: {e}", out_path.display()));
}

/// Generate `WIDTH_RANGES: &[(u32, u32, u8)]` from `char_width.tsv`.
/// Class encoding: 0 = zero-width, 2 = wide, 3 = ambiguous. Narrow (1) is the
/// default for code points not present in the table.
pub(crate) fn generate_width_ranges(tsv_path: &Path, out_path: &Path) {
    let content = fs::read_to_string(tsv_path)
        .unwrap_or_else(|e| panic!("Failed to read {}: {e}", tsv_path.display()));
    let mut rows: Vec<(u32, u32, u8)> = Vec::new();
    for line in content.lines() {
        let t = line.trim();
        if t.is_empty() || t.starts_with('#') {
            continue;
        }
        let mut it = t.split('\t');
        let start = parse_hex(it.next().unwrap_or(""), tsv_path);
        let end = parse_hex(it.next().unwrap_or(""), tsv_path);
        let class = match it.next().unwrap_or("").trim() {
            "Z" => 0u8,
            "W" => 2,
            "A" => 3,
            other => panic!("bad width class {other:?} in {}", tsv_path.display()),
        };
        rows.push((start, end, class));
    }
    rows.sort_unstable();
    let mut code = String::from("static WIDTH_RANGES: &[(u32, u32, u8)] = &[\n");
    for (s, e, c) in &rows {
        writeln!(code, "    ({s}, {e}, {c}),").unwrap();
    }
    code.push_str("];\n");
    fs::write(out_path, code).unwrap_or_else(|e| panic!("write {}: {e}", out_path.display()));
}

/// Emit the per-script confusable prototype census (#963) as a sorted static.
///
/// Sorted by script name so the lookup can binary-search, and totals asserted here
/// rather than at runtime: a census whose rows no longer sum to the source population
/// is describing a different table than the one that ships beside it.
pub(crate) fn generate_prototype_census(tsv_path: &Path, out_path: &Path) {
    let content = fs::read_to_string(tsv_path)
        .unwrap_or_else(|e| panic!("Failed to read {}: {e}", tsv_path.display()));
    let mut rows: Vec<(String, u32, u32)> = Vec::new();
    for line in content.lines() {
        let t = line.trim();
        if t.is_empty() || t.starts_with('#') {
            continue;
        }
        let mut it = t.split('\t');
        let script = it.next().unwrap_or("").to_string();
        let sources: u32 = it
            .next()
            .and_then(|f| f.parse().ok())
            .unwrap_or_else(|| panic!("Bad `sources` field in {}: {t}", tsv_path.display()));
        let folded: u32 = it
            .next()
            .and_then(|f| f.parse().ok())
            .unwrap_or_else(|| panic!("Bad `folded` field in {}: {t}", tsv_path.display()));
        assert!(
            folded <= sources,
            "{}: {script} folds {folded} of {sources} sources",
            tsv_path.display()
        );
        assert!(
            !script.is_empty() && script.is_ascii(),
            "{}: script name must be non-empty ASCII, got {script:?}",
            tsv_path.display()
        );
        rows.push((script, sources, folded));
    }
    let total: u32 = rows.iter().map(|(_, s, _)| s).sum();
    assert_eq!(
        total,
        6565,
        "{}: rows sum to {total} sources, not the 6,565 single-code-point sources in \
         confusables.txt — regenerate with scripts/gen_confusable_census.py",
        tsv_path.display()
    );
    rows.sort_unstable();
    // The lookup binary-searches this table, which is only meaningful if each script
    // appears once. A duplicated row would make the answer depend on where the search
    // landed, and the total assert above cannot see a row that was split in two.
    for pair in rows.windows(2) {
        assert_ne!(
            pair[0].0,
            pair[1].0,
            "{}: script {:?} has more than one row",
            tsv_path.display(),
            pair[0].0
        );
    }
    let mut code =
        String::from("pub(crate) static CONFUSABLE_PROTOTYPE_CENSUS: &[(&str, u32, u32)] = &[\n");
    for (script, sources, folded) in &rows {
        writeln!(code, "    (\"{script}\", {sources}, {folded}),").unwrap();
    }
    code.push_str("];\n");
    fs::write(out_path, code)
        .unwrap_or_else(|e| panic!("Failed to write {}: {e}", out_path.display()));
}

/// Generate `NAME: &[(u32, u32)]` (sorted inclusive ranges) from a 2-column TSV.
pub(crate) fn generate_range_set(tsv_path: &Path, out_path: &Path, name: &str) {
    let content = fs::read_to_string(tsv_path)
        .unwrap_or_else(|e| panic!("Failed to read {}: {e}", tsv_path.display()));
    let mut rows: Vec<(u32, u32)> = Vec::new();
    for line in content.lines() {
        let t = line.trim();
        if t.is_empty() || t.starts_with('#') {
            continue;
        }
        let mut it = t.split('\t');
        let start = parse_hex(it.next().unwrap_or(""), tsv_path);
        let end = parse_hex(it.next().unwrap_or(""), tsv_path);
        rows.push((start, end));
    }
    rows.sort_unstable();
    // Hex, not decimal: these are code points, so hex is the readable form, and it also
    // keeps clippy's `unreadable_literal` quiet on the astral ranges (#774) without an
    // `allow` at the include site.
    let mut code = format!("static {name}: &[(u32, u32)] = &[\n");
    for (s, e) in &rows {
        writeln!(
            code,
            "    (0x{:04X}_{:04X}, 0x{:04X}_{:04X}),",
            s >> 16,
            s & 0xFFFF,
            e >> 16,
            e & 0xFFFF
        )
        .unwrap();
    }
    code.push_str("];\n");
    fs::write(out_path, code).unwrap_or_else(|e| panic!("write {}: {e}", out_path.display()));
}

/// Emit the decimal-numbering-system zeros as a sorted array (#777).
///
/// A system spans ten code points from its zero, so the array is the whole table: a digit
/// belongs to the system whose zero is `cp - decimal_value`. Sorted so the lookup can
/// binary-search, and asserted sorted here rather than trusted, since the TSV is
/// hand-regenerated.
pub(crate) fn generate_decimal_digit_zeros(path: &Path, out: &Path) {
    let content = fs::read_to_string(path)
        .unwrap_or_else(|e| panic!("Failed to read {}: {e}", path.display()));
    let mut zeros: Vec<u32> = Vec::new();
    for line in content.lines() {
        let trimmed = line.trim_start();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }
        let hex = trimmed.split('\t').next().unwrap_or("").trim();
        zeros.push(u32::from_str_radix(hex, 16).unwrap_or_else(|e| {
            panic!("Bad hex '{hex}' in {}: {e}", path.display());
        }));
    }
    assert!(
        !zeros.is_empty(),
        "{}: no decimal numbering systems",
        path.display()
    );
    assert!(
        zeros.windows(2).all(|w| w[0] < w[1]),
        "{}: rows must be sorted and unique for the binary search",
        path.display()
    );
    // Every system is ten wide, and two must not overlap — the model the lookup assumes.
    assert!(
        zeros.windows(2).all(|w| w[1] - w[0] >= 10),
        "{}: two numbering systems are less than ten code points apart, so the \
         ten-wide span assumption no longer holds",
        path.display()
    );
    let body = zeros
        .iter()
        .map(|z| format!("    0x{z:04X},"))
        .collect::<Vec<_>>()
        .join("\n");
    fs::write(
        out,
        format!(
            "// Generated by build.rs from {}. Do not edit.\n\
             pub(crate) static DECIMAL_DIGIT_ZEROS: [u32; {}] = [\n{}\n];\n",
            path.file_name().unwrap().to_string_lossy(),
            zeros.len(),
            body
        ),
    )
    .unwrap();
}
