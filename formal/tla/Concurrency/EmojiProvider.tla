--------------------------- MODULE EmojiProvider ---------------------------
(***************************************************************************)
(* GLOBAL_PROVIDER: RwLock<Option<Py<PyAny>>>   (src/py/emoji.rs:25)       *)
(*                                                                         *)
(* Also models TRANSLITERATE_FALLBACK (src/py/transliterate.rs:100): same  *)
(* shape (RwLock<Option<Py>>, write = `*slot = new` under the guard, read =*)
(* clone_ref under the guard, then call Python with the guard dropped).    *)
(*                                                                         *)
(*   set_emoji_provider(p)   emoji.rs:28-31   write(); *guard = p; drop    *)
(*   _demojize               emoji.rs:265-270 read(); clone_ref; guard     *)
(*                           dropped at the end of the else-block, then    *)
(*                           demojize_impl -> provider.lookup (emoji.rs:60)*)
(*                                                                         *)
(* The GIL is a mutex. Rust code in a #[pyfunction] runs attached (holds   *)
(* the GIL) and never detaches on these paths; the GIL changes hands only  *)
(* while Python code runs (provider.lookup, an object's __del__), where the*)
(* eval loop may switch threads. Blocking on an RwLock does NOT release the*)
(* GIL.                                                                    *)
(*                                                                         *)
(* `*guard = p` drops the previous Py<PyAny>. pyo3 0.29 `impl Drop for     *)
(* Py<T>` Py_DECREFs immediately when the thread is attached, so if that   *)
(* was the last reference the old object's __del__ runs right there, with *)
(* the write guard still held. P0 is that old provider; `refs` counts its  *)
(* strong references (the slot + in-flight clones in _demojize).          *)
(*                                                                         *)
(* std's RwLock on Linux is the futex implementation: not re-entrant, and  *)
(* writer-preferring (a new reader waits while a writer waits). WriterPref *)
(* = FALSE models a reader-preferring lock for comparison.                 *)
(***************************************************************************)
EXTENDS Naturals, Sequences, FiniteSets, TLC

CONSTANTS
    Threads,        \* e.g. {1, 2}
    Setters,        \* threads that call set_emoji_provider(None) once
    ReaderCalls,    \* demojize calls per non-setter thread
    ReaderText,     \* subset of {"plain","emoji"}: what readers demojize
    DelBehaviours,  \* what P0.__del__ may do, subset of {"noop", "release_gil",
                    \*   "reenter_set", "reenter_demojize"}; chosen per __del__
    LookupReenters, \* TRUE: P0.lookup calls demojize() and set_emoji_provider()
    WriterPref,     \* TRUE: std futex policy (waiting writer blocks new readers)
    Fixed,          \* TRUE: proposed fix, old handle dropped after the guard
    MaxDepth        \* bound on nested API calls from callbacks

(* --algorithm EmojiProvider {
variables
    gil = 0,                                  \* 0 = free, else owner
    writer = 0,                               \* RwLock writer (0 = none)
    readers = [t \in Threads |-> 0],          \* per-thread read-hold count
    wwait = {},                               \* threads waiting to write
    slot = "P0",                              \* provider: "P0" | "P1" | "None"
    refs = 1,                                 \* strong refs to P0 (slot has one)
    depth = [t \in Threads |-> 0],            \* nesting of API calls in callbacks
    guardAcrossPy = FALSE;                    \* Python entered holding a guard

define {
    \* Root cause of every deadlock below: Python code started while the same
    \* thread holds a Rust lock guard.
    NoGuardAcrossPython == ~guardAcrossPy
    TypeOK ==
        /\ gil \in Threads \cup {0}
        /\ writer \in Threads \cup {0}
        /\ slot \in {"P0", "P1", "None"}
        /\ refs \in 0..10
    \* Single-thread self-deadlock: waiting on a lock this thread holds.
    NoSelfWait ==
        \A t \in Threads :
            (pc[t] = "sp_lock" => writer # t /\ readers[t] = 0)
            /\ (pc[t] = "dj_read" => writer # t)
}

\* RwLock::write(): register as waiting, then wait for no writer and no readers.
procedure SetProvider(newp)
variable old = "None";
{
sp_wait:
    wwait := wwait \cup {self};
sp_lock:
    await writer = 0 /\ \A u \in Threads : readers[u] = 0;
    writer := self;
    wwait := wwait \ {self};
    old := slot;
    slot := newp;
sp_unlock_fixed:
    \* Fix: release the guard *before* dropping the old handle
    \* (`let old = std::mem::replace(&mut *guard, p); drop(guard); drop(old);`).
    if (Fixed) { writer := 0 };
sp_drop:
    if (old = "P0") {
        refs := refs - 1;
        if (refs = 0) { call Del() }
    };
sp_unlock:
    if (~Fixed) { writer := 0 };
    return;
}

\* _demojize: read(); clone_ref; guard dropped; lookups use the clone.
procedure Demojize(text)
variable snap = "None";
{
dj_read:
    await writer = 0 /\ (~WriterPref \/ wwait = {});
    readers[self] := readers[self] + 1;
dj_clone:
    snap := slot;
    if (slot = "P0") { refs := refs + 1 };
    readers[self] := readers[self] - 1;
dj_lookup:
    if (snap # "None" /\ text = "emoji") {
        call Lookup(snap);
    };
dj_drop:
    \* effective_provider (the clone) is dropped at function end, no guard held.
    if (snap = "P0") {
        refs := refs - 1;
        if (refs = 0) { call Del() }
    };
dj_ret:
    return;
}

\* provider.lookup(seq): Python code (a GIL switch point); may re-enter the API.
procedure Lookup(p)
variable reenter = FALSE;
{
lk_py:
    if (writer = self \/ readers[self] > 0) { guardAcrossPy := TRUE };
    gil := 0;                         \* eval loop may hand the GIL over
lk_gil:
    await gil = 0;
    gil := self;
    if (p = "P0" /\ LookupReenters /\ depth[self] < MaxDepth) {
        reenter := TRUE;
        depth[self] := depth[self] + 1;
        call Demojize("emoji");       \* nested read of GLOBAL_PROVIDER
    };
lk_set:
    if (reenter) { call SetProvider("P1") };   \* nested write
lk_done:
    if (reenter) { depth[self] := depth[self] - 1 };
    return;
}

\* P0.__del__: Python code, run by whichever thread drops the last reference.
procedure Del()
variables nested = FALSE, beh = "noop";
{
del_py:
    with (b \in DelBehaviours) {
        beh := b;
        \* "noop" = the object has no __del__: no Python code runs.
        if (b # "noop" /\ (writer = self \/ readers[self] > 0)) {
            guardAcrossPy := TRUE
        }
    };
del_act:
    if (beh = "release_gil") {
        gil := 0;                     \* e.g. closing a file / socket / DB handle
    del_gil:
        await gil = 0;
        gil := self;
    } else if (beh = "reenter_set" /\ depth[self] < MaxDepth) {
        nested := TRUE;
        depth[self] := depth[self] + 1;
        call SetProvider("None");
    } else if (beh = "reenter_demojize" /\ depth[self] < MaxDepth) {
        nested := TRUE;
        depth[self] := depth[self] + 1;
        call Demojize("emoji");
    };
del_done:
    if (nested) { depth[self] := depth[self] - 1 };
    return;
}

process (th \in Threads)
variables txt = "plain", todo = IF self \in Setters THEN 1 ELSE ReaderCalls;
{
t_loop:
    while (todo > 0) {
    t_acq:
        await gil = 0;
        gil := self;                  \* entering a #[pyfunction]: attached
        if (self \in Setters) {
            call SetProvider("None");
        } else {
            with (x \in ReaderText) { txt := x };
            call Demojize(txt);
        };
    t_rel:
        todo := todo - 1;
        gil := 0;                     \* back in the Python loop: switch point
    }
}
} *)
\* BEGIN TRANSLATION (chksum(pcal) = "923da9a2" /\ chksum(tla) = "5ade214b")
CONSTANT defaultInitValue
VARIABLES pc, gil, writer, readers, wwait, slot, refs, depth, guardAcrossPy, 
          stack

(* define statement *)
NoGuardAcrossPython == ~guardAcrossPy
TypeOK ==
    /\ gil \in Threads \cup {0}
    /\ writer \in Threads \cup {0}
    /\ slot \in {"P0", "P1", "None"}
    /\ refs \in 0..10

NoSelfWait ==
    \A t \in Threads :
        (pc[t] = "sp_lock" => writer # t /\ readers[t] = 0)
        /\ (pc[t] = "dj_read" => writer # t)

VARIABLES newp, old, text, snap, p, reenter, nested, beh, txt, todo

vars == << pc, gil, writer, readers, wwait, slot, refs, depth, guardAcrossPy, 
           stack, newp, old, text, snap, p, reenter, nested, beh, txt, todo
        >>

ProcSet == (Threads)

Init == (* Global variables *)
        /\ gil = 0
        /\ writer = 0
        /\ readers = [t \in Threads |-> 0]
        /\ wwait = {}
        /\ slot = "P0"
        /\ refs = 1
        /\ depth = [t \in Threads |-> 0]
        /\ guardAcrossPy = FALSE
        (* Procedure SetProvider *)
        /\ newp = [ self \in ProcSet |-> defaultInitValue]
        /\ old = [ self \in ProcSet |-> "None"]
        (* Procedure Demojize *)
        /\ text = [ self \in ProcSet |-> defaultInitValue]
        /\ snap = [ self \in ProcSet |-> "None"]
        (* Procedure Lookup *)
        /\ p = [ self \in ProcSet |-> defaultInitValue]
        /\ reenter = [ self \in ProcSet |-> FALSE]
        (* Procedure Del *)
        /\ nested = [ self \in ProcSet |-> FALSE]
        /\ beh = [ self \in ProcSet |-> "noop"]
        (* Process th *)
        /\ txt = [self \in Threads |-> "plain"]
        /\ todo = [self \in Threads |-> IF self \in Setters THEN 1 ELSE ReaderCalls]
        /\ stack = [self \in ProcSet |-> << >>]
        /\ pc = [self \in ProcSet |-> "t_loop"]

sp_wait(self) == /\ pc[self] = "sp_wait"
                 /\ wwait' = (wwait \cup {self})
                 /\ pc' = [pc EXCEPT ![self] = "sp_lock"]
                 /\ UNCHANGED << gil, writer, readers, slot, refs, depth, 
                                 guardAcrossPy, stack, newp, old, text, snap, 
                                 p, reenter, nested, beh, txt, todo >>

sp_lock(self) == /\ pc[self] = "sp_lock"
                 /\ writer = 0 /\ \A u \in Threads : readers[u] = 0
                 /\ writer' = self
                 /\ wwait' = wwait \ {self}
                 /\ old' = [old EXCEPT ![self] = slot]
                 /\ slot' = newp[self]
                 /\ pc' = [pc EXCEPT ![self] = "sp_unlock_fixed"]
                 /\ UNCHANGED << gil, readers, refs, depth, guardAcrossPy, 
                                 stack, newp, text, snap, p, reenter, nested, 
                                 beh, txt, todo >>

sp_unlock_fixed(self) == /\ pc[self] = "sp_unlock_fixed"
                         /\ IF Fixed
                               THEN /\ writer' = 0
                               ELSE /\ TRUE
                                    /\ UNCHANGED writer
                         /\ pc' = [pc EXCEPT ![self] = "sp_drop"]
                         /\ UNCHANGED << gil, readers, wwait, slot, refs, 
                                         depth, guardAcrossPy, stack, newp, 
                                         old, text, snap, p, reenter, nested, 
                                         beh, txt, todo >>

sp_drop(self) == /\ pc[self] = "sp_drop"
                 /\ IF old[self] = "P0"
                       THEN /\ refs' = refs - 1
                            /\ IF refs' = 0
                                  THEN /\ stack' = [stack EXCEPT ![self] = << [ procedure |->  "Del",
                                                                                pc        |->  "sp_unlock",
                                                                                nested    |->  nested[self],
                                                                                beh       |->  beh[self] ] >>
                                                                            \o stack[self]]
                                       /\ nested' = [nested EXCEPT ![self] = FALSE]
                                       /\ beh' = [beh EXCEPT ![self] = "noop"]
                                       /\ pc' = [pc EXCEPT ![self] = "del_py"]
                                  ELSE /\ pc' = [pc EXCEPT ![self] = "sp_unlock"]
                                       /\ UNCHANGED << stack, nested, beh >>
                       ELSE /\ pc' = [pc EXCEPT ![self] = "sp_unlock"]
                            /\ UNCHANGED << refs, stack, nested, beh >>
                 /\ UNCHANGED << gil, writer, readers, wwait, slot, depth, 
                                 guardAcrossPy, newp, old, text, snap, p, 
                                 reenter, txt, todo >>

sp_unlock(self) == /\ pc[self] = "sp_unlock"
                   /\ IF ~Fixed
                         THEN /\ writer' = 0
                         ELSE /\ TRUE
                              /\ UNCHANGED writer
                   /\ pc' = [pc EXCEPT ![self] = Head(stack[self]).pc]
                   /\ old' = [old EXCEPT ![self] = Head(stack[self]).old]
                   /\ newp' = [newp EXCEPT ![self] = Head(stack[self]).newp]
                   /\ stack' = [stack EXCEPT ![self] = Tail(stack[self])]
                   /\ UNCHANGED << gil, readers, wwait, slot, refs, depth, 
                                   guardAcrossPy, text, snap, p, reenter, 
                                   nested, beh, txt, todo >>

SetProvider(self) == sp_wait(self) \/ sp_lock(self)
                        \/ sp_unlock_fixed(self) \/ sp_drop(self)
                        \/ sp_unlock(self)

dj_read(self) == /\ pc[self] = "dj_read"
                 /\ writer = 0 /\ (~WriterPref \/ wwait = {})
                 /\ readers' = [readers EXCEPT ![self] = readers[self] + 1]
                 /\ pc' = [pc EXCEPT ![self] = "dj_clone"]
                 /\ UNCHANGED << gil, writer, wwait, slot, refs, depth, 
                                 guardAcrossPy, stack, newp, old, text, snap, 
                                 p, reenter, nested, beh, txt, todo >>

dj_clone(self) == /\ pc[self] = "dj_clone"
                  /\ snap' = [snap EXCEPT ![self] = slot]
                  /\ IF slot = "P0"
                        THEN /\ refs' = refs + 1
                        ELSE /\ TRUE
                             /\ refs' = refs
                  /\ readers' = [readers EXCEPT ![self] = readers[self] - 1]
                  /\ pc' = [pc EXCEPT ![self] = "dj_lookup"]
                  /\ UNCHANGED << gil, writer, wwait, slot, depth, 
                                  guardAcrossPy, stack, newp, old, text, p, 
                                  reenter, nested, beh, txt, todo >>

dj_lookup(self) == /\ pc[self] = "dj_lookup"
                   /\ IF snap[self] # "None" /\ text[self] = "emoji"
                         THEN /\ /\ p' = [p EXCEPT ![self] = snap[self]]
                                 /\ stack' = [stack EXCEPT ![self] = << [ procedure |->  "Lookup",
                                                                          pc        |->  "dj_drop",
                                                                          reenter   |->  reenter[self],
                                                                          p         |->  p[self] ] >>
                                                                      \o stack[self]]
                              /\ reenter' = [reenter EXCEPT ![self] = FALSE]
                              /\ pc' = [pc EXCEPT ![self] = "lk_py"]
                         ELSE /\ pc' = [pc EXCEPT ![self] = "dj_drop"]
                              /\ UNCHANGED << stack, p, reenter >>
                   /\ UNCHANGED << gil, writer, readers, wwait, slot, refs, 
                                   depth, guardAcrossPy, newp, old, text, snap, 
                                   nested, beh, txt, todo >>

dj_drop(self) == /\ pc[self] = "dj_drop"
                 /\ IF snap[self] = "P0"
                       THEN /\ refs' = refs - 1
                            /\ IF refs' = 0
                                  THEN /\ stack' = [stack EXCEPT ![self] = << [ procedure |->  "Del",
                                                                                pc        |->  "dj_ret",
                                                                                nested    |->  nested[self],
                                                                                beh       |->  beh[self] ] >>
                                                                            \o stack[self]]
                                       /\ nested' = [nested EXCEPT ![self] = FALSE]
                                       /\ beh' = [beh EXCEPT ![self] = "noop"]
                                       /\ pc' = [pc EXCEPT ![self] = "del_py"]
                                  ELSE /\ pc' = [pc EXCEPT ![self] = "dj_ret"]
                                       /\ UNCHANGED << stack, nested, beh >>
                       ELSE /\ pc' = [pc EXCEPT ![self] = "dj_ret"]
                            /\ UNCHANGED << refs, stack, nested, beh >>
                 /\ UNCHANGED << gil, writer, readers, wwait, slot, depth, 
                                 guardAcrossPy, newp, old, text, snap, p, 
                                 reenter, txt, todo >>

dj_ret(self) == /\ pc[self] = "dj_ret"
                /\ pc' = [pc EXCEPT ![self] = Head(stack[self]).pc]
                /\ snap' = [snap EXCEPT ![self] = Head(stack[self]).snap]
                /\ text' = [text EXCEPT ![self] = Head(stack[self]).text]
                /\ stack' = [stack EXCEPT ![self] = Tail(stack[self])]
                /\ UNCHANGED << gil, writer, readers, wwait, slot, refs, depth, 
                                guardAcrossPy, newp, old, p, reenter, nested, 
                                beh, txt, todo >>

Demojize(self) == dj_read(self) \/ dj_clone(self) \/ dj_lookup(self)
                     \/ dj_drop(self) \/ dj_ret(self)

lk_py(self) == /\ pc[self] = "lk_py"
               /\ IF writer = self \/ readers[self] > 0
                     THEN /\ guardAcrossPy' = TRUE
                     ELSE /\ TRUE
                          /\ UNCHANGED guardAcrossPy
               /\ gil' = 0
               /\ pc' = [pc EXCEPT ![self] = "lk_gil"]
               /\ UNCHANGED << writer, readers, wwait, slot, refs, depth, 
                               stack, newp, old, text, snap, p, reenter, 
                               nested, beh, txt, todo >>

lk_gil(self) == /\ pc[self] = "lk_gil"
                /\ gil = 0
                /\ gil' = self
                /\ IF p[self] = "P0" /\ LookupReenters /\ depth[self] < MaxDepth
                      THEN /\ reenter' = [reenter EXCEPT ![self] = TRUE]
                           /\ depth' = [depth EXCEPT ![self] = depth[self] + 1]
                           /\ /\ stack' = [stack EXCEPT ![self] = << [ procedure |->  "Demojize",
                                                                       pc        |->  "lk_set",
                                                                       snap      |->  snap[self],
                                                                       text      |->  text[self] ] >>
                                                                   \o stack[self]]
                              /\ text' = [text EXCEPT ![self] = "emoji"]
                           /\ snap' = [snap EXCEPT ![self] = "None"]
                           /\ pc' = [pc EXCEPT ![self] = "dj_read"]
                      ELSE /\ pc' = [pc EXCEPT ![self] = "lk_set"]
                           /\ UNCHANGED << depth, stack, text, snap, reenter >>
                /\ UNCHANGED << writer, readers, wwait, slot, refs, 
                                guardAcrossPy, newp, old, p, nested, beh, txt, 
                                todo >>

lk_set(self) == /\ pc[self] = "lk_set"
                /\ IF reenter[self]
                      THEN /\ /\ newp' = [newp EXCEPT ![self] = "P1"]
                              /\ stack' = [stack EXCEPT ![self] = << [ procedure |->  "SetProvider",
                                                                       pc        |->  "lk_done",
                                                                       old       |->  old[self],
                                                                       newp      |->  newp[self] ] >>
                                                                   \o stack[self]]
                           /\ old' = [old EXCEPT ![self] = "None"]
                           /\ pc' = [pc EXCEPT ![self] = "sp_wait"]
                      ELSE /\ pc' = [pc EXCEPT ![self] = "lk_done"]
                           /\ UNCHANGED << stack, newp, old >>
                /\ UNCHANGED << gil, writer, readers, wwait, slot, refs, depth, 
                                guardAcrossPy, text, snap, p, reenter, nested, 
                                beh, txt, todo >>

lk_done(self) == /\ pc[self] = "lk_done"
                 /\ IF reenter[self]
                       THEN /\ depth' = [depth EXCEPT ![self] = depth[self] - 1]
                       ELSE /\ TRUE
                            /\ depth' = depth
                 /\ pc' = [pc EXCEPT ![self] = Head(stack[self]).pc]
                 /\ reenter' = [reenter EXCEPT ![self] = Head(stack[self]).reenter]
                 /\ p' = [p EXCEPT ![self] = Head(stack[self]).p]
                 /\ stack' = [stack EXCEPT ![self] = Tail(stack[self])]
                 /\ UNCHANGED << gil, writer, readers, wwait, slot, refs, 
                                 guardAcrossPy, newp, old, text, snap, nested, 
                                 beh, txt, todo >>

Lookup(self) == lk_py(self) \/ lk_gil(self) \/ lk_set(self)
                   \/ lk_done(self)

del_py(self) == /\ pc[self] = "del_py"
                /\ \E b \in DelBehaviours:
                     /\ beh' = [beh EXCEPT ![self] = b]
                     /\ IF b # "noop" /\ (writer = self \/ readers[self] > 0)
                           THEN /\ guardAcrossPy' = TRUE
                           ELSE /\ TRUE
                                /\ UNCHANGED guardAcrossPy
                /\ pc' = [pc EXCEPT ![self] = "del_act"]
                /\ UNCHANGED << gil, writer, readers, wwait, slot, refs, depth, 
                                stack, newp, old, text, snap, p, reenter, 
                                nested, txt, todo >>

del_act(self) == /\ pc[self] = "del_act"
                 /\ IF beh[self] = "release_gil"
                       THEN /\ gil' = 0
                            /\ pc' = [pc EXCEPT ![self] = "del_gil"]
                            /\ UNCHANGED << depth, stack, newp, old, text, 
                                            snap, nested >>
                       ELSE /\ IF beh[self] = "reenter_set" /\ depth[self] < MaxDepth
                                  THEN /\ nested' = [nested EXCEPT ![self] = TRUE]
                                       /\ depth' = [depth EXCEPT ![self] = depth[self] + 1]
                                       /\ /\ newp' = [newp EXCEPT ![self] = "None"]
                                          /\ stack' = [stack EXCEPT ![self] = << [ procedure |->  "SetProvider",
                                                                                   pc        |->  "del_done",
                                                                                   old       |->  old[self],
                                                                                   newp      |->  newp[self] ] >>
                                                                               \o stack[self]]
                                       /\ old' = [old EXCEPT ![self] = "None"]
                                       /\ pc' = [pc EXCEPT ![self] = "sp_wait"]
                                       /\ UNCHANGED << text, snap >>
                                  ELSE /\ IF beh[self] = "reenter_demojize" /\ depth[self] < MaxDepth
                                             THEN /\ nested' = [nested EXCEPT ![self] = TRUE]
                                                  /\ depth' = [depth EXCEPT ![self] = depth[self] + 1]
                                                  /\ /\ stack' = [stack EXCEPT ![self] = << [ procedure |->  "Demojize",
                                                                                              pc        |->  "del_done",
                                                                                              snap      |->  snap[self],
                                                                                              text      |->  text[self] ] >>
                                                                                          \o stack[self]]
                                                     /\ text' = [text EXCEPT ![self] = "emoji"]
                                                  /\ snap' = [snap EXCEPT ![self] = "None"]
                                                  /\ pc' = [pc EXCEPT ![self] = "dj_read"]
                                             ELSE /\ pc' = [pc EXCEPT ![self] = "del_done"]
                                                  /\ UNCHANGED << depth, stack, 
                                                                  text, snap, 
                                                                  nested >>
                                       /\ UNCHANGED << newp, old >>
                            /\ gil' = gil
                 /\ UNCHANGED << writer, readers, wwait, slot, refs, 
                                 guardAcrossPy, p, reenter, beh, txt, todo >>

del_gil(self) == /\ pc[self] = "del_gil"
                 /\ gil = 0
                 /\ gil' = self
                 /\ pc' = [pc EXCEPT ![self] = "del_done"]
                 /\ UNCHANGED << writer, readers, wwait, slot, refs, depth, 
                                 guardAcrossPy, stack, newp, old, text, snap, 
                                 p, reenter, nested, beh, txt, todo >>

del_done(self) == /\ pc[self] = "del_done"
                  /\ IF nested[self]
                        THEN /\ depth' = [depth EXCEPT ![self] = depth[self] - 1]
                        ELSE /\ TRUE
                             /\ depth' = depth
                  /\ pc' = [pc EXCEPT ![self] = Head(stack[self]).pc]
                  /\ nested' = [nested EXCEPT ![self] = Head(stack[self]).nested]
                  /\ beh' = [beh EXCEPT ![self] = Head(stack[self]).beh]
                  /\ stack' = [stack EXCEPT ![self] = Tail(stack[self])]
                  /\ UNCHANGED << gil, writer, readers, wwait, slot, refs, 
                                  guardAcrossPy, newp, old, text, snap, p, 
                                  reenter, txt, todo >>

Del(self) == del_py(self) \/ del_act(self) \/ del_gil(self)
                \/ del_done(self)

t_loop(self) == /\ pc[self] = "t_loop"
                /\ IF todo[self] > 0
                      THEN /\ pc' = [pc EXCEPT ![self] = "t_acq"]
                      ELSE /\ pc' = [pc EXCEPT ![self] = "Done"]
                /\ UNCHANGED << gil, writer, readers, wwait, slot, refs, depth, 
                                guardAcrossPy, stack, newp, old, text, snap, p, 
                                reenter, nested, beh, txt, todo >>

t_acq(self) == /\ pc[self] = "t_acq"
               /\ gil = 0
               /\ gil' = self
               /\ IF self \in Setters
                     THEN /\ /\ newp' = [newp EXCEPT ![self] = "None"]
                             /\ stack' = [stack EXCEPT ![self] = << [ procedure |->  "SetProvider",
                                                                      pc        |->  "t_rel",
                                                                      old       |->  old[self],
                                                                      newp      |->  newp[self] ] >>
                                                                  \o stack[self]]
                          /\ old' = [old EXCEPT ![self] = "None"]
                          /\ pc' = [pc EXCEPT ![self] = "sp_wait"]
                          /\ UNCHANGED << text, snap, txt >>
                     ELSE /\ \E x \in ReaderText:
                               txt' = [txt EXCEPT ![self] = x]
                          /\ /\ stack' = [stack EXCEPT ![self] = << [ procedure |->  "Demojize",
                                                                      pc        |->  "t_rel",
                                                                      snap      |->  snap[self],
                                                                      text      |->  text[self] ] >>
                                                                  \o stack[self]]
                             /\ text' = [text EXCEPT ![self] = txt'[self]]
                          /\ snap' = [snap EXCEPT ![self] = "None"]
                          /\ pc' = [pc EXCEPT ![self] = "dj_read"]
                          /\ UNCHANGED << newp, old >>
               /\ UNCHANGED << writer, readers, wwait, slot, refs, depth, 
                               guardAcrossPy, p, reenter, nested, beh, todo >>

t_rel(self) == /\ pc[self] = "t_rel"
               /\ todo' = [todo EXCEPT ![self] = todo[self] - 1]
               /\ gil' = 0
               /\ pc' = [pc EXCEPT ![self] = "t_loop"]
               /\ UNCHANGED << writer, readers, wwait, slot, refs, depth, 
                               guardAcrossPy, stack, newp, old, text, snap, p, 
                               reenter, nested, beh, txt >>

th(self) == t_loop(self) \/ t_acq(self) \/ t_rel(self)

(* Allow infinite stuttering to prevent deadlock on termination. *)
Terminating == /\ \A self \in ProcSet: pc[self] = "Done"
               /\ UNCHANGED vars

Next == (\E self \in ProcSet:  \/ SetProvider(self) \/ Demojize(self)
                               \/ Lookup(self) \/ Del(self))
           \/ (\E self \in Threads: th(self))
           \/ Terminating

Spec == Init /\ [][Next]_vars

Termination == <>(\A self \in ProcSet: pc[self] = "Done")

\* END TRANSLATION 
=============================================================================
