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
//! Naming: the `#[jni_mangle("dev.disarm.internal.Native")]` attribute generates
//! the `Java_dev_disarm_internal_Native_<method>` export symbol from each function
//! name (no hand-written `Java_*` names, no `#[unsafe(no_mangle)]`), keeping the
//! export/`extern "system"` plumbing inside the macro — the same way the Node
//! (napi) and Ruby (magnus) bindings hide it. Rust fn names are the camelCase Java
//! method names. `Native` is package-internal, so we skip the `_`-prefix "raw"
//! convention the other bindings use for language-visible functions.
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

use std::collections::{HashMap, HashSet};
use std::sync::atomic::{AtomicI64, Ordering};
use std::sync::{LazyLock, RwLock};

use disarm_core::api;
use jni::errors::{Error as JniError, Result as JniResult};
use jni::objects::{JClass, JObject, JObjectArray, JString, JValue};
use jni::strings::JNIString;
use jni::sys::{jboolean, jlong, jsize};
use jni::{Env, EnvUnowned, jni_mangle, jni_sig};

/// The error/panic → Java-exception mapping used to `resolve` every entry point.
type Policy = jni::errors::ThrowRuntimeExAndDefault;

/// JVM binary names of the exception classes the idiomatic layer defines.
const EX_INVALID: &str = "dev/disarm/DisarmInvalidArgumentException";
const EX_ERROR: &str = "dev/disarm/DisarmException";

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

/// `() -> String`, infallible (bundled-data version constants, no text argument).
fn map_string_nullary<'l>(mut env: EnvUnowned<'l>, f: impl FnOnce() -> String) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> { Ok(env.new_string(f())?.into()) })
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
    let Ok(len) = jsize::try_from(items.len()) else {
        return Err(throw_invalid(env, "array length exceeds JNI jsize::MAX"));
    };
    let array = env.new_object_array(len, JNIString::from("java/lang/String"), JObject::null())?;
    for (i, s) in items.iter().enumerate() {
        let element = env.new_string(s)?;
        array.set_element(env, i, &element)?;
    }
    Ok(array.into())
}

/// Build a Java `Object[]` of class `class_name` from already-built element objects.
fn new_object_array_of<'l>(
    env: &mut Env<'l>,
    class_name: &str,
    items: &[JObject<'l>],
) -> JniResult<JObject<'l>> {
    let Ok(len) = jsize::try_from(items.len()) else {
        return Err(throw_invalid(env, "array length exceeds JNI jsize::MAX"));
    };
    let array = env.new_object_array(len, JNIString::from(class_name), JObject::null())?;
    for (i, obj) in items.iter().enumerate() {
        array.set_element(env, i, obj)?;
    }
    Ok(array.into())
}

/// Wrap an `Object[]` in an immutable `java.util.List` via `List.of(Object[])`.
fn list_of<'l>(env: &mut Env<'l>, array: &JObject<'l>) -> JniResult<JObject<'l>> {
    env.call_static_method(
        JNIString::from("java/util/List"),
        JNIString::from("of"),
        jni_sig!("([Ljava/lang/Object;)Ljava/util/List;"),
        &[JValue::Object(array)],
    )?
    .l()
}

/// Build an immutable `List<String>` from Rust strings.
fn new_string_list<'l>(env: &mut Env<'l>, items: &[String]) -> JniResult<JObject<'l>> {
    let array = new_string_array(env, items)?;
    list_of(env, &array)
}

/// Build a Java `String`, or `null` for `None` (for nullable record components).
fn opt_string<'l>(env: &mut Env<'l>, s: Option<&str>) -> JniResult<JObject<'l>> {
    match s {
        Some(v) => Ok(env.new_string(v)?.into()),
        None => Ok(JObject::null()),
    }
}

/// Validate a size/threshold argument (JVM `long`, so negatives arrive intact
/// rather than wrapping) and narrow to `usize`, matching the Node/Ruby bindings.
/// Returns the message to throw as `DisarmInvalidArgumentException` on failure.
fn checked_size(name: &str, value: jlong) -> Result<usize, String> {
    usize::try_from(value).map_err(|_| format!("{name} must be non-negative (got {value})"))
}

// ── Transliteration ─────────────────────────────────────────────────────────────

/// Unicode → ASCII with the default scheme (the borrow-on-no-op fast path).
#[jni_mangle("dev.disarm.internal.Native")]
pub fn transliterate<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str(env, input, |t| api::transliterate(t).into_owned())
}

/// Transliterate with a scheme (`"default"` | `"strict_iso9"` | `"gost7034"`) and
/// an optional language profile (`lang`, may be null), via the core's builder.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn transliterateOpts<'l>(
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
#[jni_mangle("dev.disarm.internal.Native")]
pub fn reverseTransliterate<'l>(
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
/// The `digitPolicy` token every key builder takes (#896): parsed at the boundary, and a
/// bad token throws the core's `InvalidArgument` like any other.
fn read_policy(env: &mut Env, s: &JString) -> JniResult<api::DigitPolicy> {
    let token = s.mutf8_chars(env)?.to_string();
    match token.parse::<api::DigitPolicy>() {
        Ok(p) => Ok(p),
        Err(e) => Err(throw_core(env, &e)),
    }
}

fn read_optional(env: &Env, s: &JString) -> JniResult<Option<String>> {
    if s.is_null() {
        Ok(None)
    } else {
        Ok(Some(s.mutf8_chars(env)?.to_string()))
    }
}

/// Characters with no romanization, as a `List<Untranslatable(character, offset)>`
/// in order. `scheme`/`lang` mirror `transliterateOpts`.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn findUntranslatable<'l>(
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
        let items = match build_find_untranslatable(&text, &scheme, lang.as_deref()) {
            Ok(v) => v,
            Err(e) => return Err(throw_core(env, &e)),
        };
        let mut objs = Vec::with_capacity(items.len());
        for u in &items {
            objs.push(new_untranslatable(env, u)?);
        }
        let array = new_object_array_of(env, "dev/disarm/Untranslatable", &objs)?;
        list_of(env, &array)
    })
    .resolve::<Policy>()
}

fn build_find_untranslatable(
    text: &str,
    scheme: &str,
    lang: Option<&str>,
) -> Result<Vec<api::Untranslatable>, disarm_core::Error> {
    let mut b = api::Transliterate::new();
    if scheme != "default" {
        let scheme: api::Scheme = scheme.parse()?;
        b = b.scheme(scheme);
    }
    if let Some(lang) = lang {
        b = b.lang(lang);
    }
    Ok(b.find_untranslatable(text))
}

/// Construct a `dev.disarm.Untranslatable` record.
fn new_untranslatable<'l>(env: &mut Env<'l>, u: &api::Untranslatable) -> JniResult<JObject<'l>> {
    let ch = env.new_string(u.ch.to_string())?;
    env.new_object(
        JNIString::from("dev/disarm/Untranslatable"),
        jni_sig!("(Ljava/lang/String;J)V"),
        &[JValue::Object(&ch), JValue::Long(u.offset as jlong)],
    )
}

// ── Confusables (TR39) ──────────────────────────────────────────────────────────

/// Fold cross-script confusables toward `target` (`"latin"` | `"cyrillic"` | `"arabic"` | `"hebrew"`).
#[jni_mangle("dev.disarm.internal.Native")]
pub fn normalizeConfusables<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    target: JString<'l>,
    digit_policy: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let target = target.mutf8_chars(env)?.to_string();
        let digit_policy = digit_policy.mutf8_chars(env)?.to_string();
        let target = match target.parse::<api::TargetScript>() {
            Ok(t) => t,
            Err(e) => return Err(throw_core(env, &e)),
        };
        let digit_policy = match digit_policy.parse::<api::DigitPolicy>() {
            Ok(d) => d,
            Err(e) => return Err(throw_core(env, &e)),
        };
        Ok(env
            .new_string(api::normalize_confusables_with(&text, target, digit_policy).as_ref())?
            .into())
    })
    .resolve::<Policy>()
}

/// ML/NLP normalization preset. `lang` and `emojiStyle` may be null / "cldr";
/// `foldCase` drops the case-fold step when false.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn mlNormalize<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    lang: JString<'l>,
    emoji_style: JString<'l>,
    fold_case: jboolean,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let lang = read_optional(env, &lang)?;
        let emoji_style = emoji_style.mutf8_chars(env)?.to_string();
        match api::ml_normalize(&text, lang.as_deref(), &emoji_style, fold_case) {
            Ok(s) => Ok(env.new_string(s.as_ref())?.into()),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// Every upstream confusable source the bundled `target` table does not fold (#563).
#[jni_mangle("dev.disarm.internal.Native")]
pub fn unmappedConfusables<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    target: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let target = target.mutf8_chars(env)?.to_string();
        match target.parse::<api::TargetScript>() {
            Ok(target) => {
                let items: Vec<String> = api::unmapped_confusables(target)
                    .into_iter()
                    .map(String::from)
                    .collect();
                new_string_array(env, &items)
            }
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// Confusable sources in `text` the bundled `target` table does not fold, as a
/// `List<UnmappedConfusable(character, offset)>` in order (#563).
#[jni_mangle("dev.disarm.internal.Native")]
pub fn findUnmappedConfusables<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    target: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let target = target.mutf8_chars(env)?.to_string();
        let target = match target.parse::<api::TargetScript>() {
            Ok(t) => t,
            Err(e) => return Err(throw_core(env, &e)),
        };
        let items = api::find_unmapped_confusables(&text, target);
        let mut objs = Vec::with_capacity(items.len());
        for u in &items {
            let ch = env.new_string(u.ch.to_string())?;
            objs.push(env.new_object(
                JNIString::from("dev/disarm/UnmappedConfusable"),
                jni_sig!("(Ljava/lang/String;J)V"),
                &[JValue::Object(&ch), JValue::Long(u.offset as jlong)],
            )?);
        }
        let array = new_object_array_of(env, "dev/disarm/UnmappedConfusable", &objs)?;
        list_of(env, &array)
    })
    .resolve::<Policy>()
}

/// Whether `text` contains a character confusable with `target`.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn isConfusable<'l>(
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

#[jni_mangle("dev.disarm.internal.Native")]
pub fn stripAccents<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str(env, input, |t| api::strip_accents(t).into_owned())
}

#[jni_mangle("dev.disarm.internal.Native")]
pub fn foldCase<'l>(env: EnvUnowned<'l>, _class: JClass<'l>, input: JString<'l>) -> JObject<'l> {
    map_str(env, input, |t| api::fold_case(t).into_owned())
}

/// Whether case folding and simple lowercasing agree, so `text` is a stable
/// identity key ("groß.txt" is not; "gross.txt" is).
#[jni_mangle("dev.disarm.internal.Native")]
pub fn isCaseFoldStable<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> jboolean {
    env.with_env(|env| -> JniResult<jboolean> {
        let text = input.mutf8_chars(env)?.to_string();
        Ok(api::is_case_fold_stable(&text))
    })
    .resolve::<Policy>()
}

/// Which of `values` are the same name under `key` (#620). `key` is one of
/// `fold_case`, `search_key`, `catalog_key`, `canonicalize`, `canonicalize_strict`,
/// `normalize_confusables`; there is no default, because the choice is the policy.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn findKeyCollisions<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    values: JObjectArray<'l, JString<'l>>,
    key: JString<'l>,
    lang: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let values = read_string_array(env, &values)?;
        let key = key.mutf8_chars(env)?.to_string();
        let key: api::KeyForm = match key.parse() {
            Ok(k) => k,
            Err(e) => return Err(throw_core(env, &e)),
        };
        let lang = read_optional(env, &lang)?;
        match api::find_key_collisions(&values, key, lang.as_deref()) {
            Ok(found) => {
                let mut objs = Vec::with_capacity(found.len());
                for c in &found {
                    objs.push(new_key_collision(env, c)?);
                }
                let array = new_object_array_of(env, "dev/disarm/KeyCollision", &objs)?;
                list_of(env, &array)
            }
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// Replace emoji with their plain names; `stripModifiers` drops skin-tone marks.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn demojize<'l>(
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
#[jni_mangle("dev.disarm.internal.Native")]
pub fn normalize<'l>(
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
#[jni_mangle("dev.disarm.internal.Native")]
pub fn isNormalized<'l>(
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

#[jni_mangle("dev.disarm.internal.Native")]
pub fn collapseWhitespace<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str(env, input, api::collapse_whitespace)
}

#[jni_mangle("dev.disarm.internal.Native")]
pub fn stripControlChars<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str(env, input, api::strip_control_chars)
}

#[jni_mangle("dev.disarm.internal.Native")]
pub fn stripZeroWidthChars<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str(env, input, api::strip_zero_width_chars)
}

#[jni_mangle("dev.disarm.internal.Native")]
pub fn stripBidi<'l>(env: EnvUnowned<'l>, _class: JClass<'l>, input: JString<'l>) -> JObject<'l> {
    map_str(env, input, api::strip_bidi)
}

#[jni_mangle("dev.disarm.internal.Native")]
pub fn stripTags<'l>(env: EnvUnowned<'l>, _class: JClass<'l>, input: JString<'l>) -> JObject<'l> {
    map_str(env, input, api::strip_tags)
}

#[jni_mangle("dev.disarm.internal.Native")]
pub fn stripVariationSelectors<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str(env, input, api::strip_variation_selectors)
}

#[jni_mangle("dev.disarm.internal.Native")]
pub fn stripNoncharacters<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str(env, input, api::strip_noncharacters)
}

#[jni_mangle("dev.disarm.internal.Native")]
pub fn stripPua<'l>(env: EnvUnowned<'l>, _class: JClass<'l>, input: JString<'l>) -> JObject<'l> {
    map_str(env, input, api::strip_pua)
}

/// Collapse runs of combining marks to at most `maxMarks` per base ("de-zalgo").
#[jni_mangle("dev.disarm.internal.Native")]
pub fn stripZalgo<'l>(
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
#[jni_mangle("dev.disarm.internal.Native")]
pub fn isZalgo<'l>(
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

#[jni_mangle("dev.disarm.internal.Native")]
pub fn stripObfuscation<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    digit_policy: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let policy = read_policy(env, &digit_policy)?;
        match api::strip_obfuscation_with(&text, policy) {
            Ok(s) => Ok(env.new_string(s.as_ref())?.into()),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// Strip the non-interchange and invisible classes while keeping the script (#698).
///
/// Not composable from the seven universal `strip*` primitives, and the difference runs
/// both ways: this preserves the Private Use Area and the VS15/VS16 presentation
/// selectors after a base (`RENDERING_STRIP`), which the naive chain deletes, and it
/// collapses TAB/LF where the primitives leave them. The policy is a private constant.
/// Infallible.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn stripFormat<'l>(env: EnvUnowned<'l>, _class: JClass<'l>, input: JString<'l>) -> JObject<'l> {
    map_str(env, input, |t| api::strip_format(t).into_owned())
}

/// `canonicalize`, but refuses rather than silently normalizing away a structural
/// difference. The half of the pair that lets a caller *reject* input instead of
/// comparing a value the sender never wrote.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn canonicalizeStrict<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    digit_policy: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let policy = read_policy(env, &digit_policy)?;
        match api::canonicalize_strict_with(&text, policy) {
            Ok(s) => Ok(env.new_string(s.as_ref())?.into()),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// Whether `text` is already its own canonical form under `preset` (#730).
#[jni_mangle("dev.disarm.internal.Native")]
pub fn isCanonical<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    preset: JString<'l>,
) -> jboolean {
    env.with_env(|env| -> JniResult<jboolean> {
        let text = input.mutf8_chars(env)?.to_string();
        let preset = preset.mutf8_chars(env)?.to_string();
        match api::is_canonical(&text, &preset) {
            Ok(v) => Ok(jboolean::from(v)),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

#[jni_mangle("dev.disarm.internal.Native")]
pub fn canonicalize<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    digit_policy: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let policy = read_policy(env, &digit_policy)?;
        match api::canonicalize_with(&text, policy) {
            Ok(s) => Ok(env.new_string(s.as_ref())?.into()),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

// ── Key-derivation presets (fallible; `lang` may be null) ───────────────────────

#[jni_mangle("dev.disarm.internal.Native")]
pub fn searchKey<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    lang: JString<'l>,
    digit_policy: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let lang = read_optional(env, &lang)?;
        let policy = read_policy(env, &digit_policy)?;
        match api::search_key_with(&text, lang.as_deref(), policy) {
            Ok(s) => Ok(env.new_string(s.as_ref())?.into()),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

#[jni_mangle("dev.disarm.internal.Native")]
pub fn sortKey<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    lang: JString<'l>,
    digit_policy: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let lang = read_optional(env, &lang)?;
        let policy = read_policy(env, &digit_policy)?;
        match api::sort_key_with(&text, lang.as_deref(), policy) {
            Ok(s) => Ok(env.new_string(s.as_ref())?.into()),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

#[jni_mangle("dev.disarm.internal.Native")]
pub fn catalogKey<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    lang: JString<'l>,
    strict_iso9: jboolean,
    digit_policy: JString<'l>,
) -> JObject<'l> {
    let strict = strict_iso9;
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let lang = read_optional(env, &lang)?;
        let policy = read_policy(env, &digit_policy)?;
        match api::catalog_key_with(&text, lang.as_deref(), strict, policy) {
            Ok(s) => Ok(env.new_string(s.as_ref())?.into()),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// The TR39 identifier skeleton plus the two prototype classes disarm's table keeps apart
/// (#650). A spoof key: never for display. `digitPolicy` is `numeric` (the letter half
/// only), `tr39` (adds `1 ≡ l` and `0 ≡ O`) or `preserve`.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn skeletonKey<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    digit_policy: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let policy = read_policy(env, &digit_policy)?;
        match api::skeleton_key(&text, policy) {
            Ok(s) => Ok(env.new_string(s.as_ref())?.into()),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// Levenshtein edit distance between `a` and `b`, in characters (#894).
#[jni_mangle("dev.disarm.internal.Native")]
pub fn editDistance<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    a: JString<'l>,
    b: JString<'l>,
) -> jlong {
    env.with_env(|env| -> JniResult<jlong> {
        let a = a.mutf8_chars(env)?.to_string();
        let b = b.mutf8_chars(env)?.to_string();
        Ok(jlong::try_from(api::edit_distance(&a, &b)).unwrap_or(jlong::MAX))
    })
    .resolve::<Policy>()
}

/// The candidate closest to `value` as a zero- or one-element list of
/// `dev.disarm.NearestMatch` (#894): empty beyond `maxDistance`. A list rather than a
/// nullable object so the boundary carries one shape; the facade unwraps it.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn nearestMatch<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    value: JString<'l>,
    candidates: JObjectArray<'l, JString<'l>>,
    max_distance: jlong,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let value = value.mutf8_chars(env)?.to_string();
        let candidates = read_string_array(env, &candidates)?;
        // A negative threshold is rejected, not coerced to "exact match only" (#952 review).
        let max = match checked_size("maxDistance", max_distance) {
            Ok(n) => n,
            Err(msg) => return Err(throw_invalid(env, &msg)),
        };
        let hit = api::nearest_match(&value, candidates.iter().map(String::as_str), max);
        let mut objs = Vec::with_capacity(1);
        if let Some(m) = &hit {
            objs.push(new_nearest_match(env, m)?);
        }
        let array = new_object_array_of(env, "dev/disarm/NearestMatch", &objs)?;
        list_of(env, &array)
    })
    .resolve::<Policy>()
}

/// Turn arbitrary text into a safe filename. `platform` is `"universal"` |
/// `"windows"` | `"posix"`; `lang` may be null.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn sanitizeFilename<'l>(
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
#[jni_mangle("dev.disarm.internal.Native")]
#[allow(clippy::too_many_arguments)] // flattened SlugConfig, mirroring the Node shim
pub fn slugify<'l>(
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

#[jni_mangle("dev.disarm.internal.Native")]
pub fn graphemeLen<'l>(env: EnvUnowned<'l>, _class: JClass<'l>, input: JString<'l>) -> jlong {
    map_long(env, input, |t| api::grapheme_len(t) as jlong)
}

#[jni_mangle("dev.disarm.internal.Native")]
pub fn graphemeTruncate<'l>(
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

#[jni_mangle("dev.disarm.internal.Native")]
pub fn graphemeWidth<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    cluster: JString<'l>,
    ambiguous_wide: jboolean,
) -> jlong {
    let wide = ambiguous_wide;
    map_long(env, cluster, |t| api::grapheme_width(t, wide) as jlong)
}

#[jni_mangle("dev.disarm.internal.Native")]
pub fn terminalWidth<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    ambiguous_wide: jboolean,
) -> jlong {
    let wide = ambiguous_wide;
    map_long(env, input, |t| api::terminal_width(t, wide) as jlong)
}

// ── Hostname / script analysis (infallible String → bool) ───────────────────────

#[jni_mangle("dev.disarm.internal.Native")]
pub fn isSuspiciousHostname<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> jboolean {
    map_bool(env, input, |t| api::is_suspicious_hostname(t).suspicious)
}

/// Full hostname homoglyph analysis (#549) as a `dev.disarm.HostnameAnalysis`
/// record. `isSuspiciousHostname` is the boolean shorthand for `.suspicious`.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn analyzeHostname<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    contractions: jboolean,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let host = input.mutf8_chars(env)?.to_string();
        let analysis = api::analyze_hostname_with(&host, contractions);
        new_hostname_analysis(env, &analysis)
    })
    .resolve::<Policy>()
}

#[jni_mangle("dev.disarm.internal.Native")]
pub fn isMixedScript<'l>(env: EnvUnowned<'l>, _class: JClass<'l>, input: JString<'l>) -> jboolean {
    map_bool(env, input, api::is_mixed_script)
}

/// All twelve UAX #9 explicit formatting characters, uncontexted (#778). The counterpart
/// to `has_bidi_conflict`, which reads strong-direction letters and is blind to these; the
/// two are disjoint. The detector's `bidi` kind reports nine, holding back LRM, RLM and ALM
/// because a lone directional mark is ordinary in right-to-left text.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn hasBidiControl<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> jboolean {
    map_bool(env, input, api::has_bidi_control)
}

#[jni_mangle("dev.disarm.internal.Native")]
pub fn hasBidiConflict<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> jboolean {
    map_bool(env, input, api::has_bidi_conflict)
}

// ── String-array returns ────────────────────────────────────────────────────────

/// Split `text` into its grapheme clusters (user-perceived characters), in order.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn graphemeSplit<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str_array(env, input, api::grapheme_split)
}

/// The Unicode scripts present, in first-appearance order (Common/Inherited excluded).
#[jni_mangle("dev.disarm.internal.Native")]
pub fn detectScripts<'l>(
    env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    map_str_array(env, input, |t| {
        api::detect_scripts(t)
            .into_iter()
            .map(str::to_owned)
            .collect()
    })
}

/// The Unicode `confusables.txt` release the bundled confusable tables were folded
/// from (#560). Not a library-wide Unicode version — see docs/provenance.md.
/// The UCD release disarm's normalizer implements (#645). Not a library-wide Unicode
/// version — the bundled tables track different releases; this is the one integrators ask
/// about, because it decides whether disarm's normalization agrees with the host
/// platform's.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn unicodeVersion<'l>(env: EnvUnowned<'l>, _class: JClass<'l>) -> JObject<'l> {
    map_string_nullary(env, || disarm_core::api::UNICODE_VERSION.to_owned())
}

/// Whether a key stored under an earlier release still compares equal (#645). A
/// monotonic counter, not a version: two artifacts reporting the same value produce the
/// same key for the same input. Meaningless in isolation, by design.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn keySchemaVersion(_env: EnvUnowned, _class: JClass) -> i32 {
    disarm_core::api::KEY_SCHEMA_VERSION as i32
}

#[jni_mangle("dev.disarm.internal.Native")]
pub fn confusablesVersion<'l>(env: EnvUnowned<'l>, _class: JClass<'l>) -> JObject<'l> {
    map_string_nullary(env, || disarm_core::api::CONFUSABLES_VERSION.to_owned())
}

/// Every Unicode script name known to the transliteration tables.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn listScripts<'l>(env: EnvUnowned<'l>, _class: JClass<'l>) -> JObject<'l> {
    map_str_array_nullary(env, || {
        api::list_scripts().into_iter().map(str::to_owned).collect()
    })
}

/// Every language code that has a context-aware transliteration profile.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn listContextLangs<'l>(env: EnvUnowned<'l>, _class: JClass<'l>) -> JObject<'l> {
    map_str_array_nullary(env, || {
        api::list_context_langs()
            .into_iter()
            .map(str::to_owned)
            .collect()
    })
}

// ── Metadata introspection (record returns) ─────────────────────────────────────

/// Static facts about a language `code`; throws on an unknown code.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn langInfo<'l>(mut env: EnvUnowned<'l>, _class: JClass<'l>, code: JString<'l>) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let code = code.mutf8_chars(env)?.to_string();
        match api::lang_info(&code) {
            Ok(m) => new_lang_meta(env, &m),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// Construct a `dev.disarm.LangMeta` record.
fn new_lang_meta<'l>(env: &mut Env<'l>, m: &api::LangMeta) -> JniResult<JObject<'l>> {
    let name = env.new_string(m.name)?;
    let script = env.new_string(m.script)?;
    let region = env.new_string(m.region)?;
    let context = env.new_string(m.context)?;
    env.new_object(
        JNIString::from("dev/disarm/LangMeta"),
        jni_sig!("(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V"),
        &[
            JValue::Object(&name),
            JValue::Object(&script),
            JValue::Object(&region),
            JValue::Object(&context),
        ],
    )
}

/// Static facts about a script by `name`; throws on an unknown name.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn scriptInfo<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    name: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let name = name.mutf8_chars(env)?.to_string();
        match api::script_info(&name) {
            Ok(m) => new_script_meta(env, &m),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// Construct a `dev.disarm.ScriptMeta` record.
fn new_script_meta<'l>(env: &mut Env<'l>, m: &api::ScriptMeta) -> JniResult<JObject<'l>> {
    let name = env.new_string(m.name)?;
    let default_lang = opt_string(env, m.default_lang)?;
    let example = env.new_string(m.example)?;
    env.new_object(
        JNIString::from("dev/disarm/ScriptMeta"),
        jni_sig!("(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Z)V"),
        &[
            JValue::Object(&name),
            JValue::Object(&default_lang),
            JValue::Object(&example),
            JValue::Bool(m.context_aware),
        ],
    )
}

/// Narrow a census count to the `jint` the record takes.
///
/// Cannot fail for a table `build.rs` accepted: the whole population is 6,565 sources,
/// so every row is far inside `i32`. The `debug_assert` is what turns a table that
/// stopped being one into a test failure rather than a plausible-looking number.
fn census_count(value: u32) -> i32 {
    debug_assert!(
        i32::try_from(value).is_ok(),
        "census count {value} does not fit an i32; the table is bounded at 6,565 sources"
    );
    i32::try_from(value).unwrap_or(i32::MAX)
}

/// TR39 sources whose prototype is in `script` and how many the bundled tables fold
/// (#963); throws on an unknown script.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn confusableCoverage<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    script: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let script = script.mutf8_chars(env)?.to_string();
        match api::confusable_coverage(&script) {
            Ok(row) => {
                let name = env.new_string(row.script)?;
                env.new_object(
                    JNIString::from("dev/disarm/ConfusableCoverage"),
                    jni_sig!("(Ljava/lang/String;II)V"),
                    &[
                        JValue::Object(&name),
                        // Census counts, bounded by the source population. The invariant
                        // is enforced where it can fail — `build.rs` refuses a table
                        // whose rows do not sum to 6,565 — so this conversion is
                        // defensive only. It saturates rather than panicking because the
                        // crate denies `expect_used` and unwinding across the JNI
                        // boundary is worse than a wrong number; the assertion makes a
                        // violation loud in every debug build instead.
                        JValue::Int(census_count(row.sources)),
                        JValue::Int(census_count(row.folded)),
                    ],
                )
            }
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// Explain how `lang: "auto"` detection resolves `text` (infallible).
#[jni_mangle("dev.disarm.internal.Native")]
pub fn inspectAutoLang<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let r = api::inspect_auto_lang(&text);
        let script = opt_string(env, r.script.as_deref())?;
        let chosen_lang = opt_string(env, r.chosen_lang.as_deref())?;
        let reason = env.new_string(&r.reason)?;
        let discriminators = new_string_list(env, &r.discriminators_hit)?;
        env.new_object(
            JNIString::from("dev/disarm/AutoLangInspection"),
            jni_sig!("(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/util/List;)V"),
            &[
                JValue::Object(&script),
                JValue::Object(&chosen_lang),
                JValue::Object(&reason),
                JValue::Object(&discriminators),
            ],
        )
    })
    .resolve::<Policy>()
}

// ── Reusable handles (opaque jlong pointers) ────────────────────────────────────
//
// `Pipeline` and `Lexicon` compile/build once and are reused across calls, so the
// build cost is paid a single time (matters for the perf mandate). Handles are
// **opaque integer IDs into a safe registry** — NOT raw pointers — so the binding
// needs no `unsafe` deref (this crate contains no `unsafe` code at all; the FFI
// export ABI is synthesized inside the `#[jni_mangle]` macro). A freed/unknown
// handle is a clean thrown exception, not undefined behaviour. The idiomatic Java
// wrapper is `AutoCloseable` (+ a `Cleaner` backstop) so each handle is freed once.

/// Registry of live pipelines, keyed by the opaque handle handed to Java.
static PIPELINES: LazyLock<RwLock<HashMap<i64, api::Pipeline>>> =
    LazyLock::new(|| RwLock::new(HashMap::new()));
/// Registry of live anomaly lexicons.
static LEXICONS: LazyLock<RwLock<HashMap<i64, HashSet<String>>>> =
    LazyLock::new(|| RwLock::new(HashMap::new()));
/// Monotonic handle allocator (never reuses an ID, so a stale handle can't alias).
static NEXT_HANDLE: AtomicI64 = AtomicI64::new(1);

fn next_handle() -> i64 {
    NEXT_HANDLE.fetch_add(1, Ordering::Relaxed)
}

/// Acquire a write guard, recovering the map if a prior holder panicked (a poisoned
/// lock is not a reason to abort a registry insert/remove).
fn write_registry<V>(
    lock: &RwLock<HashMap<i64, V>>,
) -> std::sync::RwLockWriteGuard<'_, HashMap<i64, V>> {
    lock.write()
        .unwrap_or_else(std::sync::PoisonError::into_inner)
}

/// Acquire a read guard, recovering from poisoning as above.
fn read_registry<V>(
    lock: &RwLock<HashMap<i64, V>>,
) -> std::sync::RwLockReadGuard<'_, HashMap<i64, V>> {
    lock.read()
        .unwrap_or_else(std::sync::PoisonError::into_inner)
}

/// Compile a named-policy pipeline; returns an opaque handle (throws on unknown profile).
#[jni_mangle("dev.disarm.internal.Native")]
pub fn pipelineNew<'l>(mut env: EnvUnowned<'l>, _class: JClass<'l>, profile: JString<'l>) -> jlong {
    env.with_env(|env| -> JniResult<jlong> {
        let profile = profile.mutf8_chars(env)?.to_string();
        match api::get_pipeline(&profile) {
            Ok(p) => {
                let id = next_handle();
                write_registry(&PIPELINES).insert(id, p);
                Ok(id)
            }
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// A copy of `handle`'s pipeline whose confusable passes fold under `digitPolicy` (#646),
/// as a fresh handle. Throws when the profile has no confusables step and the policy is not
/// the default; `0` for a handle that is not registered (the facade guards `close()`).
#[jni_mangle("dev.disarm.internal.Native")]
pub fn pipelineWithDigitPolicy<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    handle: jlong,
    digit_policy: JString<'l>,
) -> jlong {
    env.with_env(|env| -> JniResult<jlong> {
        let policy = read_policy(env, &digit_policy)?;
        let Some(pipeline) = read_registry(&PIPELINES).get(&handle).cloned() else {
            return Ok(0);
        };
        match pipeline.with_digit_policy(policy) {
            Ok(p) => {
                let id = next_handle();
                write_registry(&PIPELINES).insert(id, p);
                Ok(id)
            }
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// What the named profile a handle was built from is for, or null (#860).
#[jni_mangle("dev.disarm.internal.Native")]
pub fn pipelinePurpose<'l>(mut env: EnvUnowned<'l>, _class: JClass<'l>, handle: jlong) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        // A stale handle must not read as "this pipeline has no purpose". `null` is a
        // real answer here — a hand-built pipeline has none — so the two have to be told
        // apart, the way `pipelineProcess` does (#962 review).
        let registry = read_registry(&PIPELINES);
        let Some(pipeline) = registry.get(&handle) else {
            return Err(throw_invalid(env, "invalid or closed Pipeline handle"));
        };
        match pipeline.purpose() {
            Some(p) => Ok(env.new_string(p)?.into()),
            None => Ok(JObject::null()),
        }
    })
    .resolve::<Policy>()
}

/// Run a pipeline handle over `text` (throws on a processing error or stale handle).
#[jni_mangle("dev.disarm.internal.Native")]
pub fn pipelineProcess<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    handle: jlong,
    input: JString<'l>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let registry = read_registry(&PIPELINES);
        let Some(pipeline) = registry.get(&handle) else {
            return Err(throw_invalid(env, "invalid or closed Pipeline handle"));
        };
        match pipeline.process(&text) {
            Ok(s) => Ok(env.new_string(s)?.into()),
            Err(e) => Err(throw_core(env, &e)),
        }
    })
    .resolve::<Policy>()
}

/// Free a pipeline handle (removing it from the registry). Idempotent.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn pipelineFree(_env: EnvUnowned, _class: JClass, handle: jlong) {
    write_registry(&PIPELINES).remove(&handle);
}

/// Build a reusable lexicon (anomaly wordlist); returns an opaque handle.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn lexiconNew<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    words: JObjectArray<'l, JString<'l>>,
) -> jlong {
    env.with_env(|env| -> JniResult<jlong> {
        let set = api::lexicon(read_string_array(env, &words)?);
        let id = next_handle();
        write_registry(&LEXICONS).insert(id, set);
        Ok(id)
    })
    .resolve::<Policy>()
}

/// Free a lexicon handle. Idempotent.
#[jni_mangle("dev.disarm.internal.Native")]
pub fn lexiconFree(_env: EnvUnowned, _class: JClass, handle: jlong) {
    write_registry(&LEXICONS).remove(&handle);
}

/// Whether `text` trips any anomaly against a prebuilt lexicon handle (throws on a
/// stale handle).
#[jni_mangle("dev.disarm.internal.Native")]
pub fn hasAnomalies<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    lexicon: jlong,
) -> jboolean {
    env.with_env(|env| -> JniResult<jboolean> {
        let text = input.mutf8_chars(env)?.to_string();
        let registry = read_registry(&LEXICONS);
        let Some(set) = registry.get(&lexicon) else {
            return Err(throw_invalid(env, "invalid or closed Lexicon handle"));
        };
        Ok(api::has_anomalies(&text, set))
    })
    .resolve::<Policy>()
}

/// Whether `text` trips any anomaly against an inline word list (per-call set build).
#[jni_mangle("dev.disarm.internal.Native")]
pub fn hasAnomaliesWords<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    words: JObjectArray<'l, JString<'l>>,
) -> jboolean {
    env.with_env(|env| -> JniResult<jboolean> {
        let text = input.mutf8_chars(env)?.to_string();
        let set = api::lexicon(read_string_array(env, &words)?);
        Ok(api::has_anomalies(&text, &set))
    })
    .resolve::<Policy>()
}

/// Full anomaly report against a prebuilt lexicon handle (throws on a stale handle).
#[jni_mangle("dev.disarm.internal.Native")]
pub fn inspectAnomalies<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    lexicon: jlong,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        // Scope the read lock so it is released before building JNI objects.
        let report = {
            let registry = read_registry(&LEXICONS);
            let Some(set) = registry.get(&lexicon) else {
                return Err(throw_invalid(env, "invalid or closed Lexicon handle"));
            };
            api::inspect_anomalies(&text, set)
        };
        new_anomaly_report(env, &report)
    })
    .resolve::<Policy>()
}

/// Full anomaly report against an inline word list (per-call set build).
#[jni_mangle("dev.disarm.internal.Native")]
pub fn inspectAnomaliesWords<'l>(
    mut env: EnvUnowned<'l>,
    _class: JClass<'l>,
    input: JString<'l>,
    words: JObjectArray<'l, JString<'l>>,
) -> JObject<'l> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let set = api::lexicon(read_string_array(env, &words)?);
        let report = api::inspect_anomalies(&text, &set);
        new_anomaly_report(env, &report)
    })
    .resolve::<Policy>()
}

/// Construct a `dev.disarm.Finding` record.
fn new_finding<'l>(env: &mut Env<'l>, f: &api::Finding) -> JniResult<JObject<'l>> {
    let kind = env.new_string(f.kind.as_str())?;
    let token = env.new_string(&f.token)?;
    let detail = env.new_string(&f.detail)?;
    let reason = env.new_string(f.reason())?;
    env.new_object(
        JNIString::from("dev/disarm/Finding"),
        jni_sig!("(Ljava/lang/String;Ljava/lang/String;JJLjava/lang/String;Ljava/lang/String;)V"),
        &[
            JValue::Object(&kind),
            JValue::Object(&token),
            JValue::Long(f.start as jlong),
            JValue::Long(f.end as jlong),
            JValue::Object(&detail),
            JValue::Object(&reason),
        ],
    )
}

/// Construct a `dev.disarm.AnomalyReport` record.
fn new_anomaly_report<'l>(env: &mut Env<'l>, r: &api::AnomalyReport) -> JniResult<JObject<'l>> {
    let kinds: Vec<String> = r.kinds.iter().map(|k| k.as_str().to_string()).collect();
    let kinds_list = new_string_list(env, &kinds)?;
    let mut finding_objs = Vec::with_capacity(r.findings.len());
    for f in &r.findings {
        finding_objs.push(new_finding(env, f)?);
    }
    let findings_array = new_object_array_of(env, "dev/disarm/Finding", &finding_objs)?;
    let findings_list = list_of(env, &findings_array)?;
    let reason = opt_string(env, r.reason.as_deref())?;
    env.new_object(
        JNIString::from("dev/disarm/AnomalyReport"),
        jni_sig!("(ZLjava/util/List;Ljava/util/List;Ljava/lang/String;)V"),
        &[
            JValue::Bool(r.anomalous),
            JValue::Object(&kinds_list),
            JValue::Object(&findings_list),
            JValue::Object(&reason),
        ],
    )
}

/// Build an immutable `List<Long>` from Rust indices.
fn new_long_list<'l>(env: &mut Env<'l>, items: &[usize]) -> JniResult<JObject<'l>> {
    let mut boxed = Vec::with_capacity(items.len());
    for &n in items {
        let obj = env
            .call_static_method(
                JNIString::from("java/lang/Long"),
                JNIString::from("valueOf"),
                jni_sig!("(J)Ljava/lang/Long;"),
                &[JValue::Long(n as jlong)],
            )?
            .l()?;
        boxed.push(obj);
    }
    let array = new_object_array_of(env, "java/lang/Long", &boxed)?;
    list_of(env, &array)
}

/// Construct a `dev.disarm.KeyCollision` record.
fn new_nearest_match<'l>(env: &mut Env<'l>, m: &api::NearestMatch) -> JniResult<JObject<'l>> {
    let value = env.new_string(&m.value)?;
    let distance = jlong::try_from(m.distance).unwrap_or(jlong::MAX);
    env.new_object(
        JNIString::from("dev/disarm/NearestMatch"),
        jni_sig!("(Ljava/lang/String;J)V"),
        &[JValue::Object(&value), JValue::Long(distance)],
    )
}

fn new_key_collision<'l>(env: &mut Env<'l>, c: &api::KeyCollision) -> JniResult<JObject<'l>> {
    let key = env.new_string(&c.key)?;
    let values = new_string_list(env, &c.values)?;
    let indices = new_long_list(env, &c.indices)?;
    env.new_object(
        JNIString::from("dev/disarm/KeyCollision"),
        jni_sig!("(Ljava/lang/String;Ljava/util/List;Ljava/util/List;)V"),
        &[
            JValue::Object(&key),
            JValue::Object(&values),
            JValue::Object(&indices),
        ],
    )
}

/// Build an immutable `List<List<String>>` from nested Rust strings.
fn new_string_list_list<'l>(env: &mut Env<'l>, items: &[Vec<String>]) -> JniResult<JObject<'l>> {
    let mut inner = Vec::with_capacity(items.len());
    for row in items {
        inner.push(new_string_list(env, row)?);
    }
    let array = new_object_array_of(env, "java/util/List", &inner)?;
    list_of(env, &array)
}

/// Build an immutable `List<Boolean>` from Rust bools (boxed via `Boolean.valueOf`).
fn new_bool_list<'l>(env: &mut Env<'l>, items: &[bool]) -> JniResult<JObject<'l>> {
    let mut boxed = Vec::with_capacity(items.len());
    for &b in items {
        let obj = env
            .call_static_method(
                JNIString::from("java/lang/Boolean"),
                JNIString::from("valueOf"),
                jni_sig!("(Z)Ljava/lang/Boolean;"),
                &[JValue::Bool(b)],
            )?
            .l()?;
        boxed.push(obj);
    }
    let array = new_object_array_of(env, "java/lang/Boolean", &boxed)?;
    list_of(env, &array)
}

/// Construct a `dev.disarm.HostnameAnalysis` record (#549).
fn new_hostname_analysis<'l>(
    env: &mut Env<'l>,
    a: &api::HostnameAnalysis,
) -> JniResult<JObject<'l>> {
    let scripts = new_string_list(env, &a.scripts)?;
    let label_scripts = new_string_list_list(env, &a.label_scripts)?;
    let label_wsc = new_bool_list(env, &a.label_whole_script_confusable)?;
    let canonical = env.new_string(&a.canonical)?;
    env.new_object(
        JNIString::from("dev/disarm/HostnameAnalysis"),
        jni_sig!("(ZLjava/util/List;ZZZZZZZLjava/util/List;ZLjava/util/List;Ljava/lang/String;)V"),
        &[
            JValue::Bool(a.suspicious),
            JValue::Object(&scripts),
            JValue::Bool(a.mixed_script),
            JValue::Bool(a.has_confusables),
            JValue::Bool(a.bidi_conflict),
            JValue::Bool(a.bidi_control),
            JValue::Bool(a.has_invisible),
            JValue::Bool(a.compat_fold),
            JValue::Bool(a.cross_label_script),
            JValue::Object(&label_scripts),
            JValue::Bool(a.whole_script_confusable),
            JValue::Object(&label_wsc),
            JValue::Object(&canonical),
        ],
    )
}
