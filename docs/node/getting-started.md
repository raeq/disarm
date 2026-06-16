# disarm for Node.js

Node.js bindings wrap the **pure-Rust `disarm` core** (no Python) via
[napi-rs](https://napi.rs). Prebuilt native addons install with no local Rust
toolchain, and the package ships TypeScript types — no `@types/disarm` needed.

## Install

```sh
npm install disarm
```

Requires Node 14+. `npm install disarm` pulls a prebuilt platform binary
(Linux x64/arm64, macOS x64/arm64, Windows x64) when one is available.

## Quick start

Options are passed as an object; scheme/target tokens are typed string unions.
The two operations people most often confuse are *visual* confusable folding
(homoglyph defence) and *phonetic* transliteration (romanization) — see
[Which function do I want?](../concepts/which-function.md).

```ts
import {
  normalizeConfusables,
  transliterate,
  slugify,
  isSuspiciousHostname,
} from 'disarm'

// Visual (TR39) confusable folding — homoglyph defence
normalizeConfusables('раypal') // => 'paypal'

// Phonetic romanization — readable ASCII, NOT a security control.
// A language profile sharpens the output: the uk profile gives Київ → Kyiv.
transliterate('Київ', { lang: 'uk' }) // => 'Kyiv'
slugify('Héllo Wörld') // => 'hello-world'

// Hostname / IDN spoof check (a false result is not a safety guarantee)
isSuspiciousHostname('pаypal.com') // => true
```

## Errors

Bad input — an unknown scheme/target/form/platform token, etc. — throws
`DisarmInvalidArgument`, a subclass of `DisarmError`, so a single
`instanceof DisarmError` catches the whole surface:

```ts
import { transliterate, DisarmError, DisarmInvalidArgument } from 'disarm'

try {
  transliterate('x', { scheme: 'klingon' })
} catch (e) {
  if (e instanceof DisarmInvalidArgument) console.warn(e.message) // also an instanceof DisarmError
}
```

## TypeScript

Every export is fully typed and the token arguments are string unions, so your
editor completes and checks them:

```ts
import { transliterate, type Scheme } from 'disarm'

const scheme: Scheme = 'strict_iso9' // 'default' | 'strict_iso9' | 'gost7034'
transliterate('Юрий', { scheme }) // → 'Jurij'
```

## Where next

- **[Node API reference](api.md)** — the full call surface, every function with a
  runnable example.
- **Concepts** (shared across every language) — start with
  [Which function do I want?](../concepts/which-function.md), then the topic
  guides under *Guide* in the sidebar.
- The binding inherits the core's guarantees and limits verbatim — read the
  [Threat Model](../THREAT_MODEL.md) before relying on it in a security context.
