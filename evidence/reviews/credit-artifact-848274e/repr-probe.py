"""The repr exception must identify the actual stdlib wrapper, not its name."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from uta import credit
from uta.credit_artifact import credit_code_artifact


def make(value):
    repr_running = {value}
    def user_function():
        return 0
    def __repr__(*args, **kwargs):
        return next(iter(repr_running)) + user_function()
    return __repr__


start, clock = datetime.now(timezone.utc).isoformat(), time.monotonic()
first, second = make(101), make(202)
with patch.object(credit.CreditService, "_borrow", first):
    before = credit_code_artifact()
with patch.object(credit.CreditService, "_borrow", second):
    after = credit_code_artifact()
print(json.dumps({"case": "nonstdlib_repr_name_excludes_financial_closure",
    "same_code": first.__code__ == second.__code__, "freevars": first.__code__.co_freevars,
    "first_result": first(), "second_result": second(),
    "expected_identity_changes": True, "actual_identity_changes": before != after,
    "started_at": start, "ended_at": datetime.now(timezone.utc).isoformat(),
    "elapsed_seconds": time.monotonic() - clock, "sql_used": False}, sort_keys=True))
# Preserve the expected red, rather than present it as a passing identity test.
raise SystemExit(1)
