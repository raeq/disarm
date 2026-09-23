import Emoji.Tables

/-!
# Executable model of `src/emoji.rs` and `src/py/emoji.rs`

Every definition mirrors one Rust function branch by branch; the comment on each names
the function and the line numbers at commit `bec93cf` (current `main` when this was
written). Characters are real `Char`s; the table predicates in `Emoji.Tables` are the
real tables projected onto the alphabet (see `scripts/gen_tables.py`). The structural
predicates below (regional indicator, tag, skin tone, keycap base, the four special
code points) are copied from the Rust exactly, over all of `Char`.

Output strings are `List Char`. Loops that the Rust writes as `while` over a
`CharWindow` are written here as recursions on a fuel argument that is always at least
the number of characters left, so running out of fuel is unreachable (each iteration
consumes at least one character); the `fuel_enough` checks in `Checks.lean` confirm it on
every input they run.
-/

namespace Emoji
open Tables

/-! ## Constants and structural predicates (emoji.rs:13-20, 510-535) -/

def ZWJ : Char := Char.ofNat 0x200D
def VS16 : Char := Char.ofNat 0xFE0F
def VS15 : Char := Char.ofNat 0xFE0E
def KEYCAP : Char := Char.ofNat 0x20E3

/-- emoji.rs:512 `is_skin_tone` -/
def isSkinTone (c : Char) : Bool := 0x1F3FB ≤ c.toNat && c.toNat ≤ 0x1F3FF
/-- emoji.rs:518 `is_tag` -/
def isTag (c : Char) : Bool := 0xE0020 ≤ c.toNat && c.toNat ≤ 0xE007F
/-- emoji.rs:524 `is_regional_indicator` -/
def isRI (c : Char) : Bool := 0x1F1E6 ≤ c.toNat && c.toNat ≤ 0x1F1FF
/-- emoji.rs:580 `matches!(first, '0'..='9' | '#' | '*')` -/
def isKeycapBase (c : Char) : Bool := ('0' ≤ c && c ≤ '9') || c == '#' || c == '*'
/-- emoji.rs:533 `opens_emoji_presentation` -/
def opensEmojiPresentation (c : Char) : Bool := isEmojiPresentation c || isRI c
/-- emoji.rs:404 `is_emoji_modifier` -/
def isEmojiModifier (c : Char) : Bool :=
  c == ZWJ || c == VS15 || c == VS16 || isSkinTone c || isTag c || c == KEYCAP
/-- The modifier arm shared by emoji.rs:599 and emoji.rs:635. -/
def isHeadMod (c : Char) : Bool := c == VS16 || c == VS15 || isSkinTone c || isTag c
/-- `str::is_ascii` for the fast paths (emoji.rs:698, 845; py/emoji.rs:104). -/
def isAscii (s : List Char) : Bool := s.all (fun c => c.toNat < 128)

/-! ## Grammar predicates -/

/-- emoji.rs:561-606 `head_len_at`. -/
def headLen : List Char → Option Nat
  | [] => none                                                       -- :562
  | first :: rest =>
    if isRI first then                                               -- :568
      some (if (rest.head?.map isRI).getD false then 2 else 1)       -- :569-575
    else if isKeycapBase first then                                  -- :580
      let after := if rest.head? == some VS16 then 1 else 0          -- :581
      if rest[after]? == some KEYCAP then some (2 + after) else none -- :582-586
    else
      let vs16Next := rest.head? == some VS16                        -- :591
      let opens := opensEmojiPresentation first || (vs16Next && isEmojiProperty first) -- :592
      if !opens then none                                            -- :593
      else some (1 + (rest.takeWhile isHeadMod).length)              -- :597-605

/-- emoji.rs:633-647, the chain loop of `presentation_len_at`. -/
def chainLoop (w : List Char) : Nat → Nat → Nat
  | 0, len => len
  | fuel + 1, len =>
    match w[len]? with
    | some c =>
      if isHeadMod c then chainLoop w fuel (len + 1)                 -- :635
      else if c == ZWJ then                                          -- :641
        match headLen (w.drop (len + 1)) with
        | some j => chainLoop w fuel (len + 1 + j)                   -- :642
        | none => len                                                -- :643
      else len                                                       -- :645
    | none => len

/-- emoji.rs:620-649 `presentation_len_at`. -/
def presLen (w : List Char) : Option Nat :=
  match w with
  | [] => none
  | first :: _ =>
    match headLen w with                                             -- :622
    | none => none
    | some len =>
      if isRI first || isKeycapBase first then some len              -- :626-628
      else some (chainLoop w w.length len)

/-- emoji.rs:674-683 `unnamed_emoji_len_at`. -/
def unnamedLen (w : List Char) : Option Nat :=
  match w with
  | [] => none
  | first :: _ =>
    if opensEmojiPresentation first then presLen w
    else if isTag first then some 1
    else none

/-! ## Name matching (emoji.rs:91-129, tables/mod.rs:928-958) -/

def isJoinLike (c : Char) : Bool := c == ZWJ || c == VS15 || c == VS16

/-- tables/mod.rs:928 `match_emoji_sequence`: the longest key (length ≥ 2, last code point
not ZWJ/VS) that is a prefix of the window. Keys ending in ZWJ/VS are already excluded
from `multiKeys` by the generator. -/
def matchSeq (w : List Char) : Option (String × Nat) :=
  multiKeys.foldl (fun best (k, v) =>
    if k.length ≥ 2 && k.length ≤ w.length && w.take k.length == k
       && !isJoinLike (k.getLast?.getD ' ') then
      match best with
      | some (_, n) => if k.length > n then some (v, k.length) else best
      | none => some (v, k.length)
    else best) none

/-- emoji.rs:91 `match_emoji_at`. -/
def matchAt (w : List Char) : Option (String × Nat) :=
  match w with
  | [] => none
  | ch :: rest =>
    let multi := if isStarter ch then matchSeq w else none           -- :100-104
    match multi with
    | some hit => some hit
    | none =>
      -- :111-115 the #972 keycap retry
      let kc : Option (String × Nat) :=
        if w.length ≥ 3 && rest[0]? == some VS16 && rest[1]? == some KEYCAP then
          (matchSeq [ch, KEYCAP]).map (fun (n, _) => (n, 3))
        else none
      match kc with
      | some hit => some hit
      | none =>
        match single ch with                                         -- :118-126
        | some name =>
          some (name, if rest.head? == some VS16 || rest.head? == some VS15 then 2 else 1)
        | none => none

/-! ## Emission helpers. `acc` is the output so far, REVERSED (head = last char). -/

/-- emoji.rs:486 `pad_emoji_replacement`. -/
def pad (acc : List Char) (name : String) : List Char :=
  let acc := match acc with
    | [] => acc
    | c :: _ => if isWhitespace c then acc else ' ' :: acc
  name.toList.reverse ++ acc

/-- emoji.rs:471 `needs_separator_after_a_name`. -/
def needsSep (c : Char) : Bool := isAlphanumeric c || isCombiningMark c || confFoldsAlnum c

/-- emoji.rs:435 `advance_past_trailing_modifiers`. -/
def sweep (s : List Char) : List Char :=
  s.dropWhile (fun c => isEmojiModifier c && c != KEYCAP)

/-- emoji.rs:726-744 `drop_marks_the_seam_would_bind`, over the unbounded remainder.
(The window version reads `win.as_slice()`, which always holds at least the two chars
this needs when they exist, so the two agree; the windowed replace scanner below uses
its own copy regardless.) -/
def seamDrop (before : Option Char) (s : List Char) : List Char :=
  match before with
  | none => s                                                        -- :727-729
  | some b =>
    let rec go : List Char → List Char
      | [] => []
      | mark :: t =>
        if !(mark == VS15 || mark == VS16 || mark == KEYCAP) then mark :: t -- :731-733
        else
          match headLen (b :: (mark :: t).take 2) with               -- :735-739
          | some l => if l < 2 then mark :: t else go t              -- :742 advance(1)
          | none => mark :: t
    go s

/-! ## `replace_emoji`: unbounded scanner (the oracle of emoji.rs:1106) -/

def replaceLoop (repl : List Char) : Nat → List Char → List Char → List Char
  | 0, _, acc => acc
  | _, [], acc => acc
  | fuel + 1, s@(c :: t), acc =>
    match presLen s with
    | some n =>
      let acc' := repl.reverse ++ acc
      replaceLoop repl fuel (seamDrop acc'.head? (s.drop n)) acc'
    | none => replaceLoop repl fuel t (c :: acc)

/-- `replace_emoji` with the whole input in hand (no `CharWindow`). -/
def replaceU (s repl : List Char) : List Char :=
  if isAscii s then s else (replaceLoop repl (s.length + 1) s []).reverse

/-! ## `CharWindow` (emoji.rs:196-373), window size `W` a parameter (Rust: `MAX_WINDOW` = 9) -/

structure Win where
  buf : List Char    -- `buf[..len]`
  pb : List Char     -- `pushback`
  rest : List Char   -- `rest`
deriving Repr

/-- emoji.rs:243 `next_char`. -/
def Win.nextChar (w : Win) : Option Char × Win :=
  match w.pb with
  | c :: t => (some c, { w with pb := t })
  | [] => match w.rest with
    | c :: t => (some c, { w with rest := t })
    | [] => (none, w)

/-- emoji.rs:288 `refill`. Fuel `W` suffices: each step grows `buf` by one. -/
def Win.refill (W : Nat) (w : Win) : Win :=
  let rec go : Nat → Win → Win
    | 0, w => w
    | fuel + 1, w =>
      if w.buf.length < W then
        match w.nextChar with
        | (some c, w') => go fuel { w' with buf := w'.buf ++ [c] }
        | (none, w') => w'
      else w
  go W w

/-- emoji.rs:221 `CharWindow::new`. -/
def Win.new (W : Nat) (s : List Char) : Win := { buf := s.take W, pb := [], rest := s.drop W }

/-- emoji.rs:268-285 `advance`. -/
def Win.advance (W : Nat) (n : Nat) (w : Win) : Win :=
  let rec loop : Nat → Nat → Win → Win
    | 0, _, w => w
    | fuel + 1, n, w =>
      if n ≥ w.buf.length && w.buf.length > 0 then                   -- :270
        let n := n - w.buf.length                                    -- :271
        let w := Win.refill W { w with buf := [] }                   -- :272-273
        if n == 0 then w else loop fuel n w                          -- :274-276
      else if w.buf.length == 0 then w                               -- :278-280
      else Win.refill W { w with buf := w.buf.drop n }               -- :282-284
  loop (n + 1) n w

/-- The growth loop of emoji.rs:346-362. Returns (scan, len, window-after-pulls). -/
def growLoop : Nat → List Char → Nat → Win → List Char × Nat × Win
  | 0, scan, len, w => (scan, len, w)
  | fuel + 1, scan, len, w =>
    let before := scan.length                                        -- :347
    -- :348-353 pull up to `before` chars
    let rec pull : Nat → List Char → Win → List Char × Win
      | 0, scan, w => (scan, w)
      | k + 1, scan, w => match w.nextChar with
        | (some c, w') => pull k (scan ++ [c]) w'
        | (none, w') => (scan, w')
    let (scan, w) := pull before scan w
    if scan.length == before then (scan, len, w)                     -- :354-356
    else
      let grown := (presLen scan).getD len                           -- :357
      if grown == len then (scan, len, w)                            -- :358-360
      else growLoop fuel scan grown w                                -- :361

/-- emoji.rs:317-372 `CharWindow::presentation_len`. -/
def Win.presentationLen (W : Nat) (w : Win) : Option (Nat × Win) :=
  match presLen w.buf with                                           -- :318
  | none => none
  | some len =>
    if w.buf.length < W then some (len, w)                           -- :319-323
    else if len < w.buf.length &&
        (w.buf[len]? != some ZWJ || w.buf.length - (len + 1) ≥ 3) then -- :335 HEAD_LOOKAHEAD = 3
      some (len, w)
    else
      let total := w.pb.length + w.rest.length + 1
      let (scan, len, w') := growLoop total w.buf len w              -- :344-362
      -- :368-370 hand back everything pulled past the window, in order
      some (len, { w' with pb := scan.drop w.buf.length ++ w'.pb })

/-- emoji.rs:726-744 `drop_marks_the_seam_would_bind`, on the window. -/
def Win.seamDrop (W : Nat) (w : Win) (before : Option Char) : Win :=
  match before with
  | none => w
  | some b =>
    let rec go : Nat → Win → Win
      | 0, w => w
      | fuel + 1, w =>
        match w.buf with
        | [] => w
        | mark :: _ =>
          if !(mark == VS15 || mark == VS16 || mark == KEYCAP) then w
          else
            let seam := b :: w.buf.take 2                            -- :735-738 (n = min(len, 2))
            match headLen seam with
            | some l => if l < 2 then w else go fuel (Win.advance W 1 w)
            | none => w
    go (w.buf.length + w.pb.length + w.rest.length + 1) w

/-- emoji.rs:694-715 `demojize_rust_replace_into`, windowed exactly as in Rust. -/
def replaceWLoop (W : Nat) (repl : List Char) : Nat → Win → List Char → List Char
  | 0, _, acc => acc
  | fuel + 1, w, acc =>
    match w.buf with                                                 -- :705 current()
    | [] => acc
    | ch :: _ =>
      match w.presentationLen W with                                 -- :706
      | some (consumed, w1) =>
        let acc' := repl.reverse ++ acc                              -- :707
        let w2 := Win.advance W consumed w1                          -- :708
        let w3 := Win.seamDrop W w2 acc'.head?                       -- :709
        replaceWLoop W repl fuel w3 acc'
      | none => replaceWLoop W repl fuel (Win.advance W 1 w) (ch :: acc) -- :712-713

def replaceW (W : Nat) (s repl : List Char) : List Char :=
  if isAscii s then s                                                -- :698-701
  else (replaceWLoop W repl (s.length + 1) (Win.new W s) []).reverse

/-- `replace_emoji(text, replacement)` as shipped: `MAX_WINDOW` = 9. -/
def replaceEmoji (s repl : List Char) : List Char := replaceW maxWindow s repl

/-! ## Pure-Rust `demojize` (emoji.rs:837-901), as run by `TextPipeline(demojize=True)` -/

/-- `NamePolicy::skips` (emoji.rs:825). `skipNonEmoji` is `PIPELINE_BASELINE`'s flag;
`skip_tr39_claimed` is false for every pipeline and preset this models. -/
def policySkips (skipNonEmoji : Bool) (c : Char) : Bool := skipNonEmoji && nonEmojiRow c

def demojizeLoop (skipNonEmoji : Bool) : Nat → List Char → List Char → Bool → List Char
  | 0, _, acc, _ => acc
  | _, [], acc, _ => acc
  | fuel + 1, s@(ch :: t), acc, lastWasEmoji =>
    if ch == VS16 || ch == VS15 || ch == ZWJ then                    -- :855-858
      demojizeLoop skipNonEmoji fuel t acc lastWasEmoji
    else if policySkips skipNonEmoji ch then                         -- :862-870
      let acc := if lastWasEmoji && needsSep ch then ' ' :: acc else acc
      demojizeLoop skipNonEmoji fuel t (ch :: acc) false
    else
      let win := s.take maxWindow
      match matchAt win with                                         -- :872
      | some (name, consumed) =>
        let acc := pad acc name                                      -- :874
        demojizeLoop skipNonEmoji fuel (sweep (s.drop consumed)) acc true -- :875-878
      | none =>
        match unnamedLen win with                                    -- :885
        | some consumed =>
          -- :886-891 dropped; close the seam
          demojizeLoop skipNonEmoji fuel (seamDrop acc.head? (s.drop consumed)) acc false
        | none =>
          let acc := if lastWasEmoji && needsSep ch then ' ' :: acc else acc -- :894-896
          demojizeLoop skipNonEmoji fuel t (ch :: acc) false         -- :897-899

/-- `demojize_rust_into(text, false, policy, out)`. -/
def demojizeRust (skipNonEmoji : Bool) (s : List Char) : List Char :=
  if isAscii s then s else (demojizeLoop skipNonEmoji (s.length + 1) s [] false).reverse

/-- `TextPipeline(demojize=True)`: `Pipeline::new` sets `PIPELINE_BASELINE`
(skip_non_emoji = true, pipeline.rs:538). -/
def pipelineDemojize (s : List Char) : List Char := demojizeRust true s

/-! ## pyo3 `demojize_impl` (py/emoji.rs:95-228) -/

inductive ErrorMode | replace | ignore | preserve
deriving DecidableEq, Repr

/-- A provider is a lookup on code-point sequences. py/emoji.rs:45 `try_python_provider`
tries lengths `min(9, window.len())` down to 1, returning the first non-None. -/
abbrev Provider := List Char → Option String

def tryProvider (p : Provider) (w : List Char) : Option (String × Nat) :=
  let rec go : Nat → Option (String × Nat)
    | 0 => none
    | len + 1 => match p (w.take (len + 1)) with
      | some n => some (n, len + 1)
      | none => go len
  go (min maxWindow w.length)

def pyLoop (mode : ErrorMode) (replaceWith : List Char) (prov : Option Provider) :
    Nat → List Char → List Char → Bool → Bool → List Char
  | 0, _, acc, _, _ => acc
  | _, [], acc, _, _ => acc
  | fuel + 1, s@(ch :: t), acc, lastWasEmoji, lastWasRaw =>
    if ch == VS16 || ch == VS15 || ch == ZWJ then                    -- :119-122
      pyLoop mode replaceWith prov fuel t acc lastWasEmoji lastWasRaw
    else
    let win := s.take maxWindow
    let provHit := match prov with
      | some p => tryProvider p win                                  -- :134-137
      | none => none
    match provHit with
    | some (name, consumed) =>
      -- :142-147 a keycap base claimed alone takes the rest of its keycap
      let consumed := if isKeycapBase ch && consumed == 1 then (presLen win).getD 1 else consumed
      let acc := pad acc name                                        -- :148
      pyLoop mode replaceWith prov fuel (sweep (s.drop consumed)) acc true false -- :149-153
    | none =>
    match matchAt win with                                           -- :158
    | some (name, consumed) =>
      let acc := pad acc name
      pyLoop mode replaceWith prov fuel (sweep (s.drop consumed)) acc true false -- :160-165
    | none =>
    match unnamedLen win with                                        -- :176
    | some consumed =>
      let acc := match mode with                                     -- :177-185
        | .replace => replaceWith.reverse ++ acc
        | .ignore => acc
        | .preserve => (win.take consumed).reverse ++ acc
      let lwe := match mode with                                     -- :193-197
        | .preserve => true
        | .replace => !replaceWith.isEmpty
        | .ignore => false
      let lwr := mode == .preserve                                   -- :198
      let rest := s.drop consumed                                    -- :186
      let rest := if !lwe then seamDrop acc.head? rest else rest     -- :202-204
      pyLoop mode replaceWith prov fuel rest acc lwe lwr
    | none =>
      let separate := if lastWasRaw then isAlphanumeric ch else needsSep ch -- :213-217
      let acc := if lastWasEmoji && separate then ' ' :: acc else acc -- :218-220
      pyLoop mode replaceWith prov fuel t (ch :: acc) false false    -- :221-224

/-- `disarm.demojize(text, errors=mode, replace_with=..., provider=...)`. -/
def demojizePy (mode : ErrorMode) (replaceWith : List Char) (prov : Option Provider)
    (s : List Char) : List Char :=
  if isAscii s then s else (pyLoop mode replaceWith prov (s.length + 1) s [] false false).reverse

/-! ## Observations used by the properties -/

/-- Some suffix of `s` starts an emoji presentation sequence. -/
def hasPresentation (s : List Char) : Bool :=
  let rec go : List Char → Bool
    | [] => false
    | c :: t => (presLen (c :: t)).isSome || go t
  go s

end Emoji
