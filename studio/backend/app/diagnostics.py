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
        "checks": checks,
    }
