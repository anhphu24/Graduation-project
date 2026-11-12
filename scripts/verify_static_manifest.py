#!/usr/bin/env python3
"""Verify that collectstatic produced a complete hashed static manifest."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Iterable


ASSET_SUFFIXES = {
    ".avif",
    ".css",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".png",
    ".svg",
    ".webp",
}
ALWAYS_REQUIRED = {"admin/css/base.css"}
HASHED_NAME = re.compile(r"\.[0-9a-f]{12}\.[^./]+$")


class ManifestVerificationError(RuntimeError):
    """Raised when a static manifest cannot safely serve required assets."""


def discover_project_assets(source_dirs: Iterable[Path]) -> set[str]:
    """Return CSS, JavaScript, and image keys below configured source roots."""
    required: set[str] = set()
    found_source_dir = False
    for source_dir in source_dirs:
        source_dir = source_dir.resolve()
        if not source_dir.is_dir():
            raise ManifestVerificationError(
                f"configured static source directory is unavailable: {source_dir}"
            )
        found_source_dir = True
        for asset in source_dir.rglob("*"):
            if asset.is_file() and asset.suffix.lower() in ASSET_SUFFIXES:
                required.add(asset.relative_to(source_dir).as_posix())
    if not found_source_dir:
        raise ManifestVerificationError("no project static source directory is configured")
    return required | ALWAYS_REQUIRED


def _safe_target_path(static_root: Path, target: str) -> Path:
    pure_target = PurePosixPath(target)
    if pure_target.is_absolute() or ".." in pure_target.parts:
        raise ManifestVerificationError(f"unsafe manifest target: {target}")
    target_path = static_root.joinpath(*pure_target.parts).resolve()
    try:
        target_path.relative_to(static_root.resolve())
    except ValueError as exc:
        raise ManifestVerificationError(f"unsafe manifest target: {target}") from exc
    return target_path


def verify_manifest(static_root: Path, required_keys: Iterable[str]) -> int:
    """Validate required mappings and return the number of checked assets."""
    static_root = static_root.resolve()
    manifest_path = static_root / "staticfiles.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestVerificationError("staticfiles.json is missing") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestVerificationError("staticfiles.json is unreadable or invalid JSON") from exc

    paths = manifest.get("paths")
    if not isinstance(paths, dict):
        raise ManifestVerificationError("staticfiles.json has no paths mapping")

    required = sorted(set(required_keys))
    if not required:
        raise ManifestVerificationError("no required static assets were supplied")

    for source in required:
        target = paths.get(source)
        if not isinstance(target, str) or not target:
            raise ManifestVerificationError(f"required manifest mapping is missing: {source}")
        if source == target or not HASHED_NAME.search(PurePosixPath(target).name):
            raise ManifestVerificationError(f"manifest target is not content-hashed: {source}")
        if PurePosixPath(source).suffix.lower() != PurePosixPath(target).suffix.lower():
            raise ManifestVerificationError(f"manifest target extension changed: {source}")
        target_path = _safe_target_path(static_root, target)
        if not target_path.is_file():
            raise ManifestVerificationError(f"manifest target file is missing: {source}")

    return len(required)


def _django_paths() -> tuple[Path, list[Path]]:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from django.conf import settings

    return Path(settings.STATIC_ROOT), [Path(value) for value in settings.STATICFILES_DIRS]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--static-root", type=Path)
    parser.add_argument("--source-dir", action="append", type=Path, dest="source_dirs")
    args = parser.parse_args(argv)
    if (args.static_root is None) != (args.source_dirs is None):
        parser.error("--static-root and --source-dir must be supplied together")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.static_root is None:
            static_root, source_dirs = _django_paths()
        else:
            static_root, source_dirs = args.static_root, args.source_dirs
        required = discover_project_assets(source_dirs)
        checked = verify_manifest(static_root, required)
    except ManifestVerificationError as exc:
        print(f"FAIL: static manifest verification: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: static manifest verified ({checked} required assets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
