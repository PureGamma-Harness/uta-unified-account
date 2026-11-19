Synthetic, hand specified source fixture; no financial implementation.

`source/abc.txt` contains exactly the three ASCII bytes `61 62 63`, with no newline.
Its standard SHA-256 test vector is
`ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad`.
`source/empty.txt` has zero bytes, whose SHA-256 is
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Thus the declared total is `3 + 0 = 3` bytes and `1 + 1 = 2` files.

The authored `manifest.json` byte checksum is
`8942ab3d487b46b66a7cc568cf44edb3a4e3171185d18af6966525efae63ca78`.
This is a fixture identity pinned literally by the test definition. It is not a
production trust root or a suggestion to derive a trusted digest from an
untrusted manifest or its neighboring sidecar.

The fixture schema explicitly reports `SYNTHETIC_FIXTURE_ONLY`. It cannot satisfy
the separate combined-source v1 schema's exact 67-path V4 runtime inventory.

Test definitions cover static mutations, omitted files, extra manifest entries,
unlisted actual files, duplicate keys and pins, missing or unknown fields,
boolean integers, unsupported numeric forms, path escapes, symlinks, nonregular
files, size/depth/read limits, a mutation between file stat checks, and private
argument redaction. A precision field is rejected as an unknown schema field;
this tool does not verify same-currency precision or any financial semantics.

Execution status for this authored milestone: **NOT_RUN**. No checker, import,
compile, discovery, or test invocation is evidence supplied by this change.
