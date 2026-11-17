# RUN-C Python 3.13: actual fixed-source small check

One authorized CPU3 execution at `1a9d6f4`, Python 3.13.5/SQLite 3.46.1:
7/7 passed in 7.410 seconds, no errors, failures, ResourceWarning or timeout.
It includes the two original cases and five real contract/negative controls.
The prior RUN-B remains 2 FAIL / 2 PASS / 1 ERROR. The actual cleanup marker
records the bound old owner exited, resume_sent=false; no replacement PID was
resumed. The exact command, before/after inputs, raw diagnostics trace and
result are retained. This is not CI 3.13.18 or a full-release result.
