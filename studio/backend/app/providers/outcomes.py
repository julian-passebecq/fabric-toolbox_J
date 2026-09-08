"""Studio-owned invocation envelope; domain payload never supplies status."""
import json


class InvocationFailure(RuntimeError):
    pass


class OutcomeUnknown(RuntimeError):
    pass


def wrap_invocation(command: str, mode: str = 'read') -> str:
    # $Error retains caught exceptions even when Write-FabricLog only logs them.
    # Clear per invocation under the session lock. Stream records are not data.
    return (
        "$Error.Clear(); $studioFailed = $false; $studioData = @(); "
        "try { $studioStreams = @(& { " + command + " } *>&1); "
        "$studioData = @($studioStreams | Where-Object { "
        "$_ -isnot [System.Management.Automation.InformationRecord] -and "
        "$_ -isnot [System.Management.Automation.WarningRecord] -and "
        "$_ -isnot [System.Management.Automation.VerboseRecord] -and "
        "$_ -isnot [System.Management.Automation.DebugRecord] -and "
        "$_ -isnot [System.Management.Automation.ErrorRecord] }); "
        "$studioFailed = $Error.Count -gt 0 -or @($studioStreams | Where-Object { "
        "$_ -is [System.Management.Automation.ErrorRecord] }).Count -gt 0 "
        "} catch { $studioFailed = $true }; "
        "[PSCustomObject]@{ studio_envelope = 1; success = (-not $studioFailed); "
        f"mode = '{mode}'; data = $studioData; error = $(if ($studioFailed) {{ 'provider_error' }} else {{ $null }}) "
        "} | ConvertTo-Json -Depth 30 -Compress"
    )


def normalize(raw: str, mode: str = 'read') -> dict:
    # ShouldProcess writes WhatIf directly to the host, outside *>&1. Upstream
    # preserves that stream as output text. Only this declared prefix is allowed;
    # the final Studio envelope and its empty data are still mandatory.
    if mode == 'what-if':
        try:
            outer = json.loads(raw)
            if isinstance(outer, dict) and set(outer) == {'success', 'output'} and outer['success'] is True and isinstance(outer['output'], str):
                raw = outer['output']
        except (ValueError, TypeError):
            pass
        lines = raw.strip().splitlines()
        if len(lines) > 1 and all(line.startswith('What if: ') for line in lines[:-1]):
            raw = lines[-1]
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise OutcomeUnknown('Malformed provider output') from exc
    if isinstance(parsed, dict) and parsed.get('success') is False and 'error_type' in parsed:
        raise InvocationFailure('Upstream invocation failed')
    if not isinstance(parsed, dict) or parsed.get('studio_envelope') != 1 or type(parsed.get('success')) is not bool or parsed.get('mode') != mode:
        raise OutcomeUnknown('Missing or mismatched Studio invocation envelope')
    if not parsed['success']:
        raise InvocationFailure('Provider reported an invocation error')
    data = parsed.get('data')
    if not isinstance(data, list):
        raise OutcomeUnknown('Invalid provider data shape')
    # Invoke-FabricAPIRequest intentionally returns an array as one pipeline
    # object (unary comma). Remove only that invocation-container level.
    if len(data) == 1 and isinstance(data[0], list):
        data = data[0]
    if any(isinstance(x, dict) and x.get('success') is False and 'error_type' in x for x in data):
        raise InvocationFailure('Upstream operation failed')
    if mode == 'what-if':
        if data:
            raise OutcomeUnknown('Unexpected validation output; validation is not approved')
    elif any(not isinstance(x, (dict, list)) for x in data):
        raise OutcomeUnknown('Unexpected plain or mixed provider output')
    # Arrays remain arrays (including zero or one element); callers unwrap explicitly.
    return {'studio_envelope': 1, 'success': True, 'mode': mode, 'data': data}
