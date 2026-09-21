#!/usr/bin/env python3
"""Build and verify an immutable Fabric Ops Studio native release bundle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

STUDIO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = STUDIO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.project_contract import load_manifest
from app.release_bundle import build_release_bundle, verify_release_bundle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    summary = build_release_bundle(
        manifest,
        project_root=args.project_root,
        profile_name=args.profile,
        revision=args.revision,
        output_path=args.output,
    )
    verified = verify_release_bundle(args.output)
    if summary.bundle_sha256 != verified.bundle_sha256:
        raise RuntimeError("post-build verification changed bundle identity")
    print(json.dumps(summary.__dict__, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
