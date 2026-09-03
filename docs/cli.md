# Command-Line Interface

disarm provides a command-line tool for transliteration, slugification, normalization, and text processing. It reads from arguments or stdin and writes to stdout, making it composable with other Unix tools.

## Installation

```bash
pip install disarm
```

After installation, the `disarm` command is available:

```bash
disarm t "café"
# cafe
```

You can also run it as a Python module:

```bash
python -m disarm t "café"
```

## Commands

Every command has a short alias for faster typing in pipelines.

| Command | Alias | Description |
|---|---|---|
| `transliterate` | `t` | Convert Unicode text to ASCII |
| `slugify` | `s` | Generate URL-safe slugs |
| `normalize` | `n` | Apply Unicode normalization |
| `pipeline` | `p` | Run multi-step text processing |
| `demojize` | `d` | Expand emoji to text descriptions |

---

### transliterate (t)

Convert Unicode text to ASCII using language-aware transliteration tables.

```bash
disarm t "café résumé"
# cafe resume

disarm t "Москва"
# Moskva

disarm t "北京市"
# bei jing shi
```

**Options:**

`--lang CODE`
:   Apply language-specific transliteration rules. Use `auto` for script-based detection.

```bash
disarm t --lang de "Ärger über Ölförderung"
# Aerger ueber Oelfoerderung

disarm t --lang auto "Москва"
# Moskva
```

`--target CODE`
:   Reverse transliteration — convert romanized Latin text back to a native script. Mutually exclusive with `--lang`.

```bash
disarm t --target ru "Moskva"
# Москва

disarm t --target el "Athina"
# Αθηνα
```

`--tones`
:   Include tone marks in Chinese pinyin output.

```bash
disarm t --tones "北京"
# běi jīng
```

`--strict-iso9`
:   Use the scholarly ASCII (ISO 9-style) transliteration for Cyrillic. NOTE: ASCII digraphs (zh/ch/sh), not the diacritic ISO 9:1995 standard.

```bash
disarm t --strict-iso9 "Юрий"
# Ûrij
```

`--gost7034`
:   Use GOST R 7.0.34 transliteration for Cyrillic.

---

### slugify (s)

Generate URL-safe slugs from Unicode text.

```bash
disarm s "Hello, World!"
# hello-world

disarm s "Ärger im Büro"
# arger-im-buro

disarm s --lang de "Ärger im Büro"
# aerger-im-buero
```

**Options:**

`--lang CODE`
:   Language-specific transliteration before slugification.

`--separator CHAR`
:   Separator character (default: `-`).

```bash
disarm s --separator "_" "Hello World"
# hello_world
```

`--max-length N`
:   Maximum slug length.

```bash
disarm s --max-length 10 "A very long blog post title"
# a-very-lon
```

---

### normalize (n)

Apply Unicode normalization.

```bash
disarm n "café"
# café  (NFC — composed form, the default)

disarm n --form NFKC "ﬁ"
# fi

disarm n --form NFD "é"
# é  (two codepoints: e + combining acute accent)
```

**Options:**

`--form {NFC,NFD,NFKC,NFKD}`
:   Normalization form (default: `NFC`).

---

### pipeline (p)

Run multiple processing steps in a single pass.

```bash
disarm p --steps "normalize,fold_case,transliterate" "Héllo WÖRLD"
# hello world

disarm p --steps "normalize,strip_accents,fold_case" "Café Résumé"
# cafe resume
```

**Options:**

`--steps STEPS`
:   Comma-separated list of processing steps (required).

Available steps: `normalize`, `transliterate`, `fold_case`, `collapse_whitespace`, `strip_accents`, `confusables`, `strip_control`, `strip_zero_width`, `demojize`.

`--form FORM`
:   Normalization form when using the `normalize` step.

---

### demojize (d)

Expand emoji to their text descriptions.

```bash
disarm d "Hello 😀 World 🌍"
# Hello grinning face World globe showing Europe-Africa
```

---

### scan (sc)

Walk files and directories and report every anomaly `inspect_anomalies` finds, located by
line and column.

```bash
disarm scan src/
# src/auth.py:41:17: bidi: "user\u202egpj.exe" contains the bidi override U+202E
# src/i18n.py:3:1: invisible: "ad\u200bmin" contains U+200B ZERO WIDTH SPACE
# scanned 212 file(s), 2 finding(s)

disarm scan . --fail            # exit 1 if anything is found — for CI
disarm scan src/ --json         # machine-readable, with line and column
```

`inspect_anomalies` has always returned everything a scanner needs — a kind, a span, evidence
and a plain-language reason — and until #704 there was no way to point it at a file.

**What the walk does, and does not do:**

- **Respects git's ignore rules, all three sources.** git reads `.gitignore` in the scanned
  directory *and every parent up to the repository root*, `.git/info/exclude`, and the
  global `core.excludesFile`. A scanner that reads only the nearest file gives different
  answers for `disarm scan src/` and `disarm scan .` on one tree. disarm asks
  `git check-ignore` rather than reimplementing the rule, so the two cannot disagree.
  `--no-gitignore` turns it off; outside a repository there is nothing to ask and the scan
  simply has no ignore rules.
- **Skips directories that hold no hand-written source** — `node_modules`, `__pycache__`,
  `.venv`, `.terraform` and the like. `build`, `dist`, `out`, `target`, `bin` and `vendor`
  are **not skipped**: they are generated in some projects and hand-written in others, and
  a scanner that skips them by name reports clean on a tree it never read.
- **Never follows symlinks**, so a scan stays inside the tree it was pointed at.
- **Skips binary and non-UTF-8 files** silently. They are not errors; they are not text.

**Options:**

`--json`
:   Emit `{"findings": [...], "scanned": N, "unreadable": [...]}`. Each finding carries
    `path`, `line`, `column`, `kind`, `reason` and `token`. `line` and `column` are
    1-based, and `column` counts characters — what an editor's gutter shows — not the byte
    offsets the library reports.

`--fail`
:   Exit `1` when anything is found. Without it a scan with findings still exits `0`, so
    the command can be used to *look* without gating.

`--no-gitignore`
:   Scan everything under the paths, ignoring git's rules.

**Exit codes** — something found is not something failed to read, and the codes keep them
apart:

| Code | Meaning |
|---|---|
| 0 | Scanned; nothing found, or found without `--fail` |
| 1 | Findings, with `--fail` |
| 2 | Invalid arguments (argparse) |
| 3 | A path could not be read — reported on stderr, scan of the rest still printed |

---

## Piping and stdin

All commands accept input from stdin when no positional argument is given. This makes disarm composable with other tools:

```bash
# Process a file
cat names.txt | disarm t

# Chain with other commands
echo "Ünïcödé Tëxt" | disarm t
# Unicode Text

# Slugify each line of a file
while IFS= read -r line; do
    echo "$line" | disarm s
done < titles.txt

# Use with xargs
cat words.txt | xargs -I{} disarm t "{}"

# Combine with sort/uniq for deduplication
cat entries.txt | disarm t | sort -u
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | No input provided (no argument and no stdin) |
| 2 | Invalid arguments (unknown command, bad option) |
| 3 | `scan` only: a path could not be read (see [scan](#scan-sc)) |
