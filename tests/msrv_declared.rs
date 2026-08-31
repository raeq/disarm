//! #718: the declared MSRV is derived from the resolved tree, not asserted by hand.
//!
//! `Cargo.toml` claimed `rust-version = "1.81"` and nothing built at it. The real floor
//! was **1.88**, set by a *runtime* dependency rather than a dev one — `idna` pulls in
//! `idna_adapter`, which pulls in `icu_normalizer` / `icu_properties` / `icu_provider`,
//! all of which declare `rust-version = "1.88"`. `idna_adapter` 1.2.2 also uses edition
//! 2024, which cargo below 1.85 cannot parse at all, so a consumer on 1.81 did not get a
//! subtle compile error: cargo refused to read the manifest.
//!
//! Measured before the fix: `cargo +1.81`, `+1.85` and `+1.87` all fail on a minimal
//! consumer of this crate; `+1.88` succeeds.
//!
//! Nothing in CI builds at the declared MSRV, so the number was documentation rather than
//! a fact. This gate makes it a fact: the floor is computed from `cargo metadata` over the
//! resolved graph and compared against what the manifest publishes. A `cargo update` that
//! raises a dependency's `rust-version` now fails here instead of shipping a manifest that
//! promises a toolchain the crate cannot be built on.
//!
//! Deliberately scoped to the **runtime** graph. A dev-dependency's floor never reaches a
//! downstream consumer — `criterion` has wanted 1.86 for some time — so folding dev-deps
//! in would raise the published MSRV for no one's benefit.

use std::process::Command;

/// A `rust-version` as comparable parts. `"1.88"` and `"1.88.0"` compare equal.
fn parts(version: &str) -> (u32, u32, u32) {
    let mut it = version.split('.').map(|p| p.parse().unwrap_or(0));
    (
        it.next().unwrap_or(0),
        it.next().unwrap_or(0),
        it.next().unwrap_or(0),
    )
}

/// `cargo metadata` over the whole resolved graph, or `None` when cargo is unavailable.
///
/// Deliberately **not** `--filter-platform`: that flag takes a full target triple, and an
/// earlier draft passed `std::env::consts::ARCH` (`"aarch64"`), which cargo rejects. The
/// call failed, the test took its unavailable branch, and the gate passed while the
/// manifest published a floor nothing could build at — a gate that cannot fail, which is
/// the failure mode this whole file exists to prevent. Scanning every platform is
/// conservative in the safe direction: it can only report a floor at least as high as the
/// host's.
fn metadata() -> Option<String> {
    let out = Command::new(std::env::var("CARGO").unwrap_or_else(|_| "cargo".into()))
        .args(["metadata", "--format-version", "1", "--locked"])
        .output()
        .ok()?;
    out.status
        .success()
        .then(|| String::from_utf8_lossy(&out.stdout).into_owned())
}

/// Every `"rust_version": "x.y[.z]"` in the metadata, with the package it belongs to.
///
/// Parsed by scanning rather than with a JSON dependency: this crate has no serde in its
/// tree, and adding one to a test would change the very graph being measured.
fn declared_floors(json: &str) -> Vec<(String, String)> {
    let mut out = Vec::new();
    let mut rest = json;
    while let Some(at) = rest.find("\"rust_version\":") {
        let after = &rest[at + "\"rust_version\":".len()..];
        let Some(open) = after.find('"') else { break };
        let Some(close) = after[open + 1..].find('"') else {
            break;
        };
        let version = after[open + 1..open + 1 + close].to_owned();
        // The package name precedes it in the same object.
        let name = rest[..at].rfind("\"name\":").map_or_else(
            || "?".into(),
            |n| {
                let seg = &rest[n + "\"name\":".len()..at];
                seg.trim()
                    .trim_start_matches('"')
                    .split('"')
                    .next()
                    .unwrap_or("?")
                    .to_owned()
            },
        );
        if !version.is_empty() {
            out.push((name, version));
        }
        rest = &after[open + 1 + close..];
    }
    out
}

/// The packages in the **runtime** graph, from `cargo tree -e no-dev`.
///
/// Two reasons this is not read out of `cargo metadata` alone. That listing includes
/// dev-dependencies of *dependencies* — an earlier draft blamed `data_locale_bench`, a
/// benchmark inside ICU4X's own workspace, for a floor really set by `icu_provider` — and
/// it includes this crate's own dev-dependencies, whose floor never reaches a downstream
/// consumer. `criterion` has wanted 1.86 for some time and must not be able to raise the
/// published MSRV on its own.
fn runtime_packages() -> Vec<String> {
    let out = Command::new(std::env::var("CARGO").unwrap_or_else(|_| "cargo".into()))
        .args(["tree", "-e", "no-dev", "--prefix", "none", "--locked"])
        .output();
    let Ok(out) = out else { return Vec::new() };
    if !out.status.success() {
        return Vec::new();
    }
    let mut names: Vec<String> = String::from_utf8_lossy(&out.stdout)
        .lines()
        .filter_map(|line| line.split_whitespace().next())
        .map(str::to_owned)
        .collect();
    names.sort();
    names.dedup();
    names
}

#[test]
fn the_manifest_publishes_the_floor_the_tree_actually_requires() {
    let Some(json) = metadata() else {
        // Offline or no cargo: the gate cannot run, and saying so beats a false pass.
        eprintln!("skipping: `cargo metadata` unavailable");
        return;
    };
    let runtime = runtime_packages();
    let floors: Vec<_> = declared_floors(&json)
        .into_iter()
        // `disarm` itself is excluded: comparing the manifest against its own claim
        // would make the gate self-referential and always green.
        .filter(|(name, _)| name != "disarm" && runtime.iter().any(|r| r == name))
        .collect();
    assert!(
        floors.len() > 5,
        "parsed {} runtime packages with a rust-version, expected the whole graph — the \
         scan is broken, not the manifest",
        floors.len()
    );

    let declared = env!("CARGO_PKG_RUST_VERSION");
    let (name, highest) = floors
        .iter()
        .max_by_key(|(_, v)| parts(v))
        .expect("at least one package declares a rust-version");

    assert!(
        parts(declared) >= parts(highest),
        "Cargo.toml publishes `rust-version = \"{declared}\"`, but `{name}` in the resolved \
         graph requires {highest}. A consumer on {declared} cannot build this crate.\n\n\
         Raise `rust-version` to {highest} and say why in the comment above it, or pin the \
         dependency back with `cargo update -p {name} --precise <older>`."
    );
}

#[test]
fn the_gate_is_actually_running() {
    // The skip branch above exists for an offline environment, and a skip that nobody
    // notices is indistinguishable from a pass. This asserts the gate ran at all.
    assert!(
        metadata().is_some(),
        "`cargo metadata --locked` failed, so the MSRV gate skipped rather than checked. \
         Fix the invocation — do not leave this passing."
    );
}

#[test]
fn the_scan_finds_the_crate_that_sets_the_floor() {
    // A gate that parses nothing passes for the wrong reason. This pins the mechanism:
    // the floor must come from a real package with a real version.
    let Some(json) = metadata() else { return };
    let runtime = runtime_packages();
    let floors: Vec<_> = declared_floors(&json)
        .into_iter()
        .filter(|(name, _)| name != "disarm" && runtime.iter().any(|r| r == name))
        .collect();
    let (name, version) = floors
        .iter()
        .max_by_key(|(_, v)| parts(v))
        .expect("no rust-version in the graph");
    assert!(!name.is_empty() && name != "?", "floor has no package name");
    assert!(parts(version) >= (1, 0, 0), "implausible floor {version}");
}
