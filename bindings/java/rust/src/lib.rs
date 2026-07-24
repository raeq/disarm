//! JNI bindings exposing the pure-Rust `disarm` core to the JVM (Java/Kotlin).
//!
//! Like the Node (`bindings/node/src/lib.rs`) and Ruby
//! (`bindings/ruby/ext/disarm/src/lib.rs`) shims, this file is the **raw native
//! layer (Layer A)**: each `Java_*` entry point is a thin wrapper over
//! `disarm_core::api` with positional arguments and string-token enums. The
//! idiomatic Java surface — options objects, defaults, the `DisarmException`
//! hierarchy — lives in the hand-written `../disarm-java` layer; idiomatic Kotlin
//! will live in `../disarm-kotlin`.
//!
//! Naming: JNI resolves `com.disarm.internal.Native.transliterate` to the symbol
//! `Java_com_disarm_internal_Native_transliterate`. `Native` is package-internal,
//! so we skip the `_`-prefix "raw" convention the other bindings use for
//! language-visible functions — it would only add JNI name-mangling (`_` → `_1`).
//!
//! Boundary discipline (jni 0.22): `EnvUnowned::with_env` upgrades the FFI env to a
//! real `Env` **and wraps the closure in `catch_unwind`**, so a panic in the core
//! becomes a thrown exception instead of unwinding across FFI (UB). `resolve` maps
//! errors/panics to Java via an [`ErrorPolicy`]. Fallible entry points throw the
//! specific `DisarmException` subclass themselves (JNI `ThrowNew`) and return
//! `Error::JavaException`; the policy sees the pending exception and yields the
//! null/zero default without clobbering it.
//!
//! Most entry points are one-liners over the shared `map_*` dispatch helpers,
//! which centralize the string-boundary + panic-guard + resolve plumbing so each
//! function only names its core call.
//!
//! Strings: `mutf8_chars`/`new_string` use modified UTF-8 (CESU-8), decoded
//! correctly for the astral plane. A faithful boundary for *lone surrogates* needs
//! raw UTF-16 (`GetStringChars`) + the WTF-8 scrub the Python/Ruby bindings do;
//! tracked as a Phase-2 follow-up.

// FFI boundary must never unwind into the JVM (S-4, mirrors Node/Ruby): forbid the
// panic-shaped constructs. `with_env` is the structural backstop; these keep the
// shim honest.
#![cfg_attr(
    not(test),
    deny(
        clippy::unwrap_used,
        clippy::expect_used,
        clippy::indexing_slicing,
        clippy::string_slice,
        clippy::panic,
        clippy::todo,
        clippy::unimplemented
    )
)]

use disarm_core::api;
use jni::errors::{Error as JniError, Result as JniResult};
use jni::objects::{JClass, JObject, JObjectArray, JString};
use jni::strings::JNIString;
use jni::sys::{jboolean, jlong, jsize};
use jni::{Env, EnvUnowned};

/// The error/panic → Java-exception mapping used to `resolve` every entry point.
type Policy = jni::errors::ThrowRuntimeExAndDefault;

/// JVM binary names of the exception classes the idiomatic layer defines.
const EX_INVALID: &str = "com/disarm/DisarmInvalidArgumentException";
const EX_ERROR: &str = "com/disarm/DisarmException";

/// Throw the Java exception matching a core error's kind and return the sentinel
/// [`JniError::JavaException`] so `resolve` keeps the pending throw. If throwing
/// itself fails, that JNI error is surfaced instead.
fn throw_core(env: &mut Env, e: &disarm_core::Error) -> JniError {
    let class = match e.kind() {
        disarm_core::ErrorKind::InvalidArgument => EX_INVALID,
        _ => EX_ERROR,
    };
    throw(env, class, &e.to_string())
}

/// Throw `DisarmInvalidArgumentException` for a binding-level validation failure
/// (e.g. a negative size), which the core's `usize` API can't represent — this
/// mirrors the Node/Ruby bindings validating sizes in the glue.
fn throw_invalid(env: &mut Env, msg: &str) -> JniError {
    throw(env, EX_INVALID, msg)
}

/// Throw `class` with `msg` and return the sentinel [`JniError::JavaException`] so
/// `resolve` keeps the pending throw. A failed throw surfaces its own JNI error.
fn throw(env: &mut Env, class: &str, msg: &str) -> JniError {
    match env.throw_new(JNIString::from(class), JNIString::from(msg)) {
        Ok(()) => JniError::JavaException,
        Err(err) => err,
    }
}

// ── Dispatch helpers ─────────────────────────────────────────────────────────────
//
// Each takes the raw JNI env + input string(s) and a closure naming the core call.
// They own the read → run → build → resolve plumbing so the `Java_*` functions stay
// declarative. Closures are `FnOnce` and may capture the decoded `&str`.

/// `String -> String`, infallible.
fn map_str<'l>(
    mut env: EnvUnowned<'l>,
    input: JString<'l>,
    f: impl FnOnce(&str) -> String,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        Ok(env.new_string(f(&text))?.into())
    })
    .resolve::<Policy>()
}

/// `String -> Result<String>`; on error throws the mapped exception.
fn map_str_try<'l>(
    mut env: EnvUnowned<'l>,
    input: JString<'l>,
    f: impl FnOnce(&str) -> Result<String, disarm_core::Error>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        match f(&text) {
            Ok(s) => Ok(env.new_string(s)?.into()),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// `String -> bool`, infallible.
fn map_bool<'l>(
    mut env: EnvUnowned<'l>,
    input: JString<'l>,
    f: impl FnOnce(&str) -> bool,
) -> jboolean {
    env.with_env(|env| -> JniResult<jboolean> {
        let text = input.mutf8_chars(env)?.to_string();
        Ok(f(&text))
    })
    .resolve::<Policy>()
}

/// `String -> long`, infallible (widths / counts, cast from `usize`).
fn map_long<'l>(mut env: EnvUnowned<'l>, input: JString<'l>, f: impl FnOnce(&str) -> i64) -> jlong {
    env.with_env(|env| -> JniResult<jlong> {
        let text = input.mutf8_chars(env)?.to_string();
        Ok(f(&text))
    })
    .resolve::<Policy>()
}

/// `String -> String[]`, infallible.
fn map_str_array<'l>(
    mut env: EnvUnowned<'l>,
    input: JString<'l>,
    f: impl FnOnce(&str) -> Vec<String>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        new_string_array(env, &f(&text))
    })
    .resolve::<Policy>()
}

/// `() -> String[]`, infallible (metadata listings with no text argument).
fn map_str_array_nullary<'l>(
    mut env: EnvUnowned<'l>,
    f: impl FnOnce() -> Vec<String>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> { new_string_array(env, &f()) })
        .resolve::<Policy>()
}

/// Decode a Java `String[]` argument into `Vec<String>`.
fn read_string_array(env: &mut Env, arr: &JObjectArray<JString>) -> JniResult<Vec<String>> {
    let len = arr.len(env)?;
    let mut out = Vec::with_capacity(len);
    for i in 0..len {
        let element = arr.get_element(env, i)?;
        out.push(element.mutf8_chars(env)?.to_string());
    }
    Ok(out)
}

/// Build a Java `String[]` from a slice of Rust strings.
fn new_string_array<'l>(env: &mut Env<'l>, items: &[String]) -> JniResult<JObject<'l>> {
    let len = jsize::try_from(items.len()).unwrap_or(jsize::MAX);
    let array = env.new_object_array(len, JNIString::from("java/lang/String"), JObject::null())?;
    for (i, s) in items.iter().enumerate() {
        let element = env.new_string(s)?;
        array.set_element(env, i, &element)?;
    }
    Ok(array.into())
}

/// Validate a size/threshold argument (JVM `long`, so negatives arrive intact
/// rather than wrapping) and narrow to `usize`, matching the Node/Ruby bindings.
/// Returns the message to throw as `DisarmInvalidArgumentException` on failure.
fn checked_size(name: &str, value: jlong) -> Result<usize, String> {
    usize::try_from(value).map_err(|_| format!("{name} must be non-negative (got {value})"))
}

// ── Transliteration ─────────────────────────────────────────────────────────────

/// Unicode → ASCII with the default scheme (the borrow-on-no-op fast path).
#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_transliterate<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str(env, input, |t| api::transliterate(t).into_owned())
}

/// Transliterate with a scheme (`"default"` | `"strict_iso9"` | `"gost7034"`) and
/// an optional language profile (`lang`, may be null), via the core's builder.
#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_transliterateOpts<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    scheme: JString<'l>,
    lang: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let scheme = scheme.mutf8_chars(env)?.to_string();
        let lang = read_optional(env, &lang)?;
        match build_transliterate(&text, &scheme, lang.as_deref()) {
            Ok(result) => Ok(env.new_string(result)?.into()),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// Reverse-transliterate Latin → native script. `lang` is `"el"` | `"ru"` | `"uk"`.
#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_reverseTransliterate<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    lang: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let lang = lang.mutf8_chars(env)?.to_string();
        match lang.parse::<api::ReverseLang>() {
            Ok(lang) => Ok(env
                .new_string(api::reverse_transliterate(&text, lang))?
                .into()),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// Shared builder logic, mirroring the Node/Ruby shims' `transliterate_opts`.
fn build_transliterate(
    text: &str,
    scheme: &str,
    lang: Option<&str>,
) -> Result<String, disarm_core::Error> {
    let mut b = api::Transliterate::new();
    if scheme != "default" {
        let scheme: api::Scheme = scheme.parse()?;
        b = b.scheme(scheme);
    }
    if let Some(lang) = lang {
        b = b.lang(lang);
    }
    Ok(b.run(text).into_owned())
}

/// Decode a nullable `JString` argument into `Option<String>`.
fn read_optional(env: &Env, s: &JString) -> JniResult<Option<String>> {
    if s.is_null() {
        Ok(None)
    } else {
        Ok(Some(s.mutf8_chars(env)?.to_string()))
    }
}

// ── Confusables (TR39) ──────────────────────────────────────────────────────────

/// Fold cross-script confusables toward `target` (`"latin"` | `"cyrillic"`).
#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_normalizeConfusables<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    target: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let target = target.mutf8_chars(env)?.to_string();
        match target.parse::<api::TargetScript>() {
            Ok(target) => Ok(env
                .new_string(api::normalize_confusables(&text, target).as_ref())?
                .into()),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// Whether `text` contains a character confusable with `target`.
#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_isConfusable<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    target: JString<'l>,
) -> jboolean {
    env.with_env(|env| -> JniResult<jboolean> {
        let text = input.mutf8_chars(env)?.to_string();
        let target = target.mutf8_chars(env)?.to_string();
        match target.parse::<api::TargetScript>() {
            Ok(target) => Ok(api::is_confusable(&text, target)),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

// ── Canonicalization primitives (infallible String → String) ────────────────────

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_stripAccents<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str(env, input, |t| api::strip_accents(t).into_owned())
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_foldCase<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str(env, input, |t| api::fold_case(t).into_owned())
}

/// Replace emoji with their plain names; `stripModifiers` drops skin-tone marks.
#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_demojize<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    strip_modifiers: jboolean,
) -> JObject<'l> {
    let strip = strip_modifiers;
    map_str(env, input, |t| api::demojize(t, strip))
}

// ── Normalization ───────────────────────────────────────────────────────────────

/// Apply a normalization form: `"NFC"` | `"NFD"` | `"NFKC"` | `"NFKD"`.
#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_normalize<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    form: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let form = form.mutf8_chars(env)?.to_string();
        match form.parse::<api::NormalizationForm>() {
            Ok(form) => Ok(env.new_string(api::normalize(&text, form))?.into()),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// Whether `text` is already in normalization `form`.
#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_isNormalized<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    form: JString<'l>,
) -> jboolean {
    env.with_env(|env| -> JniResult<jboolean> {
        let text = input.mutf8_chars(env)?.to_string();
        let form = form.mutf8_chars(env)?.to_string();
        match form.parse::<api::NormalizationForm>() {
            Ok(form) => Ok(api::is_normalized(&text, form)),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

// ── Text cleaning (infallible String → String) ──────────────────────────────────

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_collapseWhitespace<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str(env, input, api::collapse_whitespace)
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_stripControlChars<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str(env, input, api::strip_control_chars)
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_stripZeroWidthChars<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str(env, input, api::strip_zero_width_chars)
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_stripBidi<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str(env, input, api::strip_bidi)
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_stripTags<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str(env, input, api::strip_tags)
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_stripVariationSelectors<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str(env, input, api::strip_variation_selectors)
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_stripNoncharacters<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str(env, input, api::strip_noncharacters)
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_stripPua<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str(env, input, api::strip_pua)
}

/// Collapse runs of combining marks to at most `maxMarks` per base ("de-zalgo").
#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_stripZalgo<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    max_marks: jlong,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let max_marks = match checked_size("maxMarks", max_marks) {
            Ok(n) => n,
            Err(msg) => return Err(throw_invalid(env, &msg)),
        };
        Ok(env.new_string(api::strip_zalgo(&text, max_marks))?.into())
    })
    .resolve::<Policy>()
}

/// Whether `text` carries more than `threshold` combining marks on any base.
#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_isZalgo<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    threshold: jlong,
) -> jboolean {
    env.with_env(|env| -> JniResult<jboolean> {
        let text = input.mutf8_chars(env)?.to_string();
        let threshold = match checked_size("threshold", threshold) {
            Ok(n) => n,
            Err(msg) => return Err(throw_invalid(env, &msg)),
        };
        Ok(api::is_zalgo(&text, threshold))
    })
    .resolve::<Policy>()
}

// ── Deobfuscation & security presets (fallible) ─────────────────────────────────

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_stripObfuscation<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str_try(env, input, |t| {
        api::strip_obfuscation(t).map(std::borrow::Cow::into_owned)
    })
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_canonicalize<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str_try(env, input, |t| {
        api::canonicalize(t).map(std::borrow::Cow::into_owned)
    })
}

// ── Key-derivation presets (fallible; `lang` may be null) ───────────────────────

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_searchKey<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    lang: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let lang = read_optional(env, &lang)?;
        match api::search_key(&text, lang.as_deref()) {
            Ok(s) => Ok(env.new_string(s.as_ref())?.into()),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_sortKey<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    lang: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let lang = read_optional(env, &lang)?;
        match api::sort_key(&text, lang.as_deref()) {
            Ok(s) => Ok(env.new_string(s.as_ref())?.into()),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_catalogKey<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    lang: JString<'l>,
    strict_iso9: jboolean,
) -> JObject<'l> {
    let strict = strict_iso9;
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let lang = read_optional(env, &lang)?;
        match api::catalog_key(&text, lang.as_deref(), strict) {
            Ok(s) => Ok(env.new_string(s.as_ref())?.into()),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// Turn arbitrary text into a safe filename. `platform` is `"universal"` |
/// `"windows"` | `"posix"`; `lang` may be null.
#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_sanitizeFilename<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    separator: JString<'l>,
    max_length: jlong,
    platform: JString<'l>,
    lang: JString<'l>,
    preserve_extension: jboolean,
) -> JObject<'l> {
    let preserve = preserve_extension;
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let separator = separator.mutf8_chars(env)?.to_string();
        let platform = platform.mutf8_chars(env)?.to_string();
        let lang = read_optional(env, &lang)?;
        let max_length = match checked_size("maxLength", max_length) {
            Ok(n) => n,
            Err(msg) => return Err(throw_invalid(env, &msg)),
        };
        let build = || -> Result<String, disarm_core::Error> {
            let platform: api::Platform = platform.parse()?;
            api::sanitize_filename(
                &text,
                &separator,
                max_length,
                platform,
                lang.as_deref(),
                preserve,
            )
        };
        match build() {
            Ok(s) => Ok(env.new_string(s)?.into()),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

// ── Slugs ───────────────────────────────────────────────────────────────────────

/// Generate a URL-safe slug. Mirrors the Node shim's flattened option surface; the
/// idiomatic Java layer fills defaults before calling.
#[unsafe(no_mangle)]
#[allow(clippy::too_many_arguments)] // flattened SlugConfig, mirroring the Node shim
pub extern "system" fn Java_com_disarm_internal_Native_slugify<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    separator: JString<'l>,
    lowercase: jboolean,
    max_length: jlong,
    word_boundary: jboolean,
    save_order: jboolean,
    stopwords: JObjectArray<'l, JString<'l>>,
    allow_unicode: jboolean,
    lang: JString<'l>,
    entities: jboolean,
    decimal: jboolean,
    hexadecimal: jboolean,
    safe_chars: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let separator = separator.mutf8_chars(env)?.to_string();
        let safe_chars = safe_chars.mutf8_chars(env)?.to_string();
        let lang = read_optional(env, &lang)?;
        let stopwords = read_string_array(env, &stopwords)?;
        let max_length = match checked_size("maxLength", max_length) {
            Ok(n) => n,
            Err(msg) => return Err(throw_invalid(env, &msg)),
        };
        let mut config = api::SlugConfig::default()
            .with_separator(separator)
            .with_lowercase(lowercase)
            .with_max_length(max_length)
            .with_word_boundary(word_boundary)
            .with_save_order(save_order)
            .with_stopwords(stopwords)
            .with_allow_unicode(allow_unicode)
            .with_safe_chars(safe_chars);
        if let Some(lang) = lang {
            config = config.with_lang(lang);
        }
        config.entities = entities;
        config.decimal = decimal;
        config.hexadecimal = hexadecimal;
        Ok(env.new_string(api::slugify(&text, &config))?.into())
    })
    .resolve::<Policy>()
}

// ── Grapheme clusters ───────────────────────────────────────────────────────────

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_graphemeLen<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> jlong {
    map_long(env, input, |t| api::grapheme_len(t) as jlong)
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_graphemeTruncate<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    max_graphemes: jlong,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let max_graphemes = match checked_size("maxGraphemes", max_graphemes) {
            Ok(n) => n,
            Err(msg) => return Err(throw_invalid(env, &msg)),
        };
        Ok(env
            .new_string(api::grapheme_truncate(&text, max_graphemes))?
            .into())
    })
    .resolve::<Policy>()
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_graphemeWidth<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    cluster: JString<'l>,
    ambiguous_wide: jboolean,
) -> jlong {
    let wide = ambiguous_wide;
    map_long(env, cluster, |t| api::grapheme_width(t, wide) as jlong)
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_terminalWidth<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    ambiguous_wide: jboolean,
) -> jlong {
    let wide = ambiguous_wide;
    map_long(env, input, |t| api::terminal_width(t, wide) as jlong)
}

// ── Hostname / script analysis (infallible String → bool) ───────────────────────

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_isSuspiciousHostname<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> jboolean {
    map_bool(env, input, |t| api::is_suspicious_hostname(t).suspicious)
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_isMixedScript<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> jboolean {
    map_bool(env, input, api::is_mixed_script)
}

#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_hasBidiConflict<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> jboolean {
    map_bool(env, input, api::has_bidi_conflict)
}

// ── String-array returns ────────────────────────────────────────────────────────

/// Split `text` into its grapheme clusters (user-perceived characters), in order.
#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_graphemeSplit<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str_array(env, input, api::grapheme_split)
}

/// The Unicode scripts present, in first-appearance order (Common/Inherited excluded).
#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_detectScripts<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str_array(env, input, |t| {
        api::detect_scripts(t).into_iter().map(str::to_owned).collect()
    })
}

/// Every Unicode script name known to the transliteration tables.
#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_listScripts<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
) -> JObject<'l> {
    map_str_array_nullary(env, || {
        api::list_scripts().into_iter().map(str::to_owned).collect()
    })
}

/// Every language code that has a context-aware transliteration profile.
#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_listContextLangs<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
) -> JObject<'l> {
    map_str_array_nullary(env, || {
        api::list_context_langs()
            .into_iter()
            .map(str::to_owned)
            .collect()
    })
}
