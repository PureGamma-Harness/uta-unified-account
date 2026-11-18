# Explicit target marshalling for wire V3

This candidate derives the test-side target marshaller from reviewed source
f8ece4c2 and limited independent review35c5b22b. Only six literal substitutions
change its module documentation, exact wire hash/path, required envelope version,
version error label and emitted version. All DTO conversion, complete output
validation, exception boundaries, intermediate checks and resource bounds retain
their reviewed function bodies. No financial equation or independent reference
algorithm is copied into the adapter.

The pinned independent V3 contract is d3586666, 33268 bytes, SHA256
6dd60f660a9a16c836b3572c7183d5a2085f2ff3ffae82fa66c7d4bdbf2b3bcd.
Requests and responses explicitly use version3. Version2 is rejected, never
silently rewritten. The bridge constructs the exact supplied Stage/history;
it does not invent or restore missing exposure/cap references. The target must
enforce the independently reviewed local lineage rule69a3e32e/54af0876.

The older V2 marshaller, its correction history and reviews remain available as
framework regression evidence. Its tests do not establish V3 compatibility or
reference agreement. The new module has the prior18 regression definitions
ported with explicit module/version names, plus one old-envelope rejection
definition. All19 V3 tests are NOT_RUN at this freeze.

Independent V3 source export and its own CODE review remain separate. The future
differential driver must invoke each independent implementation, compare the
entire typed response, preserve actual business/error/technical outcomes, and
never manufacture expected financial values or fill missing lineage. No such
comparison has executed for this candidate.

This adds test artifacts and data only. Runtime67/1479474B, inventory V4 and all
financial service behavior remain byte-identical to public source d128ee6e.
No target/reference import, compilation, generation, validator call, test, SQL,
actor or CI ran for this delta. Revert the new V3 artifacts for rollback while
retaining historical sources and confirmed economic records. D2, capacity and
real-funds production remain NO_GO.
