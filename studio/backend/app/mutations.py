from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .catalog import combined_catalog
from .models import (
    Capability,
    MutationExecutionResult,
    MutationPlan,
    MutationValidationResult,
)
from .providers.microsoftfabricmgmt import (
    UnsafeOperation,
    build_guarded_write_command,
    runtime,
)


PLAN_TTL_MINUTES = 10


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class MutationBroker:
    """In-memory, tenant-bound approval broker for explicitly allowlisted Fabric writes."""

    def __init__(self) -> None:
        self._plans: dict[str, MutationPlan] = {}
        self._lock = threading.Lock()

    def _capability(self, capability_id: str) -> Capability:
        for item in combined_catalog():
            if item.id == capability_id:
                return item
        raise ValueError("Capability not found")

    def _expire(self, plan: MutationPlan) -> MutationPlan:
        if plan.status in {"executed", "failed", "expired"}:
            return plan
        expires = datetime.fromisoformat(plan.expires_at.replace("Z", "+00:00"))
        if _utcnow() >= expires:
            plan.status = "expired"
        return plan

    def _same_session(self, plan: MutationPlan) -> None:
        session = runtime.status()
        if not session.connected:
            raise UnsafeOperation("Connect to a Fabric tenant before using a mutation plan")
        if not session.tenant_id or session.tenant_id != plan.tenant_id:
            raise UnsafeOperation("Mutation plan belongs to a different Fabric tenant/session")

    def create_plan(self, capability: Capability, parameters: dict[str, Any]) -> MutationPlan:
        session = runtime.status()
        if not session.connected or not session.tenant_id:
            raise UnsafeOperation("Connect to a Fabric tenant before creating a mutation plan")
        if capability.provider != "MicrosoftFabricMgmt":
            raise UnsafeOperation("Guarded writes currently require the MicrosoftFabricMgmt provider")
        if capability.risk != "write" or capability.execution_policy != "guarded-write":
            raise UnsafeOperation("Capability is not explicitly allowlisted for guarded writes")

        rendered = build_guarded_write_command(capability, parameters)
        validation_command = (
            build_guarded_write_command(capability, parameters, what_if=True)
            if capability.supports_whatif
            else None
        )

        created = _utcnow()
        expires = created + timedelta(minutes=PLAN_TTL_MINUTES)
        plan_id = str(uuid.uuid4())
        canonical = json.dumps(
            {
                "capability_id": capability.id,
                "tenant_id": session.tenant_id,
                "parameters": parameters,
                "rendered_command": rendered,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        plan = MutationPlan(
            plan_id=plan_id,
            capability_id=capability.id,
            capability_title=capability.title,
            provider=capability.provider,
            risk=capability.risk,
            tenant_id=session.tenant_id,
            parameters=parameters,
            rendered_command=rendered,
            validation_command=validation_command,
            supports_validation=bool(validation_command),
            confirmation_text=f"APPLY {plan_id[:8].upper()}",
            digest=digest,
            created_at=_iso(created),
            expires_at=_iso(expires),
            status="planned",
        )
        with self._lock:
            self._plans[plan.plan_id] = plan
        return plan

    def get(self, plan_id: str) -> MutationPlan:
        with self._lock:
            plan = self._plans.get(plan_id)
            if plan is None:
                raise ValueError("Mutation plan not found")
            return self._expire(plan)

    def list(self) -> list[MutationPlan]:
        with self._lock:
            plans = [self._expire(plan) for plan in self._plans.values()]
            return sorted(plans, key=lambda item: item.created_at, reverse=True)

    def validate(self, plan_id: str) -> MutationValidationResult:
        plan = self.get(plan_id)
        self._same_session(plan)
        if plan.status == "expired":
            raise UnsafeOperation("Mutation plan has expired; create a new plan")
        if plan.status not in {"planned", "validated"}:
            raise UnsafeOperation(f"Mutation plan cannot be validated in status {plan.status}")

        capability = self._capability(plan.capability_id)
        if not capability.supports_whatif:
            raise UnsafeOperation("This mutation does not expose upstream -WhatIf validation")

        result = runtime.validate_guarded_write(capability, plan.parameters)
        plan.status = "validated"
        return MutationValidationResult(plan=plan, result=result)

    def _verify(self, capability: Capability, parameters: dict[str, Any]) -> dict[str, Any] | None:
        if not capability.verification_capability_id:
            return None
        verification = self._capability(capability.verification_capability_id)
        verification_parameters: dict[str, Any] = {}
        for target, source in capability.verification_parameter_map.items():
            if source in parameters and parameters[source] not in (None, ""):
                verification_parameters[target] = parameters[source]
        if not verification_parameters:
            return None
        return runtime.execute_read(verification, verification_parameters)

    def execute(self, plan_id: str, confirmation: str) -> MutationExecutionResult:
        plan = self.get(plan_id)
        self._same_session(plan)
        if plan.status == "expired":
            raise UnsafeOperation("Mutation plan has expired; create a new plan")
        if confirmation != plan.confirmation_text:
            raise UnsafeOperation("Confirmation text does not match the mutation plan")

        capability = self._capability(plan.capability_id)
        if capability.supports_whatif and plan.status != "validated":
            raise UnsafeOperation("Run upstream -WhatIf validation before applying this mutation")
        if plan.status not in {"planned", "validated"}:
            raise UnsafeOperation(f"Mutation plan cannot execute in status {plan.status}")

        # Mark before execution so a repeated HTTP request cannot reuse the plan.
        plan.status = "executing"
        try:
            result = runtime.execute_guarded_write(capability, plan.parameters)
            verification = self._verify(capability, plan.parameters)
            plan.status = "executed"
            return MutationExecutionResult(plan=plan, result=result, verification=verification)
        except Exception:
            plan.status = "failed"
            raise


broker = MutationBroker()
