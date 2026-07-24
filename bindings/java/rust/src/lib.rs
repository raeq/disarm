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
//! `Java_com_disarm_internal_Native_transliterate`. `Native` is already
//! package-internal, so we skip the `_`-prefix "raw" convention the other bindings
//! use for language-visible functions — it would only add JNI name-mangling
//! (`_` → `_1`) for no gain.
//!
//! Boundary discipline (jni 0.22): `EnvUnowned::with_env` upgrades the FFI env to a
//! real `Env` **and wraps the closure in `catch_unwind`**, so a panic in the core
//! becomes a thrown exception instead of unwinding across FFI (UB). `resolve` then
//! maps errors/panics to Java via an [`ErrorPolicy`]. We throw our *specific*
//! exception subclass inside the closure and return [`Error::JavaException`]; the
//! policy sees the pending exception and returns the null default without
//! clobbering it.
//!
//! Strings: `get_string`/`new_string` use modified UTF-8 (CESU-8), which the crate
//! decodes correctly for the astral plane. A fully faithful boundary for *lone
//! surrogates* needs raw UTF-16 (`GetStringChars`) + the WTF-8 scrub the
//! Python/Ruby bindings do; that refinement is tracked for the Java MVP (Phase 2).

// FFI boundary must never unwind into the JVM (S-4, mirrors Node/Ruby): forbid the
// panic-shaped constructs. `with_env` is the structural backstop; these lints keep
// the shim honest.
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
use jni::objects::{JClass, JObject, JString};
use jni::strings::JNIString;
use jni::{Env, EnvUnowned};

/// JVM binary names of the exception classes the idiomatic layer defines. JNI can
/// `ThrowNew` an arbitrary class directly (unlike napi/magnus, which tag the
/// message and let the language layer re-raise), so the shim throws the right
/// subtype itself.
const EX_INVALID: &str = "com/disarm/DisarmInvalidArgumentException";
const EX_ERROR: &str = "com/disarm/DisarmException";

/// Throw the Java exception matching a core error's kind, then signal the pending
/// exception to the [`ErrorPolicy`] via [`JniError::JavaException`].
fn throw_core(env: &mut Env, e: &disarm_core::Error) -> JniResult<JObject<'static>> {
    let class = match e.kind() {
        disarm_core::ErrorKind::InvalidArgument => EX_INVALID,
        _ => EX_ERROR,
    };
    env.throw_new(JNIString::from(class), JNIString::from(e.to_string()))?;
    Err(JniError::JavaException)
}

// ── Transliteration ─────────────────────────────────────────────────────────────

/// Unicode → ASCII with the default scheme (the borrow-on-no-op fast path).
#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_transliterate<'local>(
    mut env: EnvUnowned<'local>,
    _class: JClass<'local>,
    input: JString<'local>,
) -> JObject<'local> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let result = api::transliterate(&text).into_owned();
        Ok(env.new_string(&result)?.into())
    })
    .resolve::<jni::errors::ThrowRuntimeExAndDefault>()
}

/// Transliterate with a scheme (`"default"` | `"strict_iso9"` | `"gost7034"`) and
/// an optional language profile (`lang`, may be null), via the core's builder.
#[unsafe(no_mangle)]
pub extern "system" fn Java_com_disarm_internal_Native_transliterateOpts<'local>(
    mut env: EnvUnowned<'local>,
    _class: JClass<'local>,
    input: JString<'local>,
    scheme: JString<'local>,
    lang: JString<'local>,
) -> JObject<'local> {
    env.with_env(|env| -> JniResult<JObject> {
        let text = input.mutf8_chars(env)?.to_string();
        let scheme = scheme.mutf8_chars(env)?.to_string();
        let lang = if lang.is_null() {
            None
        } else {
            Some(lang.mutf8_chars(env)?.to_string())
        };
        match build_transliterate(&text, &scheme, lang.as_deref()) {
            Ok(result) => Ok(env.new_string(&result)?.into()),
            Err(e) => throw_core(env, &e),
        }
    })
    .resolve::<jni::errors::ThrowRuntimeExAndDefault>()
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
