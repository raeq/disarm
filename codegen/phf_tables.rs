//! The PHF emitters: `phf::Map` and `phf::Set` source for the char and string tables.

use std::collections::BTreeMap;
use std::fs;
use std::io::{BufWriter, Write};
use std::path::Path;

use super::readers::{read_char_set_tsv, read_char_str_tsv, read_str_str_tsv};

// ─── Code generators ─────────────────────────────────────────────────

/// Build a `phf::Map<char, &'static str>` source string.
pub(crate) fn build_char_str_map(entries: &BTreeMap<u32, String>, name: &str, vis: &str) -> String {
    // phf_codegen 0.13 retains the borrowed value until build(); keep the formatted
    // literals alive past the builder by collecting them first.
    let formatted: Vec<(char, String)> = entries
        .iter()
        .map(|(&cp, value)| {
            let ch = char::from_u32(cp).unwrap_or_else(|| panic!("Invalid codepoint U+{cp:04X}"));
            (ch, format!("\"{}\"", escape_str(value)))
        })
        .collect();
    let mut builder = phf_codegen::Map::<char>::new();
    for (ch, val) in &formatted {
        builder.entry(*ch, val);
    }
    let vis_prefix = if vis.is_empty() {
        String::new()
    } else {
        format!("{vis} ")
    };
    format!(
        "{vis_prefix}static {name}: phf::Map<char, &'static str> = {};\n",
        builder.build()
    )
}

/// Generate a char→str map file.
pub(crate) fn generate_char_str_map(tsv_path: &Path, out_path: &Path, name: &str, vis: &str) {
    let entries = read_char_str_tsv(tsv_path);
    let code = build_char_str_map(&entries, name, vis);
    let mut file = BufWriter::new(fs::File::create(out_path).unwrap_or_else(|e| {
        panic!("Failed to create {}: {e}", out_path.display());
    }));
    file.write_all(code.as_bytes()).unwrap();
}

/// #481: generate the compose-at-lookup widening map — a `phf::Map<&'static str, char>`
/// from a fully canonically-decomposed cluster (KA U+0915 + nukta U+093C) to its
/// composition-**excluded** precomposed scalar (QA U+0958). `compose.rs` consults it
/// after canonical NFC of a cluster: these clusters do not recompose under NFC (they are
/// exclusions), so the table is the only way they reach the precomposed entry. The key is
/// the decomposed string (the NFC of an excluded cluster equals its NFD), value the scalar.
pub(crate) fn generate_excluded_compositions_map(
    tsv_path: &Path,
    out_path: &Path,
    name: &str,
    vis: &str,
) {
    let raw = read_str_str_tsv(tsv_path);
    let formatted: Vec<(String, String)> = raw
        .iter()
        .map(|(key_hex, val_hex)| {
            let key: String = key_hex
                .split_whitespace()
                .map(|h| {
                    let cp = u32::from_str_radix(h, 16)
                        .unwrap_or_else(|e| panic!("bad decomp hex '{h}': {e}"));
                    char::from_u32(cp).unwrap_or_else(|| panic!("invalid scalar U+{cp:04X}"))
                })
                .collect();
            let cp = u32::from_str_radix(val_hex.trim(), 16)
                .unwrap_or_else(|e| panic!("bad precomposed hex '{val_hex}': {e}"));
            char::from_u32(cp).unwrap_or_else(|| panic!("invalid scalar U+{cp:04X}"));
            (key, format!("'\\u{{{cp:04X}}}'"))
        })
        .collect();
    let mut builder = phf_codegen::Map::<&str>::new();
    for (key, val) in &formatted {
        builder.entry(key.as_str(), val);
    }
    let vis_prefix = if vis.is_empty() {
        String::new()
    } else {
        format!("{vis} ")
    };
    // Longest key, in *chars* (base + marks), so the lookup-time greedy prefix scan can
    // bound itself in lockstep with the data instead of hardcoding a magic number.
    let max_key_chars = formatted
        .iter()
        .map(|(key, _)| key.chars().count())
        .max()
        .unwrap_or(0);
    // The first two chars of every key, sorted and deduplicated: a key can only match
    // where these do, so the lookup-time scan probes the map only there. Every key is a
    // base and at least one mark, which is what makes a pair a necessary condition.
    let mut heads: Vec<(char, char)> = formatted
        .iter()
        .map(|(key, _)| {
            let mut chars = key.chars();
            match (chars.next(), chars.next()) {
                (Some(a), Some(b)) => (a, b),
                _ => panic!("excluded composition key {key:?} is shorter than two chars"),
            }
        })
        .collect();
    heads.sort_unstable();
    heads.dedup();
    let heads_code: Vec<String> = heads
        .iter()
        .map(|(a, b)| {
            format!(
                "('\\u{{{:04X}}}', '\\u{{{:04X}}}')",
                u32::from(*a),
                u32::from(*b)
            )
        })
        .collect();
    let code = format!(
        "{vis_prefix}static {name}: phf::Map<&'static str, char> = {};\n\
         {vis_prefix}const {name}_MAX_KEY_CHARS: usize = {max_key_chars};\n\
         /// The first two chars of every key of `{name}`, sorted.\n\
         {vis_prefix}static {name}_HEADS: [(char, char); {}] = [{}];\n",
        builder.build(),
        heads.len(),
        heads_code.join(", ")
    );
    fs::write(out_path, code)
        .unwrap_or_else(|e| panic!("Failed to write {}: {e}", out_path.display()));
}

/// Generate a str→str map file.
pub(crate) fn generate_str_str_map(tsv_path: &Path, out_path: &Path, name: &str, vis: &str) {
    let entries = read_str_str_tsv(tsv_path);
    // phf_codegen 0.13 retains the borrowed value until build(); collect the formatted
    // literals so they outlive the builder.
    let formatted: Vec<(&str, String)> = entries
        .iter()
        .map(|(key, value)| (key.as_str(), format!("\"{}\"", escape_str(value))))
        .collect();
    let mut builder = phf_codegen::Map::<&str>::new();
    for (key, v) in &formatted {
        builder.entry(*key, v);
    }
    let vis_prefix = if vis.is_empty() {
        String::new()
    } else {
        format!("{vis} ")
    };
    let code = format!(
        "{vis_prefix}static {name}: phf::Map<&'static str, &'static str> = {};\n",
        builder.build()
    );
    let mut file = BufWriter::new(fs::File::create(out_path).unwrap_or_else(|e| {
        panic!("Failed to create {}: {e}", out_path.display());
    }));
    file.write_all(code.as_bytes()).unwrap();
}

/// Generate a char set file.
pub(crate) fn generate_char_set(tsv_path: &Path, out_path: &Path, name: &str, vis: &str) {
    let entries = read_char_set_tsv(tsv_path);
    let mut builder = phf_codegen::Set::<char>::new();
    for &cp in &entries {
        let ch = char::from_u32(cp).unwrap_or_else(|| {
            panic!("Invalid codepoint U+{cp:04X}");
        });
        builder.entry(ch);
    }
    let vis_prefix = if vis.is_empty() {
        String::new()
    } else {
        format!("{vis} ")
    };
    let code = format!(
        "{vis_prefix}static {name}: phf::Set<char> = {};\n",
        builder.build()
    );
    let mut file = BufWriter::new(fs::File::create(out_path).unwrap_or_else(|e| {
        panic!("Failed to create {}: {e}", out_path.display());
    }));
    file.write_all(code.as_bytes()).unwrap();
}

/// Escape a string for embedding in Rust source code.
pub(crate) fn escape_str(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            _ => out.push(ch),
        }
    }
    out
}
