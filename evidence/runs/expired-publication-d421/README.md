# Original d421 Python 3.10 failure

`original/` preserves the complete summary, worker result, unittest log and
unchanged test file. `copies.json` records source paths, byte counts and hashes.
`source-verification.json` independently checks all252 original validator inputs
against both frozen files and Git blobs, including unchanged before/after maps.

The original verdict remains NO-GO. No single-case reproduction or repair is
claimed by this archive. See the independent investigation plan in docs.
