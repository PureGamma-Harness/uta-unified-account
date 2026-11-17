"""Pure JSON policy for optional managed-observer output storage admission."""

GIB = 1024**3
DEFAULT_OUTPUT_BUDGET_BYTES = 6 * GIB
MIN_OUTPUT_BUDGET_BYTES = GIB


def output_budget_bytes(plan):
    """Resolve bytes without mutating the plan or accepting bool as an integer."""
    if type(plan) is not dict or type(plan.get('observer')) is not dict:
        raise ValueError('observer_output_budget_plan_invalid')
    observer = plan['observer']
    if 'output_budget_bytes' not in observer:
        return DEFAULT_OUTPUT_BUDGET_BYTES
    value = observer['output_budget_bytes']
    if type(value) is not int or not MIN_OUTPUT_BUDGET_BYTES <= value <= DEFAULT_OUTPUT_BUDGET_BYTES:
        raise ValueError('observer_output_budget_bytes_invalid')
    return value


def explicit_output_budget(plan):
    """An explicit field opts into the full output-tree measurement/drain policy."""
    output_budget_bytes(plan)
    return 'output_budget_bytes' in plan['observer']
