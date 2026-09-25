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

/// `(table, entry count, FNV-1a 64 of the sorted entries)`, pinned on phf 0.13.1, over code points (see [`cp`]).
const GOLDEN: &[(&str, usize, u64)] = &[
    ("CASE_FOLD", 1557, 0x1d42_0719_be93_79f2),
    ("DEFAULT_SMP", 164, 0x2fb9_9959_cbcb_1a80),
    ("DIGIT_TR39", 47, 0x1999_32dd_ecce_86a3),
    ("EMOJI_MULTI", 2553, 0xc441_cc94_b68c_63ca),
    ("EMOJI_MULTI_STARTERS", 188, 0xac54_cc8f_ad4b_fd0b),
    ("EMOJI_ROWS_TR39_ALSO_CLAIMS", 54, 0x1412_ba05_9395_5824),
    (
        "EMOJI_ROWS_WITHOUT_EMOJI_PROPERTY",
        326,
        0x6a86_62a5_a76f_51bf,
    ),
    ("EMOJI_SINGLE", 1727, 0x25a3_5a30_0f81_a2de),
    ("EXCLUDED_COMPOSITIONS", 71, 0xcc78_7481_ac55_481f),
    ("GOST7034", 12, 0x6d35_8e67_c4cb_3c29),
    ("HANZI_PINYIN_TONED", 2099, 0x68c6_868e_08a8_e36e),
    ("ISO9", 26, 0xb535_52ce_713d_afa2),
    ("LANG_AM", 23, 0x4183_1b15_5573_09c8),
    ("LANG_BG", 4, 0xd01b_f70a_5914_62f1),
    ("LANG_CA", 1, 0xf2b4_6049_ef18_ce6d),
    ("LANG_DE", 7, 0xa8a3_f71e_b8a7_3da4),
    ("LANG_EL", 6, 0xe0f4_e420_7472_3be2),
    ("LANG_ES", 2, 0x9c8f_1a42_19c8_281f),
    ("LANG_ET", 6, 0x8612_b725_3f02_e8db),
    ("LANG_FA", 63, 0x80a7_67dd_498c_2690),
    ("LANG_FR", 4, 0xfa9c_b229_6399_73fe),
    ("LANG_IS", 2, 0x1261_00b9_15b3_5b61),
    ("LANG_IT", 2, 0x90ca_a57e_b0ba_7591),
    ("LANG_JA", 1, 0xa5d8_8610_1968_595e),
    ("LANG_JA_KUNREI", 16, 0xadc1_3837_04f4_0f13),
    ("LANG_NL", 2, 0x7f5b_9725_3528_4446),
    ("LANG_NO", 6, 0x25aa_f3fd_3c9d_a363),
    ("LANG_PT", 2, 0x90ca_a57e_b0ba_7591),
    ("LANG_RU", 14, 0x43f0_8ca6_cc1e_4cd8),
    ("LANG_SR", 14, 0xa50e_4952_5c62_2419),
    ("LANG_SV", 4, 0x522d_fe04_2930_b63d),
    ("LANG_TR", 6, 0xd6fa_26f5_f9e9_5dec),
    ("LANG_UK", 14, 0x0d1c_f474_aa88_db85),
    ("LANG_VI", 6, 0x47b8_b6da_2f4e_ef66),
    ("REVERSE_EL", 48, 0xa1ed_11d7_4462_ebef),
    ("REVERSE_RU", 62, 0x99e4_c65a_10bb_ac0c),
    ("REVERSE_UK", 62, 0x19de_f3cc_52a8_1481),
    ("TO_ARABIC", 373, 0xcdeb_2dde_f222_023a),
    ("TO_CYRILLIC", 1354, 0xf9db_5917_32b8_4e5e),
    ("TO_HEBREW", 261, 0xc456_938e_2b7e_21e4),
    ("TO_LATIN", 2358, 0x81f2_0691_aa62_a97d),
    ("UPSTREAM_CONFUSABLE_SOURCES", 6565, 0x1b36_25d7_817a_8906),
    ("WORD_JOINERS", 38, 0xfacb_8b87_168b_b8ed),
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

/// A character as its code point. Not `{c:?}`: `Debug` escapes a character by the
/// standard library's own Unicode tables, which change between Rust releases, so a
/// digest over it would differ across toolchains (stable 1.94 and CI's newer compilers
/// disagreed on `UPSTREAM_CONFUSABLE_SOURCES`).
fn cp(c: char) -> String {
    format!("{:04X}", u32::from(c))
}

/// A string as its code points, space-separated.
fn cps(s: &str) -> String {
    s.chars().map(cp).collect::<Vec<_>>().join(" ")
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
                    .map(|(k, v)| format!("{}\t{}", cp(*k), cps(v)))
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
                    .map(|(k, v)| format!("{}\t{}", cps(k), cps(v)))
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
                    .map(|(k, v)| format!("{}\t{}", cps(k), cp(*v)))
                    .collect(),
            )
        }
        Table::CharSet(name, set) => {
            for k in set {
                assert!(set.contains(k), "{name}: {k:?} does not look itself up");
            }
            (name, set.iter().map(|k| cp(*k)).collect())
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
