from __future__ import annotations

from pathlib import Path

from .providers.microsoftfabricmgmt import REPO_ROOT


_TOOL_SPECS = [
    {
        "id": "fabric-security-audit",
        "name": "Fabric Security Audit",
        "category": "Security",
        "upstream_path": "tools/fabric-security-audit",
        "entrypoint": "tools/fabric-security-audit/Invoke-FabricSecurityAudit.ps1",
        "execution_kind": "powershell-script",
        "status": "preview-only",
        "risk": "admin",
        "description": "Audits Warehouse and Lakehouse SQL Endpoint access across workspace roles, item sharing, OneLake security, Graph identity data and SQL permissions.",
        "prerequisites": [
            "PowerShell 7",
            "Az.Accounts",
            "Fabric workspace Admin or Member permissions",
            "Microsoft Graph read permissions for user/group investigation",
            "SQL endpoint permissions for SQL security checks",
        ],
        "example": ".\\Invoke-FabricSecurityAudit.ps1 -Url '<fabric-or-powerbi-url>' -NoPrompt",
        "reason": "Catalogued but not launched generically because it can authenticate to Fabric, Graph and SQL, creates report files, and can require elevated permissions.",
    },
    {
        "id": "fabric-assessment-tool",
        "name": "Fabric Assessment Tool",
        "category": "Assessment",
        "upstream_path": "tools/fabric-assessment-tool",
        "entrypoint": "fat assess",
        "execution_kind": "python-cli",
        "status": "preview-only",
        "risk": "admin",
        "description": "Migration assessment CLI for inventorying Synapse and Databricks estates and exporting structured assessment data for Fabric migration planning.",
        "prerequisites": [
            "Python 3.10-3.12",
            "Install fabric-assessment-tool package or bundled wheel",
            "Azure CLI login for local execution, or Fabric notebook authentication",
            "Source-platform permissions appropriate to the assessment",
        ],
        "example": "fat assess --source synapse --mode full --ws <workspace> -o <output_path>",
        "reason": "Catalogued as a dedicated migration workflow; it has its own package, authentication modes, dependencies and output lifecycle and should not be flattened into the generic command executor.",
    },
    {
        "id": "lineage-extractor",
        "name": "Fabric Lineage Extractor",
        "category": "Lineage",
        "upstream_path": "tools/Lineage_Extractor",
        "entrypoint": "tools/Lineage_Extractor/Fabric-notebook",
        "execution_kind": "fabric-notebook",
        "status": "external-notebook",
        "risk": "admin",
        "description": "Notebook-based metadata and column-level lineage extraction for Lakehouses, Warehouses, reports and Copy Activities, with optional publication to Microsoft Purview.",
        "prerequisites": [
            "Import the supplied notebook into a Fabric workspace",
            "Fabric API access for the configured identity",
            "SQL access for table and column metadata",
            "Purview permissions when publishing lineage",
            "Secure secret storage for production usage",
        ],
        "example": "Import the notebook from tools/Lineage_Extractor/Fabric-notebook into Microsoft Fabric.",
        "reason": "The upstream implementation is notebook-oriented and includes Fabric/Purview configuration. Studio exposes the workflow and prerequisites but does not execute notebook cells locally.",
    },
]


def list_specialized_tools() -> list[dict]:
    tools: list[dict] = []
    for spec in _TOOL_SPECS:
        item = dict(spec)
        path = REPO_ROOT / item["upstream_path"]
        entrypoint = item["entrypoint"]
        if entrypoint.startswith("tools/"):
            entrypoint_exists = (REPO_ROOT / entrypoint).exists()
        else:
            entrypoint_exists = path.exists()
        item["available"] = path.exists() and entrypoint_exists
        tools.append(item)
    return tools
