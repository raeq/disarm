/-!
# Model of `slugify` on the ASCII path (`src/slugify.rs`)

`slugify_impl_with_stopset` (L542-805) with `allow_unicode = false`, no `replacements`,
no `regex_pattern` and no `safe_chars`, over ASCII input without `&` (so entity decoding
is the identity). On that domain `transliterate_impl` returns its input and the
lowercasing at L657-662 is ASCII lowercasing, so the model starts at L648.

The separator is arbitrary: the model does not assume it is non-alphanumeric, one
character, or non-empty. The theorems say which of those they need.
-/

namespace Sanitizers.Slug

structure Config where
  sep : List Char
  lowercase : Bool
  maxLen : Nat
  wordBoundary : Bool
  saveOrder : Bool
  stopwords : List (List Char)
  deriving Repr

/-- `char::is_alphanumeric` on ASCII. -/
def isAlnum (c : Char) : Bool := c.isAlphanum

/-- L649-666 on ASCII. -/
def lower (cfg : Config) (s : List Char) : List Char :=
  if cfg.lowercase then s.map Char.toLower else s

/-- The L707-759 loop on the ASCII path (no joiners, no marks, no safe characters).
`prev` is `prev_was_sep`, which starts `true`. -/
def build (sep : List Char) : List Char → Bool → List Char
  | [], _ => []
  | c :: cs, prev =>
    if isAlnum c then c :: build sep cs false
    else if !prev && !sep.isEmpty then sep ++ build sep cs true
    else build sep cs prev

/-- L761-764: ONE trailing separator is removed (`if`, not `while`). -/
def stripOnce (sep l : List Char) : List Char :=
  if sep.isSuffixOf l && !sep.isEmpty then l.take (l.length - sep.length) else l

/-- Rust's `str::split(sep)`: leftmost, non-overlapping matches; `split("")` yields an
empty string, then every character, then another empty string. `fuel` is the length. -/
def splitF (sep : List Char) : Nat → List Char → List Char → List (List Char)
  | 0, acc, l => [acc.reverse ++ l]
  | n + 1, acc, l =>
    match l with
    | [] => [acc.reverse]
    | c :: cs =>
      if sep.isPrefixOf l then acc.reverse :: splitF sep n [] (l.drop sep.length)
      else splitF sep n (c :: acc) cs

def split (sep l : List Char) : List (List Char) :=
  if sep.isEmpty then [] :: (l.map (fun c => [c])) ++ [[]]
  else splitF sep (l.length + 1) [] l

def join (sep : List Char) : List (List Char) → List Char
  | [] => []
  | [w] => w
  | w :: ws => w ++ sep ++ join sep ws

/-- `filter_stopwords` (L813-852). -/
def filterStop (sep : List Char) (stop : List (List Char)) (saveOrder : Bool) (slug : List Char) :
    List Char :=
  let words := split sep slug
  let isStop := fun (w : List Char) => stop.contains w
  if saveOrder then
    let front := words.dropWhile isStop
    join sep (front.reverse.dropWhile isStop).reverse
  else join sep (words.filter (fun w => !isStop w))

/-- `rfind(sep)`: the start of the rightmost match. `rfind("")` is `Some(len)`. -/
def rfind (sep l : List Char) : Option Nat :=
  ((List.range (l.length + 1)).reverse).find? (fun i => sep.isPrefixOf (l.drop i))

/-- `strip_trailing_separator_prefix` (L891-903). -/
def stripPartial (sep s : List Char) : List Char :=
  if sep.isEmpty then s
  else
    let lens := (List.range (min sep.length s.length + 1)).reverse.filter (· ≥ 1)
    match lens.find? (fun n => (s.drop (s.length - n)).isPrefixOf sep) with
    | some n => s.take (s.length - n)
    | none => s

/-- `truncate_at_boundary` (L859-883), ASCII path. -/
def truncWord (slug : List Char) (maxLen : Nat) (sep : List Char) : List Char :=
  if slug.length ≤ maxLen then slug
  else
    let t := slug.take maxLen
    match rfind sep t with
    | some pos => t.take pos
    | none => stripPartial sep t

/-- L786-802. -/
def truncate (cfg : Config) (slug : List Char) : List Char :=
  if cfg.maxLen > 0 && slug.length > cfg.maxLen then
    if cfg.wordBoundary then truncWord slug cfg.maxLen cfg.sep
    else stripOnce cfg.sep (slug.take cfg.maxLen)
  else slug

/-- `slugify_impl_with_stopset` on the ASCII path. -/
def slugify (cfg : Config) (text : List Char) : List Char :=
  if text.isEmpty then []
  else
    let v := lower cfg text
    let s0 := stripOnce cfg.sep (build cfg.sep v true)
    let s1 := if cfg.stopwords.isEmpty then s0 else filterStop cfg.sep cfg.stopwords cfg.saveOrder s0
    truncate cfg s1

/-! ## The proposed fix

* **Truncation never leaves a partial separator** (Finding 5): the plain branch strips a
  trailing separator *prefix*, as the word-boundary branch already does.
* **A word-boundary cut that lands on a word end keeps the word** (Finding 6), as
  python-slugify's `smart_truncate` does.
* **Stopwords compare case-insensitively when `lowercase` is set** (Finding 7), as the
  Rust docs say and python-slugify does.
* **With an empty separator there are no words to filter** (Finding 8), so stopword
  removal is skipped rather than applied per character.
-/

def truncWordFixed (slug : List Char) (maxLen : Nat) (sep : List Char) : List Char :=
  if slug.length ≤ maxLen then slug
  else
    let t := slug.take maxLen
    if !sep.isEmpty && sep.isPrefixOf (slug.drop maxLen) then t
    else
      match rfind sep t with
      | some pos => t.take pos
      | none => stripPartial sep t

def truncateFixed (cfg : Config) (slug : List Char) : List Char :=
  if cfg.maxLen > 0 && slug.length > cfg.maxLen then
    if cfg.wordBoundary then truncWordFixed slug cfg.maxLen cfg.sep
    else stripPartial cfg.sep (slug.take cfg.maxLen)
  else slug

def slugifyFixed (cfg : Config) (text : List Char) : List Char :=
  if text.isEmpty then []
  else
    let v := lower cfg text
    let s0 := stripOnce cfg.sep (build cfg.sep v true)
    let stop := if cfg.lowercase then cfg.stopwords.map (·.map Char.toLower) else cfg.stopwords
    let s1 :=
      if stop.isEmpty || cfg.sep.isEmpty then s0 else filterStop cfg.sep stop cfg.saveOrder s0
    truncateFixed cfg s1

end Sanitizers.Slug
