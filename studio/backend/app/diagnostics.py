from __future__ import annotations

import platform
import shutil
import sys
from collections import Counter
from pathlib import Path

from .catalog import combined_catalog
from .providers.microsoftfabricmgmt import REPO_ROOT, UPSTREAM_SESSION_PATH, runtime


def _check(name: str, ok: bool, detail: str, required: bool = True) -> dict:
    return {
        "name": name,
        "ok": ok,
        "required": required,
        "detail": detail,
    }


def _compatibility_report(catalog: list) -> dict:
    ids = [item.id for item in catalog]
    id_counts = Counter(ids)
    duplicates = sorted(item_id for item_id, count in id_counts.items() if count > 1)
    catalog_ids = set(ids)
    issues: list[dict[str, str]] = []
    local_sources_checked = 0
    local_sources_missing = 0

    for item in catalog:
        if item.verification_capability_id and item.verification_capability_id not in catalog_ids:
            issues.append({
                "severity": "error",
                "capability_id": item.id,
                "message": f"Verification capability {item.verification_capability_id} is not registered.",
            })

        if item.execution_policy == "guarded-write":
            if item.risk != "write":
                issues.append({
                    "severity": "error",
                    "capability_id": item.id,
                    "message": "guarded-write policy is only valid for write-risk capabilities.",
                })
            if not item.supports_whatif:
                issues.append({
                    "severity": "warning",
                    "capability_id": item.id,
                    "message": "Guarded write does not advertise upstream -WhatIf support.",
                })

        if item.provider == "Fabric REST API" and item.execution_policy == "read":
            if not item.endpoint or not item.endpoint.startswith("/v1/"):
                issues.append({
                    "severity": "error",
                    "capability_id": item.id,
                    "message": "Registered Fabric REST read is missing a /v1/ endpoint.",
                })

        if item.source_path:
            source_path = Path(item.source_path)
            if not source_path.is_absolute():
                source_path = REPO_ROOT / source_path
            # Only treat repository-local paths as compatibility assertions. Descriptive transport strings are ignored.
            try:
                source_path.relative_to(REPO_ROOT)
            except ValueError:
                continue
            if any(token in item.source_path for token in [" -> ", "http://", "https://"]):
                continue
            local_sources_checked += 1
            if not source_path.exists():
                local_sources_missing += 1
                issues.append({
                    "severity": "warning",
                    "capability_id": item.id,
                    "message": f"Declared source path does not exist: {item.source_path}",
                })

    for duplicate in duplicates:
        issues.append({
            "severity": "error",
            "capability_id": duplicate,
            "message": "Capability ID is duplicated in the combined catalog.",
        })

    errors = sum(1 for issue in issues if issue["severity"] == "error")
    warnings = sum(1 for issue in issues if issue["severity"] == "warning")
    return {
        "status": "compatible" if errors == 0 else "incompatible",
        "errors": errors,
        "warnings": warnings,
        "duplicate_ids": duplicates,
        "local_sources_checked": local_sources_checked,
        "local_sources_missing": local_sources_missing,
        "issues": issues[:100],
    }


def collect_diagnostics() -> dict:
    ps_source = REPO_ROOT / "tools" / "MicrosoftFabricMgmt" / "source" / "Public"
    built_manifests = list(
        (REPO_ROOT / "tools" / "MicrosoftFabricMgmt" / "output" / "module" / "MicrosoftFabricMgmt").glob(
            "*/MicrosoftFabricMgmt.psd1"
        )
    )
    security_tool = REPO_ROOT / "tools" / "fabric-security-audit" / "Invoke-FabricSecurityAudit.ps1"
    assessment_tool = REPO_ROOT / "tools" / "fabric-assessment-tool" / "pyproject.toml"
    lineage_tool = REPO_ROOT / "tools" / "Lineage_Extractor" / "Fabric-notebook"

    pwsh = shutil.which("pwsh")
    az = shutil.which("az")
    catalog = combined_catalog()
    providers = Counter(item.provider for item in catalog)
    risks = Counter(item.risk for item in catalog)
    policies = Counter(item.execution_policy or "unset" for item in catalog)
    guarded = [item for item in catalog if item.execution_policy == "guarded-write"]
    guarded_whatif = [item for item in guarded if item.supports_whatif]
    compatibility = _compatibility_report(catalog)

    checks = [
        _check("PowerShell 7", bool(pwsh), pwsh or "pwsh was not found on PATH"),
        _check("MicrosoftFabricMgmt source", ps_source.is_dir(), str(ps_source)),
        _check("Persistent PowerShell adapter", UPSTREAM_SESSION_PATH.is_file(), str(UPSTREAM_SESSION_PATH)),
        _check(
            "Built MicrosoftFabricMgmt module",
            bool(built_manifests),
            str(built_manifests[-1]) if built_manifests else "No built MicrosoftFabricMgmt.psd1 found",
        ),
        _check(
            "Guarded write allowlist",
            bool(guarded) and len(guarded) == len(guarded_whatif),
            f"{len(guarded)} guarded capabilities; {len(guarded_whatif)} expose upstream -WhatIf validation",
        ),
        _check(
            "Capability compatibility",
            compatibility["errors"] == 0,
            f"{compatibility['errors']} errors; {compatibility['warnings']} warnings; {compatibility['local_sources_checked']} local source declarations checked",
        ),
        _check("Azure CLI", bool(az), az or "az was not found on PATH; only required by some specialized tools", required=False),
        _check("Fabric Security Audit", security_tool.is_file(), str(security_tool), required=False),
        _check("Fabric Assessment Tool", assessment_tool.is_file(), str(assessment_tool), required=False),
        _check("Lineage Extractor notebook", lineage_tool.is_dir(), str(lineage_tool), required=False),
    ]

    required_ok = all(check["ok"] for check in checks if check["required"])
    return {
        "status": "ready" if required_ok else "degraded",
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "session": runtime.status().model_dump(),
        "catalog": {
            "total": len(catalog),
            "providers": dict(sorted(providers.items())),
            "risks": dict(sorted(risks.items())),
            "policies": dict(sorted(policies.items())),
        },
        "compatibility": compatibility,
        "checks": checks,
    }
