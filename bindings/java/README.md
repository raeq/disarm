# disarm — JVM bindings

Unicode canonicalization and TR39 visual confusable analysis for Java and Kotlin,
over the same pure-Rust core the other bindings use.

Two artifacts on Maven Central, versioned in lockstep with the core:

| artifact | what it is |
|---|---|
| `dev.disarm:disarm` | the Java surface: static methods, options builders, the native library for five platforms |
| `dev.disarm:disarm-kotlin` | `String` extensions and default arguments on top of it |

```kotlin
dependencies {
    implementation("dev.disarm:disarm:0.14.0")
    implementation("dev.disarm:disarm-kotlin:0.14.0")   // optional
}
```

JDK 21 or newer. The jar bundles `darwin-aarch64`, `darwin-x86_64`,
`linux-aarch64`, `linux-x86_64` and `windows-x86_64`, and extracts the right one
at class-load time.

Documentation lives on the docs site rather than here:

- [Getting started](https://docs.disarm.dev/java/getting-started.html) covers
  install, first calls in both languages, the `AutoCloseable` handles and the
  exception hierarchy.
- [JVM API](https://docs.disarm.dev/java/api.html) covers the two call styles,
  the builders, the types, and what the JVM surface does not have.

## Layout

```
bindings/java/
├── disarm-java/     the Java artifact — dev.disarm.*, and the native loader
├── disarm-kotlin/   the Kotlin artifact — dev.disarm.kotlin.*
├── rust/            the JNI shim, built by the `native` Gradle tasks
└── PUBLISHING.md    the release runbook (maintainers)
```

## Building and testing

```bash
./gradlew test --offline
```

That compiles the JNI shim, both artifacts, and runs JUnit plus `kotlin.test`. It
is part of the pre-push gate in
[CONTRIBUTING.md](https://github.com/raeq/disarm/blob/main/CONTRIBUTING.md).

Each binding builds against the **published** core, so work on an unreleased core
API needs a `[patch.crates-io]` redirect. For this binding it belongs in
`bindings/java/rust/Cargo.toml`, pointing at `../../..`. Restore the manifest
before committing — a relative-path redirect breaks packaging.

To run against a locally built native library rather than the bundled one:

```bash
java -Ddisarm.native.lib=/path/to/libdisarm_jni.dylib ...
# or: DISARM_NATIVE_LIB=/path/to/libdisarm_jni.dylib
```

## Signature stability

Every public Kotlin function with a default argument carries `@JvmOverloads`.
A Kotlin default otherwise compiles to one JVM method plus a synthetic `$default`
bridge. Adding a default to a shipped function then deletes an arity that
existed, and callers meet a `NoSuchMethodError` at run time. `JvmSignatureTest` pins the
arities in CI. See
[BINDINGS.md](https://github.com/raeq/disarm/blob/main/BINDINGS.md) for the full
rationale.
