------------------------------- MODULE WatchPR -------------------------------
(***************************************************************************)
(* The merge protocol of scripts/watch_pr.py, and the GitHub pull request  *)
(* it polls, changing underneath it.                                       *)
(*                                                                         *)
(* Two processes interleave freely:                                        *)
(*                                                                         *)
(*   Watcher -- one poll is: two non-atomic reads (`gh pr view`, then the  *)
(*              review-thread GraphQL query), `decide()`, then either      *)
(*              sleep and poll again, stop, or `gh pr merge --squash`.     *)
(*              Every read and the merge is a separate atomic step, so     *)
(*              the environment can act between any two of them: the       *)
(*              snapshot `decide()` sees is stale by the time it is acted  *)
(*              on.                                                        *)
(*                                                                         *)
(*   Env     -- GitHub plus the humans and bots around the PR: pushes      *)
(*              (new head, checks reset, the old run cancelled by          *)
(*              `concurrency: cancel-in-progress`), CI completing and      *)
(*              re-running, duplicate runs on one head, review threads     *)
(*              opened / resolved, review requests, reviews submitted      *)
(*              (optionally with an inline thread) or dismissed, the base  *)
(*              moving, the PR being closed or merged by someone else,     *)
(*              and the eventual consistency of the PR view (`viewHead`    *)
(*              lags `head`).                                              *)
(*                                                                         *)
(* GitHub's own merge rules are modelled server-side in `ServerAccepts`:   *)
(* required checks green on the *current* head, conversation resolution   *)
(* (this repo) and up-to-date branches, each switchable per config.        *)
(*                                                                         *)
(* A single required check "X" stands for the rollup (this repo gates on   *)
(* the single roll-up context "All checks passed", #583). `Fix*` constants *)
(* switch on the proposed fixes, so every finding is checked both ways.    *)
(* Line numbers in comments refer to scripts/watch_pr.py at bec93cf.       *)
(***************************************************************************)
EXTENDS Naturals, TLC

CONSTANTS
    MaxHead,            \* commits the PR can have (pushes = MaxHead - 1)
    MaxUnres,           \* unresolved review threads at most
    MaxPolls,           \* --max-polls; 0 = unbounded (for liveness)
    MaxReadFails,       \* budget of failed `gh` reads (keeps liveness fair)
    \* ---- repository / branch protection
    RequiredChecks,     \* X is a required status check
    ProtectThreads,     \* "require conversation resolution" (this repo: TRUE)
    Strict,             \* "require branches to be up to date" -> BEHIND
    SquashRejected,     \* the server rejects every merge (method off, queue, ...)
    \* ---- watcher flags
    AwaitReview,        \* --await-review (#987/#1000)
    AllowMerge,         \* not --no-merge
    ThreadsFirst,       \* hypothetical: read threads BEFORE the PR view
    \* ---- which environment behaviours are enabled
    EnvPush, EnvLag, EnvGhost, EnvThreads, EnvReviews, EnvBase, EnvClose,
    EnvOverflow,
    EnvBetweenReads,    \* env may act between the two reads of one poll
    EnvInWindow,        \* env may act after the last read, before the merge
    ThreadReadCanFail,  \* the GraphQL thread query can fail / error
    \* ---- proposed fixes
    FixMatchHead,       \* `gh pr merge --match-head-commit <headRefOid>`
    FixThreadRead,      \* a failed thread read is a failed poll, not "no threads"
    FixDedup,           \* rollup de-duplicated to the latest run per check name
    FixMergeReject,     \* a rejected merge is detected and reported
    FixChanges,         \* --await-review: a standing CHANGES_REQUESTED stops the watcher
    FixReviewHead       \* --await-review: the review must be of the current head

STUCK_POLLS   == 3      \* watch_pr.py:87
FAILURE_POLLS == 2      \* watch_pr.py:81

Heads        == 1..MaxHead
CkStates     == {"none", "pending", "success", "failure", "cancelled"}
Red          == {"failure", "cancelled"}           \* BAD_CONCLUSIONS, :91
Kinds        == {"none", "comment", "changes"}      \* latest standing non-author review
MERGEABLE    == {"CLEAN", "UNSTABLE", "HAS_HOOKS"}  \* :66
NEEDS_REBASE == {"DIRTY", "BEHIND"}                 \* :69
WAITS        == {"WAIT_RED", "WAIT_REVIEW", "WAIT_STUCK", "WAIT_PENDING"}

VARIABLES
    \* ---- GitHub (environment)
    prState,    \* "OPEN" | "MERGED" | "CLOSED"
    head,       \* the PR's actual head commit
    viewHead,   \* the head `gh pr view` currently reports (lags after a push)
    ck,         \* ck[h]: latest run of X on commit h ("none" = not created yet)
    ghost,      \* ghost[h]: an older, superseded run of X on h, CANCELLED, still in the rollup
    unres,      \* unresolved review threads
    overflow,   \* more threads than one GraphQL page (THREAD_PAGE_SIZE)
    requested,  \* a review request is pending
    review,     \* latest standing review by someone other than the author
    reviewHead, \* the head that review was submitted on (0 = none)
    behind,     \* base moved; branch not up to date
    \* ---- the watcher
    pc,         \* "r1" | "r2" | "decide" | "merge" | "done"
    poll,       \* fetches started (watch():442)
    stuckN,     \* stuck_polls   (watch():439, :462)
    failN,      \* failure_polls (watch():440, :464)
    lastBroken, \* last_broken, encoded as the COUNT of broken "X" entries (all share one name)
    snap,       \* the Snapshot being assembled / decided on
    mrej,       \* consecutive rejected merges (only used by FixMergeReject)
    fails,      \* failed reads so far (bounded by MaxReadFails)
    \* ---- history, for the invariants only
    mergedBy,   \* "nobody" | "watcher" | "other"
    issue,      \* GitHub's state at the moment the watcher last sent `gh pr merge`
    mfacts,     \* the same, for the merge GitHub accepted
    dec,        \* the watcher's last decision and what it was based on
    stop        \* why the watcher stopped, and the state at the read that caused it

envVars  == <<prState, head, viewHead, ck, ghost, unres, overflow, requested,
              review, reviewHead, behind>>
watVars  == <<pc, poll, stuckN, failN, lastBroken, snap, mrej, fails>>
histVars == <<mergedBy, issue, mfacts, dec, stop>>
vars     == <<envVars, watVars, histVars>>

-----------------------------------------------------------------------------
(* mergeStateStatus, as `gh pr view` reports it for commit h.              *)
MS(h) ==
    IF Strict /\ behind THEN "BEHIND"
    ELSE IF RequiredChecks /\ ck[h] # "success" THEN "BLOCKED"
    ELSE IF ProtectThreads /\ unres > 0 THEN "BLOCKED"
    ELSE IF ck[h] # "success" THEN "UNSTABLE"   \* a non-required check pending / red
    ELSE "CLEAN"

(* GitHub's decision on `gh pr merge`, against the state AT MERGE TIME.   *)
ServerAccepts ==
    /\ prState = "OPEN"
    /\ ~(Strict /\ behind)
    /\ RequiredChecks => ck[head] = "success"
    /\ ProtectThreads => unres = 0
    /\ FixMatchHead   => head = snap.head       \* --match-head-commit
    /\ ~SquashRejected

NoSnap == [state |-> "OPEN", ms |-> "UNKNOWN", ck |-> "none", ghost |-> FALSE,
           requested |-> FALSE, review |-> "none", reviewHead |-> 0, head |-> 0,
           curCk |-> "none", unres |-> 0, trunc |-> FALSE, rd |-> "none"]
NoFacts == [valid |-> FALSE, head |-> 0, snapHead |-> 0, ck |-> "none", unres |-> 0,
            requested |-> FALSE, review |-> "none", reviewHead |-> 0, rd |-> "none"]
NoDec  == [valid |-> FALSE, a |-> "none", rd |-> "none"]
NoStop == [a |-> "none", curCk |-> "none", snapHead |-> 0, head |-> 0]

-----------------------------------------------------------------------------
Init ==
    /\ prState = "OPEN"
    /\ head = 1 /\ viewHead = 1
    /\ ck \in [Heads -> {"none"}] \cup {[h \in Heads |-> IF h = 1 THEN "pending" ELSE "none"]}
    /\ ghost = [h \in Heads |-> FALSE]
    /\ unres = 0 /\ overflow = FALSE
    /\ requested \in (IF EnvReviews THEN BOOLEAN ELSE {FALSE})
    /\ review = "none" /\ reviewHead = 0
    /\ behind = FALSE
    /\ pc = "r1" /\ poll = 0 /\ stuckN = 0 /\ failN = 0 /\ lastBroken = 0
    /\ snap = NoSnap /\ mrej = 0 /\ fails = 0
    /\ mergedBy = "nobody" /\ issue = NoFacts /\ mfacts = NoFacts
    /\ dec = NoDec /\ stop = NoStop

-----------------------------------------------------------------------------
(***************************** The watcher *******************************)

\* A read that returned None: watch():444-452 resets all three streaks.
FailedPoll ==
    /\ fails' = fails + 1
    /\ stuckN' = 0 /\ failN' = 0 /\ lastBroken' = 0
    /\ pc' = "r1"
    /\ snap' = NoSnap /\ UNCHANGED mrej

\* `gh pr view --json state,mergeStateStatus,statusCheckRollup,author,
\* reviewRequests,reviews` (fetch():329-356). ONE GraphQL query, so these
\* fields are mutually consistent -- but they describe `viewHead`.
ViewFields(s) ==
    [s EXCEPT !.state = prState, !.ms = MS(viewHead), !.ck = ck[viewHead],
              !.ghost = ghost[viewHead], !.requested = requested,
              !.review = review, !.reviewHead = reviewHead, !.head = viewHead,
              !.curCk = ck[head]]

\* The reviewThreads query (fetch():362-393), three outcomes:
\*  ok    -- the full listing
\*  trunc -- hasPreviousPage: a page, possibly missing the unresolved ones (:381)
\*  fail  -- empty stdout / non-JSON / {"data":null,"errors":..}: the code
\*           falls through to threads=() and truncated=False (:369-383)
ThreadOutcomes ==
    (IF overflow THEN {"trunc"} ELSE {"ok"})
    \cup (IF ThreadReadCanFail /\ fails < MaxReadFails THEN {"fail"} ELSE {})

ThreadFields(s, o, vis) ==
    [s EXCEPT !.unres = vis, !.trunc = (o = "trunc"), !.rd = o]

ReadView(next) ==
    \/ /\ fails < MaxReadFails            \* :340-345 -> return None
       /\ FailedPoll
    \/ /\ snap' = ViewFields(snap)
       /\ pc' = next
       /\ UNCHANGED <<stuckN, failN, lastBroken, mrej, fails>>

ReadThreads(next) ==
    \E o \in ThreadOutcomes :
        IF o = "fail" /\ FixThreadRead
        THEN FailedPoll
        ELSE /\ \E vis \in (CASE o = "ok"    -> {unres}
                              [] o = "trunc" -> 0..unres
                              [] o = "fail"  -> {0}) :
                    snap' = ThreadFields(snap, o, vis)
             /\ fails' = IF o = "fail" THEN fails + 1 ELSE fails
             /\ pc' = next
             /\ UNCHANGED <<stuckN, failN, lastBroken, mrej>>

FirstRead(next)  == IF ThreadsFirst THEN ReadThreads(next) ELSE ReadView(next)
SecondRead(next) == IF ThreadsFirst THEN ReadView(next)    ELSE ReadThreads(next)

\* One loop iteration starts: `for poll in range(1, max_polls + 1)` (:442).
R1 ==
    /\ pc = "r1"
    /\ IF MaxPolls > 0 /\ poll = MaxPolls
       THEN /\ pc' = "done"                                       \* :488-489
            /\ stop' = [a |-> "GAVEUP", curCk |-> ck[head], snapHead |-> snap.head, head |-> head]
            /\ UNCHANGED <<poll, stuckN, failN, lastBroken, snap, mrej, fails,
                           mergedBy, issue, mfacts, dec>>
       ELSE /\ poll' = IF MaxPolls > 0 THEN poll + 1 ELSE poll
            /\ FirstRead("r2")
            \* the last poll's history has been checked; drop it (state space)
            /\ issue' = NoFacts /\ dec' = NoDec
            /\ UNCHANGED <<mergedBy, mfacts, stop>>
    /\ UNCHANGED envVars

R2 == /\ pc = "r2" /\ SecondRead("decide")
      /\ UNCHANGED poll /\ UNCHANGED envVars /\ UNCHANGED histVars

\* ---- decide(), :190-285, transcribed branch for branch.
NB   == (IF snap.ck \in Red THEN 1 ELSE 0) + (IF snap.ghost /\ ~FixDedup THEN 1 ELSE 0)
Seen == IF NB = lastBroken THEN failN + 1 ELSE 1                  \* :235
Pend == snap.ck = "pending"                                        \* Check.pending, :128
Awaited == \/ snap.requested \/ snap.review = "none"               \* Snapshot.awaited, :163-173
           \/ FixReviewHead /\ snap.reviewHead # snap.head

Decide ==
    IF snap.state = "MERGED" THEN "STOP_MERGED"                    \* :205
    ELSE IF snap.state = "CLOSED" THEN "STOP_CLOSED"               \* :207
    ELSE IF snap.unres > 0 THEN "STOP_THREADS"                     \* :211
    ELSE IF snap.trunc THEN "STOP_TRUNC"                           \* :220
    ELSE IF NB > 0 /\ Seen < FAILURE_POLLS THEN "WAIT_RED"         \* :236
    ELSE IF NB > 0 THEN "STOP_FAILED"                              \* :244
    ELSE IF snap.ms \in NEEDS_REBASE THEN "REBASE"                 \* :252
    ELSE IF AwaitReview /\ FixChanges /\ snap.review = "changes" THEN "STOP_CHANGES"
    ELSE IF AwaitReview /\ Awaited THEN "WAIT_REVIEW"              \* :257
    ELSE IF snap.ms \in MERGEABLE /\ ~AllowMerge THEN "STOP_NOMERGE" \* :261
    ELSE IF snap.ms \in MERGEABLE THEN "MERGE"                     \* :263
    ELSE IF ~Pend /\ stuckN + 1 < STUCK_POLLS THEN "WAIT_STUCK"    \* :272
    ELSE IF ~Pend THEN "STOP_STUCK"                                \* :279
    ELSE "WAIT_PENDING"                                            \* :285

DecideStep ==
    /\ pc = "decide"
    /\ LET a   == Decide
           red == a \in {"WAIT_RED", "STOP_FAILED"}
       IN /\ stuckN'     = IF a = "WAIT_STUCK" THEN stuckN + 1 ELSE 0   \* :462
          /\ failN'      = IF red THEN Seen ELSE 0                       \* :464
          /\ lastBroken' = IF red THEN NB ELSE 0                         \* :465
          /\ dec' = [valid |-> TRUE, a |-> a, rd |-> snap.rd]
          /\ mrej' = IF a = "MERGE" THEN mrej ELSE 0
          /\ pc' = IF a = "MERGE" THEN "merge"                           \* :480
                   ELSE IF a \in WAITS THEN "r1"                         \* :486
                   ELSE "done"                                           \* :467-479
          /\ stop' = IF a \in WAITS \/ a = "MERGE" THEN stop
                     ELSE [a |-> a, curCk |-> snap.curCk, snapHead |-> snap.head, head |-> head]
          /\ snap' = IF a = "MERGE" THEN snap ELSE NoSnap
    /\ UNCHANGED <<poll, fails, mergedBy, issue, mfacts>>
    /\ UNCHANGED envVars

\* `gh pr merge N --squash` (:482): no head SHA, exit status discarded by
\* `_gh` (:292-293), then sleep and poll again (:483-484).
Facts == [valid |-> TRUE, head |-> head, snapHead |-> snap.head, ck |-> ck[head],
          unres |-> unres, requested |-> requested, review |-> review,
          reviewHead |-> reviewHead, rd |-> snap.rd]

MergeStep ==
    /\ pc = "merge"
    /\ issue' = Facts
    /\ snap' = NoSnap
    /\ IF ServerAccepts
       THEN /\ prState' = "MERGED" /\ mergedBy' = "watcher" /\ mfacts' = Facts
            /\ mrej' = 0
            /\ pc' = "r1"
            /\ UNCHANGED stop
       ELSE /\ UNCHANGED <<prState, mergedBy, mfacts>>
            /\ mrej' = IF FixMergeReject THEN mrej + 1 ELSE 0   \* unbounded otherwise
            /\ IF FixMergeReject /\ mrej + 1 >= 2
               THEN /\ pc' = "done"
                    /\ stop' = [a |-> "MERGE_REJECTED", curCk |-> ck[head],
                                snapHead |-> snap.head, head |-> head]
               ELSE /\ pc' = "r1" /\ UNCHANGED stop
    /\ UNCHANGED <<head, viewHead, ck, ghost, unres, overflow, requested, review,
                   reviewHead, behind, poll, stuckN, failN, lastBroken,
                   fails, dec>>

Watcher == R1 \/ R2 \/ DecideStep \/ MergeStep

-----------------------------------------------------------------------------
(****************************** The environment ****************************)

EnvOK == /\ prState = "OPEN"
         /\ EnvInWindow \/ pc \notin {"decide", "merge"}
         /\ EnvBetweenReads \/ pc # "r2"
         /\ pc # "done"   \* once the watcher has stopped, nothing it does can change

Push ==
    /\ EnvPush /\ head < MaxHead
    /\ head' = head + 1
    \* cancel-in-progress (ci.yml:11-13): the running run on the old head is cancelled
    /\ ck' = [ck EXCEPT ![head]     = IF @ = "pending" THEN "cancelled" ELSE @,
                        ![head + 1] = "none"]
    /\ viewHead' = IF EnvLag THEN viewHead ELSE head + 1
    /\ \E rebased \in BOOLEAN : behind' = IF rebased THEN FALSE ELSE behind
    /\ UNCHANGED <<prState, ghost, unres, overflow, requested, review, reviewHead>>

Sync == /\ EnvLag /\ viewHead < head /\ viewHead' = head
        /\ UNCHANGED <<prState, head, ck, ghost, unres, overflow, requested, review,
                       reviewHead, behind>>

CkOnly(new) == /\ ck' = new
               /\ UNCHANGED <<prState, head, viewHead, ghost, unres, overflow,
                              requested, review, reviewHead, behind>>
CreateChecks == ck[head] = "none" /\ CkOnly([ck EXCEPT ![head] = "pending"])
Complete     == ck[head] = "pending" /\ \E r \in {"success", "failure"} :
                    CkOnly([ck EXCEPT ![head] = r])
Rerun        == ck[head] \in Red /\ CkOnly([ck EXCEPT ![head] = "pending"])

\* A second run of the same workflow on the SAME head (reopen, re-trigger)
\* cancels the first via the concurrency group; both stay on the commit.
Dup == /\ EnvGhost /\ ck[head] = "pending" /\ ~ghost[head]
       /\ ghost' = [ghost EXCEPT ![head] = TRUE]
       /\ UNCHANGED <<prState, head, viewHead, ck, unres, overflow, requested, review,
                      reviewHead, behind>>

ThreadsOnly(n) == /\ unres' = n
                  /\ UNCHANGED <<prState, head, viewHead, ck, ghost, overflow, requested,
                                 review, reviewHead, behind>>
OpenThread    == EnvThreads /\ unres < MaxUnres /\ ThreadsOnly(unres + 1)
ResolveThread == EnvThreads /\ unres > 0 /\ ThreadsOnly(unres - 1)
Overflow == /\ EnvOverflow /\ ~overflow /\ overflow' = TRUE
            /\ UNCHANGED <<prState, head, viewHead, ck, ghost, unres, requested, review,
                           reviewHead, behind>>

RequestReview == /\ EnvReviews /\ ~requested /\ requested' = TRUE
                 /\ UNCHANGED <<prState, head, viewHead, ck, ghost, unres, overflow,
                                review, reviewHead, behind>>
\* Submitting clears the request and may carry an inline comment (a thread)
\* in the same atomic GitHub event -- how Copilot reviews arrive.
SubmitReview ==
    /\ EnvReviews
    /\ \E k \in {"comment", "changes"}, withThread \in BOOLEAN :
        /\ requested' = FALSE /\ review' = k /\ reviewHead' = head
        /\ unres' = IF withThread /\ unres < MaxUnres THEN unres + 1 ELSE unres
    /\ UNCHANGED <<prState, head, viewHead, ck, ghost, overflow, behind>>
DismissReview == /\ EnvReviews /\ review # "none" /\ review' = "none"
                 /\ UNCHANGED <<prState, head, viewHead, ck, ghost, unres, overflow,
                                requested, reviewHead, behind>>

BaseMoves == /\ EnvBase /\ Strict /\ ~behind /\ behind' = TRUE
             /\ UNCHANGED <<prState, head, viewHead, ck, ghost, unres, overflow,
                            requested, review, reviewHead>>

CloseOrMergeElsewhere ==
    /\ EnvClose
    /\ \E s \in {"CLOSED", "MERGED"} :
        /\ prState' = s
        /\ mergedBy' = IF s = "MERGED" THEN "other" ELSE mergedBy
    /\ UNCHANGED <<head, viewHead, ck, ghost, unres, overflow, requested, review,
                   reviewHead, behind, watVars, issue, mfacts, dec, stop>>

EnvStep ==
    \/ /\ EnvOK
       /\ \/ Push \/ Sync \/ CreateChecks \/ Complete \/ Rerun \/ Dup
          \/ OpenThread \/ ResolveThread \/ Overflow
          \/ RequestReview \/ SubmitReview \/ DismissReview \/ BaseMoves
       /\ UNCHANGED <<watVars, histVars>>
    \/ EnvOK /\ CloseOrMergeElsewhere

Next == Watcher \/ EnvStep

Spec     == Init /\ [][Next]_vars
LiveSpec == Init /\ [][Next]_vars /\ WF_vars(Watcher)

-----------------------------------------------------------------------------
(******************************* Properties ********************************)

TypeOK ==
    /\ prState \in {"OPEN", "MERGED", "CLOSED"}
    /\ head \in Heads /\ viewHead \in Heads /\ viewHead <= head
    /\ ck \in [Heads -> CkStates] /\ ghost \in [Heads -> BOOLEAN]
    /\ unres \in 0..MaxUnres /\ review \in Kinds
    /\ pc \in {"r1", "r2", "decide", "merge", "done"}

\* S1  The watcher never SENDS a merge for a head other than the one it evaluated.
IssueEvaluatedHead == issue.valid => issue.head = issue.snapHead
\* S2  ... nor while the head GitHub would merge is not green.
IssueGreen == issue.valid => issue.ck = "success"
\* S3  A merge that LANDED was of the evaluated head.
MergedEvaluatedHead == mergedBy = "watcher" => mfacts.head = mfacts.snapHead
\* S3b A head the watcher did NOT evaluate is never merged red (the head race alone).
UnevaluatedNotRed == (mergedBy = "watcher" /\ mfacts.head # mfacts.snapHead)
                         => mfacts.ck \notin Red
\* S4  A merge that landed was not of a red head ("a red PR must not be merged", :202).
MergedNotRed == mergedBy = "watcher" => mfacts.ck \notin Red
\* S4b A merge that landed was of a head whose check had COMPLETED green.
MergedCompletedGreen == mergedBy = "watcher" => mfacts.ck = "success"
\* S5  A merge that landed had no unresolved thread.
MergedNoUnresolved == mergedBy = "watcher" => mfacts.unres = 0
\* S6  Past the thread gate only on a complete listing: a failed or truncated
\*     read never reads as "no threads".
ThreadGateSound ==
    (dec.valid /\ dec.a \notin {"STOP_MERGED", "STOP_CLOSED", "STOP_THREADS", "STOP_TRUNC"})
        => dec.rd = "ok"
\* S6b A stuck / failure sighting counts only on a complete read: "a poll whose
\*     read failed does not count towards the streak" (CONTRIBUTING).
StreakFromCompleteReads ==
    (dec.valid /\ dec.a \in {"WAIT_STUCK", "STOP_STUCK", "WAIT_RED", "STOP_FAILED"})
        => dec.rd = "ok"
\* S7  --await-review contract: no merge with a request pending or before a
\*     non-author review stands (Snapshot.awaited, :163-173).
AwaitContract == (AwaitReview /\ mergedBy = "watcher")
                     => (~mfacts.requested /\ mfacts.review # "none")
\* S8  (intent) ... nor over a standing CHANGES_REQUESTED.
AwaitNoChangesRequested == (AwaitReview /\ mergedBy = "watcher") => mfacts.review # "changes"
\* S9  (intent) ... nor of a head nobody reviewed (the review predates a push).
AwaitReviewedThisHead == (AwaitReview /\ mergedBy = "watcher") => mfacts.reviewHead = mfacts.head
\* S10 STOP_FAILED only when the latest run of the check on the PR's ACTUAL
\*     head was red when read: a superseded / cancelled run never stops it.
NoStaleFailStop == stop.a = "STOP_FAILED" => stop.curCk \in Red
\* S11 STOP_STUCK (the BLOCKED-with-nothing-pending branch) never fires while
\*     the current head's checks simply have not been created yet.
NoFalseStuck == stop.a = "STOP_STUCK" => stop.curCk # "none"

\* L1  If the PR eventually stays mergeable, the watcher eventually stops
\*     (merged, or a defined reason) -- it does not poll forever.
Good == /\ prState = "OPEN" /\ viewHead = head
        /\ ck[head] = "success" /\ ~ghost[head]
        /\ unres = 0 /\ ~overflow /\ ~(Strict /\ behind)
        /\ AwaitReview => (~requested /\ review # "none")
        /\ AwaitReview /\ FixChanges => review # "changes"
        /\ AwaitReview /\ FixReviewHead => reviewHead = head
EventuallyStops == (<>[]Good) => <>(pc = "done")
\* L2  ... and when it does, it merged (or was told --no-merge), not gave up.
\*     Stated from any point where the watcher is about to START a poll and Good
\*     holds from then on: a poll already in flight may have read a thread that
\*     has since been resolved, and stopping on it is the watcher doing its job.
EventuallyMerges ==
    []((pc = "r1" /\ []Good)
         => <>(pc = "done" /\ stop.a \in {"STOP_MERGED", "STOP_NOMERGE"}))
=============================================================================
