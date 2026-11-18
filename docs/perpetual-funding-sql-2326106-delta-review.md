# FUND-SQL-CODE-001 finite delta closure

Exact source `2326106b3bf8cf6d2713e4cf8c7926afdf6962ab` (tree `6a31eee93bf6ce0368d65fab0c654d9e0771fb51`) closes FUND-SQL-CODE-001 at CODE level. Root has not granted SQL execution. Previous candidate d668 remains NOT_RUN0, and independent finding `c4ca14fe8c60d9d93dd76b946cb37ff0c64cba59` remains unchanged.

The runner changes exactly two expressions: actual position keys become (account_id,symbol), expected keys become (account,oracle.base.symbol). Reverting only those expressions restores the entire runner byte-for-byte to d668. No financial, test, manual monetary oracle, selector, database scope or resource budget changes. The new plan only rebinds this driver/total bytes and retains explicit correction history. Old d668 plan/preparation copies are byte-exact.

The existing-only constructor verifies the original uta_positions schema including NOT NULL account_id/symbol and PRIMARY KEY(account_id,symbol), before these full-row reads. Therefore tuple keys preserve every valid position row. The earlier example with both a/BTC-PERP and a/OTHER-PERP now has two distinct actual keys against one expected key and is rejected even if both quantities/costs match. This is static key-set reasoning, not an executed test or SQL experiment.

All67 physical canonical regular inputs (1,412,889 bytes) match exact Git and plan pins; every input other than this runner is byte-identical to d668. Driver44,499 bytes, SHA `da7904d0cc22debc4378b570894177f2c4b35a2501de1c2938c5c1a7f0872c9e`; plan SHA `fb3d1fb820f3cf4112699615a0a8ae05bae82ec945ac1c7d858a2c92fed7f241`.

The limited SQL CODE proposal is closed with all prior scope constraints retained:3 failfast methods,5 new DBs,6 matches/12 fills/32 journals/3 periods, proposed20-second target and22-second classification, control8MiB/DB source-bound80MiB/per-file4MiB/shared raw32KiB. These are not execution GO, a hard aggregate disk quota or production acceptance. No target compile/import, SQL or probe ran during this review.

Root must issue a separate exact unique once GO. Actual first SQL evidence and independent RAW review, scheduling/DUE/unsettled obligations, operations/custody approval, managed migration/HA, failure/capacity evidence and human financial/real-funds approval remain OPEN.
