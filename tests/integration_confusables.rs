//! Cross-script confusable folding — #341, #342, #343 (carved from #336).
//!
//! Mirrors `tests/test_confusables_cross_script.py` at the pure-Rust `api` layer:
//! #341 folds TR39's non-ASCII Latin-extended prototypes to basic ASCII, #342
//! adds seven Greek/Cyrillic pairs, #343 re-points the bare iota to the l class.

use disarm::api::{normalize_confusables as nc, TargetScript};

const LATIN: TargetScript = TargetScript::Latin;
const CYR: TargetScript = TargetScript::Cyrillic;

// ── #341: non-ASCII prototypes fold to basic ASCII ──────────────────────────

#[test]
fn fold_341_sources_are_ascii() {
    for (src, want) in [("κ", "k"), ("ε", "e"), ("β", "b"), ("ɛ", "e"), ("є", "e")] {
        let out = nc(src, LATIN);
        assert_eq!(out, want, "{src} → {out}");
        assert!(out.is_ascii(), "{src} → {out} not ASCII");
    }
}

#[test]
fn fold_341_greek_latin_collision() {
    assert_eq!(nc("κ", LATIN), nc("k", LATIN));
    assert_eq!(nc("ε", LATIN), nc("e", LATIN));
    assert_eq!(nc("β", LATIN), nc("b", LATIN));
}

#[test]
fn fold_341_idempotent() {
    for c in ["κ", "ε", "β", "ɛ"] {
        let once = nc(c, LATIN);
        assert_eq!(nc(&once, LATIN), once);
    }
}

#[test]
fn fold_341_sigma_folds_to_s() {
    // esh is no longer residue (#341): TR39's sigma/summation skeleton folds to
    // ASCII. Capital Σ → S (case-preserved); the caseless summation ∑ → s.
    assert_eq!(nc("Σ", LATIN), "S");
    assert_eq!(nc("∑", LATIN), "s");
    assert!(nc("Σ", LATIN).is_ascii());
}

// ── #342: seven additive pairs collide on a shared representative ────────────

#[test]
fn pairs_342_latin_closure() {
    // (gap, partner, shared latin)
    for (a, b, shared) in [
        ("ί", "і", "i"),
        ("п", "η", "n"),
        ("χ", "х", "x"),
        ("ω", "ѡ", "w"),
        ("ό", "о", "o"),
        ("ѻ", "ο", "o"),
    ] {
        assert_eq!(nc(a, LATIN), shared, "{a}");
        assert_eq!(nc(b, LATIN), shared, "{b}");
        assert!(shared.is_ascii());
    }
}

#[test]
fn pairs_342_eta_pe_pi_transitive() {
    for c in ["η", "п", "π"] {
        assert_eq!(nc(c, LATIN), "n", "{c}");
    }
}

#[test]
fn pairs_342_beta_ve_collide() {
    // β via #341 (ß→b), в via #342 — they meet at b.
    assert_eq!(nc("β", LATIN), "b");
    assert_eq!(nc("в", LATIN), "b");
}

#[test]
fn pairs_342_cyrillic_closure() {
    for (a, b) in [("ί", "і"), ("χ", "х"), ("ϊ", "ї"), ("ό", "о"), ("ѻ", "ο")] {
        assert_eq!(nc(a, CYR), nc(b, CYR), "cyr {a} == {b}");
    }
    assert_eq!(nc("β", CYR), "в");
    assert_eq!(nc("η", CYR), "п");
    assert_eq!(nc("ѡ", CYR), "ꙍ");
}

// ── #343: unify the vertical-bar class ι / ӏ / ا ────────────────────────────

#[test]
fn bar_343_latin_l() {
    for c in ["ι", "ӏ", "ا"] {
        assert_eq!(nc(c, LATIN), "l", "{c} → l");
    }
}

#[test]
fn bar_343_cyrillic_palochka() {
    for c in ["ι", "ӏ", "ا"] {
        assert_eq!(nc(c, CYR), "ӏ", "{c} → ӏ");
    }
}

#[test]
fn bar_343_accented_iotas_still_i() {
    // #342 boundary: diacritic'd iotas read as i; only the bare stroke is l.
    assert_eq!(nc("ί", LATIN), "i");
    assert_eq!(nc("ϊ", LATIN), "i");
}
