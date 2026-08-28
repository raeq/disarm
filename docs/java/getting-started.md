# Getting started (Java & Kotlin)

disarm ships two JVM artifacts from the same native core: `dev.disarm:disarm` for
Java, and `dev.disarm:disarm-kotlin` for the idiomatic Kotlin surface on top of
it. Both are on Maven Central.

## Install

=== "Gradle (Kotlin DSL)"

    ```kotlin
    dependencies {
        implementation("dev.disarm:disarm:0.14.0")
        // optional: String extensions and default arguments
        implementation("dev.disarm:disarm-kotlin:0.14.0")
    }
    ```

=== "Gradle (Groovy)"

    ```groovy
    dependencies {
        implementation 'dev.disarm:disarm:0.14.0'
        implementation 'dev.disarm:disarm-kotlin:0.14.0'
    }
    ```

=== "Maven"

    ```xml
    <dependency>
      <groupId>dev.disarm</groupId>
      <artifactId>disarm</artifactId>
      <version>0.14.0</version>
    </dependency>
    ```

`disarm-kotlin` depends on `disarm`, so adding it alone is enough if you only
write Kotlin. The two versions move in lockstep — see
[RELEASING.md](../RELEASING.md).

### JDK 21 or newer

Both artifacts are built with `JavaLanguageVersion.of(21)`, and the Java module
uses a `Cleaner` to back up the native handles described below. There is no
supported path on an older JDK.

### Bundled platforms

The `disarm` jar carries the native library for five targets and extracts the
right one at class-load time:

| | |
|---|---|
| macOS | `darwin-aarch64`, `darwin-x86_64` |
| Linux (glibc) | `linux-aarch64`, `linux-x86_64` |
| Windows | `windows-x86_64` |

Anything else (musl, 32-bit ARM, FreeBSD) has no bundled binary and fails at
class-load with a message naming the platform it looked for. The C ABI in
`bindings/cabi` is the route for those.

## First calls

The two artifacts are the same library with two surfaces. Java gets static
methods and options builders; Kotlin gets `String` extensions and default
arguments.

=== "Java"

    ```java
    import dev.disarm.Disarm;
    import dev.disarm.TargetScript;

    // Fold homoglyphs, strip bidi overrides, invisibles and controls — one call
    // for untrusted input you are about to compare. It does NOT make text safe
    // to emit: encode at the sink.
    Disarm.canonicalize("Ηello Ꮤorld");        // "Hello World"

    Disarm.transliterate("Москва");             // "Moskva"
    Disarm.slugify("Hello, World!");            // "hello-world"
    Disarm.searchKey("  Café  RÉSUMÉ  ");       // "cafe resume"

    Disarm.isConfusable("раypal", TargetScript.LATIN);   // true
    Disarm.isSuspiciousHostname("аpple.com");            // true
    ```

=== "Kotlin"

    ```kotlin
    import dev.disarm.TargetScript
    import dev.disarm.kotlin.*

    "Ηello Ꮤorld".canonicalize()      // "Hello World"

    "Москва".transliterate()           // "Moskva"
    "Hello, World!".slugify()          // "hello-world"
    "  Café  RÉSUMÉ  ".searchKey()     // "cafe resume"

    "раypal".isConfusable(TargetScript.LATIN)   // true
    "аpple.com".isSuspiciousHostname()          // true
    ```

Kotlin's functions are top-level rather than members of a `Disarm` object.
Import `dev.disarm.kotlin.*` and call them on the string. The enums and result
types still come from `dev.disarm`.

## Passing options

=== "Java"

    ```java
    import dev.disarm.SlugOptions;
    import dev.disarm.TransliterateOptions;

    Disarm.transliterate("München",
        TransliterateOptions.builder().lang("de").build());   // "Muenchen"

    Disarm.slugify("Hello, World!",
        SlugOptions.builder().separator("_").maxLength(12).build());  // "hello_world"
    ```

=== "Kotlin"

    ```kotlin
    "München".transliterate(lang = "de")                  // "Muenchen"
    "Hello, World!".slugify(separator = "_", maxLength = 12)  // "hello_world"
    ```

Four builders cover the wide functions: `TransliterateOptions`, `SlugOptions`,
`SanitizeFilenameOptions` and `MlNormalizeOptions`. Kotlin does not use them,
because default arguments cover the same ground.

## `Pipeline` and `Lexicon` hold native handles

Both implement `AutoCloseable`. This is the one thing on the JVM surface with no
counterpart in the Python, Ruby or Node bindings, so no other page teaches it.

=== "Java"

    ```java
    import dev.disarm.Lexicon;
    import dev.disarm.Pipeline;
    import java.util.List;

    try (Pipeline pipeline = Disarm.getPipeline("search_index")) {
        pipeline.process("Café");                 // "cafe"
    }

    try (Lexicon lexicon = new Lexicon(List.of("free"))) {
        Disarm.hasAnomalies("get fr33 now", lexicon);   // true
    }
    ```

=== "Kotlin"

    ```kotlin
    getPipeline("search_index").use { pipeline ->
        pipeline.process("Café")     // "cafe"
    }
    ```

A `Cleaner` frees a handle you forget, so a leak is not fatal. Try-with-resources
(or `use { }`) is still the intended idiom: the `Cleaner` runs whenever the
collector gets round to it, which is not a schedule you want native memory on.

## The anomaly detectors take a word list

`hasAnomalies` and `inspectAnomalies` have no single-argument form on the JVM.
Both take a lexicon, meaning the words to check leetspeak substitutions against.
An empty list asks for the character-class checks alone:

=== "Java"

    ```java
    import dev.disarm.AnomalyReport;
    import java.util.List;

    Disarm.hasAnomalies("ad​min", List.of());   // true — a zero-width space

    AnomalyReport report = Disarm.inspectAnomalies("ad​min", List.of());
    report.kinds();                                  // ["invisible"]
    ```

=== "Kotlin"

    ```kotlin
    "ad​min".hasAnomalies(emptyList())   // true
    ```

Passing the same word list repeatedly is what `Lexicon` is for: it builds the set
once instead of per call.

## Errors

Two classes, and the narrow one extends the broad one:

```
DisarmException                    (extends RuntimeException)
└── DisarmInvalidArgumentException
```

Both are unchecked, so nothing forces a `try`. Catch `DisarmException` to cover
everything the library throws; catch `DisarmInvalidArgumentException` when you
want to separate *you passed a bad value* from *something else went wrong*.

```java
try {
    Disarm.getPipeline("no-such-profile");
} catch (DisarmInvalidArgumentException e) {
    // names the offending value and lists the valid profiles
}
```

## Signature stability

Every public Kotlin function with a default argument carries `@JvmOverloads`, so
each default emits a real JVM method rather than a synthetic `$default` bridge.
Without it, adding a default to an existing function silently deletes the arity
that shipped, and Java callers get a `NoSuchMethodError` at run time. So do
Kotlin callers who have not recompiled.

`JvmSignatureTest` asserts the arities in CI. The cost is generated methods
rather than maintained ones: `slugify` has twelve defaults and emits thirteen
arities, and the compiler writes all of them.

## Where to go next

The JVM pages cover the surface. The behaviour is language-neutral and documented
once:

- [Which function do I want?](../concepts/which-function.md) draws the
  transliterate-versus-confusables distinction, which is the mistake everyone
  makes first.
- [Adversarial-Text Defense](../security/adversarial-defense.md) and
  [CVE Validation](../security/cve-validation.md) say what these functions stop,
  and what they do not.
- [Limitations](../limitations.md) is the one to read before pointing a cleaning
  preset at non-Latin body text. What it does there is not what most readers
  expect.
- [JVM API](api.md) covers the surface itself, and maps it to names you may
  already know from the other bindings.
