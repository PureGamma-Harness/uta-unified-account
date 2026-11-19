# Offline inspector engineering acceptance

The standalone inspector source 21a565889356c17ee7ea77dbf0454b01a28884a9
received independent review c28a892272537fa37bb4d82cdfabcfe61b352993.
The first Python3.12 synthetic author suite ran29 tests with zero failures or
skips; a separate8-test boundary/TOCTOU harness and standalone synthetic CLI
also passed. Exact invocation, output hashes and limitations are preserved in
docs/reviews/deployment-manifest-inspector-21a56588-independent.md.

The earlier author document's NOT_RUN statements describe its source freeze;
the later independent results above supersede only those explicitly run scopes.
No inspection of the actual UTA runtime inventory or financial state occurred.
First normal push and pull-request CI for this delivery remain pending and must
retain their own original results. No CI rerun may replace the first failure.

This addition changes no UTA runtime, database schema, authorization, fencing,
CI configuration or benchmark. Distribute the script through an engineering
tool channel with a separately trusted expected manifest digest. Rollback stops
using and removes the new standalone tool; confirmed financial effects and
authority state are unaffected. Packaging, removal and all unverified deployment
properties are detailed in docs/deployment/offline-manifest.md.

STATIC_PIN_MATCH is a bounded offline byte comparison. It does not authenticate
the supplied manifest, inspect unlisted actual files, attest loaded code, grant
activation, or satisfy production/recovery/capacity acceptance. Production NO_GO.
