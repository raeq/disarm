//! #208 hot-path guard: the per-codepoint loop in `transliterate_impl_inner` and
//! the per-token loop in `context::resolve` must contain NO logging macro, so a
//! `--features log` build never logs inside an inner loop. This is a source-level
//! scan (always on, independent of the `log` feature) — if someone adds a `tl_*!`
//! call inside either hot loop, this test fails.

use std::path::Path;

/// Return the source span of `fn <name>` in `src` (from the `fn` keyword to the
/// matching closing brace), via brace counting.
fn fn_body<'a>(src: &'a str, signature: &str) -> &'a str {
    let start = src
        .find(signature)
        .unwrap_or_else(|| panic!("function `{signature}` not found"));
    let after = &src[start..];
    let brace = after.find('{').expect("function body opening brace");
    let mut depth = 0usize;
    for (i, ch) in after[brace..].char_indices() {
        match ch {
            '{' => depth += 1,
            '}' => {
                depth -= 1;
                if depth == 0 {
                    return &after[..=(brace + i)];
                }
            }
            _ => {}
        }
    }
    panic!("unbalanced braces in `{signature}`");
}

fn read(rel: &str) -> String {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join(rel);
    std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("read {}: {e}", path.display()))
}

#[test]
fn no_log_macro_in_transliterate_inner_loop() {
    let src = read("src/transliterate.rs");
    let body = fn_body(&src, "fn transliterate_impl_inner");
    assert!(
        !body.contains("tl_"),
        "a logging macro (tl_*!) appears inside transliterate_impl_inner — the \
         per-codepoint hot loop must never log (#208). Move the record to the \
         transliterate_impl boundary instead."
    );
    // Also no direct `log::` calls.
    assert!(
        !body.contains("log::"),
        "direct log:: call inside the hot loop"
    );
}

#[test]
fn no_log_macro_in_context_resolve() {
    let src = read("src/context.rs");
    let body = fn_body(&src, "fn resolve");
    assert!(
        !body.contains("tl_"),
        "a logging macro (tl_*!) appears inside context::resolve — the per-token \
         hot loop must never log (#208)."
    );
    assert!(
        !body.contains("log::"),
        "direct log:: call inside context::resolve"
    );
}
