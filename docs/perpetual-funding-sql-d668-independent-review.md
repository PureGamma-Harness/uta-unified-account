# Funding SQL once d668: independent CODE finding

Exact source `d6687e877faf04f90686ea257351d90745d92642`, tree `0b9fd9e995f2b7d173a6240654084736821f2b6c`, remains **NOT_CLOSED / NOT_RUN0**. Root confirmed no execution GO was given. This is a static acceptance-oracle finding, not a failed target run or demonstrated financial loss.

## FUND-SQL-CODE-001 — position inventory loses symbol

At tools/run_funding_sql_once.py:422–425, actual uta_positions rows are reduced to a dictionary keyed only by account_id; the expected dictionary also omits symbol. An intended a/BTC-PERP quantity1/cost100 plus an unintended a/OTHER-PERP quantity1/cost100 reduce to the same {a:[1,100]} projection, regardless of row order. The declared complete position inventory check therefore omits a dimension and row cardinality. No SQL or target was executed to reason about this static example. The current intended catalogue remains single-symbol.

The minimal fix is to use (account_id,symbol) keys for actual rows and (account,oracle.base.symbol) keys for expected rows. Do not change monetary expectations, original three methods, five DB scope, financial modules or resource limits. Freeze new driver/plan pins and obtain delta CODE review before root grants any execution. d668 must retain NOT_RUN0 history.

All67 canonical regular physical input files (1,412,844 bytes) match exact Git blobs and declared pins. Original65 pins, f341 seven financial/test/docs files and prior pure SAFE12 files are unchanged. The runner and inline bootstrap were parsed only as AST. No target compile/import/test, SQL, process or PID probe ran.

Other reviewed code boundaries close within their declared scope: fixed3 SQL failfast methods and5 ordered new authorities; explicitly added native pending RO setup; manual balances/fees.46/custody-10002.04 and6 matches/12 fills/32 journals/3 periods; new ro/query-only guarded existing-only service construction without repair in the final reopen stage; matching and funding verifiers joined to that snapshot; expected orphan rejection; persistent risk cancel/replacement state; retained source loading with no sqlite3.connect patch; native connect/handle accounting and failure-preserving owned cleanup.

The proposed20s target plus22s completion guard, control8MiB, source-reviewed20 file families at4MiB each and32KiB allFD capture are not execution approval or aggregate OS disk quota. Metadata peaks are observations, not continuous native write monitoring. Actual host wait/reap/EOF, BEGIN/END/TAIL and separately observed caller outer exit remain required.

An intermediate no-blocker/CLOSED message was withdrawn before any GO when this final key review found the issue. This record is the final independent d668 conclusion. SQL actual RAW, durable scheduling and unsettled obligations, operations/custody approval, managed migration/HA, failure/capacity evidence and human financial/real-funds approval remain OPEN.
