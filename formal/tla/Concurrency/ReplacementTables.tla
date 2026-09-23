------------------------- MODULE ReplacementTables -------------------------
(***************************************************************************)
(* GLOBAL_REPLACEMENTS + GLOBAL_REPLACEMENTS_AC + HAS_REPLACEMENTS         *)
(* (src/tables/mod.rs:88, 105, 138) read by the GIL-released batch path.   *)
(*                                                                         *)
(* Writers (GIL held for the whole call, no detach):                       *)
(*   register_replacements  tables/mod.rs:602-631                          *)
(*   remove_replacement     tables/mod.rs:644-650                          *)
(*   clear_replacements     tables/mod.rs:661-666                          *)
(*   each: GLOBAL_REPLACEMENTS.write() -> mutate -> build automaton ->     *)
(*   GLOBAL_REPLACEMENTS_AC.write() swap (mod.rs:128-132) -> drop AC guard *)
(*   -> HAS_REPLACEMENTS.store(Release) -> drop table guard.               *)
(*                                                                         *)
(* Reader (the only one): apply_replacements (mod.rs:682-695):             *)
(*   HAS_REPLACEMENTS.load(Acquire); if set, GLOBAL_REPLACEMENTS_AC.read() *)
(*   for the whole item. Nobody reads GLOBAL_REPLACEMENTS itself.          *)
(* Called per item inside py.detach in _transliterate_batch               *)
(*   (src/py/transliterate.rs:427-457), chunks of BATCH_CHUNK_SIZE with    *)
(*   the GIL re-taken between chunks (transliterate.rs:421-426).           *)
(*                                                                         *)
(* The same shape covers LANG_TABLES: lookup_registered (mod.rs:419-428)   *)
(* takes LANG_TABLES.read() once per *character* inside the same detach;   *)
(* read "item" below as "character" and "batch" as "one output string".   *)
(*                                                                         *)
(* Table contents are abstracted to a value: 0 = empty table, k > 0 = the  *)
(* k-th distinct non-empty table. An item's result is the content it was   *)
(* transformed with (0 when HAS_REPLACEMENTS was false or the AC was None).*)
(*                                                                         *)
(* Poisoned: crate::recover_lock (src/lib.rs:402-441) on a poisoned lock   *)
(* calls Python::attach -> warnings.warn while the recovered guard is      *)
(* held. Detached, that is "hold AC read, then wait for the GIL".          *)
(* Snapshot: the proposed fix (clone an Arc of the automaton once, while   *)
(* still attached, before py.detach; use it for every item).               *)
(***************************************************************************)
EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANTS
    Writers,        \* threads calling register/clear (GIL held)
    Readers,        \* threads running one transliterate(list) batch
    OpsPerWriter,   \* mutations per writer
    Items,          \* items (lock acquisitions) per batch
    ChunkSize,      \* items per py.detach chunk
    WriterPref,     \* TRUE: std futex RwLock (waiting writer blocks new readers)
    Poisoned,       \* TRUE: GLOBAL_REPLACEMENTS_AC is poisoned (latent path)
    Snapshot        \* TRUE: proposed fix

Threads == Writers \cup Readers

(* --algorithm ReplacementTables {
variables
    gil = 0,
    tblLock = 0,                        \* GLOBAL_REPLACEMENTS writer (only writers lock it)
    acWriter = 0,                       \* GLOBAL_REPLACEMENTS_AC writer
    acReaders = [t \in Threads |-> 0],
    acWwait = {},
    table = 0,                          \* GLOBAL_REPLACEMENTS content
    ac = 0,                             \* content GLOBAL_REPLACEMENTS_AC was built from
    has = FALSE,                        \* HAS_REPLACEMENTS
    fresh = 1,                          \* next non-empty content id
    lastDone = 0,                       \* content after the last *returned* mutation
    inflight = [w \in Writers |-> -1],  \* content being installed by an unreturned mutation
    inItem = [r \in Readers |-> FALSE],
    itemWin = [r \in Readers |-> {}],   \* linearizable results for the current item
    batchWin = [r \in Readers |-> {}],  \* linearizable results for the whole batch
    results = [r \in Readers |-> <<>>],
    itemBad = FALSE;                    \* an item returned a non-linearizable result

define {
    TypeOK ==
        /\ gil \in Threads \cup {0}
        /\ tblLock \in Writers \cup {0}
        /\ acWriter \in Writers \cup {0}
        /\ has \in BOOLEAN
    \* The automaton matches the table whenever no mutation is in its critical
    \* section, and HAS_REPLACEMENTS agrees (the "pair" invariant).
    ACInSync == tblLock = 0 => (ac = table /\ has = (table # 0))
    \* Each item's result is the content of some table version current during
    \* that item (standard register linearizability).
    ItemLinearizable == ~itemBad
    \* Every result of one batch was produced from one table version.
    BatchSingleVersion ==
        \A r \in Readers :
            \A a, b \in 1..Len(results[r]) : results[r][a] = results[r][b]
    \* Every batch result is some version current during the batch.
    BatchLinearizable ==
        \A r \in Readers :
            \A a \in 1..Len(results[r]) : results[r][a] \in batchWin[r]
}

process (wr \in Writers)
variables ops = OpsPerWriter, newc = 0;
{
w_loop:
    while (ops > 0) {
    w_gil:
        await gil = 0;
        gil := self;                                    \* #[pyfunction] entry
    w_tbl:
        await tblLock = 0;
        tblLock := self;
        \* c = fresh: register_replacements (a new non-empty table);
        \* c = 0: clear_replacements (or removing the last key).
        with (c \in {fresh, 0}) {
            newc := c;
            table := c;
            inflight[self] := c;
            itemWin := [x \in Readers |->
                IF inItem[x] THEN itemWin[x] \cup {c} ELSE itemWin[x]];
            batchWin := [x \in Readers |-> batchWin[x] \cup {c}];
        };
        fresh := fresh + 1;
    w_acwait:
        acWwait := acWwait \cup {self};
    w_aclock:                                           \* GIL still held while waiting
        await acWriter = 0 /\ \A t \in Threads : acReaders[t] = 0;
        acWriter := self;
        acWwait := acWwait \ {self};
        ac := newc;
    w_acunlock:
        acWriter := 0;
    w_has:
        has := newc # 0;
    w_done:
        tblLock := 0;
        lastDone := newc;
        inflight[self] := -1;
        ops := ops - 1;
        gil := 0;
    }
}

process (rd \in Readers)
variables i = 0, k = 0, v = 0, snapc = 0;
{
r_gil:
    await gil = 0;
    gil := self;
    batchWin[self] := {lastDone} \cup {inflight[x] : x \in {y \in Writers : inflight[y] # -1}};
r_snap:
    \* Fix: one Arc<automaton> clone, taken attached, before py.detach.
    if (Snapshot) {
        await acWriter = 0 /\ (~WriterPref \/ acWwait = {});
        snapc := IF has THEN ac ELSE 0;
    };
r_chunks:
    while (i < Items) {
    r_detach:
        gil := 0;                                       \* py.detach(...)
        k := 0;
    r_items:
        while (i < Items /\ k < ChunkSize) {
        r_start:
            inItem[self] := TRUE;
            itemWin[self] := {lastDone} \cup {inflight[x] : x \in {y \in Writers : inflight[y] # -1}};
            if (Snapshot) {
                v := snapc;
                goto r_end;
            } else if (~has) {                           \* HAS_REPLACEMENTS.load(Acquire)
                v := 0;
                goto r_end;
            };
        r_rd:
            await acWriter = 0 /\ (~WriterPref \/ acWwait = {});
            acReaders[self] := acReaders[self] + 1;
        r_poison:
            \* recover_lock on a poisoned guard: Python::attach while holding it.
            if (Poisoned) {
                await gil = 0;
                gil := self;
            };
        r_warned:
            if (Poisoned) { gil := 0 };                 \* attach scope ends
        r_val:
            v := ac;
            acReaders[self] := acReaders[self] - 1;
        r_end:
            if (~Snapshot /\ v \notin itemWin[self]) { itemBad := TRUE };
            results[self] := Append(results[self], v);
            inItem[self] := FALSE;
            i := i + 1;
            k := k + 1;
        };
    r_attach:
        await gil = 0;                                  \* detach returns: re-attach
        gil := self;
    };
r_exit:
    gil := 0;
}
} *)
\* BEGIN TRANSLATION (chksum(pcal) = "3cb366f0" /\ chksum(tla) = "f897df78")
VARIABLES pc, gil, tblLock, acWriter, acReaders, acWwait, table, ac, has, 
          fresh, lastDone, inflight, inItem, itemWin, batchWin, results, 
          itemBad

(* define statement *)
TypeOK ==
    /\ gil \in Threads \cup {0}
    /\ tblLock \in Writers \cup {0}
    /\ acWriter \in Writers \cup {0}
    /\ has \in BOOLEAN


ACInSync == tblLock = 0 => (ac = table /\ has = (table # 0))


ItemLinearizable == ~itemBad

BatchSingleVersion ==
    \A r \in Readers :
        \A a, b \in 1..Len(results[r]) : results[r][a] = results[r][b]

BatchLinearizable ==
    \A r \in Readers :
        \A a \in 1..Len(results[r]) : results[r][a] \in batchWin[r]

VARIABLES ops, newc, i, k, v, snapc

vars == << pc, gil, tblLock, acWriter, acReaders, acWwait, table, ac, has, 
           fresh, lastDone, inflight, inItem, itemWin, batchWin, results, 
           itemBad, ops, newc, i, k, v, snapc >>

ProcSet == (Writers) \cup (Readers)

Init == (* Global variables *)
        /\ gil = 0
        /\ tblLock = 0
        /\ acWriter = 0
        /\ acReaders = [t \in Threads |-> 0]
        /\ acWwait = {}
        /\ table = 0
        /\ ac = 0
        /\ has = FALSE
        /\ fresh = 1
        /\ lastDone = 0
        /\ inflight = [w \in Writers |-> -1]
        /\ inItem = [r \in Readers |-> FALSE]
        /\ itemWin = [r \in Readers |-> {}]
        /\ batchWin = [r \in Readers |-> {}]
        /\ results = [r \in Readers |-> <<>>]
        /\ itemBad = FALSE
        (* Process wr *)
        /\ ops = [self \in Writers |-> OpsPerWriter]
        /\ newc = [self \in Writers |-> 0]
        (* Process rd *)
        /\ i = [self \in Readers |-> 0]
        /\ k = [self \in Readers |-> 0]
        /\ v = [self \in Readers |-> 0]
        /\ snapc = [self \in Readers |-> 0]
        /\ pc = [self \in ProcSet |-> CASE self \in Writers -> "w_loop"
                                        [] self \in Readers -> "r_gil"]

w_loop(self) == /\ pc[self] = "w_loop"
                /\ IF ops[self] > 0
                      THEN /\ pc' = [pc EXCEPT ![self] = "w_gil"]
                      ELSE /\ pc' = [pc EXCEPT ![self] = "Done"]
                /\ UNCHANGED << gil, tblLock, acWriter, acReaders, acWwait, 
                                table, ac, has, fresh, lastDone, inflight, 
                                inItem, itemWin, batchWin, results, itemBad, 
                                ops, newc, i, k, v, snapc >>

w_gil(self) == /\ pc[self] = "w_gil"
               /\ gil = 0
               /\ gil' = self
               /\ pc' = [pc EXCEPT ![self] = "w_tbl"]
               /\ UNCHANGED << tblLock, acWriter, acReaders, acWwait, table, 
                               ac, has, fresh, lastDone, inflight, inItem, 
                               itemWin, batchWin, results, itemBad, ops, newc, 
                               i, k, v, snapc >>

w_tbl(self) == /\ pc[self] = "w_tbl"
               /\ tblLock = 0
               /\ tblLock' = self
               /\ \E c \in {fresh, 0}:
                    /\ newc' = [newc EXCEPT ![self] = c]
                    /\ table' = c
                    /\ inflight' = [inflight EXCEPT ![self] = c]
                    /\ itemWin' =        [x \in Readers |->
                                  IF inItem[x] THEN itemWin[x] \cup {c} ELSE itemWin[x]]
                    /\ batchWin' = [x \in Readers |-> batchWin[x] \cup {c}]
               /\ fresh' = fresh + 1
               /\ pc' = [pc EXCEPT ![self] = "w_acwait"]
               /\ UNCHANGED << gil, acWriter, acReaders, acWwait, ac, has, 
                               lastDone, inItem, results, itemBad, ops, i, k, 
                               v, snapc >>

w_acwait(self) == /\ pc[self] = "w_acwait"
                  /\ acWwait' = (acWwait \cup {self})
                  /\ pc' = [pc EXCEPT ![self] = "w_aclock"]
                  /\ UNCHANGED << gil, tblLock, acWriter, acReaders, table, ac, 
                                  has, fresh, lastDone, inflight, inItem, 
                                  itemWin, batchWin, results, itemBad, ops, 
                                  newc, i, k, v, snapc >>

w_aclock(self) == /\ pc[self] = "w_aclock"
                  /\ acWriter = 0 /\ \A t \in Threads : acReaders[t] = 0
                  /\ acWriter' = self
                  /\ acWwait' = acWwait \ {self}
                  /\ ac' = newc[self]
                  /\ pc' = [pc EXCEPT ![self] = "w_acunlock"]
                  /\ UNCHANGED << gil, tblLock, acReaders, table, has, fresh, 
                                  lastDone, inflight, inItem, itemWin, 
                                  batchWin, results, itemBad, ops, newc, i, k, 
                                  v, snapc >>

w_acunlock(self) == /\ pc[self] = "w_acunlock"
                    /\ acWriter' = 0
                    /\ pc' = [pc EXCEPT ![self] = "w_has"]
                    /\ UNCHANGED << gil, tblLock, acReaders, acWwait, table, 
                                    ac, has, fresh, lastDone, inflight, inItem, 
                                    itemWin, batchWin, results, itemBad, ops, 
                                    newc, i, k, v, snapc >>

w_has(self) == /\ pc[self] = "w_has"
               /\ has' = (newc[self] # 0)
               /\ pc' = [pc EXCEPT ![self] = "w_done"]
               /\ UNCHANGED << gil, tblLock, acWriter, acReaders, acWwait, 
                               table, ac, fresh, lastDone, inflight, inItem, 
                               itemWin, batchWin, results, itemBad, ops, newc, 
                               i, k, v, snapc >>

w_done(self) == /\ pc[self] = "w_done"
                /\ tblLock' = 0
                /\ lastDone' = newc[self]
                /\ inflight' = [inflight EXCEPT ![self] = -1]
                /\ ops' = [ops EXCEPT ![self] = ops[self] - 1]
                /\ gil' = 0
                /\ pc' = [pc EXCEPT ![self] = "w_loop"]
                /\ UNCHANGED << acWriter, acReaders, acWwait, table, ac, has, 
                                fresh, inItem, itemWin, batchWin, results, 
                                itemBad, newc, i, k, v, snapc >>

wr(self) == w_loop(self) \/ w_gil(self) \/ w_tbl(self) \/ w_acwait(self)
               \/ w_aclock(self) \/ w_acunlock(self) \/ w_has(self)
               \/ w_done(self)

r_gil(self) == /\ pc[self] = "r_gil"
               /\ gil = 0
               /\ gil' = self
               /\ batchWin' = [batchWin EXCEPT ![self] = {lastDone} \cup {inflight[x] : x \in {y \in Writers : inflight[y] # -1}}]
               /\ pc' = [pc EXCEPT ![self] = "r_snap"]
               /\ UNCHANGED << tblLock, acWriter, acReaders, acWwait, table, 
                               ac, has, fresh, lastDone, inflight, inItem, 
                               itemWin, results, itemBad, ops, newc, i, k, v, 
                               snapc >>

r_snap(self) == /\ pc[self] = "r_snap"
                /\ IF Snapshot
                      THEN /\ acWriter = 0 /\ (~WriterPref \/ acWwait = {})
                           /\ snapc' = [snapc EXCEPT ![self] = IF has THEN ac ELSE 0]
                      ELSE /\ TRUE
                           /\ snapc' = snapc
                /\ pc' = [pc EXCEPT ![self] = "r_chunks"]
                /\ UNCHANGED << gil, tblLock, acWriter, acReaders, acWwait, 
                                table, ac, has, fresh, lastDone, inflight, 
                                inItem, itemWin, batchWin, results, itemBad, 
                                ops, newc, i, k, v >>

r_chunks(self) == /\ pc[self] = "r_chunks"
                  /\ IF i[self] < Items
                        THEN /\ pc' = [pc EXCEPT ![self] = "r_detach"]
                        ELSE /\ pc' = [pc EXCEPT ![self] = "r_exit"]
                  /\ UNCHANGED << gil, tblLock, acWriter, acReaders, acWwait, 
                                  table, ac, has, fresh, lastDone, inflight, 
                                  inItem, itemWin, batchWin, results, itemBad, 
                                  ops, newc, i, k, v, snapc >>

r_detach(self) == /\ pc[self] = "r_detach"
                  /\ gil' = 0
                  /\ k' = [k EXCEPT ![self] = 0]
                  /\ pc' = [pc EXCEPT ![self] = "r_items"]
                  /\ UNCHANGED << tblLock, acWriter, acReaders, acWwait, table, 
                                  ac, has, fresh, lastDone, inflight, inItem, 
                                  itemWin, batchWin, results, itemBad, ops, 
                                  newc, i, v, snapc >>

r_items(self) == /\ pc[self] = "r_items"
                 /\ IF i[self] < Items /\ k[self] < ChunkSize
                       THEN /\ pc' = [pc EXCEPT ![self] = "r_start"]
                       ELSE /\ pc' = [pc EXCEPT ![self] = "r_attach"]
                 /\ UNCHANGED << gil, tblLock, acWriter, acReaders, acWwait, 
                                 table, ac, has, fresh, lastDone, inflight, 
                                 inItem, itemWin, batchWin, results, itemBad, 
                                 ops, newc, i, k, v, snapc >>

r_start(self) == /\ pc[self] = "r_start"
                 /\ inItem' = [inItem EXCEPT ![self] = TRUE]
                 /\ itemWin' = [itemWin EXCEPT ![self] = {lastDone} \cup {inflight[x] : x \in {y \in Writers : inflight[y] # -1}}]
                 /\ IF Snapshot
                       THEN /\ v' = [v EXCEPT ![self] = snapc[self]]
                            /\ pc' = [pc EXCEPT ![self] = "r_end"]
                       ELSE /\ IF ~has
                                  THEN /\ v' = [v EXCEPT ![self] = 0]
                                       /\ pc' = [pc EXCEPT ![self] = "r_end"]
                                  ELSE /\ pc' = [pc EXCEPT ![self] = "r_rd"]
                                       /\ v' = v
                 /\ UNCHANGED << gil, tblLock, acWriter, acReaders, acWwait, 
                                 table, ac, has, fresh, lastDone, inflight, 
                                 batchWin, results, itemBad, ops, newc, i, k, 
                                 snapc >>

r_rd(self) == /\ pc[self] = "r_rd"
              /\ acWriter = 0 /\ (~WriterPref \/ acWwait = {})
              /\ acReaders' = [acReaders EXCEPT ![self] = acReaders[self] + 1]
              /\ pc' = [pc EXCEPT ![self] = "r_poison"]
              /\ UNCHANGED << gil, tblLock, acWriter, acWwait, table, ac, has, 
                              fresh, lastDone, inflight, inItem, itemWin, 
                              batchWin, results, itemBad, ops, newc, i, k, v, 
                              snapc >>

r_poison(self) == /\ pc[self] = "r_poison"
                  /\ IF Poisoned
                        THEN /\ gil = 0
                             /\ gil' = self
                        ELSE /\ TRUE
                             /\ gil' = gil
                  /\ pc' = [pc EXCEPT ![self] = "r_warned"]
                  /\ UNCHANGED << tblLock, acWriter, acReaders, acWwait, table, 
                                  ac, has, fresh, lastDone, inflight, inItem, 
                                  itemWin, batchWin, results, itemBad, ops, 
                                  newc, i, k, v, snapc >>

r_warned(self) == /\ pc[self] = "r_warned"
                  /\ IF Poisoned
                        THEN /\ gil' = 0
                        ELSE /\ TRUE
                             /\ gil' = gil
                  /\ pc' = [pc EXCEPT ![self] = "r_val"]
                  /\ UNCHANGED << tblLock, acWriter, acReaders, acWwait, table, 
                                  ac, has, fresh, lastDone, inflight, inItem, 
                                  itemWin, batchWin, results, itemBad, ops, 
                                  newc, i, k, v, snapc >>

r_val(self) == /\ pc[self] = "r_val"
               /\ v' = [v EXCEPT ![self] = ac]
               /\ acReaders' = [acReaders EXCEPT ![self] = acReaders[self] - 1]
               /\ pc' = [pc EXCEPT ![self] = "r_end"]
               /\ UNCHANGED << gil, tblLock, acWriter, acWwait, table, ac, has, 
                               fresh, lastDone, inflight, inItem, itemWin, 
                               batchWin, results, itemBad, ops, newc, i, k, 
                               snapc >>

r_end(self) == /\ pc[self] = "r_end"
               /\ IF ~Snapshot /\ v[self] \notin itemWin[self]
                     THEN /\ itemBad' = TRUE
                     ELSE /\ TRUE
                          /\ UNCHANGED itemBad
               /\ results' = [results EXCEPT ![self] = Append(results[self], v[self])]
               /\ inItem' = [inItem EXCEPT ![self] = FALSE]
               /\ i' = [i EXCEPT ![self] = i[self] + 1]
               /\ k' = [k EXCEPT ![self] = k[self] + 1]
               /\ pc' = [pc EXCEPT ![self] = "r_items"]
               /\ UNCHANGED << gil, tblLock, acWriter, acReaders, acWwait, 
                               table, ac, has, fresh, lastDone, inflight, 
                               itemWin, batchWin, ops, newc, v, snapc >>

r_attach(self) == /\ pc[self] = "r_attach"
                  /\ gil = 0
                  /\ gil' = self
                  /\ pc' = [pc EXCEPT ![self] = "r_chunks"]
                  /\ UNCHANGED << tblLock, acWriter, acReaders, acWwait, table, 
                                  ac, has, fresh, lastDone, inflight, inItem, 
                                  itemWin, batchWin, results, itemBad, ops, 
                                  newc, i, k, v, snapc >>

r_exit(self) == /\ pc[self] = "r_exit"
                /\ gil' = 0
                /\ pc' = [pc EXCEPT ![self] = "Done"]
                /\ UNCHANGED << tblLock, acWriter, acReaders, acWwait, table, 
                                ac, has, fresh, lastDone, inflight, inItem, 
                                itemWin, batchWin, results, itemBad, ops, newc, 
                                i, k, v, snapc >>

rd(self) == r_gil(self) \/ r_snap(self) \/ r_chunks(self) \/ r_detach(self)
               \/ r_items(self) \/ r_start(self) \/ r_rd(self)
               \/ r_poison(self) \/ r_warned(self) \/ r_val(self)
               \/ r_end(self) \/ r_attach(self) \/ r_exit(self)

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == (\E self \in Writers: wr(self))
           \/ (\E self \in Readers: rd(self))
           \/ Terminating

Spec == Init /\ [][Next]_vars

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 
=============================================================================
