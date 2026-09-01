# What disarm reaches on an AI watermark

People arrive at this library asking whether it removes AI watermarks, usually after
finding a page about invisible characters. It is a fair question to arrive with, and until
now this documentation did not answer it: the words *watermark*, *SynthID* and *C2PA*
appeared nowhere in the README, the threat model, or any page under `docs/`.

The short answer is that "AI watermark" names four different things, disarm reaches one of
them, and stripping invisible characters is not the same as removing a watermark.

## The four categories

| | what it is | does disarm reach it |
|---|---|---|
| **1. Character-level markers** | invisible or confusable code points inserted into the text | **yes** — this is what disarm does |
| **2. Provenance metadata** | C2PA Content Credentials, EXIF `Software`, PDF `/Producer`, Office document properties | no — out of scope by choice, see below |
| **3. Statistical token watermarks** | SynthID-Text and similar: the model is biased toward particular words among near-equivalent choices | **no, and no character tool can** |
| **4. Pixel and audio watermarks** | the same idea one layer down, in image or audio samples | no — disarm does not touch binary media |

## Category 1: what disarm actually does

A character-level marker hides a payload in code points a reader cannot see. That is the
same mechanism as the smuggling this library was built for, so the coverage is real — but
it is not uniform, and the difference between *removing* and *reporting* matters if you are
trying to answer "was this text marked?" rather than "is this text clean?".

Measured over the 405 assigned `Default_Ignorable_Code_Point` characters, each placed
between two letters:

| | count |
|---|---:|
| `canonicalize` removes it **and** `inspect_anomalies` reports it | 117 |
| `canonicalize` removes it, nothing reports it | 266 |
| reported but **not** removed | 10 |
| neither | 12 |

The 266 is the number to understand. Variation selectors and the Tags block are stripped
without a finding, because in ordinary text they are not anomalous — a variation selector
after an emoji base is correct usage. So a pipeline that only *reports* will miss most of
this class, and one that only *transforms* will clean text without telling you it was
marked. Run both if the question is provenance.

The 10 that are reported and not removed are the fillers and Khmer vowel-position
characters, which `canonicalize` keeps because removing them would damage ordinary text in
those scripts. The 12 that are neither are the Shorthand Format Controls and the musical
notation controls.

```python
from disarm import canonicalize, inspect_anomalies

# Escapes, not literals: a zero-width space renders as nothing, so a literal one here
# would be indistinguishable from a typo on the page it is meant to explain.
marked = "The quick\u200b brown\u200b fox"
clean = "The quick brown fox"

assert inspect_anomalies(marked).kinds == ["invisible"]  # something is here
assert canonicalize(marked) == clean  # and now it is not

# And the point of the section: the cleaned text is indistinguishable from text that
# never carried a marker, so this is a defence and not a provenance check.
assert canonicalize(marked) == canonicalize(clean)
assert inspect_anomalies(canonicalize(marked)).kinds == []
```

**Removing the characters does not tell you the text was watermarked, and cleaning it does
not tell anyone else it was not.** disarm makes no claim about the provenance of text it
has processed. A marker that has been stripped is indistinguishable from a text that never
carried one, which is the property that makes stripping useful for defence and useless as
evidence.

## Category 2: out of scope by choice, not by oversight

C2PA Content Credentials, EXIF, PDF and Office document properties are reachable in
principle — they are structured fields in a container, and reading or clearing them is
ordinary parsing work. disarm does not do it, for two reasons.

It is **container-format work, not Unicode text work.** disarm's entire surface takes a
string and returns a string. A C2PA manifest is a signed JUMBF box inside a file; nothing
about the existing library helps with it, and the code that would do it shares no
machinery with the code that is here.

And it would be **owed across six bindings.** Every public function in this library exists
in Rust, Python, Ruby, Node, Java/Kotlin and the C ABI. A feature that cannot be expressed
as "string in, string out" costs six implementations and six test suites, which is a
different project rather than a larger version of this one.

If you need this, the C2PA reference implementations and `exiftool` are the tools for it.

## Category 3: why no character tool can reach it

A statistical token watermark such as SynthID-Text does not add anything to the text. It
biases the model's choice *among words that would all have been reasonable*, and the signal
is the pattern of those choices spread across a passage.

There are no extra characters, so there is nothing for a character-level tool to find. The
words are ordinary words. Detecting the mark requires the key and a statistical test over
enough text; removing it means rewriting the prose until the choices no longer correlate —
which is paraphrasing, not sanitizing.

**A tool that claims to remove a statistical text watermark is making a claim you cannot
check**, because the scheme and its key are unpublished. disarm makes no such claim, and
this section exists so that the absence is a stated position rather than a gap you have to
infer.

## What to take away

- If your text has invisible characters in it, disarm removes them, and that is worth doing
  on its own merits.
- If you are asking whether a passage came from a model, disarm cannot tell you.
- If you have cleaned text with disarm, you have not proved anything about where it came
  from — to yourself or to anyone else.

## See also

- [Limitations](../limitations.md) — what every function does not do.
- [Threat model](../THREAT_MODEL.md) — the classes disarm covers and the ones it does not.
- [Anomaly detection](../user-guide/anomaly-detection.md) — the reporting half.
