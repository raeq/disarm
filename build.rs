//! Build script: generates PHF (perfect hash function) maps from data files.
//!
//! This avoids proc-macro overhead (`phf_macros`) by running the PHF
//! computation once during `build.rs`, writing the generated Rust code
//! to `$OUT_DIR`. Source files then `include!()` the output.
//!
//! Data files live in `src/tables/data/` as simple TSV (tab-separated):
//!   - char→str maps: `HEXCODEPOINT\tvalue`
//!   - str→str maps:  `key\tvalue`
//!   - char sets:      `HEXCODEPOINT`

use std::collections::BTreeMap;
use std::env;
use std::fmt::Write as _;
use std::fs;
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};

fn main() {
    let out_dir = PathBuf::from(env::var("OUT_DIR").unwrap());
    let data_dir = Path::new("src/tables/data");

    // Tell Cargo to re-run only when data files change
    println!("cargo:rerun-if-changed=src/tables/data");
    println!("cargo:rerun-if-changed=build.rs");

    // --- Hanzi Pinyin ---
    {
        let entries = read_char_str_tsv(&data_dir.join("hanzi_pinyin.tsv"));
        assert!(
            entries.len() >= 20_000,
            "hanzi_pinyin.tsv: expected ≥20,000 entries, got {}",
            entries.len()
        );
        for (&cp, value) in &entries {
            assert!(
                value.is_ascii(),
                "hanzi_pinyin.tsv: non-ASCII value {value:?} for U+{cp:04X}"
            );
        }
        let code = build_char_str_map(&entries, "HANZI_PINYIN", "pub");
        fs::write(out_dir.join("hanzi_pinyin_phf.rs"), code).unwrap();
    }

    // --- Hanzi Pinyin (toned) ---
    generate_char_str_map(
        &data_dir.join("hanzi_pinyin_toned.tsv"),
        &out_dir.join("hanzi_pinyin_toned_phf.rs"),
        "HANZI_PINYIN_TONED",
        "pub",
    );

    // --- Confusables (Latin target) ---
    {
        let entries = read_char_str_tsv(&data_dir.join("confusables_to_latin.tsv"));
        assert!(
            entries.len() >= 1_000,
            "confusables_to_latin.tsv: expected ≥1,000 entries, got {}",
            entries.len()
        );
        let code = build_char_str_map(&entries, "TO_LATIN", "");
        fs::write(out_dir.join("confusables_phf.rs"), code).unwrap();
    }

    // --- Confusables (Cyrillic target) ---
    {
        let entries = read_char_str_tsv(&data_dir.join("confusables_to_cyrillic.tsv"));
        assert!(
            !entries.is_empty(),
            "confusables_to_cyrillic.tsv: expected ≥1 entries, got 0",
        );
        let code = build_char_str_map(&entries, "TO_CYRILLIC", "");
        fs::write(out_dir.join("confusables_to_cyrillic_phf.rs"), code).unwrap();
    }

    // --- Emoji ---
    generate_char_str_map(
        &data_dir.join("emoji_single.tsv"),
        &out_dir.join("emoji_single_phf.rs"),
        "EMOJI_SINGLE",
        "pub",
    );
    generate_str_str_map(
        &data_dir.join("emoji_multi.tsv"),
        &out_dir.join("emoji_multi_phf.rs"),
        "EMOJI_MULTI",
        "pub",
    );
    generate_char_set(
        &data_dir.join("emoji_starters.tsv"),
        &out_dir.join("emoji_starters_phf.rs"),
        "EMOJI_MULTI_STARTERS",
        "pub",
    );

    // --- Case Folding (full Unicode CaseFolding.txt) ---
    generate_char_str_map(
        &data_dir.join("case_folding.tsv"),
        &out_dir.join("case_folding_phf.rs"),
        "CASE_FOLD",
        "pub",
    );

    // --- Transliteration: default table (flat BMP array) ---
    {
        let default_entries = read_char_str_tsv(&data_dir.join("translit_default.tsv"));
        assert!(
            default_entries.len() >= 5_000,
            "translit_default.tsv: expected ≥5,000 entries, got {}",
            default_entries.len()
        );
        for (&cp, value) in &default_entries {
            assert!(
                value.is_ascii(),
                "translit_default.tsv: non-ASCII value {value:?} for U+{cp:04X}"
            );
        }
    }
    generate_translit_flat_array(
        &data_dir.join("translit_default.tsv"),
        &out_dir.join("translit_default_flat.rs"),
    );

    // --- Transliteration: SMP default table (ancient/historic scripts above U+FFFF) ---
    {
        let smp_entries = read_char_str_tsv(&data_dir.join("translit_default_smp.tsv"));
        for (&cp, value) in &smp_entries {
            assert!(
                value.is_ascii(),
                "translit_default_smp.tsv: non-ASCII value {value:?} for U+{cp:04X}"
            );
        }
    }
    generate_char_str_map(
        &data_dir.join("translit_default_smp.tsv"),
        &out_dir.join("translit_default_smp_phf.rs"),
        "DEFAULT_SMP",
        "",
    );

    // --- Transliteration: language-specific tables ---
    // Auto-discover language override tables by scanning the data dir, so adding a
    // language is just dropping in a `translit_lang_<code>.tsv` file — no hand-edit of a
    // hardcoded list that could silently drop a language (#74). The const name is the
    // file stem upper-cased (`lang_de` → `LANG_DE`), matching the names the dispatch in
    // `src/tables/transliteration.rs` references. The two romanization *standards*
    // (iso9, gost7034) are not languages, so they stay explicit.
    let mut lang_tables: Vec<(String, String)> = Vec::new();
    for entry in fs::read_dir(data_dir).expect("read src/tables/data") {
        let name = entry
            .expect("data dir entry")
            .file_name()
            .to_string_lossy()
            .into_owned();
        if let Some(code) = name
            .strip_prefix("translit_lang_")
            .and_then(|s| s.strip_suffix(".tsv"))
        {
            let file_stem = format!("lang_{code}");
            let const_name = file_stem.to_uppercase();
            lang_tables.push((file_stem, const_name));
        }
    }
    assert!(
        lang_tables.len() >= 20,
        "expected ≥20 translit_lang_*.tsv override tables, found {} — wrong data dir?",
        lang_tables.len()
    );
    lang_tables.push(("iso9".to_string(), "ISO9".to_string()));
    lang_tables.push(("gost7034".to_string(), "GOST7034".to_string()));
    // Deterministic order → reproducible generated output.
    lang_tables.sort();

    // Generate each language table to its own file, then combine
    let mut all_lang_code = String::new();
    for (file_stem, const_name) in &lang_tables {
        let tsv_path = data_dir.join(format!("translit_{file_stem}.tsv"));
        let entries = read_char_str_tsv(&tsv_path);
        for (&cp, value) in &entries {
            assert!(
                value.is_ascii(),
                "translit_{file_stem}.tsv: non-ASCII value {value:?} for U+{cp:04X}"
            );
        }
        all_lang_code.push_str(&build_char_str_map(&entries, const_name, ""));
        all_lang_code.push('\n');
    }

    let lang_out = out_dir.join("translit_langs_phf.rs");
    fs::write(&lang_out, all_lang_code).unwrap_or_else(|e| {
        panic!("Failed to write {}: {e}", lang_out.display());
    });

    // --- Reverse transliteration tables ---
    let reverse_tables = [
        ("reverse_ru", "REVERSE_RU"),
        ("reverse_uk", "REVERSE_UK"),
        ("reverse_el", "REVERSE_EL"),
    ];

    let mut all_reverse_code = String::new();
    for (file_stem, const_name) in &reverse_tables {
        let tsv_path = data_dir.join(format!("{file_stem}.tsv"));
        let entries = read_str_str_tsv(&tsv_path);
        // phf_codegen 0.13 retains the borrowed value until build(), so the formatted
        // literals must outlive the builder — collect them first.
        let formatted: Vec<(&str, String)> = entries
            .iter()
            .map(|(key, value)| (key.as_str(), format!("\"{}\"", escape_str(value))))
            .collect();
        let mut builder = phf_codegen::Map::<&str>::new();
        for (key, v) in &formatted {
            builder.entry(*key, v);
        }
        write!(
            all_reverse_code,
            "static {const_name}: phf::Map<&'static str, &'static str> = {};\n\n",
            builder.build()
        )
        .unwrap();
    }

    let reverse_out = out_dir.join("reverse_translit_phf.rs");
    fs::write(&reverse_out, all_reverse_code).unwrap_or_else(|e| {
        panic!("Failed to write {}: {e}", reverse_out.display());
    });
}

// ─── Data readers ────────────────────────────────────────────────────

/// Read a TSV file with lines of `HEX_CODEPOINT\tvalue`.
/// Skips blank lines and lines starting with `#`.
fn read_char_str_tsv(path: &Path) -> BTreeMap<u32, String> {
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
        let (hex, value) = trimmed.split_once('\t').unwrap_or((trimmed.trim_end(), ""));
        let cp = u32::from_str_radix(hex.trim(), 16).unwrap_or_else(|e| {
            panic!("Bad hex '{hex}' in {}: {e}", path.display());
        });
        // Unescape Rust-style escapes from the extracted data
        map.insert(cp, unescape_rust_str(value));
    }
    map
}

/// Read a TSV file with lines of `key\tvalue` (string keys).
fn read_str_str_tsv(path: &Path) -> Vec<(String, String)> {
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
fn read_char_set_tsv(path: &Path) -> Vec<u32> {
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

// ─── Code generators ─────────────────────────────────────────────────

/// Build a `phf::Map<char, &'static str>` source string.
fn build_char_str_map(entries: &BTreeMap<u32, String>, name: &str, vis: &str) -> String {
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
fn generate_char_str_map(tsv_path: &Path, out_path: &Path, name: &str, vis: &str) {
    let entries = read_char_str_tsv(tsv_path);
    let code = build_char_str_map(&entries, name, vis);
    let mut file = BufWriter::new(fs::File::create(out_path).unwrap_or_else(|e| {
        panic!("Failed to create {}: {e}", out_path.display());
    }));
    file.write_all(code.as_bytes()).unwrap();
}

/// Generate a str→str map file.
fn generate_str_str_map(tsv_path: &Path, out_path: &Path, name: &str, vis: &str) {
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
fn generate_char_set(tsv_path: &Path, out_path: &Path, name: &str, vis: &str) {
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

/// Generate a flat `Option<&'static str>` array for BMP transliteration.
///
/// Instead of a PHF map, this produces an array indexed by `(codepoint - 0x80)`.
/// Lookup becomes a bounds check + pointer dereference — no hashing.
/// The array covers U+0080–U+FFFF (65,408 slots).
fn generate_translit_flat_array(tsv_path: &Path, out_path: &Path) {
    const BASE: u32 = 0x80;
    const SIZE: u32 = 0x10000 - BASE; // 65,408

    let entries = read_char_str_tsv(tsv_path);

    let mut file = BufWriter::new(fs::File::create(out_path).unwrap_or_else(|e| {
        panic!("Failed to create {}: {e}", out_path.display());
    }));

    writeln!(
        file,
        "/// Flat BMP transliteration array: index = (codepoint - 0x80)."
    )
    .unwrap();
    writeln!(file, "/// Generated by build.rs from translit_default.tsv.").unwrap();
    writeln!(
        file,
        "static DEFAULT_BMP: [Option<&'static str>; {SIZE}] = ["
    )
    .unwrap();

    for cp in BASE..0x10000 {
        if let Some(value) = entries.get(&cp) {
            writeln!(file, "    Some(\"{}\"),", escape_str(value)).unwrap();
        } else {
            writeln!(file, "    None,").unwrap();
        }
    }

    writeln!(file, "];").unwrap();
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

/// Escape a string for embedding in Rust source code.
fn escape_str(s: &str) -> String {
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
