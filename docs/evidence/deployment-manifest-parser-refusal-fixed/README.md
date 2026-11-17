# Parser refusal correction: first changed-source batch

Independent review `679320943d8186260f07a4225afae0b2c2bee31c` observed a
4512-byte JSON input containing a4501-digit integer escape `main()` as a plain
ValueError on Python3.13.5. Its original stdout was empty; no return2 or complete
traceback was recorded. That original result and its limitations remain intact.
The review was copied as `686a152`, without rerunning the old source.

Code `fb54a5aa0907e9113e1ead75bba93b05e9ad8899` first preserves deliberate
ManifestError codes, then maps ordinary decoder ValueError to
`manifest_json_invalid`. It also validates the manifest argument's NUL/UTF8
boundary before metadata/content I/O while preserving the original relative-path
refusal. No manifest schema, private-path rule or activation policy was relaxed.

The one new source-bound batch completed21 methods with zero failures, errors
or skips on Python3.12.14, CPU2, integer-digit limit4300. The measured interval
was23,842,343ns before result serialization; it is not a full supervisor wall
measurement or deployment performance claim. The8-second self-alarm did not fire.
Source and imported tool/test paths were bound in the same PID before the batch,
and both source hashes remained unchanged afterward.

The batch covers the real4512-byte input, a plain decoder ValueError, preservation
of duplicate/nonfinite codes, manifest-argument NUL/UTF8 rejection before I/O and
the prior path/role tests. For interpreters whose integer guard is disabled, the
large literal is still refused by the strict schema; the test does not pretend
that such a runtime raised the original decoder error. The mock decoder-error
case separately verifies stable handling of the exception itself.

SQL connections, child processes and signals were hard-denied during tests.
Content reads were allowed only for fresh synthetic `manifest.json` fixtures;
there were six reads, maximum4512 bytes, and zero forbidden API calls. No actual
secret, profile, wheel or database body was read. Original private files remain
outside Git; these explicit source/proof/raw copies contain only code, aggregate
results and successful test names. No original fixture body is published.

This closes the changed-source component checks only. Independent differential
review, actual artifact/settings verification, deployment, recovery and production
approval are separate gates. The tool still returns activation/production=false;
its rollback remains removal of this offline review step without changing data.
