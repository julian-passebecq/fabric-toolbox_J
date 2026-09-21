"""Offline Fabric Ops Studio project contract and trust validation.

This module is intentionally independent from Fabric providers. A valid manifest is
only a design contract; it is never deployment authorization or evidence of tenant
support. Native Fabric definitions remain opaque files owned by the project repo.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

import yaml

STUDIO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = STUDIO_ROOT / "contracts" / "project.schema.json"
MAX_MANIFEST_BYTES = 1_048_576


@dataclass(frozen=True)
class ProjectFinding:
    severity: str
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class ProjectValidation:
    project: dict[str, Any] | None
    findings: tuple[ProjectFinding, ...]
    deployable: bool = False

    @property
    def valid(self) -> bool:
        return not any(f.severity == "error" for f in self.findings)


class ProjectContractError(ValueError):
    def __init__(self, code: str, path: str, message: str):
        super().__init__(message)
        self.code = code
        self.path = path
        self.message = message


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProjectContractError("parse.duplicate_key", "$", f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ProjectContractError("parse.nonfinite", "$", f"Non-JSON numeric constant: {value}")


class _StrictYamlLoader(yaml.SafeLoader):
    pass


def _strict_yaml_mapping(loader: _StrictYamlLoader, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key == "<<":
            raise ProjectContractError("parse.yaml_merge", "$", "YAML merge keys are not supported")
        if not isinstance(key, str):
            raise ProjectContractError("parse.yaml_key", "$", "YAML mapping keys must be strings")
        if key in mapping:
            raise ProjectContractError("parse.duplicate_key", "$", f"Duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_StrictYamlLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _strict_yaml_mapping,
)


def _reject_yaml_aliases(text: str) -> None:
    try:
        for event in yaml.parse(text):
            if isinstance(event, yaml.events.AliasEvent) or getattr(event, "anchor", None):
                raise ProjectContractError(
                    "parse.yaml_alias", "$", "YAML anchors and aliases are not supported in project manifests"
                )
    except yaml.YAMLError as exc:
        raise ProjectContractError("parse.yaml", "$", f"Invalid YAML: {exc}") from exc


def load_manifest(path: Path) -> dict[str, Any]:
    """Load JSON/YAML with duplicate-key and size checks; never calls Fabric."""
    raw = path.read_bytes()
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ProjectContractError("parse.size", "$", "Manifest exceeds 1 MiB limit")
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise ProjectContractError("parse.encoding", "$", "Manifest must be UTF-8") from exc

    suffix = path.suffix.casefold()
    try:
        if suffix == ".json":
            value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        elif suffix in {".yaml", ".yml"}:
            _reject_yaml_aliases(text)
            value = yaml.load(text, Loader=_StrictYamlLoader)
        else:
            raise ProjectContractError("parse.extension", "$", "Manifest must use .json, .yaml, or .yml")
    except ProjectContractError:
        raise
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ProjectContractError("parse.syntax", "$", f"Invalid manifest syntax: {exc}") from exc
    if not isinstance(value, dict):
        raise ProjectContractError("schema.type", "$", "Manifest root must be an object")
    return value


def load_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open("r", encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)


def _path_join(base: str, part: str | int) -> str:
    return f"{base}/{part}" if base != "$" else f"$/{part}"


def _matches_type(value: Any, type_name: str) -> bool:
    if type_name == "object":
        return isinstance(value, dict)
    if type_name == "array":
        return isinstance(value, list)
    if type_name == "string":
        return isinstance(value, str)
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "boolean":
        return isinstance(value, bool)
    return True


def _schema_findings(value: Any, schema: dict[str, Any], path: str = "$") -> list[ProjectFinding]:
    findings: list[ProjectFinding] = []

    expected = schema.get("type")
    if expected and not _matches_type(value, expected):
        return [ProjectFinding("error", "schema.type", path, f"Expected {expected}")]

    if "const" in schema and value != schema["const"]:
        findings.append(ProjectFinding("error", "schema.const", path, f"Expected {schema['const']!r}"))
    if "enum" in schema and value not in schema["enum"]:
        findings.append(ProjectFinding("error", "schema.enum", path, "Value is not in the allowed set"))

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            findings.append(ProjectFinding("error", "schema.min_length", path, "String is too short"))
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            findings.append(ProjectFinding("error", "schema.max_length", path, "String is too long"))
        if pattern := schema.get("pattern"):
            if re.fullmatch(pattern, value) is None:
                findings.append(ProjectFinding("error", "schema.pattern", path, "String does not match required pattern"))

    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            findings.append(ProjectFinding("error", "schema.minimum", path, "Integer is below minimum"))
        if "maximum" in schema and value > schema["maximum"]:
            findings.append(ProjectFinding("error", "schema.maximum", path, "Integer exceeds maximum"))

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            findings.append(ProjectFinding("error", "schema.min_items", path, "Array has too few items"))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            findings.append(ProjectFinding("error", "schema.max_items", path, "Array has too many items"))
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in value]
            if len(encoded) != len(set(encoded)):
                findings.append(ProjectFinding("error", "schema.unique", path, "Array items must be unique"))
        if item_schema := schema.get("items"):
            for index, item in enumerate(value):
                findings.extend(_schema_findings(item, item_schema, _path_join(path, index)))

    if isinstance(value, dict):
        if "minProperties" in schema and len(value) < schema["minProperties"]:
            findings.append(ProjectFinding("error", "schema.min_properties", path, "Object has too few properties"))
        if "maxProperties" in schema and len(value) > schema["maxProperties"]:
            findings.append(ProjectFinding("error", "schema.max_properties", path, "Object has too many properties"))
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                findings.append(ProjectFinding("error", "schema.required", _path_join(path, key), "Required field is missing"))
        if name_schema := schema.get("propertyNames"):
            for key in value:
                findings.extend(_schema_findings(key, name_schema, _path_join(path, key)))
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            child_schema = properties.get(key)
            if child_schema is None:
                if additional is False:
                    findings.append(ProjectFinding("error", "schema.unknown_field", _path_join(path, key), "Unknown field"))
                    continue
                if isinstance(additional, dict):
                    child_schema = additional
            if child_schema:
                findings.extend(_schema_findings(item, child_schema, _path_join(path, key)))
    return findings


_RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}


def safe_relative_path(value: str) -> bool:
    if not value or value.startswith(("/", "\\")) or "\\" in value or ":" in value:
        return False
    parts = value.split("/")
    if any(part in {"", ".", ".."} or part.endswith((" ", ".")) for part in parts):
        return False
    if any(any(ord(char) < 32 or char in '<>"|?*' for char in part) for part in parts):
        return False
    if any(part.split(".")[0].casefold() in _RESERVED or part.casefold() == ".git" for part in parts):
        return False
    return True


def _contains_hidden_credential(value: Any, path: str = "$") -> list[ProjectFinding]:
    findings: list[ProjectFinding] = []
    sensitive_keys = re.compile(r"(^|_)(password|passwd|secret|token|api.?key|access.?key|connection.?string|client.?secret)($|_)", re.I)
    strong_value = re.compile(r"(AccountKey=|SharedAccessSignature=|Authorization:\s*Bearer|-----BEGIN [A-Z ]*PRIVATE KEY-----|client_secret=)", re.I)
    if isinstance(value, dict):
        for key, item in value.items():
            child = _path_join(path, key)
            if sensitive_keys.search(key):
                findings.append(ProjectFinding("error", "security.inline_credential", child, "Credential-like fields are not allowed; use a reference"))
            findings.extend(_contains_hidden_credential(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_contains_hidden_credential(item, _path_join(path, index)))
    elif isinstance(value, str) and strong_value.search(value):
        findings.append(ProjectFinding("error", "security.inline_credential", path, "Inline credential material is not allowed"))
    return findings


def _semantic_findings(manifest: dict[str, Any], profile_name: str | None = None) -> list[ProjectFinding]:
    findings: list[ProjectFinding] = []
    resources = manifest["resources"]
    keys = [resource["key"] for resource in resources]
    known = set(keys)
    if len(keys) != len(known):
        findings.append(ProjectFinding("error", "resource.duplicate_key", "$/resources", "Logical resource keys must be unique"))

    seen_paths: set[str] = set()
    for index, resource in enumerate(resources):
        resource_path = f"$/resources/{index}"
        definition = resource["definitionPath"]
        if not safe_relative_path(definition):
            findings.append(ProjectFinding("error", "path.unsafe", f"{resource_path}/definitionPath", "Definition path is not a trusted relative path"))
        folded = definition.casefold()
        if folded in seen_paths:
            findings.append(ProjectFinding("error", "path.duplicate", f"{resource_path}/definitionPath", "Definition path is duplicated (case-insensitive)"))
        seen_paths.add(folded)
        for dep in resource["dependsOn"]:
            if dep not in known:
                findings.append(ProjectFinding("error", "dependency.missing", f"{resource_path}/dependsOn", f"Unknown dependency: {dep}"))
            elif dep == resource["key"]:
                findings.append(ProjectFinding("error", "dependency.self", f"{resource_path}/dependsOn", "Resource cannot depend on itself"))

    pending = {resource["key"]: set(resource["dependsOn"]) & known for resource in resources}
    while pending:
        ready = [key for key, deps in pending.items() if not deps]
        if not ready:
            findings.append(ProjectFinding("error", "dependency.cycle", "$/resources", "Provisioning dependency cycle detected"))
            break
        for key in ready:
            del pending[key]
        for deps in pending.values():
            deps.difference_update(ready)

    edges: set[tuple[str, str, str]] = set()
    for index, edge in enumerate(manifest["dataFlows"]):
        edge_path = f"$/dataFlows/{index}"
        if edge["from"] not in known or edge["to"] not in known:
            findings.append(ProjectFinding("error", "flow.unknown_endpoint", edge_path, "Data-flow endpoint is not a known resource"))
        if edge["from"] == edge["to"]:
            findings.append(ProjectFinding("error", "flow.self", edge_path, "Data-flow edge cannot target itself"))
        edge_key = (edge["from"], edge["to"], edge["kind"])
        if edge_key in edges:
            findings.append(ProjectFinding("error", "flow.duplicate", edge_path, "Duplicate data-flow edge"))
        edges.add(edge_key)

    for name, profile in manifest["profiles"].items():
        if profile["deploymentOwner"] == "native-git" and name != "dev":
            findings.append(ProjectFinding("error", "profile.native_git_scope", f"$/profiles/{name}", "native-git ownership is DEV-only"))
        for field in ("capacityRef", "identityRef"):
            ref_name = profile[field].split(":", 1)[1]
            if not safe_relative_path(ref_name):
                findings.append(ProjectFinding("error", "profile.unsafe_reference", f"$/profiles/{name}/{field}", "Reference name is unsafe"))
    if profile_name is not None and profile_name not in manifest["profiles"]:
        findings.append(ProjectFinding("error", "profile.unknown", "$/profiles", f"Unknown profile: {profile_name}"))

    if telemetry := manifest.get("telemetry"):
        ref_name = telemetry["sourceConnectionRef"].split(":", 1)[1]
        if not safe_relative_path(ref_name):
            findings.append(ProjectFinding("error", "telemetry.unsafe_reference", "$/telemetry/sourceConnectionRef", "Reference name is unsafe"))
    return findings


def validate_project(manifest: Any, *, profile_name: str | None = None) -> ProjectValidation:
    schema = load_schema()
    structural = _schema_findings(manifest, schema)
    security = _contains_hidden_credential(manifest)
    if structural:
        return ProjectValidation(manifest if isinstance(manifest, dict) else None, tuple(structural + security), False)
    assert isinstance(manifest, dict)
    semantic = _semantic_findings(manifest, profile_name=profile_name)
    return ProjectValidation(manifest, tuple(security + semantic), False)


def resolve_profile(manifest: dict[str, Any], profile_name: str) -> dict[str, Any]:
    result = validate_project(manifest, profile_name=profile_name)
    if not result.valid:
        first = result.findings[0]
        raise ProjectContractError(first.code, first.path, first.message)
    return dict(manifest["profiles"][profile_name])


def resolve_trusted_definition(project_root: Path, definition_path: str, *, must_exist: bool = False) -> Path:
    """Resolve a native definition path without opening it and reject symlink escapes."""
    if not safe_relative_path(definition_path):
        raise ProjectContractError("path.unsafe", "definitionPath", "Definition path is not a trusted relative path")
    root = project_root.resolve(strict=True)
    candidate = (root / definition_path).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ProjectContractError("path.escape", "definitionPath", "Definition path escapes project root") from exc
    if must_exist and not candidate.exists():
        raise ProjectContractError("path.missing", "definitionPath", "Definition path does not exist")
    return candidate


def validate_definition_trust(manifest: dict[str, Any], project_root: Path, *, must_exist: bool = False) -> tuple[ProjectFinding, ...]:
    result = validate_project(manifest)
    if not result.valid:
        return result.findings
    findings: list[ProjectFinding] = []
    for index, resource in enumerate(manifest["resources"]):
        try:
            resolve_trusted_definition(project_root, resource["definitionPath"], must_exist=must_exist)
        except ProjectContractError as exc:
            findings.append(ProjectFinding("error", exc.code, f"$/resources/{index}/definitionPath", exc.message))
    return tuple(findings)


def save_manifest(path: Path, manifest: dict[str, Any], *, project_root: Path) -> None:
    """Atomically save only the manifest. Native definitions are never regenerated."""
    result = validate_project(manifest)
    if not result.valid:
        first = result.findings[0]
        raise ProjectContractError(first.code, first.path, first.message)
    root = project_root.resolve(strict=True)
    target = path.resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ProjectContractError("path.escape", "$", "Manifest target escapes project root") from exc
    suffix = target.suffix.casefold()
    if suffix == ".json":
        payload = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    elif suffix in {".yaml", ".yml"}:
        payload = yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True)
    else:
        raise ProjectContractError("parse.extension", "$", "Manifest must use .json, .yaml, or .yml")
    temp = target.with_name(target.name + ".tmp")
    temp.write_text(payload, encoding="utf-8", newline="\n")
    temp.replace(target)


def validation_payload(result: ProjectValidation) -> dict[str, Any]:
    return {
        "valid": result.valid,
        "deployable": result.deployable,
        "project": result.project,
        "findings": [finding.__dict__ for finding in result.findings],
    }
