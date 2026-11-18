# Admission / credit-v2 policy compatibility

CODE_ONLY / NOT_RUN. First PR52 source137562a0 failed all eight normal CI jobs:
each fixed unit suite had2066 tests,16 credit-v2 policy errors and one restart
assertion failure. Original evidence is sealed separately. It is not a timing
explanation and the original failure is not replaced by this change.

The order decision policy added admission_contract, while CreditAuditV2
compared that runtime dictionary to the fixed ten-field persisted credit
valuation policy. The dictionaries differ even for a fresh valid authority.

DecisionAudit.valuation_policy now constructs the existing ten valuation
fields from actual runtime configuration. DecisionAudit.policy adds the
order admission contract to that dictionary. CreditAuditV2 explicitly reads
valuation_policy; its persisted-policy reconstruction, exact dictionary
comparison, supported-scope checks, field declarations and replay calculations
are unchanged. No key filtering, unknown-field dropping, fallback or archive
rewrite is introduced. Order admission still records and verifies its contract.

Four pure regression methods verify the exact legacy credit wire fields,
the full order envelope, credit's explicit valuation dependency, and rejection
of altered or unknown runtime valuation fields. Persisted reads are mocked
for these unit contracts; they do not establish real SQL/restart acceptance.
The original full CI credit helper/restart tests must pass on a separately
identified corrected source. A custom AuthDB probe remains blocked and is not
invoked by this work.

This changes no financial formula, balance/borrow mutation, fee, quote rounding,
database DDL or policy format. It is still a fresh-authority candidate. Existing
artifact checks must reject incompatible code; old audit archives are retained
under their original source. No existing writer migration is permitted here.

Rollback restores the candidate's prior code in a new synthetic environment;
never erase confirmed financial history or rewrite policies to match a binary.
Keep the original failed CI and prior SQL4 results pinned to their actual SHAs.
Corrected-source CI, retained pure execution and independent review remain
required. Production, capacity, managed credit activation, migration and
real-funds approval remain NO_GO.
