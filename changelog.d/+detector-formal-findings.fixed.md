- **The anomaly detector missed characters `canonicalize` deletes from a word, and a
  doubled RTL mark hid a reordered number run.** Found by the Lean model of the detector
  in `formal/lean/Detection` (Findings 1 and 2). The deprecated format controls
  `U+206A`-`U+206F` and the interlinear annotation characters `U+FFF9`-`U+FFFB` were
  defined only inside the bidi strip, so `strip_bidi`, `strip_format` and `canonicalize`
  turned `pay\u206apal` into `paypal` while `has_anomalies` said `False`. The set now
  lives in one predicate that both read, and the detector reports it as `invisible`, as
  it does `U+200B`. The 66 noncharacters, which `canonicalize` also deletes, are
  reported too, as an `invisible` run of one: nothing legitimate emits one, and the
  hostname screen and the smuggled-payload decoder already treated them as invisible.
  Separately, the #741 rule for an `RLM` or `ALM` in front of a number run tested only
  the first mark in the token, so `Transfer \u200f\u200f100 200 300 to Bob`, which renders
  `Transfer 300 200 100 to Bob` exactly as the single-mark form does, screened clean. Every
  mark is tested now.
- **Canonically equivalent text got different anomaly verdicts, and ordinary French
  reported as a disguise.** Found by the same model (Findings 3 and 4). Four of the
  detector's tests asked for an ASCII letter as spelled, so `\u00e9t\u00e9` followed by an
  isolate was clean in NFC and `bidi` in NFD, and the NFC spelling, the common one, was
  the unreported one; the model's sweep found 2,328,179 split verdicts. The detector now
  classifies each token composed and reads a letter through its canonical decomposition,
  so both spellings get one report, lexicon included; `tests/exhaustive_anomalies.rs`
  checks it over every Unicode scalar. One consequence: a canonical singleton reads as
  its target, so `\u212aey` (KELVIN SIGN) reports what `Key` does, which is nothing. And
  `confusable` no longer fires on a letter whose fold only drops its accent
  (`Fran\u00e7ais`, `gar\u00e7on`, `ch\u1ec9`), which the guide already said was spared. The
  letters the fold changes in shape (`\u00f8`, `\u0142`, `\u0111`) still report, and
  `docs/user-guide/anomaly-detection.md` now says which Latin letters those are. The
  folds themselves, and every stored key, are unchanged.
- **Detector documentation the code contradicted.** `docs/api/predicates.md` said the
  detector never fires on text `canonicalize` leaves alone; that holds per code point
  only, and `a\u03bb` is canonical and `mixed_script`. The guide counted "eight
  branches" where fifteen kinds exist, the `DuplicateMark` doc said a repeated mark
  survives canonicalization (the key builders drop it since #835), and a comment claimed
  `U+1C80` resolves as Cyrillic. Found by the same model (Finding 7).
