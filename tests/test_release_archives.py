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


class ReleaseArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name) / "source"
        cls.root.mkdir()
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
            "uta/__init__.py": b'__version__ = "0.4.0a1"\n',
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
        for name, content in cls.files.items():
            target = cls.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        def git(*args):
            return subprocess.check_output(["git", *args], cwd=cls.root, text=True).strip()
        git("init", "--quiet")
        git("add", ".")
        git("-c", "user.name=Release Fixture", "-c", "user.email=fixture@example.invalid",
            "commit", "--quiet", "-m", "synthetic artifact source")
        cls.commit = git("rev-parse", "HEAD")

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)

    def archives(self, *, omit=None, mutate=None, duplicate=None, extra=None):
        wheel = self.output / "release.whl"
        sdist = self.output / "release.tar.gz"
        with zipfile.ZipFile(wheel, "w") as archive:
            for name, content in self.files.items():
                if name.startswith("uta/"):
                    archive.writestr(name, content)
            archive.writestr("uta-0.4.0a1.dist-info/METADATA", "Version: 0.4.0a1\n")
            archive.writestr("uta-0.4.0a1.dist-info/entry_points.txt", "[console_scripts]\n"
                "uta = uta.__main__:main\nuta-ops = uta.ops:main\nuta-durable = uta.durable_cli:main\n")
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
                info = tarfile.TarInfo("uta-0.4.0a1/" + name)
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


if __name__ == "__main__":
    unittest.main()
