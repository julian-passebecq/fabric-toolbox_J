#!/usr/bin/env python3
"""Offline native release bundle CLI. There is deliberately no publish command."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

STUDIO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = STUDIO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.project_contract import load_manifest
from app.release_bundle import (
    approval_challenge,
    approve_release,
    build_release_bundle,
    import_release_bundle,
    verify_release_bundle,
)


def emit(value) -> None:
    print(json.dumps(asdict(value) if hasattr(value, "__dataclass_fields__") else value, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument("manifest", type=Path)
    build.add_argument("--project-root", type=Path, required=True)
    build.add_argument("--profile", required=True)
    build.add_argument("--revision", required=True)
    build.add_argument("--output", type=Path, required=True)

    verify = sub.add_parser("verify")
    verify.add_argument("bundle", type=Path)

    inspect = sub.add_parser("challenge")
    inspect.add_argument("bundle", type=Path)

    approve = sub.add_parser("approve")
    approve.add_argument("bundle", type=Path)
    approve.add_argument("--confirmation", required=True)

    imp = sub.add_parser("import")
    imp.add_argument("bundle", type=Path)
    imp.add_argument("--destination", type=Path, required=True)

    args = parser.parse_args()

    if args.command == "build":
        manifest = load_manifest(args.manifest)
        emit(build_release_bundle(
            manifest,
            project_root=args.project_root,
            profile_name=args.profile,
            revision=args.revision,
            output_path=args.output,
        ))
        return 0
    if args.command == "verify":
        emit(verify_release_bundle(args.bundle))
        return 0
    if args.command == "challenge":
        print(approval_challenge(verify_release_bundle(args.bundle)))
        return 0
    if args.command == "approve":
        summary = verify_release_bundle(args.bundle)
        emit(approve_release(summary, args.confirmation))
        return 0
    if args.command == "import":
        destination = import_release_bundle(args.bundle, args.destination)
        emit({"destination": str(destination), "imported": True})
        return 0
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
