# RUN-C Python 3.12: separate cross-SQLite check

One sequential CPU3 execution at `1a9d6f4`, Python 3.12.14/SQLite 3.53.1:
the same 7 cases passed in 7.780 seconds, no errors, failures, ResourceWarning
or timeout. Inputs are identical to the Python 3.13 run and unchanged across
this run. The actual cleanup marker records the bound old owner exited,
resume_sent=false. This separate interpreter execution covers another SQLite
build; it does not create seven additional distinct cases or qualify full CI.
