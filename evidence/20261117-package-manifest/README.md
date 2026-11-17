# Release manifest selection check

This check exercises setuptools' actual `MANIFEST.in` selector against the
tracked paths from `d08ab2623bf992ee2a8e923531caea3b0d37b579`. It does not build a
wheel or source archive, install a package, or run a financial test. The next
frozen candidate still needs independent archive and installation validation.

The original template omits nine tracked documentation/evidence files: seven
documentation JSON files (including the readiness observations and six archived
benchmark summaries), plus two evidence README files. Adding `*.json` under
`docs` and `*.md` under `evidence` includes all 259 tracked documentation/evidence
files in this source snapshot. The first inspection expected only the three
explicitly reported omissions; the complete selector result identified the six
additional benchmark JSON files, so the final check covers the whole tracked
documentation/evidence set.

There are no tracked `.jsonl` or `.log` files under these two directories in the
checked snapshot. Those formats are not added speculatively. Existing archived
benchmark arrivals use `.jsonl.gz` under `benchmarks`, already covered by its
separate manifest rule. No database or secret-file rule is added.

The exact command is in `commands.txt`; its actual stdout and stderr are
retained beside the machine-readable `selection.json`. This result only proves
manifest selection. It does not establish production, availability, throughput,
or real-funds qualification.
