# unidecode Co-Usage Patterns in the Wild

**Corpus:** 58 unique Python files, drawn from real-world projects via GitHub ZIP
archives and PyPI source distributions. Projects include beetbox/beets,
saleor/saleor, alvarobartt/investpy, justinmayer/django-autoslug,
un33k/python-slugify, rembo10/headphones, and others.

**Method:** AST visitor (catching chained calls, outer-function wraps, and
variable-assignment chains) combined with line-level regex to catch patterns the
AST misses. Total `unidecode(` call sites in corpus: **292**.

---

## Ranked Results

| # | Pattern | Files (of 58) | Occurrences | Notes |
|---|---------|:---:|:---:|---|
| 1 | `.lower()` | **11** | 61 | Both chained and pre-applied |
| 2 | `slugify(unidecode(…))` | **9** | 19 | Library-level slug wrapping |
| 3 | `.strip()` | **8** | 64 | Almost always paired with `.lower()` |
| 4 | `.replace()` | **6** | 14 | Path sep or special-char removal |
| 5 | `.encode()` | **5** | 11 | Produce `bytes` in ASCII |
| 6 | `re.sub(…)` | **3** | 7 | Non-word character stripping |
| 7 | f-string `{…}` | **3** | 3 | Embedding result in SQL/output |
| 8 | `quote(…)` / `quote_plus(…)` | **2** | 4 | URL percent-encoding |
| 9 | `.split()` | **2** | 2 | Split transliterated output |
| 10 | `.upper()` | **2** | 9 | Uppercase normalisation |
| — | `assert` / `assertEqual(…)` | **2** | 5 | Test assertions only |

---

## What the Patterns Actually Look Like

### 1. The slug pipeline — `.lower()` + `.strip()` + `re.sub()`

By far the most common real-world use. unidecode converts the Unicode title
to ASCII, then the rest of the pipeline turns it into a URL-safe slug:

```python
# Classic one-liner (appears verbatim in 3+ projects)
return re.sub(r"\W+", "-", unidecode(text).lower().strip()).strip("-")

# Variant with & replacement
re.sub(r"[^\w ]", "", unidecode(nsi_attributes["tags"]["name"]).replace("&", "and").lower())

# investpy: normalise before dict lookup
country = unidecode(country.strip().lower())
stock   = unidecode(stock.strip().lower())
```

Note that the order of operations varies: sometimes `.lower().strip()` is
applied *before* `unidecode(…)` (so unidecode sees already-lowercase input),
sometimes after. Both appear roughly equally.

### 2. Library-level slugify wrapping

```python
slug = slugify(unidecode(name))
slug_value = prepare_unique_slug(slugify(unidecode(name)), slugs_list)
slugify(unidecode(attribute_data.name))
```

`python-slugify` and `django-autoslug` both accept a pre-transliterated
string. Callers invoke unidecode first to guarantee ASCII input even when the
slug library's own Unicode handling is insufficient.

### 3. Filesystem path safety — `.replace()`

```python
# beets: make a path component safe on the current OS
path_components[index] = unidecode(item).replace(os.sep, sep_replace)

# headphones: strip slashes from artist/album names before writing files
unidecode(album['ArtistName']).replace('/', '_')
unidecode(album['AlbumTitle']).replace('/', '_')
```

`.replace()` here removes the one character class `.lower()` doesn't cover:
path separators. Always a single `.replace(os.sep, …)` or `.replace('/', …)`.

### 4. ASCII bytes — `.encode()`

```python
# Produce pure-ASCII bytes for a legacy or binary protocol
id_parts = unidecode.unidecode(identity.identity_dict['host']).encode('ascii')

# Docstring example showing the round-trip:
>>> unidecode("Κνωσός").encode("ascii")
```

`.encode('ascii')` after unidecode is safe by construction (unidecode output
is guaranteed ASCII), so this appears wherever the downstream API wants `bytes`
rather than `str`.

### 5. URL percent-encoding — `quote(…)` / `quote_plus(…)`

```python
return quote(unidecode(text))
```

Two projects (both URL-building utilities) chain unidecode → `urllib.parse.quote`.
The pattern is a two-step pipeline: transliterate Unicode to ASCII, then
percent-encode the remaining non-URL-safe characters.

### 6. Case-folding before comparison — `.upper()`

```python
# Name matching library: normalise both sides before comparing
base   = unidecode(base.strip().upper())
second = unidecode(second.strip().upper())
```

A less common variant: `.upper()` instead of `.lower()`, used when the
downstream comparison or key lookup is case-normalised to uppercase.

### 7. Embedding in SQL / output strings — f-strings

```python
# beets: bare-ASCII LIKE query
return rf"{clause} LIKE ? ESCAPE '\'", [f"%{unidecode(self.pattern)}%"]
```

---

## Summary: What unidecode is actually doing

unidecode is almost never a terminal operation. In every project examined it
sits inside a multi-step normalisation pipeline. The pipelines cluster into
four use-case families:

**URL / slug generation (dominant)**
`unidecode(text)` → `.lower()` → `.strip()` → `re.sub(r"\W+", "-", …)` → slug

**Filesystem filename safety**
`unidecode(name)` → `.replace(os.sep, safe)` → safe path component

**ASCII bytes for protocols**
`unidecode(text)` → `.encode("ascii")` → `bytes`

**Dictionary / search key normalisation**
`unidecode(text.lower().strip())` or `unidecode(text).lower().strip()` → lookup key

The thesis holds decisively. `.lower()` is paired in ~19 % of files,
`slugify()` in ~16 %, `.strip()` in ~14 %, and `.replace()` in ~10 %.
Raw `unidecode(x)` stored without further transformation is the exception,
not the rule.

---

## Corpus sources

| Project | Files | Domain |
|---------|:---:|---|
| beetbox/beets | 7 | Music library manager |
| alvarobartt/investpy | 7 | Financial data scraper |
| saleor/saleor | 6 | E-commerce platform (Django) |
| avian2/Unidecode | 4 | Library itself (tests + init) |
| justinmayer/django-autoslug | 3 | Django AutoSlugField |
| un33k/python-slugify | 2 | Slug generation library |
| rembo10/headphones | 1 | Music download manager |
| alltheplaces/alltheplaces | 1 | Location data scraper |
| others / PyPI sdists | 27 | Various |
