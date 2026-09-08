"""Shared, strict input contracts. No provider dispatch or permissive coercion."""
import re
import uuid
from typing import Any

from .models import Capability


def validate_parameters(capability: Capability, parameters: dict[str, Any] | None) -> dict[str, Any]:
    provided = parameters or {}
    specs = {s.name: s for s in capability.parameter_specs}
    unknown = set(provided) - set(capability.parameters)
    if unknown:
        raise ValueError(f"Unknown parameters: {', '.join(sorted(unknown))}")
    for name in capability.parameters:
        if name not in specs:
            raise ValueError(f"Unsupported parameter contract: {name}")
    for spec in specs.values():
        if spec.mandatory and spec.name not in provided:
            raise ValueError(f"Missing required parameter: {spec.name}")
    result = {}
    for name, value in provided.items():
        spec = specs[name]
        kind = spec.type.lower()
        def check(v, t):
            if t.endswith('[]'):
                return isinstance(v, list) and all(check(x, t[:-2]) for x in v)
            if t in {'string', 'guid'}:
                if not isinstance(v, str) or not v.strip():
                    return False
                if t == 'guid':
                    try:
                        uuid.UUID(v)
                    except ValueError:
                        return False
                return True
            if t in {'bool', 'boolean', 'switch'}:
                return type(v) is bool
            if t in {'int', 'int32', 'int64', 'long'}:
                bits = 64 if t in {'int64', 'long'} else 32
                return type(v) is int and -(2 ** (bits-1)) <= v < 2 ** (bits-1)
            return False
        if not check(value, kind):
            raise ValueError(f"Invalid or unsupported {kind} parameter: {name}")
        values = value if isinstance(value, list) else [value]
        if spec.allowed_values and any(str(v).casefold() not in {a.casefold() for a in spec.allowed_values} for v in values):
            raise ValueError(f"Value outside ValidateSet: {name}")
        result[name] = list(value) if isinstance(value, list) else value
    if capability.required_any_of and not any(n in result for n in capability.required_any_of):
        raise ValueError(f"At least one of these parameters is required: {', '.join(capability.required_any_of)}")
    exclusive = {
        'Get-FabricWorkspace': ('WorkspaceId', 'WorkspaceName'),
        'Get-FabricCapacity': ('CapacityId', 'CapacityName'),
        'Get-FabricConnection': ('ConnectionId', 'ConnectionName'),
    }.get(capability.command, ())
    if sum(n in result for n in exclusive) > 1:
        raise ValueError(f"Mutually exclusive parameters: {', '.join(exclusive)}")
    return result


def parse_endpoint(capability: Capability) -> tuple[str, str, set[str]]:
    match = re.fullmatch(r'(GET|POST|PATCH|PUT|DELETE) (/v1/[A-Za-z0-9_{}./-]+)', capability.endpoint or '')
    if not match:
        raise ValueError('Invalid REST method/path declaration')
    method, path = match.groups()
    placeholders = set(re.findall(r'\{([A-Za-z_][A-Za-z0-9_]*)\}', path))
    if '{' in re.sub(r'\{[A-Za-z_][A-Za-z0-9_]*\}', '', path) or '}' in re.sub(r'\{[A-Za-z_][A-Za-z0-9_]*\}', '', path) or '..' in path:
        raise ValueError('Malformed REST path placeholder')
    specs = {s.name: s for s in capability.parameter_specs}
    if any(n not in specs or not specs[n].mandatory for n in placeholders):
        raise ValueError('Endpoint placeholders must declare mandatory parameters')
    return method, path, placeholders
