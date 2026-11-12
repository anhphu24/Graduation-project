#!/usr/bin/env python3
"""Self-tests for the static manifest verifier."""

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from verify_static_manifest import (  # noqa: E402
    ManifestVerificationError,
    _django_paths,
    discover_project_assets,
    verify_manifest,
)


class StaticManifestVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.source = self.root / "source"
        self.output = self.root / "output"
        self.source.mkdir()
        self.output.mkdir()
        self.assets = {
            "css/app.css": "css/app.0123456789ab.css",
            "js/app.js": "js/app.abcdef012345.js",
            "images/logo.svg": "images/logo.a1b2c3d4e5f6.svg",
            "admin/css/base.css": "admin/css/base.1234567890ab.css",
        }
        for source_name in ("css/app.css", "js/app.js", "images/logo.svg"):
            path = self.source / source_name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("source", encoding="utf-8")
        ignored = self.source / "notes.txt"
        ignored.write_text("not a static asset class checked here", encoding="utf-8")

    def write_manifest(self, paths=None, create_targets=True):
        paths = self.assets if paths is None else paths
        (self.output / "staticfiles.json").write_text(
            json.dumps({"version": "1.1", "paths": paths}),
            encoding="utf-8",
        )
        if create_targets:
            for target in paths.values():
                if target.startswith("../"):
                    continue
                path = self.output / target
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("collected", encoding="utf-8")

    def required(self):
        return discover_project_assets([self.source])

    def test_accepts_complete_hashed_manifest(self):
        self.write_manifest()
        self.assertEqual(verify_manifest(self.output, self.required()), 4)

    def test_discovers_supported_assets_and_requires_admin(self):
        self.assertEqual(self.required(), set(self.assets))

    def test_rejects_invalid_json(self):
        (self.output / "staticfiles.json").write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(ManifestVerificationError, "invalid JSON"):
            verify_manifest(self.output, self.required())

    def test_rejects_missing_mapping(self):
        paths = dict(self.assets)
        paths.pop("js/app.js")
        self.write_manifest(paths)
        with self.assertRaisesRegex(ManifestVerificationError, "mapping is missing"):
            verify_manifest(self.output, self.required())

    def test_rejects_unhashed_mapping(self):
        paths = dict(self.assets)
        paths["css/app.css"] = "css/app.css"
        self.write_manifest(paths)
        with self.assertRaisesRegex(ManifestVerificationError, "not content-hashed"):
            verify_manifest(self.output, self.required())

    def test_rejects_missing_target_file(self):
        self.write_manifest(create_targets=False)
        with self.assertRaisesRegex(ManifestVerificationError, "target file is missing"):
            verify_manifest(self.output, self.required())

    def test_rejects_unsafe_target(self):
        paths = dict(self.assets)
        paths["css/app.css"] = "../app.0123456789ab.css"
        self.write_manifest(paths)
        with self.assertRaisesRegex(ManifestVerificationError, "unsafe manifest target"):
            verify_manifest(self.output, self.required())


class StaticManifestIntegrationTests(unittest.TestCase):
    def test_django_paths_load_when_current_directory_is_not_project_root(self):
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary_directory:
            try:
                os.chdir(temporary_directory)
                static_root, source_dirs = _django_paths()
            finally:
                os.chdir(original_cwd)
        self.assertEqual(static_root, PROJECT_ROOT / "staticfiles")
        self.assertIn(PROJECT_ROOT / "static", source_dirs)

    def test_ci_collects_and_verifies_before_tests(self):
        script = (PROJECT_ROOT / "scripts" / "run_ci.sh").read_text(encoding="utf-8")
        collect = script.index("python manage.py collectstatic --noinput --clear")
        verify = script.index("python scripts/verify_static_manifest.py")
        tests = script.index("python manage.py test --verbosity 2")
        self.assertLess(collect, verify)
        self.assertLess(verify, tests)

    def test_deploy_and_rollback_verify_without_clearing_live_static(self):
        script = (PROJECT_ROOT / "scripts" / "deploy_ec2.sh").read_text(encoding="utf-8")
        self.assertNotIn("collectstatic --noinput --clear", script)
        self.assertIn(
            "elif ! verify_static_manifest; then\n"
            "                echo \"Rollback static manifest verification failed.\"",
            script,
        )
        self.assertIn(
            "django_manage collectstatic --noinput\n"
            "verify_static_manifest\n"
            "systemctl restart",
            script,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
