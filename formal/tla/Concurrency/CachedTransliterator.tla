------------------------ MODULE CachedTransliterator ------------------------
(***************************************************************************)
(* make_cached_transliterator (python/disarm/_api.py:3693-3716) and the    *)
(* registration generation counter (_api.py:3432-3438, bumped by           *)
(* register_lang / register_replacements / remove_replacement /            *)
(* clear_replacements AFTER the Rust mutation returns: _api.py:3474-3475,  *)
(* 3506-3507, 3527-3528, 3539-3540).                                       *)
(*                                                                         *)
(*   def cached(text):                                                     *)
(*       nonlocal seen_generation                                          *)
(*       if _registration_generation != seen_generation:   # c_check       *)
(*           _cached.cache_clear()                         # c_clear       *)
(*           seen_generation = _registration_generation    # c_seen        *)
(*       return _cached(text)            # lru: c_lookup / c_compute /     *)
(*                                       #      c_store                    *)
(*                                                                         *)
(* This is pure Python under the GIL: every labelled step is atomic, and   *)
(* the eval loop may switch threads between any two of them. In particular *)
(* functools.lru_cache (C) calls the wrapped Python function on a miss;    *)
(* the eval-breaker check after `transliterate(...)` returns inside        *)
(* `_cached` is a switch point, so compute and store are separate steps.   *)
(* The Rust transliterate / register calls hold the GIL throughout and are *)
(* single steps.                                                           *)
(*                                                                         *)
(* One cache key; `table` is the registration table's version; a cache    *)
(* entry records the table version its value was computed from.           *)
(*                                                                         *)
(* KeyedByGen: proposed fix, the lru key includes the generation read at   *)
(* call start (`_cached(text, _registration_generation)`).                 *)
(***************************************************************************)
EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANTS
    Readers,        \* threads calling cached(k)
    Writer,         \* the thread registering (one registration)
    CallsPerReader,
    KeyedByGen      \* TRUE: proposed fix

NoEntry == -1

(* --algorithm CachedTransliterator {
variables
    table = 0,                        \* Rust registration table version
    gen = 0,                          \* _registration_generation
    seen = 0,                         \* the closure's seen_generation
    cache = [x \in 0..1 |-> NoEntry], \* lru entry for key k (per generation if KeyedByGen)
    writerDone = FALSE,
    staleServed = FALSE;              \* a call that began after the registration
                                      \* returned a pre-registration result

define {
    \* The docstring's promise: once a registration has returned, no later
    \* call serves a result that pre-dates it.
    NoStaleAfterRegistration == ~staleServed
    \* After everything quiesces, no entry that could still be served is stale.
    Quiescent == \A t \in Readers \cup {Writer} : pc[t] = "Done"
    NoStaleAfterQuiesce ==
        Quiescent =>
            LET live == IF KeyedByGen THEN gen ELSE 0
            IN cache[live] \in {NoEntry, table}
}

process (w = Writer)
variable tmp = 0;
{
w_reg:
    table := 1;                       \* _register_replacements(...) (Rust, atomic)
w_bump_read:
    tmp := gen;                       \* _registration_generation += 1 (read ...
w_bump_write:
    gen := tmp + 1;                   \* ... then write: two bytecodes)
    writerDone := TRUE;
}

process (rd \in Readers)
variables n = CallsPerReader, g = 0, v = 0, after = FALSE;
{
c_call:
    while (n > 0) {
    c_check:
        after := writerDone;
        g := gen;
        if (KeyedByGen) { goto c_lookup }
        else if (gen = seen) { goto c_lookup };
    c_clear:
        cache := [x \in 0..1 |-> NoEntry];
    c_seen:
        seen := gen;
    c_lookup:
        if (cache[IF KeyedByGen THEN g ELSE 0] # NoEntry) {
            v := cache[IF KeyedByGen THEN g ELSE 0];
            goto c_ret;
        };
    c_compute:
        v := table;                   \* transliterate(text): Rust, atomic
    c_store:
        cache[IF KeyedByGen THEN g ELSE 0] := v;   \* lru_cache inserts the result
    c_ret:
        if (after /\ v # table) { staleServed := TRUE };
        n := n - 1;
    }
}
} *)
\* BEGIN TRANSLATION (chksum(pcal) = "ef991833" /\ chksum(tla) = "f5d82664")
VARIABLES pc, table, gen, seen, cache, writerDone, staleServed

(* define statement *)
NoStaleAfterRegistration == ~staleServed

Quiescent == \A t \in Readers \cup {Writer} : pc[t] = "Done"
NoStaleAfterQuiesce ==
    Quiescent =>
        LET live == IF KeyedByGen THEN gen ELSE 0
        IN cache[live] \in {NoEntry, table}

VARIABLES tmp, n, g, v, after

vars == << pc, table, gen, seen, cache, writerDone, staleServed, tmp, n, g, v, 
           after >>

ProcSet == {Writer} \cup (Readers)

Init == (* Global variables *)
        /\ table = 0
        /\ gen = 0
        /\ seen = 0
        /\ cache = [x \in 0..1 |-> NoEntry]
        /\ writerDone = FALSE
        /\ staleServed = FALSE
        (* Process w *)
        /\ tmp = 0
        (* Process rd *)
        /\ n = [self \in Readers |-> CallsPerReader]
        /\ g = [self \in Readers |-> 0]
        /\ v = [self \in Readers |-> 0]
        /\ after = [self \in Readers |-> FALSE]
        /\ pc = [self \in ProcSet |-> CASE self = Writer -> "w_reg"
                                        [] self \in Readers -> "c_call"]

w_reg == /\ pc[Writer] = "w_reg"
         /\ table' = 1
         /\ pc' = [pc EXCEPT ![Writer] = "w_bump_read"]
         /\ UNCHANGED << gen, seen, cache, writerDone, staleServed, tmp, n, g, 
                         v, after >>

w_bump_read == /\ pc[Writer] = "w_bump_read"
               /\ tmp' = gen
               /\ pc' = [pc EXCEPT ![Writer] = "w_bump_write"]
               /\ UNCHANGED << table, gen, seen, cache, writerDone, 
                               staleServed, n, g, v, after >>

w_bump_write == /\ pc[Writer] = "w_bump_write"
                /\ gen' = tmp + 1
                /\ writerDone' = TRUE
                /\ pc' = [pc EXCEPT ![Writer] = "Done"]
                /\ UNCHANGED << table, seen, cache, staleServed, tmp, n, g, v, 
                                after >>

w == w_reg \/ w_bump_read \/ w_bump_write

c_call(self) == /\ pc[self] = "c_call"
                /\ IF n[self] > 0
                      THEN /\ pc' = [pc EXCEPT ![self] = "c_check"]
                      ELSE /\ pc' = [pc EXCEPT ![self] = "Done"]
                /\ UNCHANGED << table, gen, seen, cache, writerDone, 
                                staleServed, tmp, n, g, v, after >>

c_check(self) == /\ pc[self] = "c_check"
                 /\ after' = [after EXCEPT ![self] = writerDone]
                 /\ g' = [g EXCEPT ![self] = gen]
                 /\ IF KeyedByGen
                       THEN /\ pc' = [pc EXCEPT ![self] = "c_lookup"]
                       ELSE /\ IF gen = seen
                                  THEN /\ pc' = [pc EXCEPT ![self] = "c_lookup"]
                                  ELSE /\ pc' = [pc EXCEPT ![self] = "c_clear"]
                 /\ UNCHANGED << table, gen, seen, cache, writerDone, 
                                 staleServed, tmp, n, v >>

c_clear(self) == /\ pc[self] = "c_clear"
                 /\ cache' = [x \in 0..1 |-> NoEntry]
                 /\ pc' = [pc EXCEPT ![self] = "c_seen"]
                 /\ UNCHANGED << table, gen, seen, writerDone, staleServed, 
                                 tmp, n, g, v, after >>

c_seen(self) == /\ pc[self] = "c_seen"
                /\ seen' = gen
                /\ pc' = [pc EXCEPT ![self] = "c_lookup"]
                /\ UNCHANGED << table, gen, cache, writerDone, staleServed, 
                                tmp, n, g, v, after >>

c_lookup(self) == /\ pc[self] = "c_lookup"
                  /\ IF cache[IF KeyedByGen THEN g[self] ELSE 0] # NoEntry
                        THEN /\ v' = [v EXCEPT ![self] = cache[IF KeyedByGen THEN g[self] ELSE 0]]
                             /\ pc' = [pc EXCEPT ![self] = "c_ret"]
                        ELSE /\ pc' = [pc EXCEPT ![self] = "c_compute"]
                             /\ v' = v
                  /\ UNCHANGED << table, gen, seen, cache, writerDone, 
                                  staleServed, tmp, n, g, after >>

c_compute(self) == /\ pc[self] = "c_compute"
                   /\ v' = [v EXCEPT ![self] = table]
                   /\ pc' = [pc EXCEPT ![self] = "c_store"]
                   /\ UNCHANGED << table, gen, seen, cache, writerDone, 
                                   staleServed, tmp, n, g, after >>

c_store(self) == /\ pc[self] = "c_store"
                 /\ cache' = [cache EXCEPT ![IF KeyedByGen THEN g[self] ELSE 0] = v[self]]
                 /\ pc' = [pc EXCEPT ![self] = "c_ret"]
                 /\ UNCHANGED << table, gen, seen, writerDone, staleServed, 
                                 tmp, n, g, v, after >>

c_ret(self) == /\ pc[self] = "c_ret"
               /\ IF after[self] /\ v[self] # table
                     THEN /\ staleServed' = TRUE
                     ELSE /\ TRUE
                          /\ UNCHANGED staleServed
               /\ n' = [n EXCEPT ![self] = n[self] - 1]
               /\ pc' = [pc EXCEPT ![self] = "c_call"]
               /\ UNCHANGED << table, gen, seen, cache, writerDone, tmp, g, v, 
                               after >>

rd(self) == c_call(self) \/ c_check(self) \/ c_clear(self) \/ c_seen(self)
               \/ c_lookup(self) \/ c_compute(self) \/ c_store(self)
               \/ c_ret(self)

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == w
           \/ (\E self \in Readers: rd(self))
           \/ Terminating

Spec == Init /\ [][Next]_vars

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 
=============================================================================
