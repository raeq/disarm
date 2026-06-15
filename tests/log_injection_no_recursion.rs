//! #208 anti-recursion guard: the diagnostic logger (`tl_trace_content!`)
//! dogfoods `strip_log_injection_str` to neutralize the samples it emits, so the
//! log-injection module MUST NOT itself log — a sanitizer that logged would
//! recurse on a single record. This is an always-on source scan (independent of
//! the `log` feature): if anyone adds a `tl_*!` or a direct `log::` call to
//! `src/log_injection.rs`, this test fails.

use std::path::Path;

fn read(rel: &str) -> String {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join(rel);
    std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("read {}: {e}", path.display()))
}

#[test]
fn log_injection_module_does_not_log() {
    let src = read("src/log_injection.rs");
    // Scan code only — strip the `//!`/`//` doc/comment lines that legitimately
    // mention `tl_*!`/`log::` while explaining this very invariant.
    let code: String = src
        .lines()
        .filter(|l| !l.trim_start().starts_with("//"))
        .collect::<Vec<_>>()
        .join("\n");
    assert!(
        !code.contains("tl_"),
        "a logging macro (tl_*!) appears in src/log_injection.rs — the log-injection \
         sanitizer is on the logger's own path (tl_trace_content! dogfoods it), so it \
         must never log or a single record would recurse (#208)."
    );
    assert!(
        !code.contains("log::"),
        "a direct log:: call appears in src/log_injection.rs — see the anti-recursion \
         invariant in this module's header (#208)."
    );
}
