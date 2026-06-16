# disarm (Node.js)

Unicode confusable/text-security building blocks for Node.js — TR39 *visual*
homoglyph folding, deobfuscation (bidi / zalgo / zero-width / invisible / emoji),
and standards-based *phonetic* transliteration. Powered by a **pure-Rust core**
([`disarm`](https://crates.io/crates/disarm)) via [napi-rs](https://napi.rs); the
prebuilt native addons install with no Rust toolchain.

```sh
npm install disarm
```

Ships TypeScript types (`.d.ts`) — no `@types/disarm` needed. Requires Node 14+.

## Quick start

```ts
import {
  normalizeConfusables,
  transliterate,
  slugify,
  isSuspiciousHostname,
} from 'disarm'

// Visual (TR39) confusable folding — homoglyph defence
normalizeConfusables('раypal') // → 'paypal'  (Cyrillic а/р folded to Latin)

// Phonetic romanization — readable ASCII, NOT a security control.
// A language profile sharpens the output: the uk profile gives Київ → Kyiv.
transliterate('Київ', { lang: 'uk' }) // → 'Kyiv'
slugify('Héllo Wörld') // → 'hello-world'

// Hostname / IDN spoof check (a false result is not a safety guarantee)
isSuspiciousHostname('pаypal.com') // → true  (Cyrillic 'а')
```

The two operations people most often confuse are *visual* confusable folding
(homoglyph defence) and *phonetic* transliteration (romanization) — see
[Which function do I want?](https://docs.disarm.dev/concepts/which-function/).

## Idioms

- **Options objects with defaults** — `transliterate(text, { scheme, lang })`,
  `slugify(text, { separator, maxLength, … })`, `normalize(text, { form })`.
- **String-union tokens** — `scheme: 'default' | 'strict_iso9' | 'gost7034'`,
  `form: 'NFC' | 'NFD' | 'NFKC' | 'NFKD'`, `platform: 'universal' | 'windows' | 'posix'`,
  fully typed in your editor.
- **A native error type** — bad input (an unknown scheme/target/form/platform)
  throws `DisarmInvalidArgument`, a subclass of `DisarmError`:

  ```ts
  import { transliterate, DisarmError } from 'disarm'

  try {
    transliterate('x', { scheme: 'klingon' })
  } catch (e) {
    if (e instanceof DisarmError) console.warn(e.message)
  }
  ```

## What's here

Transliteration (`transliterate`, `reverseTransliterate`, `findUntranslatable`),
confusables (`normalizeConfusables`, `isConfusable`), slugs (`slugify`),
normalization (`normalize`, `isNormalized`), text cleaning (`collapseWhitespace`,
`stripControlChars`, `stripZeroWidthChars`, `stripBidi`, `stripZalgo`, `isZalgo`),
deobfuscation/security presets (`stripObfuscation`, `securityClean`,
`sanitizeFilename`), grapheme clusters (`graphemeLen`, `graphemeSplit`,
`graphemeTruncate`, `graphemeWidth`, `terminalWidth`), and script analysis
(`detectScripts`, `isMixedScript`, `isSuspiciousHostname`, `inspectAutoLang`).
Every export is fully typed.

## Security posture

disarm normalizes **input**; it is a defense-in-depth layer, **not** an output
sanitizer. It performs no escaping and is not an XSS/SQL/HTML defense — encode at
the output sink. Read the
[Threat Model](https://github.com/raeq/disarm/blob/main/THREAT_MODEL.md) before
relying on it in a security context.

## Links

- **Docs:** <https://docs.disarm.dev>
- **Core (Rust):** <https://crates.io/crates/disarm>
- **Source / issues:** <https://github.com/raeq/disarm>

MIT licensed.
