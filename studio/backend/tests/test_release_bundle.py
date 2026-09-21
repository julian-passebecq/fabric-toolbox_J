from __future__ import annotations

from copy import deepcopy
import io
import json
from pathlib import Path
import zipfile

import pytest

from app.project_contract import load_manifest
from app.release_bundle import (
    ReleaseBundleError,
    approval_challenge,
    approve_release,
    build_release_bundle,
    import_release_bundle,
    verify_release_bundle,
)

STUDIO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = STUDIO_ROOT / "examples" / "fabric-project" / "foil.project.json"


def project():
    return load_manifest(EXAMPLE)


def materialize(root: Path, manifest: dict):
    for resource in manifest["resources"]:
        if resource["management"] != "managed":
            continue
        target = root / resource["definitionPath"]
        target.mkdir(parents=True, exist_ok=True)
        (target / "definition.json").write_text(json.dumps({"key": resource["key"]}), encoding="utf-8")
    binary = root / manifest["resources"][0]["definitionPath"] / "opaque.bin"
    binary.write_bytes(b"native\x00fabric\xffbytes")
    return binary


def test_bundle_is_deterministic_immutable_and_verifiable(tmp_path):
    manifest = project()
    root = tmp_path / "project"; root.mkdir()
    materialize(root, manifest)

    first = build_release_bundle(manifest, project_root=root, profile_name="dev", revision="abc123", output_path=tmp_path / "one.zip")
    second = build_release_bundle(manifest, project_root=root, profile_name="dev", revision="abc123", output_path=tmp_path / "two.zip")
    assert first.bundle_sha256 == second.bundle_sha256
    assert (tmp_path / "one.zip").read_bytes() == (tmp_path / "two.zip").read_bytes()
    assert verify_release_bundle(tmp_path / "one.zip").scope_digest == first.scope_digest

    with pytest.raises(ReleaseBundleError) as error:
        build_release_bundle(manifest, project_root=root, profile_name="dev", revision="abc123", output_path=tmp_path / "one.zip")
    assert error.value.code == "bundle.immutable"


def test_native_artifact_round_trip_preserves_opaque_bytes(tmp_path):
    manifest = project()
    root = tmp_path / "project"; root.mkdir()
    binary = materialize(root, manifest)
    expected = binary.read_bytes()

    bundle = tmp_path / "release.zip"
    build_release_bundle(manifest, project_root=root, profile_name="dev", revision="r1", output_path=bundle)
    imported = import_release_bundle(bundle, tmp_path / "imported")
    imported_binary = imported / binary.relative_to(root)
    assert imported_binary.read_bytes() == expected
    assert load_manifest(imported / "fabric-project.json") == manifest
    assert (imported / ".studio-release.json").is_file()


def test_tampered_native_artifact_is_rejected(tmp_path):
    manifest = project()
    root = tmp_path / "project"; root.mkdir()
    materialize(root, manifest)
    bundle = tmp_path / "release.zip"
    build_release_bundle(manifest, project_root=root, profile_name="dev", revision="r1", output_path=bundle)

    source = zipfile.ZipFile(bundle, "r")
    entries = {name: source.read(name) for name in source.namelist()}
    source.close()
    artifact = next(name for name in entries if name.startswith("project/"))
    entries[artifact] = b"tampered"
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(tampered, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)

    with pytest.raises(ReleaseBundleError) as error:
        verify_release_bundle(tampered)
    assert error.value.code == "bundle.artifact_digest"


def test_bundle_rejects_symlinks_inside_native_definition(tmp_path):
    manifest = project()
    root = tmp_path / "project"; root.mkdir()
    materialize(root, manifest)
    definition = root / manifest["resources"][0]["definitionPath"]
    outside = tmp_path / "outside.txt"; outside.write_text("outside", encoding="utf-8")
    link = definition / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ReleaseBundleError) as error:
        build_release_bundle(manifest, project_root=root, profile_name="dev", revision="r1", output_path=tmp_path / "release.zip")
    assert error.value.code == "bundle.symlink"


def test_approval_binds_exact_bundle_scope_profile_target_and_revision(tmp_path):
    manifest = project()
    root = tmp_path / "project"; root.mkdir()
    materialize(root, manifest)
    summary = build_release_bundle(manifest, project_root=root, profile_name="dev", revision="git:abc", output_path=tmp_path / "release.zip")

    with pytest.raises(ReleaseBundleError) as wrong:
        approve_release(summary, "APPROVE something else")
    assert wrong.value.code == "approval.confirmation"

    approval = approve_release(summary, approval_challenge(summary))
    assert approval.bundle_sha256 == summary.bundle_sha256
    assert approval.scope_digest == summary.scope_digest
    assert approval.profile_name == "dev"
    assert approval.workspace_display_name == "foil-dev"
    assert approval.revision == "git:abc"
    assert approval.executable is False


def test_native_git_owned_profile_cannot_receive_studio_publish_approval(tmp_path):
    manifest = project()
    manifest["profiles"]["dev"]["deploymentOwner"] = "native-git"
    root = tmp_path / "project"; root.mkdir()
    materialize(root, manifest)
    summary = build_release_bundle(manifest, project_root=root, profile_name="dev", revision="r1", output_path=tmp_path / "release.zip")
    assert summary.studio_publish_allowed is False
    with pytest.raises(ReleaseBundleError) as error:
        approve_release(summary, approval_challenge(summary))
    assert error.value.code == "approval.deployment_owner"


def test_import_rejects_existing_destination(tmp_path):
    manifest = project()
    root = tmp_path / "project"; root.mkdir()
    materialize(root, manifest)
    bundle = tmp_path / "release.zip"
    build_release_bundle(manifest, project_root=root, profile_name="dev", revision="r1", output_path=bundle)
    destination = tmp_path / "existing"; destination.mkdir()
    with pytest.raises(ReleaseBundleError) as error:
        import_release_bundle(bundle, destination)
    assert error.value.code == "import.destination_exists"


def test_verifier_rejects_zip_slip_paths(tmp_path):
    malicious = tmp_path / "malicious.zip"
    with zipfile.ZipFile(malicious, "w") as archive:
        archive.writestr("../escape.txt", b"escape")
        archive.writestr("release/manifest.json", b"{}")
        archive.writestr("release/project.json", b"{}")
    with pytest.raises(ReleaseBundleError) as error:
        verify_release_bundle(malicious)
    assert error.value.code == "bundle.unsafe_path"
