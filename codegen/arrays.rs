//! The dense emitters, for tables a PHF would make larger or slower: the interned
//! Hanzi array, the emoji sequence trie and the two-level BMP transliteration table.

use std::collections::BTreeMap;
use std::fmt::Write as _;
use std::fs;
use std::io::{BufWriter, Write};
use std::path::Path;

use super::phf_tables::escape_str;
use super::readers::{read_char_str_tsv, read_str_str_tsv};

/// Generate a dense interned table over a contiguous codepoint range
/// `[base, base + len)`: a `[u16; len]` id array (indexed by `cp - base`) plus a
/// `[&'static str; K]` value table where **id 0 = `""` = no entry**. Far smaller
/// than a PHF or a `[&str; len]` when values repeat heavily, and the lookup is a
/// flat index with no hashing (#237 item 2). Emits `<name>_VALUES`, `<name>_IDS`,
/// and `<name>_BASE`.
pub(crate) fn build_dense_interned_array(
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
pub(crate) fn generate_emoji_trie(tsv_path: &Path, out_path: &Path, name: &str) {
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
pub(crate) fn generate_translit_flat_array(tsv_path: &Path, out_path: &Path) {
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
