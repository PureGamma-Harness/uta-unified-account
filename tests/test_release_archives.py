"""Artifact verifier contracts, using real Git, ZIP and source archives."""
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
import unittest
import zipfile


VERIFIER = Path(__file__).resolve().parents[1] / "tools" / "verify_release_archives.py"


def commit_source(root, files):
    root.mkdir()
    for name, content in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()
    git("init", "--quiet")
    git("add", ".")
    git("-c", "user.name=Release Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "--quiet", "-m", "synthetic artifact source")
    return git("rev-parse", "HEAD")


class ReleaseArchiveTests(unittest.TestCase):
    VERSION = "0.4.0a1"  # Preserve coverage of the historical release contract.

    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name) / "source"
        fixture = io.BytesIO()
        with tarfile.open(fileobj=fixture, mode="w:gz") as archive:
            info = tarfile.TarInfo("LICENSE")
            content = b"synthetic licensed fixture\n"
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
        cls.files = {
            ".gitignore": b"__pycache__/\n",
            ".github/workflows/ci.yml": b"name: synthetic-ci\n",
            "LICENSE": b"synthetic source license\n",
            "pyproject.toml": ('[project]\nname = "uta-reference-exchange"\nversion = "' + cls.VERSION + '"\n').encode(),
            "uta/__init__.py": ('__version__ = "' + cls.VERSION + '"\n').encode(),
            "uta/dashboard.html": b"<p>synthetic</p>\n",
            "tests/test_durable_cli.py": b"# synthetic frozen helper\n",
            "tests/fixtures/legacy_ad3f5b8_uta.tar.gz": fixture.getvalue(),
            "tests/fixtures/legacy_ad3f5b8_provenance.json": json.dumps(
                {"archive_sha256": sha256(fixture.getvalue()).hexdigest()}).encode(),
            "formal/results/model.json": b'{}\n',
            "tools/probe.py": b"# synthetic probe\n",
            "docs/readiness-observations.json": b'{}\n',
            "evidence/runs/probe/allocation-probe.py": b"# synthetic allocation probe\n",
            "deploy/uta.service": b"[Unit]\n",
            "config/example.json": b'{}\n',
            "scripts/reproduce.py": b"# synthetic reproducer\n",
            "benchmarks/results/regression.txt.gz": b"synthetic archived bytes\n",
        }
        cls.commit = commit_source(cls.root, cls.files)

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)

    def archives(self, *, omit=None, mutate=None, duplicate=None, extra=None,
                 metadata=None, second_metadata=False):
        wheel = self.output / "release.whl"
        sdist = self.output / "release.tar.gz"
        with zipfile.ZipFile(wheel, "w") as archive:
            for name, content in self.files.items():
                if name.startswith("uta/"):
                    archive.writestr(name, content)
            info = "uta-" + self.VERSION + ".dist-info/"
            archive.writestr(info + "METADATA", metadata if metadata is not None else "Version: " + self.VERSION + "\n")
            archive.writestr(info + "entry_points.txt", "[console_scripts]\n"
                "uta = uta.__main__:main\nuta-ops = uta.ops:main\nuta-durable = uta.durable_cli:main\n")
            if second_metadata:
                archive.writestr("other-1.dist-info/METADATA", "Version: " + self.VERSION + "\n")
            if duplicate == "wheel":
                # ZIP's duplicate warning is expected fixture construction.
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    archive.writestr("uta/__init__.py", self.files["uta/__init__.py"])
            if extra == "wheel":
                archive.writestr("uta/untracked.py", b"# unexpected runtime\n")
        with tarfile.open(sdist, "w:gz") as archive:
            def add(name, content):
                info = tarfile.TarInfo("uta-" + self.VERSION + "/" + name)
                info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
            for name, content in self.files.items():
                if name != omit:
                    add(name, b"mutated\n" if name == mutate else content)
            if duplicate == "sdist":
                add("uta/__init__.py", self.files["uta/__init__.py"])
            if extra == "sdist":
                add("uta/untracked.py", b"# unexpected runtime\n")
        return wheel, sdist

    def verify(self, **kwargs):
        wheel, sdist = self.archives(**kwargs)
        report = self.output / "report.json"
        report.unlink(missing_ok=True)
        result = subprocess.run([sys.executable, str(VERIFIER), "--source", str(self.root),
            "--commit", self.commit, "--wheel", str(wheel), "--sdist", str(sdist),
            "--output", str(report)], cwd=self.output, capture_output=True, text=True, timeout=10)
        return result, json.loads(report.read_text()) if report.exists() else None

    def test_all_tracked_source_files_are_required(self):
        result, report = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(report["passed"])
        self.assertEqual(set(report["sdist_required_files"]), set(self.files))
        for omitted in ("docs/readiness-observations.json", "evidence/runs/probe/allocation-probe.py",
                        "deploy/uta.service", "config/example.json", "scripts/reproduce.py",
                        "benchmarks/results/regression.txt.gz", ".github/workflows/ci.yml", ".gitignore"):
            with self.subTest(omitted=omitted):
                result, report = self.verify(omit=omitted)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(report["passed"])
                self.assertEqual(report["sdist_missing"], [omitted])

    def test_duplicate_members_and_extra_runtime_are_rejected(self):
        for option, archive, message in (
            ("duplicate", "wheel", "duplicate wheel archive member"),
            ("duplicate", "sdist", "duplicate source distribution member"),
            ("extra", "wheel", "unexpected wheel runtime file"),
            ("extra", "sdist", "unexpected source distribution runtime file"),
        ):
            with self.subTest(option=option, archive=archive):
                result, report = self.verify(**{option: archive})
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
                self.assertIsNone(report)

    def test_mismatched_documentation_bytes_are_rejected(self):
        name = "docs/readiness-observations.json"
        result, report = self.verify(mutate=name)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["sdist_mismatched"], [name])
        self.assertFalse(report["passed"])

    def test_dirty_tracked_documentation_is_rejected(self):
        name = "docs/readiness-observations.json"
        target = self.root / name
        try:
            target.write_text("dirty tracked source\n")
            result, report = self.verify()
            self.assertEqual(result.returncode, 1)
            self.assertIn("release checkout HEAD/runtime/manifest differs", result.stderr)
            self.assertIsNone(report)
        finally:
            target.write_bytes(self.files[name])

    def test_duplicate_version_headers_are_rejected_even_when_identical(self):
        result, report = self.verify(metadata=("Version: " + self.VERSION + "\n") * 2)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report["checks"]["version"])
        self.assertEqual(report["metadata_versions"], [self.VERSION, self.VERSION])
        self.assertTrue(report["checks"]["wheel_runtime_exact"])
        self.assertTrue(report["checks"]["sdist_required_files_exact"])


class ReleaseArchiveVersionTests(ReleaseArchiveTests):
    VERSION = "0.5.0a1"

    def source_with(self, changes):
        self.files = {**type(self).files, **changes}
        number = len(list(self.output.glob("changed-source-*")))
        self.root = self.output / ("changed-source-" + str(number))
        self.commit = commit_source(self.root, self.files)

    def assert_version_rejected(self, metadata):
        result, report = self.verify(metadata=metadata)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(report["passed"])
        self.assertFalse(report["checks"]["version"])
        self.assertEqual(report["version"], self.VERSION)
        for check in ("wheel_runtime_exact", "sdist_runtime_exact", "sdist_required_files_exact"):
            self.assertTrue(report["checks"][check], check)

    def test_new_declared_version_accepts_real_archives(self):
        result, report = self.verify(metadata="Metadata-Version: 2.4\nName: uta-reference-exchange\nVersion: 0.5.0a1\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(report["passed"])
        self.assertEqual(report["version"], "0.5.0a1")
        self.assertEqual(report["metadata_versions"], ["0.5.0a1"])
        self.assertEqual(report["source_commit"], self.commit)

    def test_wrong_missing_or_duplicate_metadata_version_is_rejected(self):
        for metadata in ("Version: 0.4.0a1\n", "Name: uta-reference-exchange\n",
                         "Version: 0.5.0a1\nVersion: 0.5.0a1\n",
                         "Version: 0.5.0a1\nvErSiOn: 0.4.0a1\n",
                         "Version: 0.4.0a1\n\nDescription mentioning Version: 0.5.0a1\n"):
            with self.subTest(metadata=metadata):
                self.assert_version_rejected(metadata)

    def test_two_distribution_metadata_files_are_rejected(self):
        result, report = self.verify(second_metadata=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("exactly one METADATA", result.stderr)
        self.assertIsNone(report)

    def test_frozen_project_and_runtime_version_must_agree(self):
        for changes in ({"uta/__init__.py": b'__version__ = "0.4.0a1"\n'},
                        {"pyproject.toml": b'[project]\nversion = "0.6.0a1"\n'}):
            with self.subTest(changed=list(changes)):
                self.source_with(changes)
                result, report = self.verify()
                self.assertEqual(result.returncode, 1)
                self.assertIn("uta.__version__ differs from project.version", result.stderr)
                self.assertIsNone(report)

    def test_dynamic_duplicate_or_unsupported_project_version_is_rejected(self):
        declarations = (
            '[project]\ndynamic = ["version"]\n',
            '[project]\nversion = "0.5.0a1"\nversion = "0.5.0a1"\n',
            '[project]\nversion = "0.5.0a1"\n[project]\nversion = "0.5.0a1"\n',
            '[project]\nversion = compute_version()\n',
            '[project]\n"version" = "0.5.0a1"\n',
            '[project]\nversion = """0.5.0a1"""\n',
        )
        for declaration in declarations:
            with self.subTest(declaration=declaration):
                self.source_with({"pyproject.toml": declaration.encode()})
                result, report = self.verify()
                self.assertEqual(result.returncode, 1)
                self.assertIsNone(report)

    def test_runtime_version_declaration_is_not_executed(self):
        self.source_with({"uta/__init__.py": b'raise RuntimeError("VERSION_CODE_WAS_EXECUTED")\n__version__ = "0.5.0a1"\n'})
        result, report = self.verify()
        self.assertEqual(result.returncode, 1)
        self.assertIn("one static literal assignment", result.stderr)
        self.assertNotIn("VERSION_CODE_WAS_EXECUTED", result.stderr)
        self.assertIsNone(report)

    def test_dirty_version_declaration_is_rejected_before_artifact_checks(self):
        path = self.root / "pyproject.toml"
        try:
            path.write_text('[project]\nversion = "0.6.0a1"\n')
            result, report = self.verify()
            self.assertEqual(result.returncode, 1)
            self.assertIn("release checkout HEAD/runtime/manifest differs", result.stderr)
            self.assertIsNone(report)
        finally:
            path.write_bytes(self.files["pyproject.toml"])

    def test_untracked_project_version_cannot_supply_frozen_identity(self):
        self.files = dict(type(self).files)
        project = self.files.pop("pyproject.toml")
        self.root = self.output / "untracked-project"
        self.commit = commit_source(self.root, self.files)
        (self.root / "pyproject.toml").write_bytes(project)
        self.files["pyproject.toml"] = project
        result, report = self.verify()
        self.assertEqual(result.returncode, 1)
        self.assertIn("must track both release version declarations", result.stderr)
        self.assertIsNone(report)

    def test_untracked_source_file_is_rejected(self):
        path = self.root / "untracked-source.txt"
        try:
            path.write_text("not part of the frozen commit\n")
            result, report = self.verify()
            self.assertEqual(result.returncode, 1)
            self.assertIn("contains untracked source files", result.stderr)
            self.assertIsNone(report)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
