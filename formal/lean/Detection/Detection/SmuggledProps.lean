import Detection.Smuggled

/-!
# General theorems about the decoder (induction, no `native_decide`)

* `decodeF_fuel`: `l.length` fuel is enough, so `decodeAt` is the loop.
* `decodeAt_cut`: an ordinary character is a cut point. Decoding `u ++ x :: v` is decoding
  `u` and `v` separately, for every `u` and `v`.
* `roundtrip_tag`, `roundtrip_vs`, `roundtrip_zw`: each documented encoder's output, set
  between two ordinary characters anywhere in any text, decodes to exactly the bytes that
  were encoded, with the right span, and nothing else in the text changes.

`Findings.lean` shows the guard is necessary: next to a carrier of its own scheme (a
presentation selector already on an emoji, a stray `U+200B`), the payload is not
recovered, and the zero-width case recovers *different* printable text.
-/

namespace Detection

open S

theorem decodeF_nil (n pos : Nat) : decodeF n pos [] = [] := by
  cases n <;> rfl

theorem decodeF_fuel : ∀ (n m pos : Nat) (l : List S),
    l.length ≤ n → l.length ≤ m → decodeF n pos l = decodeF m pos l := by
  intro n
  induction n with
  | zero =>
    intro m pos l h _
    have : l = [] := List.eq_nil_of_length_eq_zero (by omega)
    subst this; simp [decodeF_nil]
  | succ n ih =>
    intro m pos l h1 h2
    cases l with
    | nil => simp [decodeF_nil]
    | cons c rest =>
      cases m with
      | zero => simp at h2
      | succ m =>
        simp only [decodeF]
        congr 1
        apply ih <;> simp only [List.length_drop, List.length_cons] at * <;> omega

/-! ## Cutting at an ordinary character -/

theorem flagScan_cut (u v : List S) (acc : List Nat) (k : Nat) :
    flagScan (u ++ .x :: v) acc k = flagScan u acc k := by
  induction u generalizing acc k with
  | nil => simp [flagScan, isTagLetter]
  | cons c u ih => simp [flagScan, ih]

theorem flagLen_cut (c : S) (u v : List S) :
    flagLen (c :: (u ++ .x :: v)) = flagLen (c :: u) := by
  cases c <;> simp [flagLen, flagScan_cut]

theorem run_cut (p : S → Bool) (f : S → Nat) (u v : List S) (hx : p .x = false) :
    run p f (u ++ .x :: v) = run p f u := by
  induction u with
  | nil => simp [run, hx]
  | cons c u ih => simp [run, ih]

theorem zwRun_cut (u v : List S) : zwRun (u ++ .x :: v) = zwRun u := by
  induction u with
  | nil => simp [zwRun, isZW]
  | cons c u ih => simp [zwRun, ih]

theorem run_le (p : S → Bool) (f : S → Nat) (u : List S) : (run p f u).2 ≤ u.length := by
  induction u with
  | nil => simp [run]
  | cons c u ih => simp only [run]; split <;> simp <;> omega

theorem zwRun_le (u : List S) : (zwRun u).2 ≤ u.length := by
  induction u with
  | nil => simp [zwRun]
  | cons c u ih => simp only [zwRun]; split <;> simp <;> omega

theorem flagScan_le (u : List S) (acc : List Nat) (k n : Nat) :
    flagScan u acc k = some n → n ≤ u.length + k := by
  induction u generalizing acc k with
  | nil => simp [flagScan]
  | cons c u ih =>
    simp only [flagScan]
    split
    · intro h; have := ih _ _ h; simp; omega
    · split
      · split
        · intro h; simp at h; simp; omega
        · simp
      · simp

theorem flagLen_le (u : List S) (n : Nat) : flagLen u = some n → n ≤ u.length := by
  cases u with
  | nil => simp [flagLen]
  | cons c rest =>
    cases c <;> simp [flagLen]
    intro h; have := flagScan_le _ _ _ _ h; omega

theorem headIs_cut (u v : List S) (k : Nat) (hk : k ≤ u.length) :
    headIs .cancel ((u ++ .x :: v).drop k) = headIs .cancel (u.drop k) := by
  rw [List.drop_append_of_le_length hk]
  cases h : u.drop k with
  | nil => simp [headIs]
  | cons d w => simp [headIs]

theorem headIs_drop_lt (c : S) (u : List S) (k : Nat) :
    headIs c (u.drop k) = true → k < u.length := by
  intro h
  rcases Nat.lt_or_ge k u.length with hk | hk
  · exact hk
  · have : u.drop k = [] := List.drop_eq_nil_of_le hk
    rw [this] at h; simp [headIs] at h

theorem step_cut (c : S) (u v : List S) : step (c :: (u ++ .x :: v)) = step (c :: u) := by
  have e : c :: (u ++ .x :: v) = (c :: u) ++ .x :: v := rfl
  have ht : run isTagByte tagByte (c :: (u ++ .x :: v)) = run isTagByte tagByte (c :: u) := by
    rw [e]; exact run_cut _ _ _ _ rfl
  have hv : run isVS vsByte (c :: (u ++ .x :: v)) = run isVS vsByte (c :: u) := by
    rw [e]; exact run_cut _ _ _ _ rfl
  have hz : zwRun (c :: (u ++ .x :: v)) = zwRun (c :: u) := by
    rw [e]; exact zwRun_cut _ _
  have hd : headIs .cancel ((c :: (u ++ .x :: v)).drop (run isTagByte tagByte (c :: u)).2)
      = headIs .cancel ((c :: u).drop (run isTagByte tagByte (c :: u)).2) := by
    rw [e]; exact headIs_cut _ _ _ (run_le _ _ _)
  unfold step
  simp only [flagLen_cut, ht, hv, hz, hd]

theorem step_le (c : S) (u : List S) : max 1 (step (c :: u)).2 ≤ (c :: u).length := by
  unfold step
  simp only
  split
  · rename_i k hk; have := flagLen_le _ _ hk; simp at this ⊢; omega
  · split
    · have h1 := run_le isTagByte tagByte (c :: u)
      split
      · rename_i hh; have := headIs_drop_lt _ _ _ hh; simp at this h1 ⊢; omega
      · simp at h1 ⊢; omega
    · split
      · have h1 := run_le isVS vsByte (c :: u)
        split <;> simp at h1 ⊢ <;> omega
      · split
        · have h1 := zwRun_le (c :: u)
          split <;> simp at h1 ⊢ <;> omega
        · simp

theorem step_x (v : List S) : step (.x :: v) = (none, 1) := by
  simp [step, flagLen, isTagByte, isVS, isZWStart]

theorem decodeF_cut (v : List S) : ∀ (n pos : Nat) (u : List S),
    u.length + 1 + v.length ≤ n →
    decodeF n pos (u ++ .x :: v) = decodeAt pos u ++ decodeAt (pos + u.length + 1) v := by
  intro n
  induction n with
  | zero => intro pos u h; omega
  | succ n ih =>
    intro pos u h
    cases u with
    | nil =>
      have hx : decodeF (n + 1) pos (.x :: v) = decodeF n (pos + 1) v := by
        simp [decodeF, step_x]
      rw [List.nil_append, hx]
      simp only [decodeAt, List.length_nil, decodeF_nil, List.nil_append, Nat.add_zero]
      exact decodeF_fuel _ _ _ _ (by simp at h; omega) (Nat.le_refl _)
    | cons c u =>
      have hk := step_le c u
      simp only [List.cons_append, decodeF, step_cut]
      have hdrop : (c :: (u ++ .x :: v)).drop (max 1 (step (c :: u)).2)
          = (c :: u).drop (max 1 (step (c :: u)).2) ++ .x :: v := by
        rw [show c :: (u ++ .x :: v) = (c :: u) ++ .x :: v from rfl]
        exact List.drop_append_of_le_length hk
      rw [hdrop, ih _ _ (by simp only [List.length_drop, List.length_cons] at h ⊢; omega)]
      have hw : decodeAt pos (c :: u)
          = ((step (c :: u)).1.map (shift pos)).toList ++
            decodeAt (pos + max 1 (step (c :: u)).2) ((c :: u).drop (max 1 (step (c :: u)).2)) := by
        simp only [decodeAt, List.length_cons, decodeF]
        congr 1
        exact decodeF_fuel _ _ _ _ (by simp; omega) (Nat.le_refl _)
      rw [hw, List.append_assoc]
      congr 3
      simp only [List.length_drop, List.length_cons] at hk ⊢
      omega

/-- **An ordinary character is a cut point** for the decoder. -/
theorem decodeAt_cut (pos : Nat) (u v : List S) :
    decodeAt pos (u ++ .x :: v) = decodeAt pos u ++ decodeAt (pos + u.length + 1) v :=
  decodeF_cut v _ pos u (by simp only [List.length_append, List.length_cons]; omega)

/-! ## The encoders round-trip -/

theorem run_encTag (bs : List Nat) (h : ∀ b ∈ bs, 0x20 ≤ b ∧ b ≤ 0x7E) :
    run isTagByte tagByte (encTag bs) = (bs, bs.length) := by
  induction bs with
  | nil => rfl
  | cons b bs ih =>
    have hb := h b List.mem_cons_self
    have ih' := ih (fun b' m => h b' (List.mem_cons_of_mem _ m))
    have hp : isTagByte (tagb b) = true := by simp [isTagByte, hb]
    show run isTagByte tagByte (tagb b :: encTag bs) = _
    simp [run, hp, ih', tagByte]

theorem run_encVS (bs : List Nat) (h : ∀ b ∈ bs, b < 256) :
    run isVS vsByte (encVS bs) = (bs, bs.length) := by
  induction bs with
  | nil => rfl
  | cons b bs ih =>
    have hb := h b List.mem_cons_self
    have ih' := ih (fun b' m => h b' (List.mem_cons_of_mem _ m))
    have hp : isVS (vsb b) = true := by simp [isVS, hb]
    show run isVS vsByte (vsb b :: encVS bs) = _
    simp [run, hp, ih', vsByte]

theorem bits8_bit (b : Nat) : ∀ bit ∈ bits8 b, bit = 0 ∨ bit = 1 := by
  simp [bits8]; omega

theorem zwRun_bits (l w : List Nat) (hl : ∀ bit ∈ l, bit = 0 ∨ bit = 1) :
    zwRun (l.map bitChar ++ w.map bitChar) = (l ++ (zwRun (w.map bitChar)).1,
      l.length + (zwRun (w.map bitChar)).2) := by
  induction l with
  | nil => simp
  | cons bit l ih =>
    have hb := hl bit List.mem_cons_self
    have ih' := ih (fun b m => hl b (List.mem_cons_of_mem _ m))
    rcases hb with rfl | rfl <;>
      simp [zwRun, bitChar, isZW, zwBit, ih'] <;> omega

theorem encZW_cons (b : Nat) (bs : List Nat) :
    encZW (b :: bs) = (bits8 b).map bitChar ++ encZW bs := by
  simp [encZW]

theorem length_encZW (bs : List Nat) : (encZW bs).length = 8 * bs.length := by
  induction bs with
  | nil => rfl
  | cons b bs ih => rw [encZW_cons, List.length_append, ih]; simp [bits8]; omega

theorem encZW_eq (bs : List Nat) : encZW bs = (bs.flatMap bits8).map bitChar := by
  simp [encZW, List.map_flatMap]

theorem zwRun_encZW (bs : List Nat) :
    zwRun (encZW bs) = (bs.flatMap bits8, 8 * bs.length) := by
  induction bs with
  | nil => rfl
  | cons b bs ih =>
    rw [encZW_cons, encZW_eq bs, zwRun_bits _ _ (bits8_bit b), ← encZW_eq bs, ih]
    simp [bits8]; omega

theorem toBytes_bits8 (b : Nat) (hb : b < 256) (rest : List Nat) :
    toBytes (bits8 b ++ rest) = b :: toBytes rest := by
  simp only [bits8, List.cons_append, List.nil_append, toBytes, List.cons.injEq, and_true]
  omega

theorem toBytes_flatMap (bs : List Nat) (h : ∀ b ∈ bs, b < 256) :
    toBytes (bs.flatMap bits8) = bs := by
  induction bs with
  | nil => rfl
  | cons b bs ih =>
    rw [List.flatMap_cons, toBytes_bits8 b (h b List.mem_cons_self),
      ih (fun b' m => h b' (List.mem_cons_of_mem _ m))]

theorem decodeAt_single (pos : Nat) (l : List S) (p : Payload) (hl : l ≠ [])
    (hs : step l = (some p, l.length)) : decodeAt pos l = [shift pos p] := by
  cases l with
  | nil => exact absurd rfl hl
  | cons c rest =>
    simp only [decodeAt, List.length_cons, decodeF, hs]
    have : max 1 (rest.length + 1) = rest.length + 1 := by omega
    simp [this, decodeF_nil]

theorem step_encTag (bs : List Nat) (hne : bs ≠ []) (h : ∀ b ∈ bs, 0x20 ≤ b ∧ b ≤ 0x7E) :
    step (encTag bs) = (some ⟨.tagAscii, 0, bs.length, bs⟩, (encTag bs).length) := by
  cases bs with
  | nil => exact absurd rfl hne
  | cons b bs' =>
    have hb := h b List.mem_cons_self
    have hr := run_encTag (b :: bs') h
    have hlen : (encTag (b :: bs')).length = (b :: bs').length := by simp [encTag]
    have hdrop : headIs .cancel ((encTag (b :: bs')).drop (b :: bs').length) = false := by
      rw [← hlen, List.drop_length]; rfl
    simp only [encTag, List.map_cons] at hr hdrop ⊢
    have hd2 : List.drop bs'.length (List.map tagb bs') = [] := List.drop_eq_nil_of_le (by simp)
    simp [step, flagLen, isTagByte, hb, hr, hd2, headIs]

theorem step_encVS (bs : List Nat) (h2 : 2 ≤ bs.length) (h : ∀ b ∈ bs, b < 256) :
    step (encVS bs) = (some ⟨.variationBytes, 0, bs.length, bs⟩, (encVS bs).length) := by
  cases bs with
  | nil => simp at h2
  | cons b bs' =>
    have hb := h b List.mem_cons_self
    have hr := run_encVS (b :: bs') h
    simp only [encVS, List.map_cons] at hr ⊢
    simp only [List.length_cons] at h2
    have h2' : 2 ≤ bs'.length + 1 := h2
    simp [step, flagLen, isTagByte, isVS, hb, hr, h2']

theorem step_encZW (bs : List Nat) (hne : bs ≠ []) (h : ∀ b ∈ bs, b < 256) :
    step (encZW bs) = (some ⟨.zeroWidthBinary, 0, 8 * bs.length, bs⟩, (encZW bs).length) := by
  cases bs with
  | nil => exact absurd rfl hne
  | cons b bs' =>
    have hr := zwRun_encZW (b :: bs')
    have hbytes := toBytes_flatMap (b :: bs') h
    rw [List.flatMap_cons] at hbytes
    have hlen := length_encZW (b :: bs')
    rw [encZW_cons] at hr hlen ⊢
    have hhead : ∃ c t, (bits8 b).map bitChar ++ encZW bs' = c :: t ∧
        (c = .z0 ∨ c = .z1) := by
      refine ⟨bitChar (b / 128 % 2), _, rfl, ?_⟩
      simp only [bitChar]; split <;> simp
    obtain ⟨c, t, ht, hc⟩ := hhead
    rw [ht] at hr hlen ⊢
    rcases hc with rfl | rfl <;>
      simp [step, flagLen, isTagByte, isVS, isZWStart, hr, hbytes, hlen]

/-- **`tag_ascii` round-trips** between two ordinary characters, in any text. -/
theorem roundtrip_tag (pre post : List S) (bs : List Nat) (hne : bs ≠ [])
    (h : ∀ b ∈ bs, 0x20 ≤ b ∧ b ≤ 0x7E) :
    decode (pre ++ .x :: (encTag bs ++ .x :: post)) =
      decode pre ++ ⟨.tagAscii, pre.length + 1, bs.length, bs⟩ ::
        decodeAt (pre.length + 1 + bs.length + 1) post := by
  have hne' : encTag bs ≠ [] := by simpa [encTag] using hne
  have hlen : (encTag bs).length = bs.length := by simp [encTag]
  rw [decode, decodeAt_cut, decodeAt_cut, decodeAt_single _ _ _ hne' (step_encTag bs hne h)]
  simp [shift, hlen, decode]

/-- **`variation_bytes` round-trips** between two ordinary characters, from two bytes. -/
theorem roundtrip_vs (pre post : List S) (bs : List Nat) (h2 : 2 ≤ bs.length)
    (h : ∀ b ∈ bs, b < 256) :
    decode (pre ++ .x :: (encVS bs ++ .x :: post)) =
      decode pre ++ ⟨.variationBytes, pre.length + 1, bs.length, bs⟩ ::
        decodeAt (pre.length + 1 + bs.length + 1) post := by
  have hne' : encVS bs ≠ [] := by
    intro e; simp [encVS] at e; subst e; simp at h2
  have hlen : (encVS bs).length = bs.length := by simp [encVS]
  rw [decode, decodeAt_cut, decodeAt_cut, decodeAt_single _ _ _ hne' (step_encVS bs h2 h)]
  simp [shift, hlen, decode]

/-- **`zero_width_binary` round-trips** between two ordinary characters. -/
theorem roundtrip_zw (pre post : List S) (bs : List Nat) (hne : bs ≠ [])
    (h : ∀ b ∈ bs, b < 256) :
    decode (pre ++ .x :: (encZW bs ++ .x :: post)) =
      decode pre ++ ⟨.zeroWidthBinary, pre.length + 1, 8 * bs.length, bs⟩ ::
        decodeAt (pre.length + 1 + 8 * bs.length + 1) post := by
  have hlen := length_encZW bs
  have hne' : encZW bs ≠ [] := by
    intro e; have := congrArg List.length e; rw [hlen] at this
    cases bs with
    | nil => exact hne rfl
    | cons _ _ => simp at this
  rw [decode, decodeAt_cut, decodeAt_cut, decodeAt_single _ _ _ hne' (step_encZW bs hne h)]
  simp [shift, hlen, decode]

end Detection
