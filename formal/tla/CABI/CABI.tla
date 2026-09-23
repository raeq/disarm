-------------------------------- MODULE CABI --------------------------------
(***************************************************************************)
(* The ownership and input protocol of the C ABI (bindings/cabi).          *)
(*                                                                         *)
(* One C client calls the library up to MaxCalls times and then frees      *)
(* everything it owns. The library side is the code as written: every      *)
(* entry point takes `char const *` arguments that safer-ffi turns into    *)
(* `char_p::Ref` and reads with `to_str()` (no NULL check in a release     *)
(* build, no UTF-8 check in any build), and returns either a `char *`      *)
(* (`char_p::Box`) or a `DisarmResult` whose two halves are nullable        *)
(* `char_p::Box`es. An EMPTY output is not allocated: safer-ffi returns the *)
(* address of one read-only static byte (EMPTY_SENTINEL), and its drop     *)
(* recognises that address and does nothing. A non-empty output is a heap  *)
(* `Box<[u8]>` whose drop recomputes the length with strlen.              *)
(*                                                                         *)
(* The client is the one `disarm.h` describes: it may pass any `char const *` *)
(* in `Inputs`, it owns every returned `char *` (a mutable pointer, so     *)
(* `ClientWrites` lets it store into the buffer, including a NUL that      *)
(* shortens it), and it frees each owned pointer once with                 *)
(* disarm_string_free, NULL included.                                     *)
(*                                                                         *)
(* `Fixed = TRUE` models the proposed fix: NULL and invalid UTF-8 are      *)
(* rejected at the boundary (an error in a DisarmResult, NULL from a plain *)
(* `char *` function). The store hazards are closed by documenting that a  *)
(* returned string is read-only, which is `ClientWrites = FALSE`.          *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets

CONSTANTS MaxCalls,      \* calls the client makes before cleaning up
          Inputs,        \* subset of {"valid", "invalid_utf8", "null"}
          ClientWrites,  \* does the client store into buffers it owns?
          Fixed          \* model the proposed fix instead of the code

NULL == 0
STATIC == MaxCalls + 1          \* the address of safer-ffi's EMPTY_SENTINEL
Heap == 1..MaxCalls             \* one fresh heap address per call, never reused
Addr == {NULL, STATIC} \cup Heap
OutLens == {0, 2}               \* an empty output, or a two-byte one
NoResult == [value |-> STATIC + 1, error |-> STATIC + 1]   \* no DisarmResult yet

VARIABLES heap,     \* Heap -> {"unalloc", "live", "freed"}
          len,      \* Heap -> bytes allocated (string + NUL), fixed at allocation
          strl,     \* Heap -> current strlen, which a client store may shorten
          owned,    \* set of handles [id, addr] the client holds
          calls,    \* calls made so far
          phase,    \* "run" | "cleanup" | "done"
          ub,       \* set of undefined-behaviour events that have happened
          last      \* the last DisarmResult returned: [value, error], or NoResult

vars == <<heap, len, strl, owned, calls, phase, ub, last>>

Init == /\ heap = [a \in Heap |-> "unalloc"]
        /\ len = [a \in Heap |-> 0]
        /\ strl = [a \in Heap |-> 0]
        /\ owned = {}
        /\ calls = 0
        /\ phase = "run"
        /\ ub = {}
        /\ last = NoResult

\* The address the library hands back for an output of `n` bytes, allocated by call k.
OutAddr(n, k) == IF n = 0 THEN STATIC ELSE k

\* Heap bookkeeping for an allocation at address a of an n-byte string.
Alloc(a, n) == /\ heap' = IF a \in Heap THEN [heap EXCEPT ![a] = "live"] ELSE heap
               /\ len' = IF a \in Heap THEN [len EXCEPT ![a] = n + 1] ELSE len
               /\ strl' = IF a \in Heap THEN [strl EXCEPT ![a] = n] ELSE strl

Handle(a) == [id |-> calls + 1, addr |-> a]

\* A call whose input breaks the precondition the code relies on.
\*   null:          `char_p::Ref` is a NonNull; safer-ffi's from_raw_unchecked reaches
\*                  `unreachable_unchecked` in a release build (a panic, and so an
\*                  abort across `extern "C"`, in a debug one).
\*   invalid_utf8:  `char_p::Ref::to_str` is `str::from_utf8_unchecked`, so safe code
\*                  holds a `&str` that is not UTF-8 (library UB).
BadCall(in) ==
    /\ phase = "run" /\ calls < MaxCalls
    /\ in \in Inputs \ {"valid"}
    /\ \/ /\ ~Fixed
          /\ ub' = ub \cup {IF in = "null" THEN "null_arg" ELSE "invalid_utf8"}
          /\ UNCHANGED <<heap, len, strl, owned, last>>
       \/ /\ Fixed   \* rejected: an error message in a DisarmResult ...
          /\ Alloc(calls + 1, 2)
          /\ owned' = owned \cup {[id |-> (calls + 1) + MaxCalls, addr |-> NULL], Handle(calls + 1)}
          /\ last' = [value |-> NULL, error |-> calls + 1]
          /\ UNCHANGED ub
       \/ /\ Fixed   \* ... or NULL from a plain `char *` function
          /\ owned' = owned \cup {Handle(NULL)}
          /\ UNCHANGED <<heap, len, strl, ub, last>>
    /\ calls' = calls + 1
    /\ UNCHANGED phase

\* A plain `char *` function (disarm_transliterate, disarm_strip_bidi, ...).
PlainCall(n) ==
    /\ phase = "run" /\ calls < MaxCalls /\ "valid" \in Inputs
    /\ Alloc(OutAddr(n, calls + 1), n)
    /\ owned' = owned \cup {Handle(OutAddr(n, calls + 1))}
    /\ calls' = calls + 1
    /\ UNCHANGED <<phase, ub, last>>

\* A DisarmResult function: success puts the output in `value`, failure puts a
\* (never empty) message in `error`; the other half is NULL.
ResultCall(n, success) ==
    /\ phase = "run" /\ calls < MaxCalls /\ "valid" \in Inputs
    /\ LET a == IF success THEN OutAddr(n, calls + 1) ELSE calls + 1
       IN /\ Alloc(a, IF success THEN n ELSE 2)
          /\ last' = IF success THEN [value |-> a, error |-> NULL]
                                ELSE [value |-> NULL, error |-> a]
          \* the client keeps both halves and frees both (the header says NULL is fine)
          /\ owned' = owned \cup {[id |-> calls + 1, addr |-> a],
                                  [id |-> (calls + 1) + MaxCalls, addr |-> NULL]}
    /\ calls' = calls + 1
    /\ UNCHANGED <<phase, ub>>

\* The client stores into a buffer it owns. A store of a NUL at position i < strlen
\* shortens the string; storing into the sentinel faults (it is read-only memory).
Write(h) ==
    /\ ClientWrites /\ phase = "run" /\ h \in owned /\ h.addr # NULL
    /\ IF h.addr = STATIC
         THEN /\ ub' = ub \cup {"write_to_static"}
              /\ UNCHANGED strl
         ELSE /\ heap[h.addr] = "live" /\ strl[h.addr] > 0
              /\ \E i \in 0..(strl[h.addr] - 1) : strl' = [strl EXCEPT ![h.addr] = i]
              /\ UNCHANGED ub
    /\ UNCHANGED <<heap, len, owned, calls, phase, last>>

\* disarm_string_free(h). The drop frees Box<[u8]> of strlen + 1 bytes: a size that
\* differs from the allocation's is a Layout mismatch (UB under GlobalAlloc).
Free(h) ==
    /\ phase \in {"run", "cleanup"} /\ h \in owned
    /\ owned' = owned \ {h}
    /\ CASE h.addr \in {NULL, STATIC} ->
                UNCHANGED <<heap, ub>>
         [] heap[h.addr] = "live" ->
                /\ heap' = [heap EXCEPT ![h.addr] = "freed"]
                /\ ub' = IF strl[h.addr] + 1 # len[h.addr] THEN ub \cup {"layout_mismatch"} ELSE ub
         [] OTHER ->
                /\ ub' = ub \cup {"double_free"}
                /\ UNCHANGED heap
    /\ UNCHANGED <<len, strl, calls, phase, last>>

StartCleanup == /\ phase = "run" /\ calls = MaxCalls
                /\ phase' = "cleanup"
                /\ UNCHANGED <<heap, len, strl, owned, calls, ub, last>>

Finish == /\ phase = "cleanup" /\ owned = {}
          /\ phase' = "done"
          /\ UNCHANGED <<heap, len, strl, owned, calls, ub, last>>

Done == phase = "done" /\ UNCHANGED vars

Next == \/ \E in \in Inputs : BadCall(in)
        \/ \E n \in OutLens : PlainCall(n)
        \/ \E n \in OutLens, s \in BOOLEAN : ResultCall(n, s)
        \/ \E h \in owned : Write(h) \/ Free(h)
        \/ StartCleanup \/ Finish \/ Done

Spec == Init /\ [][Next]_vars

-----------------------------------------------------------------------------
TypeOK == /\ heap \in [Heap -> {"unalloc", "live", "freed"}]
          /\ owned \subseteq [id : 1..(2 * MaxCalls), addr : Addr]
          /\ ub \subseteq {"null_arg", "invalid_utf8", "write_to_static", "layout_mismatch", "double_free"}

NoNullArgUB     == "null_arg" \notin ub
NoInvalidUtf8UB == "invalid_utf8" \notin ub
NoWriteToStatic == "write_to_static" \notin ub
NoLayoutMismatch == "layout_mismatch" \notin ub
NoDoubleFree    == "double_free" \notin ub

\* `DisarmResult`: "exactly one of value / error is non-NULL".
ResultExclusive == last = NoResult \/((last.value = NULL) # (last.error = NULL))

\* Every allocation is freed once the client has released everything it owns.
NoLeak == phase = "done" => \A a \in Heap : heap[a] # "live"

\* Two handles the client owns never name the same memory (a store through one
\* would change the other, and freeing one would free the other).
NoAlias == \A h1, h2 \in owned :
               (h1.id # h2.id /\ h1.addr # NULL /\ h2.addr # NULL) => h1.addr # h2.addr
=============================================================================
