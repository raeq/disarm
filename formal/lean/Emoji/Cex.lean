import Emoji.Suite

/-! `lake exe cex [N] [shipped|fixed|extra] [filter]`: for each property of the suite,
search every string over its alphabet up to length N (default 4) and print the shortest
counterexample, with the model's output and a second pass over it. -/

open Emoji Emoji.Tables

def fmt (s : List Char) : String :=
  "\"" ++ String.join (s.map fun c =>
    if c.toNat ≥ 0x20 && c.toNat < 0x7F then c.toString
    else "\\u{" ++ (String.ofList (Nat.toDigits 16 c.toNat)).toUpper ++ "}") ++ "\""

def main (args : List String) : IO Unit := do
  let n := (args.head? >>= String.toNat?).getD 4
  let which := args.getD 1 "shipped"
  let filt := args.getD 2 ""
  let checks := match which with
    | "fixed" => suite fixed
    | "extra" => shippedExtra
    | _ => suite shipped
  for c in checks do
    if filt != "" && (c.name.splitOn filt).length ≤ 1 then continue
    match firstCex c.alpha c.p n with
    | none => IO.println s!"HOLDS ≤{n}  {c.name}"
    | some s =>
      let out := c.f s
      IO.println s!"FAILS      {c.name}: {fmt s} ↦ {fmt out}   (again ↦ {fmt (c.f out)})"
