# JVM API

The surface of `dev.disarm:disarm` and `dev.disarm:disarm-kotlin`, and how it
lines up with the names used in the other bindings. For install, the JDK floor
and the bundled platforms, see [Getting started](getting-started.md).

This page covers what is specific to the JVM. Behaviour is language-neutral and
lives once, in the [concept](../concepts/which-function.md) and
[user-guide](../user-guide/confusables.md) pages.

## Two call styles

`Disarm` is a final class of static methods. `disarm-kotlin` adds top-level
extension functions over the same native core, so the choice is a matter of which
reads better in your codebase rather than which is capable.

| | Java | Kotlin |
|---|---|---|
| entry point | `Disarm.transliterate(text)` | `text.transliterate()` |
| wide calls | options builders | default arguments |
| naming | `camelCase` | `camelCase` |
| package | `dev.disarm` | `dev.disarm.kotlin` for functions, `dev.disarm` for types |

Kotlin's functions are top-level. There is no `Disarm` object to call them on,
and `getPipeline` is a top-level function too.

```kotlin
import dev.disarm.TargetScript          // types
import dev.disarm.kotlin.*              // functions
```

## What the JVM surface does not have

Measured against the 86 canonical operations in `generated/parity.yaml`, the JVM
covers 50. Some of the remainder are deprecated aliases or Python-only
conveniences and are not gaps at all. These are the ones that are:

| absent | what it is | reach it with |
|---|---|---|
| `canonicalizeStrict` | the stricter comparison preset | `canonicalize`, then screen separately |
| `stripFormat` | strip bidi and invisibles, keep the script | `canonicalize` (also folds confusables) |
| `escapeHtml`, `percentEncode` | output encoders | your framework's encoder, which you should prefer anyway |
| `stripLogInjection` | neutralize a log line | `canonicalize` plus your own newline handling |
| `decodeToUtf8`, `detectEncoding` | encoding recovery | — |
| `listLangs`, `listProfiles`, `reverseLangs` | introspection | — |
| `registerLang`, `registerReplacements` | runtime registration | — |
| `setEmojiProvider` | custom emoji naming | — |
| `isAscii` | a predicate | `text.chars().allMatch(c -> c < 128)` |

`canonicalizeStrict` is the one to know about.
[CVE Validation](../security/cve-validation.md) measures that
`canonicalize_strict` and `strip_obfuscation` are the two presets that clear every
row of the matrix, and recommends them on that basis. On the JVM only
`stripObfuscation` exists, so the two-call advice cannot be followed as written.
`stripObfuscation` alone clears the matrix; `canonicalize` misses the eclipsing
mark in CVE-2017-7833.

The JVM is also absent from the parity matrix itself, which tracks rust, python,
ruby and node. The coverage figure above was measured for this page rather than
read off a gate, so treat it as accurate on the day it was written rather than
maintained. Both halves are tracked in [#677](https://github.com/raeq/disarm/issues/677).

## Options builders

Four, all with the same shape: a static `builder()`, chained setters, and
`build()`.

```java
TransliterateOptions.builder().scheme(Scheme.STRICT_ISO9).lang("ru").build();

SlugOptions.builder()
    .separator("_").lowercase(true).maxLength(64)
    .wordBoundary(true).saveOrder(true).stopwords(List.of("the"))
    .allowUnicode(false).lang("de")
    .build();

SanitizeFilenameOptions.builder()
    .separator("_").maxLength(255).platform(Platform.WINDOWS)
    .lang("de").preserveExtension(true)
    .build();

MlNormalizeOptions.builder().lang("de").emojiStyle("cldr").foldCase(false).build();
```

Kotlin passes the same values as named arguments and does not use the builders.

## Types

| type | what it carries |
|---|---|
| `AnomalyReport` | `anomalous`, `kinds`, `findings`, `reason` |
| `Finding` | one anomaly: `kind`, `token`, `start`, `end`, `detail`, `reason` |
| `HostnameAnalysis` | `suspicious`, `canonical`, `scripts`, `mixedScript`, `hasConfusables`, `bidiConflict`, `bidiControl`, `hasInvisible`, `compatFold`, `crossLabelScript`, `labelScripts`, `wholeScriptConfusable`, `labelWholeScriptConfusable` |
| `KeyCollision` | `key`, `values`, `indices` |
| `UnmappedConfusable`, `Untranslatable` | coverage residue |
| `LangMeta`, `ScriptMeta`, `AutoLangInspection` | metadata |
| `Lexicon`, `Pipeline` | native handles, `AutoCloseable` |
| `TargetScript`, `NormalizationForm`, `DigitPolicy`, `Platform` | enums |
| `Scheme` | nested in `TransliterateOptions`; Kotlin aliases it as `Scheme` |

## Name mapping

The other bindings use `snake_case`; the JVM uses `camelCase`. Everything else is
the same name, with three exceptions worth knowing:

| elsewhere | JVM |
|---|---|
| `is_suspicious_hostname` → `(bool, analysis)` in Python | `isSuspiciousHostname` → `boolean`, and `analyzeHostname` → `HostnameAnalysis` |
| `has_anomalies(text)` | `hasAnomalies(text, words)` — no single-argument form |
| `Disarm.canonicalize(...)` in Java | `"...".canonicalize()` in Kotlin |

The hostname split is the one that catches people. Python returns the verdict and
the analysis together; the JVM has a predicate and a separate analysis call, so
asking for both means two calls or one call to `analyzeHostname` and reading
`.suspicious()` off it.

## Errors

```
DisarmException                    (extends RuntimeException)
└── DisarmInvalidArgumentException
```

Unchecked, so nothing forces a `try`. `DisarmInvalidArgumentException` is thrown
for a value the library can name as wrong (an unknown profile, an unsupported
scheme) and carries the offending value and the valid set in its message.

## Signature stability (#588)

Every public Kotlin function with a default argument carries `@JvmOverloads`, so
each default emits a real JVM method instead of a synthetic `$default` bridge.
Without it, adding a default to a shipped function deletes an arity that existed,
and callers who have not recompiled meet a `NoSuchMethodError` at run time.

`JvmSignatureTest` pins the arities in CI. See
[BINDINGS.md](../BINDINGS.md#jvm-signature-stability-588) for why this is a
guarantee rather than a style.
