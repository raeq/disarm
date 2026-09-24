//! `sanitize_filename` over fuzzed text, separator, `max_length`, platform, language and
//! `preserve_extension`.
//!
//! Properties (the docstring in `src/api/safety.rs`, the P-properties of
//! `formal/lean/Sanitizers`, and the #1026 fixes):
//!
//! - **Errors** only for what the docstring names: a separator holding a character other
//!   than printable, non-space ASCII, one illegal on the platform, or a path separator; or
//!   an unknown language. Both are `InvalidArgument`.
//! - **P1** never empty; **P2** never `.` or `..`.
//! - **P3/P4** no character illegal on the platform, no control, no whitespace other than
//!   what the caller's separator brings (a valid separator carries none).
//! - **P6** no leading dot or space, no trailing dot or space.
//! - **P7** at most `max_length` bytes when `max_length > 0`.
//! - **P8** on universal and Windows, never a device name as Windows reads one: the part
//!   before the first dot, trailing spaces ignored, compared case-insensitively.
//! - **P9** a fixed point: sanitizing the output again returns it unchanged, however
//!   many passes the input needs (a debug build also asserts the pass bound is not hit).
//! - The output is ASCII (the docstring's premise for the passes after the first).
//! - Every `%` in the output is one the input contained (#721, #1026): checked when the
//!   separator carries none.
#![no_main]

use arbitrary::Arbitrary;
use disarm::api::{sanitize_filename, Platform};
use disarm::ErrorKind;
use disarm_fuzz::{text_and, Lang};
use libfuzzer_sys::fuzz_target;

#[derive(Debug, Arbitrary)]
enum PlatformOpt {
    Universal,
    Windows,
    Posix,
}

#[derive(Debug, Arbitrary)]
enum Sep {
    Underscore,
    Empty,
    Dash,
    Dot,
    Raw(String),
}

#[derive(Debug, Arbitrary)]
struct Opts {
    platform: PlatformOpt,
    sep: Sep,
    max_length: u16,
    lang: Lang,
    preserve_extension: bool,
}

const RESERVED: &[&str] = &[
    "CON", "PRN", "AUX", "NUL", "COM0", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7",
    "COM8", "COM9", "LPT0", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    "CLOCK$", "KEYBD$", "SCREEN$",
];
const UNIVERSAL_ILLEGAL: &[char] = &['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\0'];
const POSIX_ILLEGAL: &[char] = &['/', '\0'];

fn device_stem(name: &str) -> &str {
    name.split('.').next().unwrap_or(name).trim_end_matches(' ')
}

fuzz_target!(|data: &[u8]| {
    let Some((s, o)) = text_and::<Opts>(data) else {
        return;
    };
    let (platform, illegal) = match o.platform {
        PlatformOpt::Universal => (Platform::Universal, UNIVERSAL_ILLEGAL),
        PlatformOpt::Windows => (Platform::Windows, UNIVERSAL_ILLEGAL),
        PlatformOpt::Posix => (Platform::Posix, POSIX_ILLEGAL),
    };
    let sep = match &o.sep {
        Sep::Underscore => "_",
        Sep::Empty => "",
        Sep::Dash => "-",
        Sep::Dot => ".",
        Sep::Raw(r) => r.as_str(),
    };
    // Mostly small budgets, where truncation interacts with everything else; 0 = no limit.
    let max_length = usize::from(o.max_length % 300);
    let lang = o.lang.code();
    let sep_valid = sep
        .chars()
        .all(|c| c.is_ascii_graphic() && c != '/' && c != '\\' && !illegal.contains(&c));

    let out = match sanitize_filename(
        &s,
        sep,
        max_length,
        platform,
        lang.as_deref(),
        o.preserve_extension,
    ) {
        Ok(out) => out,
        Err(e) => {
            assert_eq!(e.kind(), ErrorKind::InvalidArgument, "{e}");
            // A valid separator and a listed language cannot fail.
            let listed = lang
                .as_deref()
                .is_none_or(|l| l == "auto" || disarm::api::list_langs().iter().any(|k| k == l));
            assert!(!(sep_valid && listed), "refused valid arguments: {e}");
            return;
        }
    };
    assert!(sep_valid, "accepted the invalid separator {sep:?}");

    // P1, P2.
    assert!(!out.is_empty(), "P1: empty output for {s:?}");
    assert!(out != "." && out != "..", "P2: {out:?}");
    // P3, P4, and ASCII.
    assert!(out.is_ascii(), "non-ASCII output {out:?}");
    for c in out.chars() {
        assert!(!illegal.contains(&c), "P3: illegal {c:?} in {out:?}");
        assert!(!c.is_control(), "P4: control {c:?} in {out:?}");
        assert!(
            !c.is_whitespace() || c == ' ',
            "whitespace {c:?} in {out:?}"
        );
    }
    // P6.
    assert!(
        !out.starts_with(['.', ' ']),
        "P6: leading dot or space in {out:?}"
    );
    assert!(
        !out.ends_with(['.', ' ']),
        "P6: trailing dot or space in {out:?}"
    );
    // P7.
    if max_length > 0 {
        assert!(
            out.len() <= max_length,
            "P7: {} > {max_length} in {out:?}",
            out.len()
        );
    }
    // P8.
    if platform != Platform::Posix {
        let stem = device_stem(&out);
        assert!(
            !RESERVED.iter().any(|r| stem.eq_ignore_ascii_case(r)),
            "P8: device name {out:?} from {s:?}"
        );
    }
    // `%` is never manufactured.
    if !sep.contains('%') {
        assert!(
            out.matches('%').count() <= s.matches('%').count(),
            "manufactured a % in {out:?} from {s:?}"
        );
    }
    // P9.
    let again = sanitize_filename(
        &out,
        sep,
        max_length,
        platform,
        lang.as_deref(),
        o.preserve_extension,
    )
    .expect("the arguments were accepted once");
    assert_eq!(again, out, "P9: not a fixed point for {s:?}");
});
