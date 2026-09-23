---------------------------- MODULE Registration ----------------------------
(***************************************************************************)
(* Check-then-act in register_lang (src/transliterate.rs:1654-1678):       *)
(*                                                                         *)
(*   check_not_sealed("register_lang")?            REGISTRATIONS_SEALED    *)
(*   let current = tables::registered_lang_count(); LANG_TABLES.read()     *)
(*   if current >= MAX_REGISTERED_LANGS && !has_registered_lang(code) {    *)
(*       return Err(RegisterLangLimit) }            LANG_TABLES.read()     *)
(*   tables::register_lang(code, mappings)          LANG_TABLES.write()    *)
(*                                                  (tables/mod.rs:561-565)*)
(*                                                                         *)
(* versus seal_registrations (tables/mod.rs:167-170): one Release store.   *)
(* Each check takes and drops its own guard, so nothing makes the check    *)
(* and the insert one atomic step EXCEPT the GIL: the PyO3 shim            *)
(* (src/py/transliterate.rs:60-62) holds it for the whole call, runs no    *)
(* Python code in between, and blocking on LANG_TABLES.write() does not    *)
(* release it. The public Rust API (src/api/transliterate.rs:271-272) has  *)
(* no GIL. GilAtomic selects which caller is modelled.                     *)
(* register_replacements does its cap check under the write lock           *)
(* (tables/mod.rs:603-618) and is not affected; its seal check is.         *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, TLC

CONSTANTS
    Registrants,    \* threads each registering one new language code
    Sealer,         \* thread calling seal_registrations()
    Max,            \* MAX_REGISTERED_LANGS
    GilAtomic       \* TRUE: Python binding (GIL held across the call)

(* --algorithm Registration {
variables
    gil = 0,
    sealed = FALSE,
    sealReturned = FALSE,
    langs = {},
    mutatedAfterSeal = FALSE;

define {
    CapRespected == Cardinality(langs) <= Max
    NoMutationAfterSeal == ~mutatedAfterSeal
}

process (s = Sealer)
{
s_gil:
    if (GilAtomic) { await gil = 0; gil := Sealer };
s_seal:
    sealed := TRUE;
    sealReturned := TRUE;
    if (GilAtomic) { gil := 0 };
}

process (reg \in Registrants)
variable count = 0;
{
r_gil:
    if (GilAtomic) { await gil = 0; gil := self };
r_sealchk:
    if (sealed) { goto r_out };                     \* check_not_sealed
r_count:
    count := Cardinality(langs);                    \* registered_lang_count()
r_cap:
    if (count >= Max /\ self \notin langs) { goto r_out };
r_insert:
    langs := langs \cup {self};                     \* LANG_TABLES.write().insert
    if (sealReturned) { mutatedAfterSeal := TRUE };
r_out:
    if (GilAtomic) { gil := 0 };
}
} *)
\* BEGIN TRANSLATION (chksum(pcal) = "e5c0016b" /\ chksum(tla) = "e2fb5c40")
VARIABLES pc, gil, sealed, sealReturned, langs, mutatedAfterSeal

(* define statement *)
CapRespected == Cardinality(langs) <= Max
NoMutationAfterSeal == ~mutatedAfterSeal

VARIABLE count

vars == << pc, gil, sealed, sealReturned, langs, mutatedAfterSeal, count >>

ProcSet == {Sealer} \cup (Registrants)

Init == (* Global variables *)
        /\ gil = 0
        /\ sealed = FALSE
        /\ sealReturned = FALSE
        /\ langs = {}
        /\ mutatedAfterSeal = FALSE
        (* Process reg *)
        /\ count = [self \in Registrants |-> 0]
        /\ pc = [self \in ProcSet |-> CASE self = Sealer -> "s_gil"
                                        [] self \in Registrants -> "r_gil"]

s_gil == /\ pc[Sealer] = "s_gil"
         /\ IF GilAtomic
               THEN /\ gil = 0
                    /\ gil' = Sealer
               ELSE /\ TRUE
                    /\ gil' = gil
         /\ pc' = [pc EXCEPT ![Sealer] = "s_seal"]
         /\ UNCHANGED << sealed, sealReturned, langs, mutatedAfterSeal, count >>

s_seal == /\ pc[Sealer] = "s_seal"
          /\ sealed' = TRUE
          /\ sealReturned' = TRUE
          /\ IF GilAtomic
                THEN /\ gil' = 0
                ELSE /\ TRUE
                     /\ gil' = gil
          /\ pc' = [pc EXCEPT ![Sealer] = "Done"]
          /\ UNCHANGED << langs, mutatedAfterSeal, count >>

s == s_gil \/ s_seal

r_gil(self) == /\ pc[self] = "r_gil"
               /\ IF GilAtomic
                     THEN /\ gil = 0
                          /\ gil' = self
                     ELSE /\ TRUE
                          /\ gil' = gil
               /\ pc' = [pc EXCEPT ![self] = "r_sealchk"]
               /\ UNCHANGED << sealed, sealReturned, langs, mutatedAfterSeal, 
                               count >>

r_sealchk(self) == /\ pc[self] = "r_sealchk"
                   /\ IF sealed
                         THEN /\ pc' = [pc EXCEPT ![self] = "r_out"]
                         ELSE /\ pc' = [pc EXCEPT ![self] = "r_count"]
                   /\ UNCHANGED << gil, sealed, sealReturned, langs, 
                                   mutatedAfterSeal, count >>

r_count(self) == /\ pc[self] = "r_count"
                 /\ count' = [count EXCEPT ![self] = Cardinality(langs)]
                 /\ pc' = [pc EXCEPT ![self] = "r_cap"]
                 /\ UNCHANGED << gil, sealed, sealReturned, langs, 
                                 mutatedAfterSeal >>

r_cap(self) == /\ pc[self] = "r_cap"
               /\ IF count[self] >= Max /\ self \notin langs
                     THEN /\ pc' = [pc EXCEPT ![self] = "r_out"]
                     ELSE /\ pc' = [pc EXCEPT ![self] = "r_insert"]
               /\ UNCHANGED << gil, sealed, sealReturned, langs, 
                               mutatedAfterSeal, count >>

r_insert(self) == /\ pc[self] = "r_insert"
                  /\ langs' = (langs \cup {self})
                  /\ IF sealReturned
                        THEN /\ mutatedAfterSeal' = TRUE
                        ELSE /\ TRUE
                             /\ UNCHANGED mutatedAfterSeal
                  /\ pc' = [pc EXCEPT ![self] = "r_out"]
                  /\ UNCHANGED << gil, sealed, sealReturned, count >>

r_out(self) == /\ pc[self] = "r_out"
               /\ IF GilAtomic
                     THEN /\ gil' = 0
                     ELSE /\ TRUE
                          /\ gil' = gil
               /\ pc' = [pc EXCEPT ![self] = "Done"]
               /\ UNCHANGED << sealed, sealReturned, langs, mutatedAfterSeal, 
                               count >>

reg(self) == r_gil(self) \/ r_sealchk(self) \/ r_count(self) \/ r_cap(self)
                \/ r_insert(self) \/ r_out(self)

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == s
           \/ (\E self \in Registrants: reg(self))
           \/ Terminating

Spec == Init /\ [][Next]_vars

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 
=============================================================================
