The original smoke02 evidence remains unchanged. Root appended the exact timing clarification archived at `evidence/runs/managed-909acec-smoke-02/root--timing-boundary-erratum.json`.

The recorded 64.379813724 seconds covers the actual first producer Popen through controller completion (including business-stage raw hashes), outer stream close/fsync, raw read/parse, and first-Popen metadata read. Root auxiliary stdout/stderr SHA calculation and final attestation serialization follow that monotonic endpoint. No post-auxiliary-hash BOOTTIME was recorded; complete auxiliary-finalization latency is unmeasured and is not backfilled.

This corrects the earlier archive prose that included every root stream hash in that endpoint. Seven-stage smoke results, original numeric timing, first01 permanent NO_GO, and all long/production flags remain unchanged.
