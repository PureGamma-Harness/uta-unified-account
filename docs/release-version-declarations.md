# Release version declarations

The batch, cache and credit development stage declares `0.5.0a1` in
`pyproject.toml` and `uta/__init__.py`. This source change does not establish a
new built or installed release. Historical `0.4.0a1` artifacts and acceptance
records keep their original identity and verdicts.

`tools/verify_release_archives.py` derives the expected version from the exact
requested Git commit. HEAD must equal that commit, tracked source must be
unchanged, and non-ignored untracked files are rejected. Both declarations must
be tracked. The initializer is parsed as Python syntax without importing the
package: after its optional docstring it must contain one literal `__version__`
assignment equal to `[project].version`.

The tool supports Python 3.10 without dependencies. Its TOML reader deliberately
supports this repository's controlled format: canonical bare table/key names
and one unescaped, single-line ASCII version string. Dynamic versions,
duplicate declarations, quoted/dotted project keys and multiline strings are
rejected. A future declaration-format change needs an explicit tool review;
this is not a general TOML parser.

The wheel must have exactly one distribution `METADATA` file. Its parsed headers
must contain exactly one `Version`, matching the frozen source declaration.
Header names are case insensitive; a body string mentioning the expected
version cannot satisfy the check. The archive report records the source-derived
version and observed headers. The installed-release checker then requires both
installed distribution metadata and `uta.__version__` to match that report.
All existing runtime, tracked-source, entry-point and legacy-fixture checks
continue to apply.

The [focused evidence](../evidence/20261117-release-version-050/README.md)
contains actual temporary Git/ZIP/tar fixture runs for both `0.4.0a1` and
`0.5.0a1`, including retained counterexamples against the previous checker.
It supplies no new project package, installed-runtime, capacity, production,
HA or real-funds qualification. A future frozen source still needs its own
complete CI and fresh package acceptance.
