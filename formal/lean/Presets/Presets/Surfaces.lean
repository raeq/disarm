import Presets.Pipelines

/-!
# Every public surface the differential test compares

The names are the ones `scripts/difftest.py` maps to library calls.
-/

namespace Presets

def pols : List (String × Pol) := [("numeric", .numeric), ("tr39", .tr39), ("preserve", .preserve)]

def surfaces : List (String × (Str -> Str)) :=
  (pols.flatMap fun (n, p) =>
    [ ("canonicalize@" ++ n, canonicalize p),
      ("canonicalize_strict@" ++ n, canonicalizeStrict p),
      ("strip_obfuscation@" ++ n, stripObfuscation p),
      ("search_key@" ++ n, searchKey p),
      ("catalog_key@" ++ n, catalogKey p),
      ("sort_key@" ++ n, sortKey p),
      ("skeleton_key@" ++ n, skeletonKey p) ]) ++
  [ ("strip_format", stripFormat),
    ("ml_normalize", mlNormalize true),
    ("ml_normalize@nofold", mlNormalize false) ] ++
  (profileNames.map fun n => ("profile:" ++ n, profile n)) ++
  [ ("profile:llm_guardrail@tr39", profile "llm_guardrail" .tr39),
    ("profile:normalize_web_input@tr39", profile "normalize_web_input" .tr39),
    ("profile:library_catalog_key_eu@tr39", profile "library_catalog_key_eu" .tr39) ] ++
  -- single steps with a public function of their own
  [ ("step:nfc", nfc), ("step:nfkc", nfkc), ("step:nfd", nfd),
    ("step:fold_case", foldCase), ("step:strip_accents", stripAccents),
    ("step:strip_bidi", stripBidi), ("step:strip_zero_width", stripZeroWidth),
    ("step:strip_control", stripControl), ("step:collapse_ws", collapseWs),
    ("step:zalgo3", zalgo 3), ("step:zalgo0", zalgo 0), ("step:strip_pua", stripPua),
    ("step:conf_public@numeric", confPublic .numeric), ("step:conf_public@tr39", confPublic .tr39),
    ("step:resolve_deletions", resolveDeletions),
    ("step:translit_preserve", translitPreserve), ("step:translit_ignore", translitIgnore) ]

end Presets
