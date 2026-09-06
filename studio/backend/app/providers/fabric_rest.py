from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode, quote

from ..models import Capability
from .microsoftfabricmgmt import UnsafeOperation, _ps_literal, runtime


FABRIC_BASE_URL = "https://api.fabric.microsoft.com"
_ENDPOINT_RE = re.compile(r"^(?P<method>[A-Z]+)\s+(?P<path>/v1/[A-Za-z0-9_{}?&=./-]+)$")
_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _normalise_query_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_rest_get_command(capability: Capability, parameters: dict[str, Any] | None = None) -> str:
    if capability.provider != "Fabric REST API":
        raise UnsafeOperation("Capability is not provided by the Fabric REST API")
    if capability.risk != "read":
        raise UnsafeOperation(f"Only read-only REST capabilities are enabled; risk={capability.risk}")
    if not capability.endpoint:
        raise UnsafeOperation("REST capability has no registered endpoint")

    endpoint_match = _ENDPOINT_RE.fullmatch(capability.endpoint.strip())
    if not endpoint_match:
        raise UnsafeOperation("REST endpoint declaration is invalid")

    method = endpoint_match.group("method")
    if method != "GET":
        raise UnsafeOperation(f"Only GET is enabled for REST capabilities; method={method}")

    if capability.response_mode not in {"sync", "fabric-lro"}:
        raise UnsafeOperation(f"Unsupported REST response mode: {capability.response_mode}")

    path = endpoint_match.group("path")
    provided = parameters or {}
    allowed = {spec.name for spec in capability.parameter_specs} or set(capability.parameters)
    unknown = sorted(set(provided) - allowed)
    if unknown:
        raise ValueError(f"Unknown REST parameters: {', '.join(unknown)}")

    mandatory = {spec.name for spec in capability.parameter_specs if spec.mandatory}
    missing = sorted(name for name in mandatory if provided.get(name) in (None, ""))
    if missing:
        raise ValueError(f"Missing required REST parameters: {', '.join(missing)}")

    placeholders = set(_PLACEHOLDER_RE.findall(path))
    for name in placeholders:
        if name not in provided or provided[name] in (None, ""):
            raise ValueError(f"Missing endpoint path parameter: {name}")
        path = path.replace("{" + name + "}", quote(str(provided[name]), safe=""))

    query_pairs: list[tuple[str, str]] = []
    for name, value in provided.items():
        if name in placeholders or value in (None, ""):
            continue
        query_pairs.append((name, _normalise_query_value(value)))

    if query_pairs:
        separator = "&" if "?" in path else "?"
        path = path + separator + urlencode(query_pairs)

    url = FABRIC_BASE_URL + path
    url_literal = _ps_literal(url)
    lro_switch = " -WaitForCompletion" if capability.response_mode == "fabric-lro" else ""
    command = (
        f"$headers = Get-FabricAPIHeaders; "
        f"$result = Invoke-FabricAPIRequest -BaseURI {url_literal} -Headers $headers -Method 'Get'{lro_switch}; "
        "$result | ConvertTo-Json -Depth 20 -Compress"
    )
    return command


def execute_rest_read(capability: Capability, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    return runtime.run_json(build_rest_get_command(capability, parameters))
