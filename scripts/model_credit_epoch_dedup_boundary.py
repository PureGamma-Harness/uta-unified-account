#!/usr/bin/env python3
"""Pure bounded counterexamples; no actual directory, AuthStore, SQL or grants."""
from datetime import datetime, timezone
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import sys
import time


KEY = ("logical-domain", "explicit-tenant", "account-A", "original-CID")
ORIGINAL_PAYLOAD = b'{"amount":"2","asset":"BTC"}'
ORIGINAL_RECEIPT = b'{"command_id":"original-CID","state":"SUCCEEDED"}'


def admit(directory, payload, kind):
    """Authoritative lookup; absence means a proved complete current cut."""
    if directory == "unavailable":
        return "UNKNOWN"
    if directory == "complete-absent":
        return "reserve-current-key"
    if payload != ORIGINAL_PAYLOAD or kind != "BORROW":
        return "CONFLICT"
    return ORIGINAL_RECEIPT if directory == "original-terminal" else "original-UNKNOWN"


def cut_allowed(auth_state, acceptance_epoch_known, revocation_epoch_known):
    return (auth_state == "verified-none-outstanding" and acceptance_epoch_known
            and revocation_epoch_known)


def main():
    began = datetime.now(timezone.utc).isoformat()
    cpu_start = time.process_time()
    scenarios = 0
    for directory, same_payload, kind in product(
            ("original-terminal", "original-accepted", "complete-absent", "unavailable"),
            (True, False), ("BORROW", "REPAY")):
        payload = ORIGINAL_PAYLOAD if same_payload else b'{"amount":"3","asset":"BTC"}'
        result = admit(directory, payload, kind)
        assert (result == "reserve-current-key") == (directory == "complete-absent")
        if directory == "original-terminal" and same_payload and kind == "BORROW":
            assert result == ORIGINAL_RECEIPT
        if directory == "unavailable":
            assert result == "UNKNOWN"
        if directory in ("original-terminal", "original-accepted") and (
                not same_payload or kind != "BORROW"):
            assert result == "CONFLICT"
        scenarios += 1
    auth_scenarios = 0
    for state, acceptance_known, revocation_known in product(
            ("verified-none-outstanding", "nonce-committed-grant-undelivered", "auth-COMMIT-unknown"),
            (False, True), (False, True)):
        assert cut_allowed(state, acceptance_known, revocation_known) == (
            state == "verified-none-outstanding" and acceptance_known and revocation_known)
        auth_scenarios += 1
    # Mutant: successor starts with an empty inbox and consults only that file.
    global_directory = {KEY: ORIGINAL_RECEIPT}
    successor_local_inbox = {}
    old_loan_effects = 1
    local_only_result = "new-loan" if KEY not in successor_local_inbox else "original"
    mutated_total_effects = old_loan_effects + int(local_only_result == "new-loan")
    assert KEY in global_directory and mutated_total_effects == 2
    correct_result = admit("original-terminal", ORIGINAL_PAYLOAD, "BORROW")
    correct_total_effects = old_loan_effects + int(correct_result == "reserve-current-key")
    assert correct_result == ORIGINAL_RECEIPT and correct_total_effects == 1
    # Same business CID remains distinct in a DIFFERENT trusted namespace.
    assert (KEY[0], "other-tenant", KEY[2], KEY[3]) != KEY
    assert (KEY[0], KEY[1], "other-account", KEY[3]) != KEY
    elapsed = time.process_time() - cpu_start
    assert elapsed < 3.0
    print(json.dumps({
        "model": "credit-epoch-dedup-auth-boundary-v1", "status": "passed",
        "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": sys.version, "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "start_utc": began, "end_utc": datetime.now(timezone.utc).isoformat(),
        "process_cpu_seconds": round(elapsed, 6), "CPU_budget_seconds": 3,
        "command": "timeout 3s taskset -c 3 python3 -W error::ResourceWarning scripts/model_credit_epoch_dedup_boundary.py",
        "directory_scenarios": scenarios, "auth_cut_scenarios": auth_scenarios,
        "negative_control": {"name": "successor-local-only-lookup",
                             "old_effects": old_loan_effects,
                             "mutated_total_effects": mutated_total_effects,
                             "correct_total_effects": correct_total_effects,
                             "detected": True},
        "assumptions": ["directory input is authoritative and complete",
                        "tenant/account mapping is trusted and stable",
                        "auth/nonce/epoch input is authoritative",
                        "real consistency, CAS and source-delivery protocol are NOT modeled"],
        "production_approval": False,
        "scope": "Separate pure design check; no runtime, SQL, HMAC or actual binary acceptance"
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
