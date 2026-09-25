//! Every generated `phf` table, checked against its own lookup and against a pinned digest.
//!
//! `build.rs` writes each table with `phf_codegen`, and the library reads it back with
//! `phf`. The two crates must agree on the hash and on the layout of the displacement
//! array: a table built by one release and read by another still compiles, and still
//! iterates every entry, but `get` looks in the wrong slot and misses. That is the risk
//! of moving the pair, so this test asks each table two questions:
//!
//! * **Does every entry look itself up?** Each key the table iterates is passed back to
//!   `get` (or `contains`), which is the hash path. Iteration reads the entries array
//!   directly, so the two can disagree only if codegen and runtime do.
//! * **Is the content what it was?** A count and an FNV-1a digest of the sorted entries,
//!   pinned below. The digest is independent of hash seed and slot order, so a `phf`
//!   upgrade that reshuffles the layout keeps it, and one that changes an entry does
//!   not.
//!
//! The table list is complete by construction: the generated sources in `OUT_DIR` are
//! scanned for every `static NAME: phf::…`, and a table missing from [`GOLDEN`] or from a
//! module's `phf_tables()` fails the test, so a new table cannot go unchecked.
//!
//! To re-pin after a deliberate table change, run the test and copy the `actual` rows
//! it prints into [`GOLDEN`].

use std::collections::BTreeMap;
use std::fmt::Write as _;

/// One generated table, by the shape `build.rs` emits.
pub(crate) enum Table {
    CharStr(&'static str, &'static phf::Map<char, &'static str>),
    StrStr(&'static str, &'static phf::Map<&'static str, &'static str>),
    StrChar(&'static str, &'static phf::Map<&'static str, char>),
    CharSet(&'static str, &'static phf::Set<char>),
    U32Set(&'static str, &'static phf::Set<u32>),
}

/// `(table, entry count, FNV-1a 64 of the sorted entries)`, pinned on phf 0.13.1.
const GOLDEN: &[(&str, usize, u64)] = &[
    ("CASE_FOLD", 1557, 0x1abd_fcdd_cfea_9256),
    ("DEFAULT_SMP", 164, 0x37de_dd39_6d1a_3aa3),
    ("DIGIT_TR39", 47, 0x3c54_9bca_25b2_1aa5),
    ("EMOJI_MULTI", 2553, 0xa9bf_624a_4689_0fd3),
    ("EMOJI_MULTI_STARTERS", 188, 0xe9f7_ddff_29fa_8bd6),
    ("EMOJI_ROWS_TR39_ALSO_CLAIMS", 54, 0x1412_ba05_9395_5824),
    (
        "EMOJI_ROWS_WITHOUT_EMOJI_PROPERTY",
        326,
        0x6a86_62a5_a76f_51bf,
    ),
    ("EMOJI_SINGLE", 1727, 0x33d5_d127_4e51_ecb4),
    ("EXCLUDED_COMPOSITIONS", 71, 0xcba2_eb9b_cc3d_37e8),
    ("GOST7034", 12, 0x762e_da0d_e2c3_140e),
    ("HANZI_PINYIN_TONED", 2099, 0x767d_4b9c_647d_d0ad),
    ("ISO9", 26, 0x1fa5_790f_092e_1dac),
    ("LANG_AM", 23, 0xee4f_db27_98ad_48e9),
    ("LANG_BG", 4, 0xdc5b_9ae5_04e2_44c7),
    ("LANG_CA", 1, 0xb4c4_6f6d_2bbb_8f91),
    ("LANG_DE", 7, 0x4655_ffe9_70c1_e263),
    ("LANG_EL", 6, 0x26a4_c3ba_2d74_5b4b),
    ("LANG_ES", 2, 0x7f80_9903_fc4f_f40f),
    ("LANG_ET", 6, 0xe982_dd17_7106_a021),
    ("LANG_FA", 63, 0x5101_cf77_9719_a20f),
    ("LANG_FR", 4, 0x6225_2248_9c13_8680),
    ("LANG_IS", 2, 0x3bb8_ad0e_6a03_c785),
    ("LANG_IT", 2, 0x3405_4270_3466_9d47),
    ("LANG_JA", 1, 0xc57b_b9b6_1e27_9bd6),
    ("LANG_JA_KUNREI", 16, 0xc090_cf1c_7054_5ecb),
    ("LANG_NL", 2, 0x9f54_ceca_1998_2500),
    ("LANG_NO", 6, 0xb837_9785_c921_2065),
    ("LANG_PT", 2, 0x3405_4270_3466_9d47),
    ("LANG_RU", 14, 0x3d28_68ec_72a3_a9bb),
    ("LANG_SR", 14, 0x2ccc_e5b0_82ca_70b1),
    ("LANG_SV", 4, 0xc884_db0c_0d68_81d5),
    ("LANG_TR", 6, 0x684f_7b21_bd1e_f838),
    ("LANG_UK", 14, 0x9ed6_d91e_5fb0_cb3a),
    ("LANG_VI", 6, 0xbbfc_4af4_5dd3_9a54),
    ("REVERSE_EL", 48, 0x6131_8ce4_86e2_accf),
    ("REVERSE_RU", 62, 0xd6ce_aa23_7061_b9bb),
    ("REVERSE_UK", 62, 0x28d7_a0cf_ba32_11b7),
    ("TO_ARABIC", 373, 0x318c_e252_ec6b_71f4),
    ("TO_CYRILLIC", 1354, 0x1daf_5775_52d0_3824),
    ("TO_HEBREW", 261, 0x841f_24d0_5d1b_ab9f),
    ("TO_LATIN", 2358, 0x4de3_5a6d_b179_98d2),
    ("UPSTREAM_CONFUSABLE_SOURCES", 6565, 0xf4aa_9875_c35e_0987),
    ("WORD_JOINERS", 38, 0xee47_29a9_5156_9174),
];

fn fnv1a(lines: &[String]) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for line in lines {
        for b in line.bytes().chain(std::iter::once(b'\n')) {
            h ^= u64::from(b);
            h = h.wrapping_mul(0x0000_0100_0000_01b3);
        }
    }
    h
}

/// Check that every entry looks itself up, and return `(name, count, digest)`.
fn measure(table: &Table) -> (&'static str, usize, u64) {
    let (name, mut lines) = match *table {
        Table::CharStr(name, map) => {
            for (k, v) in map.entries() {
                assert_eq!(map.get(k), Some(v), "{name}: {k:?} does not look itself up");
            }
            (
                name,
                map.entries()
                    .map(|(k, v)| format!("{k:?}\t{v:?}"))
                    .collect::<Vec<_>>(),
            )
        }
        Table::StrStr(name, map) => {
            for (k, v) in map.entries() {
                assert_eq!(
                    map.get(*k),
                    Some(v),
                    "{name}: {k:?} does not look itself up"
                );
            }
            (
                name,
                map.entries()
                    .map(|(k, v)| format!("{k:?}\t{v:?}"))
                    .collect(),
            )
        }
        Table::StrChar(name, map) => {
            for (k, v) in map.entries() {
                assert_eq!(
                    map.get(*k),
                    Some(v),
                    "{name}: {k:?} does not look itself up"
                );
            }
            (
                name,
                map.entries()
                    .map(|(k, v)| format!("{k:?}\t{v:?}"))
                    .collect(),
            )
        }
        Table::CharSet(name, set) => {
            for k in set {
                assert!(set.contains(k), "{name}: {k:?} does not look itself up");
            }
            (name, set.iter().map(|k| format!("{k:?}")).collect())
        }
        Table::U32Set(name, set) => {
            for k in set {
                assert!(set.contains(k), "{name}: {k:#x} does not look itself up");
            }
            (name, set.iter().map(|k| format!("{k:#x}")).collect())
        }
    };
    lines.sort_unstable();
    (name, lines.len(), fnv1a(&lines))
}

/// Every `static NAME: phf::…` the build script generated.
fn generated_names() -> Vec<String> {
    let out = std::path::Path::new(env!("OUT_DIR"));
    let mut names = Vec::new();
    for entry in std::fs::read_dir(out).expect("OUT_DIR is readable") {
        let path = entry.expect("OUT_DIR entry").path();
        if path.extension().is_none_or(|e| e != "rs") {
            continue;
        }
        let src = std::fs::read_to_string(&path).expect("generated source is UTF-8");
        for line in src.lines() {
            let Some(rest) = line.split("static ").nth(1) else {
                continue;
            };
            if let Some((name, ty)) = rest.split_once(':') {
                if ty.trim_start().starts_with("phf::") {
                    names.push(name.trim().to_owned());
                }
            }
        }
    }
    names.sort_unstable();
    names
}

#[test]
fn every_generated_phf_table_looks_itself_up_and_keeps_its_content() {
    let mut tables = crate::tables::phf_tables();
    tables.extend(crate::compose::phf_tables());
    tables.extend(crate::reverse::phf_tables());

    let actual: BTreeMap<&str, (usize, u64)> = tables
        .iter()
        .map(|t| {
            let (name, n, digest) = measure(t);
            (name, (n, digest))
        })
        .collect();
    assert_eq!(actual.len(), tables.len(), "a table is registered twice");

    let registered: Vec<String> = actual.keys().map(|&k| k.to_owned()).collect();
    assert_eq!(
        registered,
        generated_names(),
        "the registered tables and the phf statics in OUT_DIR differ: register a new table \
         in its module's phf_tables() and pin it in GOLDEN"
    );

    let golden: BTreeMap<&str, (usize, u64)> =
        GOLDEN.iter().map(|&(name, n, d)| (name, (n, d))).collect();
    if golden != actual {
        let mut rows = String::new();
        for (name, (n, d)) in &actual {
            let hex = format!("{d:016x}");
            let _ = writeln!(
                rows,
                "    (\"{name}\", {n}, 0x{}_{}_{}_{}),",
                &hex[..4],
                &hex[4..8],
                &hex[8..12],
                &hex[12..]
            );
        }
        panic!("phf table content differs from GOLDEN; actual:\n{rows}");
    }
}

/// The lookup check is not vacuous: a table read with a hash other than the one it was
/// built with (what a `phf` / `phf_codegen` version split produces) fails it. The copy
/// keeps every entry and changes only the hash key, so iteration still sees them all and
/// only `get` can tell.
#[test]
fn a_table_read_with_another_hash_fails_the_lookup_check() {
    let Some(Table::CharStr(_, map)) = crate::tables::phf_tables()
        .into_iter()
        .find(|t| matches!(t, Table::CharStr("TO_LATIN", _)))
    else {
        panic!("TO_LATIN is registered as a char -> str table");
    };
    let rehashed: &'static phf::Map<char, &'static str> = Box::leak(Box::new(phf::Map {
        key: map.key ^ 1,
        disps: map.disps,
        entries: map.entries,
    }));
    let caught = std::panic::catch_unwind(|| measure(&Table::CharStr("TO_LATIN", rehashed)));
    assert!(caught.is_err(), "a rehashed table passed the lookup check");
}
