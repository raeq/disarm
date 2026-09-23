import Transliterate.Lift

/-!
# The argument that *does* fit the real engine

`transliterate` is not a homomorphism (composition at the boundary, canonical
reordering, CJK spacing, the Indic inherent-`a` rule, `lang="auto"` detection —
see the README), so `Lift.lean` does not apply to it. What the engine *is* is
an emitter: `transliterate_run` (src/transliterate.rs) walks the (composed)
input and only ever

* appends a piece (`push_str`) — an ASCII run of the input, a table value, the
  separator `' '`, or `replace_with` / the raw character on the unmapped path;
* appends the result of a recursive run (`handle_unmapped`'s NFKC recovery,
  `transliterate_dispatch` on the NFKC form);
* deletes the last character (`result.pop()`, the Indic inherent-`a` rule).

Which pieces it appends, and when, may depend on *anything* — the whole input,
the language, detected script, neighbours. The model below keeps that freedom:
`plan` is an arbitrary function from input to action list.

**Theorem (engine_I2):** if every piece a plan can emit is ASCII, the output is
ASCII for every input, at every recursion depth. No homomorphism needed.

**Premise E** (`EmitsAscii`) is what must be checked against the code, piece by
piece — and it is *not* what the per-code-point exhaustion checks. It is
discharged (or not) as follows (README, "Premise E"):

| piece | ASCII? |
|---|---|
| ASCII run of the input | yes — selected by `bytes[i] < 0x80` |
| default / SMP / lang / iso9 / gost table value | yes — `build.rs` asserts every value |
| toned-pinyin value (`tones=True`) | **no** — `běi`, `jīng` (not asserted) |
| `register_lang` value | **no** — accepted unvalidated |
| separator `' '` | yes |
| unmapped, `errors='ignore'` | yes — emits nothing |
| unmapped, `errors='replace'` | iff `replace_with` is ASCII |
| unmapped, `errors='preserve'` | **no** — emits the character |
| NFKC recovery | yes, by induction (`engine_I2`) |
| `pop` | preserves ASCII (`AllA.dropLast`) |

Then I1 is the fast path (`if text.is_ascii() { return Cow::Borrowed(text) }`
in `transliterate_impl_inner`), and I3 follows from I1 + I2 (`I3_of_I1_I2`).
-/

namespace Transliterate

variable {α : Type}

theorem AllA.dropLast {asc : α → Bool} {s : List α} (h : AllA asc s) : AllA asc s.dropLast :=
  fun x hx => h x (List.dropLast_subset s hx)

/-- One step of the emitter. -/
inductive Act (α : Type) where
  | emit (p : List α)      -- push_str of a piece
  | recover (t : List α)   -- push_str of a recursive run on `t` (NFKC recovery)
  | pop                    -- result.pop()

/-- Execute an action list against an accumulator; `sub` is the recursive run. -/
def exec (sub : List α → List α) : List (Act α) → List α → List α
  | [], acc => acc
  | .emit p :: as, acc => exec sub as (acc ++ p)
  | .recover t :: as, acc => exec sub as (acc ++ sub t)
  | .pop :: as, acc => exec sub as acc.dropLast

theorem exec_ascii {asc : α → Bool} {sub : List α → List α}
    (hsub : ∀ t, AllA asc (sub t)) :
    ∀ (acts : List (Act α)) (acc : List α),
      (∀ p, Act.emit p ∈ acts → AllA asc p) → AllA asc acc → AllA asc (exec sub acts acc) := by
  intro acts
  induction acts with
  | nil => intro acc _ hacc; exact hacc
  | cons a as ih =>
    intro acc hp hacc
    have hp' : ∀ p, Act.emit p ∈ as → AllA asc p :=
      fun p hm => hp p (List.mem_cons_of_mem _ hm)
    cases a with
    | emit p =>
      exact ih _ hp' (hacc.append (hp p (List.mem_cons_self ..)))
    | recover t => exact ih _ hp' (hacc.append (hsub t))
    | pop => exact ih _ hp' hacc.dropLast

/-- **Premise E.** Every piece the plan can emit, for any input, is ASCII. -/
def EmitsAscii (asc : α → Bool) (plan : List α → List (Act α)) : Prop :=
  ∀ s p, Act.emit p ∈ plan s → AllA asc p

/-- The engine with recursion fuel (NFKC recovery nests; the real depth is
bounded because NFKC is idempotent, but the theorem holds at every depth). -/
def run (plan : List α → List (Act α)) : Nat → List α → List α
  | 0, _ => []
  | n + 1, s => exec (run plan n) (plan s) []

theorem engine_I2 {asc : α → Bool} {plan : List α → List (Act α)} (hE : EmitsAscii asc plan) :
    ∀ n s, AllA asc (run plan n s) := by
  intro n
  induction n with
  | zero => intro s; exact AllA.nil _
  | succ n ih =>
    intro s
    exact exec_ascii ih (plan s) [] (hE s) (AllA.nil _)

/-- `transliterate_impl_inner`: ASCII fast path, else the engine. -/
def translit (asc : α → Bool) (plan : List α → List (Act α)) (fuel : Nat) (s : List α) : List α :=
  if s.all asc then s else run plan fuel s

theorem all_iff_AllA {asc : α → Bool} {s : List α} : s.all asc = true ↔ AllA asc s := by
  simp [AllA, List.all_eq_true]

/-- **I1** — structural: it is the fast path, for every plan. -/
theorem translit_I1 (asc : α → Bool) (plan : List α → List (Act α)) (fuel : Nat) :
    ∀ s, AllA asc s → translit asc plan fuel s = s := by
  intro s h
  simp [translit, all_iff_AllA.mpr h]

/-- **I2** — under premise E, for every string, with no homomorphism premise. -/
theorem translit_I2 {asc : α → Bool} {plan : List α → List (Act α)} (fuel : Nat)
    (hE : EmitsAscii asc plan) : ∀ s, AllA asc (translit asc plan fuel s) := by
  intro s
  unfold translit
  split
  · rename_i h; exact all_iff_AllA.mp h
  · exact engine_I2 hE fuel s

/-- **I3** — under premise E, for every string, with no homomorphism premise. -/
theorem translit_I3 {asc : α → Bool} {plan : List α → List (Act α)} (fuel : Nat)
    (hE : EmitsAscii asc plan) :
    ∀ s, translit asc plan fuel (translit asc plan fuel s) = translit asc plan fuel s :=
  I3_of_I1_I2 (translit_I1 asc plan fuel) (translit_I2 fuel hE)

/-- Premise E is necessary: one non-ASCII emitted piece on one input breaks I2
there (the `tones=True`, `errors='preserve'` and `register_lang` cases). -/
theorem not_I2_of_emit {asc : α → Bool} {plan : List α → List (Act α)} {s : List α}
    {x : α} (hs : s.all asc = false) (hx : asc x = false)
    (hplan : plan s = [Act.emit [x]]) (fuel : Nat) :
    ¬ AllA asc (translit asc plan (fuel + 1) s) := by
  intro h
  have hx' := h x (by simp [translit, hs, run, hplan, exec])
  rw [hx] at hx'; exact Bool.false_ne_true hx'

/-! ## `context=True` (src/context.rs::transliterate_context)

The context engine tokenises the input into word spans (Arabic/Hebrew letters
and marks) and non-word spans, runs each *word* through the dictionary and then
through `f`, and appends every **non-word span verbatim** (`result.push_str(&token.text)`).
A verbatim span is an emitted piece that is not guaranteed ASCII, so premise E
fails. `ctxShipped` is that shape; `ctxFixed` routes non-word spans through `f`
as well, and inherits I1, I2 and I3 from `f`. -/

section Context

variable (asc : α → Bool) (isWord : List α → Bool) (resolve : List α → List α)
  (f : List α → List α) (tokenize : List α → List (List α))

def ctxShipped (s : List α) : List α :=
  (tokenize s).flatMap fun tok => if isWord tok then f (resolve tok) else tok

def ctxFixed (s : List α) : List α :=
  (tokenize s).flatMap fun tok => if isWord tok then f (resolve tok) else f tok

/-- The shipped shape is not ASCII-safe even when `f` is: a non-word, non-ASCII
token comes out as-is. -/
theorem ctxShipped_not_I2 {s tok : List α} {x : α}
    (htok : tok ∈ tokenize s) (hw : isWord tok = false) (hx : x ∈ tok) (hna : asc x = false) :
    ¬ AllA asc (ctxShipped isWord resolve f tokenize s) := by
  intro h
  have : x ∈ ctxShipped isWord resolve f tokenize s :=
    List.mem_flatMap.mpr ⟨tok, htok, by simp [hw, hx]⟩
  have := h x this
  rw [hna] at this; exact Bool.false_ne_true this

theorem ctxFixed_I2 (hf : ∀ s, AllA asc (f s)) :
    ∀ s, AllA asc (ctxFixed isWord resolve f tokenize s) := by
  intro s x hx
  obtain ⟨tok, _, hx⟩ := List.mem_flatMap.mp hx
  split at hx
  · exact hf _ x hx
  · exact hf _ x hx

/-- I1 for the fixed context engine: tokenisation is a partition
(`flatten = id`), ASCII input has no word tokens, and `f` fixes ASCII. -/
theorem ctxFixed_I1
    (hpart : ∀ s, (tokenize s).flatten = s)
    (hnoword : ∀ s, AllA asc s → ∀ tok ∈ tokenize s, isWord tok = false)
    (hf1 : ∀ s, AllA asc s → f s = s) :
    ∀ s, AllA asc s → ctxFixed isWord resolve f tokenize s = s := by
  intro s hs
  have htoks : ∀ tok ∈ tokenize s, AllA asc tok := by
    intro tok ht x hx
    apply hs x
    rw [← hpart s]
    exact List.mem_flatten.mpr ⟨tok, ht, hx⟩
  have key : ∀ l : List (List α), (∀ tok ∈ l, isWord tok = false ∧ AllA asc tok) →
      l.flatMap (fun tok => if isWord tok then f (resolve tok) else f tok) = l.flatten := by
    intro l
    induction l with
    | nil => intro _; rfl
    | cons t ts ih =>
      intro hl
      have ⟨hw, ha⟩ := hl t (List.mem_cons_self ..)
      simp only [List.flatMap_cons, List.flatten_cons, hw, Bool.false_eq_true, ite_false]
      rw [hf1 t ha, ih (fun tok hm => hl tok (List.mem_cons_of_mem _ hm))]
  unfold ctxFixed
  rw [key _ (fun tok ht => ⟨hnoword s hs tok ht, htoks tok ht⟩), hpart]

theorem ctxFixed_I3
    (hpart : ∀ s, (tokenize s).flatten = s)
    (hnoword : ∀ s, AllA asc s → ∀ tok ∈ tokenize s, isWord tok = false)
    (hf1 : ∀ s, AllA asc s → f s = s) (hf2 : ∀ s, AllA asc (f s)) :
    ∀ s, ctxFixed isWord resolve f tokenize (ctxFixed isWord resolve f tokenize s)
      = ctxFixed isWord resolve f tokenize s :=
  I3_of_I1_I2 (ctxFixed_I1 asc isWord resolve f tokenize hpart hnoword hf1)
    (ctxFixed_I2 asc isWord resolve f tokenize hf2)

end Context

end Transliterate
