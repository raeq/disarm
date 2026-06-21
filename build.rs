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
            assert!(
                (0x4E00..=0x9FFF).contains(&cp),
                "hanzi_pinyin.tsv: U+{cp:04X} outside the CJK Unified block; \
                 the dense table (#237 item 2) covers only U+4E00–U+9FFF"
            );
        }
        // #237 item 2: the toneless table is ~99.7% dense over U+4E00–U+9FFF
        // (20,924 of 20,992 cps), so a flat interned id array beats a PHF on both
        // size (~50 KB vs ~600 KB) and lookup cost (no hashing). The sparse toned
        // table below stays a PHF.
        let code = build_dense_interned_array(
            &entries,
            0x4E00,
            0x9FFF - 0x4E00 + 1,
            "HANZI_PINYIN",
            "pub",
        );
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
    // H1 invariant (#38): `api::normalize_confusables` / `api::is_confusable` are
    // infallible because every `TargetScript` variant maps to a populated table.
    // build.rs is a separate compilation unit and cannot call the crate's
    // `resolve_confusable_map`, so the guarantee is encoded here: these two blocks
    // assert the source TSVs backing the Latin and Cyrillic maps are non-empty. If
    // either were ever dropped, this build fails rather than the Layer-2 `.expect()`
    // panicking at runtime.
    {
        let mut entries = read_char_str_tsv(&data_dir.join("confusables_to_latin.tsv"));
        // #481: a canonical singleton resolves as its target. Add the row only when the
        // target itself folds (is already a confusable) — that is the real recovery gap
        // (U+1F77 GREEK IOTA WITH OXIA should fold like its tonos form U+03AF). When the
        // target does NOT fold, the singleton is a benign passthrough re-encoding (two
        // encodings of the same non-Latin letter); minting a row there would put a
        // non-Latin value in the to-Latin table and make the fold a partial normalizer.
        inject_folding_singleton_rows(&data_dir.join("canonical_singletons.tsv"), &mut entries);
        assert!(
            entries.len() >= 1_000,
            "confusables_to_latin.tsv: expected ≥1,000 entries, got {}",
            entries.len()
        );
        let code = build_char_str_map(&entries, "TO_LATIN", "");
        fs::write(out_dir.join("confusables_phf.rs"), code).unwrap();

        // ASCII confusable sources for the preset fast-path guard (#458). The
        // guard skips the whole pipeline on benign input that no step can change;
        // it must therefore know which ASCII bytes the confusable fold rewrites
        // (today 0x22 `"`→`''`, 0x60 `` ` ``→`'`, 0x7C `|`→`l`). Derive that set
        // from the data here, as a `[bool; 128]`, so it can never silently rot if
        // the table gains or drops an ASCII source — the guard stays pure byte
        // arithmetic at runtime while staying in lockstep with the PHF data.
        let mut ascii = [false; 128];
        for (&cp, value) in &entries {
            if cp < 128 && *value != char::from_u32(cp).unwrap().to_string() {
                ascii[cp as usize] = true;
            }
        }
        let flags: String = ascii
            .iter()
            .map(|b| if *b { "true," } else { "false," })
            .collect();
        fs::write(
            out_dir.join("ascii_confusable_latin.rs"),
            format!(
                "// Generated by build.rs (#458). ASCII codepoints (0x00–0x7F) the\n\
                 // confusables→latin map rewrites; used by the preset fast-path guard.\n\
                 pub(crate) static ASCII_CONFUSABLE_LATIN: [bool; 128] = [{flags}];\n"
            ),
        )
        .unwrap();
    }

    // --- Confusables (Cyrillic target) ---
    {
        let mut entries = read_char_str_tsv(&data_dir.join("confusables_to_cyrillic.tsv"));
        inject_folding_singleton_rows(&data_dir.join("canonical_singletons.tsv"), &mut entries);
        assert!(
            !entries.is_empty(),
            "confusables_to_cyrillic.tsv: expected ≥1 entries, got 0",
        );
        let code = build_char_str_map(&entries, "TO_CYRILLIC", "");
        fs::write(out_dir.join("confusables_to_cyrillic_phf.rs"), code).unwrap();
    }

    // --- Excluded compositions (compose-at-lookup widening, #481) ---
    // Base+mark composition exclusions (KA+nukta → QA, shin+sin-dot → U+FB2B) that
    // canonical NFC does not recompose, so #479's compose-at-lookup misses them. Consulted
    // in `compose.rs` after NFC of a cluster. Shared by confusables and transliterate.
    generate_excluded_compositions_map(
        &data_dir.join("excluded_compositions.tsv"),
        &out_dir.join("excluded_compositions_phf.rs"),
        "EXCLUDED_COMPOSITIONS",
        "pub(crate)",
    );

    // --- Emoji ---
    generate_char_str_map(
        &data_dir.join("emoji_single.tsv"),
        &out_dir.join("emoji_single_phf.rs"),
        "EMOJI_SINGLE",
        "pub",
    );
    // Production matcher (#242 item 4): compact code-point trie.
    generate_emoji_trie(
        &data_dir.join("emoji_multi.tsv"),
        &out_dir.join("emoji_multi_trie.rs"),
        "EMOJI_MULTI_TRIE",
    );
    // The hex-key PHF is retained as the test-only equivalence oracle (it is
    // `#[cfg(test)]`-gated at the include site, so it is not in the shipped
    // binary — that is the table-size win).
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

    // --- Terminal-width tables (#224): sorted, binary-searched range tables ---
    generate_width_ranges(
        &data_dir.join("char_width.tsv"),
        &out_dir.join("char_width_ranges.rs"),
    );
    generate_range_set(
        &data_dir.join("emoji_presentation.tsv"),
        &out_dir.join("emoji_presentation_ranges.rs"),
        "EMOJI_PRESENTATION_RANGES",
    );
}

/// Generate `WIDTH_RANGES: &[(u32, u32, u8)]` from `char_width.tsv`.
/// Class encoding: 0 = zero-width, 2 = wide, 3 = ambiguous. Narrow (1) is the
/// default for code points not present in the table.
fn generate_width_ranges(tsv_path: &Path, out_path: &Path) {
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

/// Generate `NAME: &[(u32, u32)]` (sorted inclusive ranges) from a 2-column TSV.
fn generate_range_set(tsv_path: &Path, out_path: &Path, name: &str) {
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
    let mut code = format!("static {name}: &[(u32, u32)] = &[\n");
    for (s, e) in &rows {
        writeln!(code, "    ({s}, {e}),").unwrap();
    }
    code.push_str("];\n");
    fs::write(out_path, code).unwrap_or_else(|e| panic!("write {}: {e}", out_path.display()));
}

/// Parse an uppercase hex code point, panicking with file context on error.
fn parse_hex(hex: &str, path: &Path) -> u32 {
    u32::from_str_radix(hex.trim(), 16)
        .unwrap_or_else(|e| panic!("Bad hex '{hex}' in {}: {e}", path.display()))
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

/// Generate a dense interned table over a contiguous codepoint range
/// `[base, base + len)`: a `[u16; len]` id array (indexed by `cp - base`) plus a
/// `[&'static str; K]` value table where **id 0 = `""` = no entry**. Far smaller
/// than a PHF or a `[&str; len]` when values repeat heavily, and the lookup is a
/// flat index with no hashing (#237 item 2). Emits `<name>_VALUES`, `<name>_IDS`,
/// and `<name>_BASE`.
fn build_dense_interned_array(
    entries: &BTreeMap<u32, String>,
    base: u32,
    len: usize,
    name: &str,
    vis: &str,
) -> String {
    let mut values: Vec<&str> = vec![""]; // id 0 = no entry / hole
    let mut id_of: std::collections::HashMap<&str, u16> = std::collections::HashMap::new();
    let mut ids: Vec<u16> = vec![0u16; len];
    for (&cp, value) in entries {
        let off = cp
            .checked_sub(base)
            .filter(|&o| (o as usize) < len)
            .unwrap_or_else(|| panic!("U+{cp:04X} outside dense range [{base:#X}, +{len})"));
        let id = *id_of.entry(value.as_str()).or_insert_with(|| {
            let next = u16::try_from(values.len()).expect("interned value count exceeds u16");
            values.push(value.as_str());
            next
        });
        ids[off as usize] = id;
    }
    let vis_prefix = if vis.is_empty() {
        String::new()
    } else {
        format!("{vis} ")
    };
    let mut out = String::with_capacity(len * 6 + values.len() * 8);
    writeln!(
        out,
        "{vis_prefix}static {name}_VALUES: [&str; {}] = [",
        values.len()
    )
    .unwrap();
    for v in &values {
        writeln!(out, "    \"{}\",", escape_str(v)).unwrap();
    }
    out.push_str("];\n");
    writeln!(out, "{vis_prefix}static {name}_IDS: [u16; {len}] = [").unwrap();
    for (i, id) in ids.iter().enumerate() {
        if i % 32 == 0 {
            out.push_str("    ");
        }
        write!(out, "{id},").unwrap();
        if i % 32 == 31 {
            out.push('\n');
        }
    }
    out.push_str("\n];\n");
    writeln!(out, "{vis_prefix}const {name}_BASE: u32 = {base:#X};").unwrap();
    out
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

/// #481: inject "real" canonical-singleton rows into a char→str fold table. For each
/// singleton `s → g` (from `canonical_singletons.tsv`), give `s` the same value as `g`
/// **only when `g` already folds** (has an entry). That is the real recovery gap — the
/// raw singleton should fold exactly as its canonical target (U+1F77 GREEK IOTA WITH
/// OXIA → "i", like its tonos form U+03AF). When `g` does not fold, `s` is a benign
/// passthrough re-encoding (same non-target letter, two encodings); a row there would
/// put a foreign-script value in the table and turn the fold into a partial normalizer,
/// so it is skipped (carved out in the form-invariance oracle instead). Never overrides
/// a curated row.
fn inject_folding_singleton_rows(singletons_path: &Path, entries: &mut BTreeMap<u32, String>) {
    for (s_hex, g_hex) in read_str_str_tsv(singletons_path) {
        let s = u32::from_str_radix(s_hex.trim(), 16)
            .unwrap_or_else(|e| panic!("bad singleton hex '{s_hex}': {e}"));
        let g = u32::from_str_radix(g_hex.trim(), 16)
            .unwrap_or_else(|e| panic!("bad singleton hex '{g_hex}': {e}"));
        if entries.contains_key(&s) {
            continue;
        }
        if let Some(value) = entries.get(&g).cloned() {
            entries.insert(s, value);
        }
    }
}

/// #481: generate the compose-at-lookup widening map — a `phf::Map<&'static str, char>`
/// from a fully canonically-decomposed cluster (KA U+0915 + nukta U+093C) to its
/// composition-**excluded** precomposed scalar (QA U+0958). `compose.rs` consults it
/// after canonical NFC of a cluster: these clusters do not recompose under NFC (they are
/// exclusions), so the table is the only way they reach the precomposed entry. The key is
/// the decomposed string (the NFC of an excluded cluster equals its NFD), value the scalar.
fn generate_excluded_compositions_map(tsv_path: &Path, out_path: &Path, name: &str, vis: &str) {
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
    let code = format!(
        "{vis_prefix}static {name}: phf::Map<&'static str, char> = {};\n",
        builder.build()
    );
    fs::write(out_path, code)
        .unwrap_or_else(|e| panic!("Failed to write {}: {e}", out_path.display()));
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

/// Generate a flattened codepoint trie for the multi-codepoint emoji sequences
/// (#242 item 4). Each `HEX_HEX_…` key in `emoji_multi.tsv` is parsed into a
/// code-point sequence and inserted into a trie; the matcher then walks one
/// forward path per input position with no per-probe hex-key construction, and
/// the table shrinks (codepoint edges vs fat hex-underscore string keys —
/// subsuming the cluster-C item-5 finding).
///
/// Emits, for `name = EMOJI_MULTI_TRIE`: `<name>_EDGE_START: [u32; nodes + 1]`
/// (node `i`'s edges are `[EDGE_START[i], EDGE_START[i + 1])`), `<name>_EDGE_CP`
/// (edge code points, **sorted** within each node), `<name>_EDGE_TARGET` (child
/// node id per edge), `<name>_NODE_VALUE` (value index into VALUES, or `u32::MAX`
/// for a non-terminal node), and `<name>_VALUES: [&str; …]` (deduped names).
/// Node 0 is the root.
fn generate_emoji_trie(tsv_path: &Path, out_path: &Path, name: &str) {
    struct Node {
        edges: BTreeMap<u32, usize>,
        value: Option<usize>,
    }
    fn emit_u32(out: &mut String, arr: &[u32], decl: &str) {
        out.push_str(decl);
        for (i, v) in arr.iter().enumerate() {
            if i % 16 == 0 {
                out.push_str("\n    ");
            }
            write!(out, "{v},").unwrap();
        }
        out.push_str("\n];\n");
    }

    let entries = read_str_str_tsv(tsv_path);
    let mut nodes: Vec<Node> = vec![Node {
        edges: BTreeMap::new(),
        value: None,
    }];
    let mut value_of: BTreeMap<String, usize> = BTreeMap::new();
    let mut values: Vec<String> = Vec::new();

    for (key, emoji_name) in &entries {
        let mut node = 0usize;
        for hex in key.split('_') {
            let cp = u32::from_str_radix(hex, 16).unwrap_or_else(|_| {
                panic!("emoji_multi.tsv: bad hex code point {hex:?} in {key:?}")
            });
            node = if let Some(&child) = nodes[node].edges.get(&cp) {
                child
            } else {
                let child = nodes.len();
                nodes.push(Node {
                    edges: BTreeMap::new(),
                    value: None,
                });
                nodes[node].edges.insert(cp, child);
                child
            };
        }
        let vidx = *value_of.entry(emoji_name.clone()).or_insert_with(|| {
            values.push(emoji_name.clone());
            values.len() - 1
        });
        nodes[node].value = Some(vidx);
    }

    // Flatten (BTreeMap iterates edges in sorted code-point order).
    let mut edge_start: Vec<u32> = Vec::with_capacity(nodes.len() + 1);
    let mut edge_cp: Vec<u32> = Vec::new();
    let mut edge_target: Vec<u32> = Vec::new();
    let mut node_value: Vec<u32> = Vec::with_capacity(nodes.len());
    for node in &nodes {
        edge_start.push(u32::try_from(edge_cp.len()).expect("edge count fits u32"));
        for (&cp, &child) in &node.edges {
            edge_cp.push(cp);
            edge_target.push(u32::try_from(child).expect("node id fits u32"));
        }
        node_value.push(node.value.map_or(u32::MAX, |v| {
            u32::try_from(v).expect("value index fits u32")
        }));
    }
    edge_start.push(u32::try_from(edge_cp.len()).expect("edge count fits u32"));

    let mut out = String::with_capacity(edge_cp.len() * 8 + values.len() * 16);
    emit_u32(
        &mut out,
        &edge_start,
        &format!(
            "pub static {name}_EDGE_START: [u32; {}] = [",
            edge_start.len()
        ),
    );
    emit_u32(
        &mut out,
        &edge_cp,
        &format!("pub static {name}_EDGE_CP: [u32; {}] = [", edge_cp.len()),
    );
    emit_u32(
        &mut out,
        &edge_target,
        &format!(
            "pub static {name}_EDGE_TARGET: [u32; {}] = [",
            edge_target.len()
        ),
    );
    emit_u32(
        &mut out,
        &node_value,
        &format!(
            "pub static {name}_NODE_VALUE: [u32; {}] = [",
            node_value.len()
        ),
    );
    writeln!(
        out,
        "pub static {name}_VALUES: [&str; {}] = [",
        values.len()
    )
    .unwrap();
    for v in &values {
        writeln!(out, "    \"{}\",", escape_str(v)).unwrap();
    }
    out.push_str("];\n");

    fs::write(out_path, out)
        .unwrap_or_else(|e| panic!("Failed to write {}: {e}", out_path.display()));
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
/// Two-level page-table + interned-blob codegen for the BMP default table
/// (#237 item 1). Replaces the former flat `[Option<&str>; 65408]` (~1 MB,
/// mostly `None`) with: a deduped value `BLOB` (~5 KB), a flat `ENTRIES` array of
/// `u32`-packed `(offset << 8) | len` cells (`u32::MAX` = no mapping), and a
/// `PAGES[cp >> 8]` table of base offsets into `ENTRIES` where every all-empty
/// page aliases one shared empty page. Lookup stays O(1) (two indexed loads);
/// footprint drops to tens of KB and same-script runs share cache lines.
///
/// Sentinel guardrail: `u32::MAX` is `None` (no mapping → fall through), while a
/// cell with `len == 0` is `Some("")` (maps to empty → drop the char). A
/// build-time self-check below asserts the packed trie decodes identically to
/// the flat map for every code point, so a packing bug breaks the build.
fn generate_translit_flat_array(tsv_path: &Path, out_path: &Path) {
    const NONE_ENTRY: u32 = u32::MAX;
    const PAGE_LEN: usize = 256;

    let entries = read_char_str_tsv(tsv_path); // BTreeMap<u32, String>, cp in 0x80..0x10000

    // 1. Deduped value blob. "" interns to offset 0 / len 0 so `Some("")` packs
    //    to a non-`NONE_ENTRY` cell, distinct from `None`.
    let mut blob = String::new();
    let mut offset_of: std::collections::HashMap<&str, u32> = std::collections::HashMap::new();
    offset_of.insert("", 0);
    for value in entries.values() {
        if value.is_empty() {
            continue;
        }
        offset_of.entry(value.as_str()).or_insert_with(|| {
            let off = u32::try_from(blob.len()).expect("BMP blob offset fits u32");
            blob.push_str(value);
            off
        });
    }
    assert!(
        blob.len() <= 0x00FF_FFFF,
        "DEFAULT_BMP blob {} B exceeds the 16 MB u24 offset budget",
        blob.len()
    );

    let encode = |cp: u32| -> u32 {
        match entries.get(&cp) {
            None => NONE_ENTRY,
            Some(v) => {
                let len = u32::try_from(v.len()).expect("BMP value len fits u32");
                assert!(len <= 255, "DEFAULT_BMP value too long for u8 len: {v:?}");
                (offset_of[v.as_str()] << 8) | len
            }
        }
    };

    // 2. Pages: ENTRIES slot 0 is the shared all-empty page; every unpopulated
    //    page in PAGES aliases it (base 0).
    let mut pages_entries: Vec<u32> = vec![NONE_ENTRY; PAGE_LEN];
    let mut page_base: Vec<u32> = vec![0u32; 256];
    for (page, base_slot) in page_base.iter_mut().enumerate() {
        let lo = (page as u32) << 8;
        let populated = (0u32..256).any(|o| {
            let cp = lo | o;
            (0x80..0x10000).contains(&cp) && entries.contains_key(&cp)
        });
        if !populated {
            continue; // keep aliasing the shared empty page
        }
        *base_slot = u32::try_from(pages_entries.len()).expect("ENTRIES base fits u32");
        for o in 0u32..256 {
            let cp = lo | o;
            pages_entries.push(if (0x80..0x10000).contains(&cp) {
                encode(cp)
            } else {
                NONE_ENTRY
            });
        }
    }

    // 3. Build-time self-check: the packed trie must decode to exactly the flat
    //    map (including the None vs Some("") distinction) for every code point.
    let decode = |cp: u32| -> Option<String> {
        let base = page_base[(cp >> 8) as usize] as usize;
        let cell = pages_entries[base + (cp & 0xFF) as usize];
        if cell == NONE_ENTRY {
            None
        } else {
            let off = (cell >> 8) as usize;
            let len = (cell & 0xFF) as usize;
            Some(blob[off..off + len].to_string())
        }
    };
    for cp in 0x80u32..0x10000 {
        let expected = entries.get(&cp).cloned();
        assert_eq!(
            decode(cp),
            expected,
            "DEFAULT_BMP trie self-check failed at U+{cp:04X}"
        );
    }

    // 4. Emit.
    let mut file = BufWriter::new(fs::File::create(out_path).unwrap_or_else(|e| {
        panic!("Failed to create {}: {e}", out_path.display());
    }));
    writeln!(
        file,
        "/// Two-level BMP transliteration trie (#237 item 1), generated by build.rs\n\
         /// from translit_default.tsv. `u32::MAX` = None; else `(offset << 8) | len`\n\
         /// into DEFAULT_BMP_BLOB, with len==0 meaning Some(\"\")."
    )
    .unwrap();
    writeln!(
        file,
        "static DEFAULT_BMP_BLOB: &str = \"{}\";",
        escape_str(&blob)
    )
    .unwrap();
    writeln!(
        file,
        "static DEFAULT_BMP_ENTRIES: [u32; {}] = [",
        pages_entries.len()
    )
    .unwrap();
    for (i, cell) in pages_entries.iter().enumerate() {
        if i % 16 == 0 {
            write!(file, "    ").unwrap();
        }
        write!(file, "{cell},").unwrap();
        if i % 16 == 15 {
            writeln!(file).unwrap();
        }
    }
    writeln!(file, "\n];").unwrap();
    writeln!(file, "static DEFAULT_BMP_PAGES: [u32; 256] = [").unwrap();
    for (i, b) in page_base.iter().enumerate() {
        if i % 16 == 0 {
            write!(file, "    ").unwrap();
        }
        write!(file, "{b},").unwrap();
        if i % 16 == 15 {
            writeln!(file).unwrap();
        }
    }
    writeln!(file, "\n];").unwrap();
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
