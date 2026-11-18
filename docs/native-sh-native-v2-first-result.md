# First native SH baseline v2 — bounded local result, independent RAW pending

The exact unique root-authorized run used source
48d045d478564f7ea15239e21f8164ca517339ca, tree
4ee064c8a94b9e6656295768b782975a3671e14c, after independent CODE review
132ab64d080c6ffa94ff91f27c46d012cfdc482c. This is the unchanged PR35/6010
46905e runtime, without PR37's registration cap. It ran once against a fresh
private authority. No retry, candidate run, push, CI or deployment followed it.

The original TestCase.run completed one test with zero failures, errors, skips,
expected failures or unexpected successes. All original assertions completed.
It used one capture attempt, one actual test signal entry, no capture undo and
no forced test cleanup kill or cleanup error. The original five-second lease,
capture and recovery periods and all financial/schema/cache/publication
assertions were unchanged. The capture FD is still explicitly an extra real
test-tool SH FD in the actual owner PID on the same kernel gate, rather than
the native financial critical-section FD.

Relative to the original publication start, the held owner's pidfd exit was
observed at0.253291745s, the new generation at0.857148973s and publication finished
at1.048380085s. The real replacement READY event was observed. These original
five-second assertions passed in this one local instrumented case.

The separate caller recorded actual controller exit0 and owned reap after
8,409,570,634ns, within51s. The controller recorded original case-parent exit0,
all terminal/reaped roles and no unknown/watchdog condition. Roles were one
case parent, three cumulative financial births and one tracker; the original
two-shard topology and two-live financial guard remained. The stopped old
financial actor exited-9; the sibling, replacement, tracker and case parent
exited0. No outer cleanup signal was dispatched.

END and raw trailer correctly remained PENDING_FINAL_RETURN with an observed
candidate; they did not certify a future exit. Both PRE_EXIT records proposed0
before the shared deadline, FINAL_OWNERSHIP confirmed all registered roles
terminal, and the separate creator wait supplied actual exit/reap evidence.
Both original raw pipes reached EOF under the frozen controller. Launcher raw
stdout/stderr were empty and the external tool observed launcher completion0.

Launcher metadata recorded Python3.12.14, the exact executable SHA256
fa67443527ed9647f760d807e2a38f26340757123e643c4639cf273ed15d5ea7,
-I/-S/-B and CPU1; the actual case reported CPU1. The unchanged parent_case entry
equality check against SQLite3.53.1 completed before authority creation. No
replacement metadata value was probed and retried after a mismatch.

Original stdout was309B, SHA256
4e3d1bdb9c343f9a32c2352dba53bec2b80b6f802dcfc97562a966614d4a52cb;
stderr was671B, SHA256
79019596c4199b6010602b42ac0c7665c56f4d7fbdf7c062a8d107fc6154095f.
The stderr profile contains private process/boot binding and was not copied to
Git. Combined original raw was980B; events were36 records/36,729B. Authority
logical peak observed was929,848B and final measured size925,696B. Monitoring
remains sampled/logical and is not a hard quota. Original source, private source
copy and stdlib before/after comparisons all matched.

All98 original files, totaling2,569,983B, were sealed without modifying them
under the two authorized private roots:

- /workspace/uta-native-sh-baseline-native-v2-once01
- /workspace/uta-native-sh-baseline-native-v2-once01-host-once01

The private host PRIVATE-SEAL.json is28,592B, SHA256
9782b6267254f3530322c005ddda0598489d0705686300b363154f64b24ec664.
Its inventory includes the private authority and binding facts and stays local.
Git receives only this note and the allowlisted SAFE derived JSON
first-native-v2-once01-safe-summary.json, SHA256
a7f42fd232a4b35b5ea833d46cbf6a130f4e044bd1c3c641ebeb3779b59553df.
No DB, capsule, raw profile, boot identity, PID/birth binding or nonce is exported.

This author result awaits independent RAW review. It supports one successful
fresh instrumented baseline recovery within the original five-second assertions.
It does not establish the unique cause of PR35/PR41 CI recovery failures, prove
an uninstrumented engine or performance guarantee, compare the .1 registration
cap, certify production recovery/RTO, or exercise quota/timeout/error branches.
All earlier failures and the c98 zero-attempt record remain unchanged. A later
scope needs its own source, authority, first record and explicit root GO.
