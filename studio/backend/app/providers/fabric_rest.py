from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode, quote

from ..models import Capability
from ..contracts import parse_endpoint, validate_parameters
from ..admission import require_admission
from .microsoftfabricmgmt import UnsafeOperation, _ps_literal, runtime
from .outcomes import wrap_invocation


FABRIC_BASE_URL = "https://api.fabric.microsoft.com"
_ENDPOINT_RE = re.compile(r"^(?P<method>[A-Z]+)\s+(?P<path>/v1/[A-Za-z0-9_{}?&=./-]+)$")
_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _normalise_query_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_rest_get_command(capability: Capability, parameters: dict[str, Any] | None = None) -> str:
    require_admission(capability, 'read')
    if capability.provider != "Fabric REST API":
        raise UnsafeOperation("Capability is not provided by the Fabric REST API")
    if capability.risk != "read":
        raise UnsafeOperation(f"Only read-only REST capabilities are enabled; risk={capability.risk}")
    if not capability.endpoint:
        raise UnsafeOperation("REST capability has no registered endpoint")

    method, path, placeholders = parse_endpoint(capability)
    if method != "GET":
        raise UnsafeOperation(f"Only GET is enabled for REST capabilities; method={method}")

    if capability.response_mode not in {"sync", "fabric-lro"}:
        raise UnsafeOperation(f"Unsupported REST response mode: {capability.response_mode}")

    provided = validate_parameters(capability, parameters)
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
        "& (Get-Module MicrosoftFabricMgmt) { Invoke-FabricAuthCheck -ThrowOnFailure; "
        f"Invoke-FabricAPIRequest -BaseURI {url_literal} -Headers $script:FabricAuthContext.FabricHeaders -Method 'Get'{lro_switch} "
        "}"
    )
    return wrap_invocation(command)


def execute_rest_read(capability: Capability, parameters: dict[str, Any] | None = None, *, expected=None) -> dict[str, Any]:
    expected = expected or runtime.status()
    with runtime.dispatch(expected):
        command = build_rest_get_command(capability, parameters)
        runtime._check_loaded_artifact()
        return runtime.run_json(command)
