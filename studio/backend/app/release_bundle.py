"""Deterministic native Fabric artifact bundles.

M04 treats native Fabric definitions as opaque bytes. The bundle builder validates
only Studio's project contract and filesystem trust boundary, then packages the
exact selected files with per-file hashes. Bundles are immutable (never
overwritten), deterministic for a given revision/project/content, and contain no
publish side effect.

Publishing is intentionally absent here. Approval records bind an immutable
bundle hash, scope digest, profile and target workspace so a later runner cannot
silently expand scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from typing import Any
import zipfile

from .project_contract import (
    ProjectContractError,
    resolve_trusted_definition,
    validate_project,
)

BUNDLE_SCHEMA_VERSION = "1.0"
BUNDLE_KIND = "fabric-ops-studio-release"
MAX_BUNDLE_FILES = 20_000
MAX_BUNDLE_BYTES = 1_073_741_824
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


class ReleaseBundleError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ReleaseBundleSummary:
    path: str
    project_id: str
    profile_name: str
    revision: str
    workspace_display_name: str
    deployment_owner: str
    studio_publish_allowed: bool
    bundle_sha256: str
    scope_digest: str
    file_count: int
    total_bytes: int


@dataclass(frozen=True)
class ReleaseApproval:
    bundle_sha256: str
    scope_digest: str
    project_id: str
    profile_name: str
    revision: str
    workspace_display_name: str
    approved_at: str
    executable: bool = False


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_archive_path(value: str) -> bool:
    if not value or "\\" in value or ":" in value or value.startswith("/"):
        return False
    path = PurePosixPath(value)
    return all(part not in {"", ".", ".."} for part in path.parts)


def _zip_info(path: str) -> zipfile.ZipInfo:
    if not _safe_archive_path(path):
        raise ReleaseBundleError("bundle.unsafe_path", f"Unsafe archive path: {path}")
    info = zipfile.ZipInfo(path, _FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def _definition_files(project_root: Path, definition_path: str) -> list[tuple[str, bytes]]:
    candidate = resolve_trusted_definition(project_root, definition_path, must_exist=True)
    if candidate.is_symlink():
        raise ReleaseBundleError("bundle.symlink", f"Definition is a symlink: {definition_path}")

    files: list[tuple[str, bytes]] = []
    if candidate.is_file():
        files.append((f"project/{definition_path}", candidate.read_bytes()))
        return files
    if not candidate.is_dir():
        raise ReleaseBundleError("bundle.definition_type", f"Definition must be a file or directory: {definition_path}")

    for child in sorted(candidate.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if child.is_symlink():
            raise ReleaseBundleError("bundle.symlink", f"Symlink inside definition: {definition_path}")
        if not child.is_file():
            continue
        resolved = child.resolve(strict=True)
        try:
            relative = resolved.relative_to(project_root.resolve(strict=True)).as_posix()
        except ValueError as exc:
            raise ReleaseBundleError("bundle.path_escape", f"Definition file escaped project root: {child}") from exc
        if not _safe_archive_path(relative):
            raise ReleaseBundleError("bundle.unsafe_path", f"Unsafe definition path: {relative}")
        files.append((f"project/{relative}", child.read_bytes()))
    return files


def _resource_digest(file_entries: list[dict[str, Any]]) -> str:
    return _sha256(_canonical_json([
        {"path": item["path"], "sha256": item["sha256"], "size": item["size"]}
        for item in file_entries
    ]))


def _prepare_bundle(
    manifest: dict[str, Any],
    *,
    project_root: Path,
    profile_name: str,
    revision: str,
) -> tuple[dict[str, Any], dict[str, bytes], str]:
    validation = validate_project(manifest, profile_name=profile_name)
    if not validation.valid:
        first = validation.findings[0]
        raise ProjectContractError(first.code, first.path, first.message)
    if not revision or len(revision) > 128 or any(ord(ch) < 32 for ch in revision):
        raise ReleaseBundleError("bundle.revision", "Revision must be a non-empty printable string up to 128 characters")

    root = project_root.resolve(strict=True)
    profile = manifest["profiles"][profile_name]
    payloads: dict[str, bytes] = {}
    resource_records: list[dict[str, Any]] = []
    total_bytes = 0
    total_files = 0

    for resource in manifest["resources"]:
        record: dict[str, Any] = {
            "key": resource["key"],
            "type": resource["type"],
            "displayName": resource["displayName"],
            "management": resource["management"],
            "definitionPath": resource["definitionPath"],
            "dependsOn": list(resource["dependsOn"]),
            "included": resource["management"] == "managed",
            "files": [],
            "resourceDigest": None,
        }
        if resource["management"] == "managed":
            files = _definition_files(root, resource["definitionPath"])
            if not files:
                raise ReleaseBundleError("bundle.empty_definition", f"Managed definition has no files: {resource['definitionPath']}")
            file_records = []
            for archive_path, content in files:
                if archive_path in payloads:
                    raise ReleaseBundleError("bundle.duplicate_path", f"Duplicate bundle path: {archive_path}")
                total_files += 1
                total_bytes += len(content)
                if total_files > MAX_BUNDLE_FILES:
                    raise ReleaseBundleError("bundle.file_limit", "Bundle exceeds file-count limit")
                if total_bytes > MAX_BUNDLE_BYTES:
                    raise ReleaseBundleError("bundle.size_limit", "Bundle exceeds uncompressed size limit")
                payloads[archive_path] = content
                file_records.append({"path": archive_path, "sha256": _sha256(content), "size": len(content)})
            record["files"] = file_records
            record["resourceDigest"] = _resource_digest(file_records)
        resource_records.append(record)

    project_snapshot = _canonical_json(manifest)
    project_digest = _sha256(project_snapshot)
    payloads["release/project.json"] = project_snapshot

    descriptor = {
        "schemaVersion": BUNDLE_SCHEMA_VERSION,
        "kind": BUNDLE_KIND,
        "projectId": manifest["projectId"],
        "projectSchemaVersion": manifest["schemaVersion"],
        "profile": profile_name,
        "revision": revision,
        "target": {
            "workspaceDisplayName": profile["workspaceDisplayName"],
            "capacityRef": profile["capacityRef"],
            "identityRef": profile["identityRef"],
            "deploymentOwner": profile["deploymentOwner"],
        },
        "studioPublishAllowed": profile["deploymentOwner"] == "studio-runner",
        "projectDigest": project_digest,
        "resources": resource_records,
        "dataFlows": manifest["dataFlows"],
    }
    descriptor_bytes = _canonical_json(descriptor)
    scope_digest = _sha256(descriptor_bytes)
    descriptor["scopeDigest"] = scope_digest
    payloads["release/manifest.json"] = _canonical_json(descriptor)
    return descriptor, payloads, scope_digest


def build_release_bundle(
    manifest: dict[str, Any],
    *,
    project_root: Path,
    profile_name: str,
    revision: str,
    output_path: Path,
) -> ReleaseBundleSummary:
    descriptor, payloads, scope_digest = _prepare_bundle(
        manifest,
        project_root=project_root,
        profile_name=profile_name,
        revision=revision,
    )

    output = output_path.resolve(strict=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    fd: int | None = None
    try:
        fd = os.open(output, flags, 0o600)
        with os.fdopen(fd, "wb") as raw:
            fd = None
            with zipfile.ZipFile(raw, "w") as archive:
                for path in sorted(payloads):
                    archive.writestr(_zip_info(path), payloads[path])
    except FileExistsError as exc:
        raise ReleaseBundleError("bundle.immutable", f"Release bundle already exists and will not be overwritten: {output}") from exc
    except Exception:
        if fd is not None:
            os.close(fd)
        try:
            output.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    content = output.read_bytes()
    profile = manifest["profiles"][profile_name]
    artifact_entries = [
        entry
        for resource in descriptor["resources"]
        for entry in resource["files"]
    ]
    return ReleaseBundleSummary(
        path=str(output),
        project_id=manifest["projectId"],
        profile_name=profile_name,
        revision=revision,
        workspace_display_name=profile["workspaceDisplayName"],
        deployment_owner=profile["deploymentOwner"],
        studio_publish_allowed=profile["deploymentOwner"] == "studio-runner",
        bundle_sha256=_sha256(content),
        scope_digest=scope_digest,
        file_count=len(artifact_entries),
        total_bytes=sum(item["size"] for item in artifact_entries),
    )


def _load_verified_bundle(path: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    raw = path.read_bytes()
    try:
        with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ReleaseBundleError("bundle.duplicate_path", "Bundle contains duplicate archive paths")
            if any(not _safe_archive_path(name) for name in names):
                raise ReleaseBundleError("bundle.unsafe_path", "Bundle contains an unsafe archive path")
            if len(names) > MAX_BUNDLE_FILES + 2:
                raise ReleaseBundleError("bundle.file_limit", "Bundle exceeds file-count limit")
            total = sum(info.file_size for info in archive.infolist())
            if total > MAX_BUNDLE_BYTES + 2_000_000:
                raise ReleaseBundleError("bundle.size_limit", "Bundle exceeds uncompressed size limit")
            payloads = {name: archive.read(name) for name in names}
    except zipfile.BadZipFile as exc:
        raise ReleaseBundleError("bundle.invalid_zip", "Release bundle is not a valid ZIP archive") from exc

    if "release/manifest.json" not in payloads or "release/project.json" not in payloads:
        raise ReleaseBundleError("bundle.metadata", "Release bundle metadata is incomplete")
    try:
        descriptor = json.loads(payloads["release/manifest.json"])
        project = json.loads(payloads["release/project.json"])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseBundleError("bundle.metadata", "Release metadata must be valid UTF-8 JSON") from exc

    if descriptor.get("schemaVersion") != BUNDLE_SCHEMA_VERSION or descriptor.get("kind") != BUNDLE_KIND:
        raise ReleaseBundleError("bundle.schema", "Unsupported release bundle schema")
    if _sha256(_canonical_json(project)) != descriptor.get("projectDigest"):
        raise ReleaseBundleError("bundle.project_digest", "Project snapshot digest does not match release metadata")

    scope_copy = dict(descriptor)
    claimed_scope = scope_copy.pop("scopeDigest", None)
    actual_scope = _sha256(_canonical_json(scope_copy))
    if claimed_scope != actual_scope:
        raise ReleaseBundleError("bundle.scope_digest", "Release scope digest does not match metadata")

    expected_artifacts: set[str] = set()
    for resource in descriptor.get("resources", []):
        files = resource.get("files", [])
        if resource.get("included"):
            if not files:
                raise ReleaseBundleError("bundle.metadata", "Included resource has no files")
            if _resource_digest(files) != resource.get("resourceDigest"):
                raise ReleaseBundleError("bundle.resource_digest", f"Resource digest mismatch: {resource.get('key')}")
        elif files:
            raise ReleaseBundleError("bundle.metadata", "External resource unexpectedly contains bundled files")
        for item in files:
            artifact_path = item.get("path")
            if not isinstance(artifact_path, str) or not artifact_path.startswith("project/") or not _safe_archive_path(artifact_path):
                raise ReleaseBundleError("bundle.metadata", "Invalid artifact path in release metadata")
            expected_artifacts.add(artifact_path)
            content = payloads.get(artifact_path)
            if content is None:
                raise ReleaseBundleError("bundle.missing_artifact", f"Missing bundled artifact: {artifact_path}")
            if len(content) != item.get("size") or _sha256(content) != item.get("sha256"):
                raise ReleaseBundleError("bundle.artifact_digest", f"Artifact digest mismatch: {artifact_path}")

    actual_artifacts = {name for name in payloads if name.startswith("project/")}
    if actual_artifacts != expected_artifacts:
        raise ReleaseBundleError("bundle.scope_extra", "Bundle artifact set differs from reviewed release scope")
    allowed = expected_artifacts | {"release/manifest.json", "release/project.json"}
    if set(payloads) != allowed:
        raise ReleaseBundleError("bundle.scope_extra", "Bundle contains unreviewed files")
    return descriptor, payloads


def verify_release_bundle(path: Path) -> ReleaseBundleSummary:
    descriptor, payloads = _load_verified_bundle(path)
    raw = path.read_bytes()
    artifact_entries = [
        entry
        for resource in descriptor["resources"]
        for entry in resource["files"]
    ]
    target = descriptor["target"]
    return ReleaseBundleSummary(
        path=str(path.resolve(strict=True)),
        project_id=descriptor["projectId"],
        profile_name=descriptor["profile"],
        revision=descriptor["revision"],
        workspace_display_name=target["workspaceDisplayName"],
        deployment_owner=target["deploymentOwner"],
        studio_publish_allowed=bool(descriptor["studioPublishAllowed"]),
        bundle_sha256=_sha256(raw),
        scope_digest=descriptor["scopeDigest"],
        file_count=len(artifact_entries),
        total_bytes=sum(item["size"] for item in artifact_entries),
    )


def approval_challenge(summary: ReleaseBundleSummary) -> str:
    return (
        f"APPROVE {summary.bundle_sha256[:12]} "
        f"{summary.project_id}/{summary.profile_name} "
        f"{summary.workspace_display_name} "
        f"{summary.revision}"
    )


def approve_release(summary: ReleaseBundleSummary, confirmation: str) -> ReleaseApproval:
    if not summary.studio_publish_allowed or summary.deployment_owner != "studio-runner":
        raise ReleaseBundleError(
            "approval.deployment_owner",
            "Studio publish approval is forbidden because this profile is owned by native-git",
        )
    expected = approval_challenge(summary)
    if confirmation != expected:
        raise ReleaseBundleError("approval.confirmation", "Approval text does not match the exact immutable release target")
    return ReleaseApproval(
        bundle_sha256=summary.bundle_sha256,
        scope_digest=summary.scope_digest,
        project_id=summary.project_id,
        profile_name=summary.profile_name,
        revision=summary.revision,
        workspace_display_name=summary.workspace_display_name,
        approved_at=datetime.now(timezone.utc).isoformat(),
        executable=False,
    )


def import_release_bundle(bundle_path: Path, destination_root: Path) -> Path:
    """Import a verified Studio release into a new local project directory.

    The destination must not already exist. Extraction occurs in a sibling staging
    directory and is renamed into place only after every file has been written.
    """
    descriptor, payloads = _load_verified_bundle(bundle_path)
    destination = destination_root.resolve(strict=False)
    if destination.exists():
        raise ReleaseBundleError("import.destination_exists", "Import destination already exists")

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.import-", dir=destination.parent))
    try:
        project_snapshot = json.loads(payloads["release/project.json"])
        (staging / "fabric-project.json").write_bytes(_canonical_json(project_snapshot))
        for name, content in sorted(payloads.items()):
            if not name.startswith("project/"):
                continue
            relative = PurePosixPath(name).relative_to("project")
            target = staging.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(content)
        descriptor_copy = staging / ".studio-release.json"
        descriptor_copy.write_bytes(_canonical_json(descriptor))
        staging.rename(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination
