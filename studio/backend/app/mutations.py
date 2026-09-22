from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .catalog import combined_catalog
from .models import (
    Capability,
    MutationArtifactDigest,
    MutationArtifactRequest,
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
MAX_ARTIFACT_BYTES = 5_000_000
ARTIFACT_ROOT = Path(tempfile.gettempdir()) / "fabric-ops-studio" / "mutation-artifacts"
_ARTIFACT_PARAMETER_SUFFIXES = ("PathDefinition", "PathPlatformDefinition")


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

    def _cleanup_artifacts(self, plan: MutationPlan) -> None:
        if not plan.artifacts:
            return
        root = ARTIFACT_ROOT / plan.plan_id
        shutil.rmtree(root, ignore_errors=True)

    def _expire(self, plan: MutationPlan) -> MutationPlan:
        if plan.status in {"executed", "failed", "expired"}:
            return plan
        expires = datetime.fromisoformat(plan.expires_at.replace("Z", "+00:00"))
        if _utcnow() >= expires:
            plan.status = "expired"
            self._cleanup_artifacts(plan)
        return plan

    def _same_session(self, plan: MutationPlan) -> None:
        session = runtime.status()
        if not session.connected:
            raise UnsafeOperation("Connect to a Fabric tenant before using a mutation plan")
        if not session.tenant_id or session.tenant_id != plan.tenant_id:
            raise UnsafeOperation("Mutation plan belongs to a different Fabric tenant/session")

    @staticmethod
    def _validate_parameters(capability: Capability, parameters: dict[str, Any]) -> None:
        if capability.required_any_of and not any(
            name in parameters and parameters[name] not in (None, "")
            for name in capability.required_any_of
        ):
            joined = ", ".join(capability.required_any_of)
            raise ValueError(f"At least one of these parameters is required: {joined}")


    @staticmethod
    def _artifact_parameter_allowed(capability: Capability, parameter: str) -> bool:
        return (
            parameter in capability.parameters
            and parameter.endswith(_ARTIFACT_PARAMETER_SUFFIXES)
        )

    def _materialize_artifacts(
        self,
        plan_id: str,
        capability: Capability,
        parameters: dict[str, Any],
        artifacts: list[MutationArtifactRequest],
    ) -> tuple[dict[str, Any], list[MutationArtifactDigest]]:
        if not artifacts:
            return dict(parameters), []

        effective = dict(parameters)
        digests: list[MutationArtifactDigest] = []
        seen_parameters: set[str] = set()
        seen_filenames: set[str] = set()
        artifact_dir = ARTIFACT_ROOT / plan_id

        try:
            for artifact in artifacts:
                if artifact.parameter in seen_parameters:
                    raise ValueError(f"Duplicate artifact parameter: {artifact.parameter}")
                seen_parameters.add(artifact.parameter)

                if not self._artifact_parameter_allowed(capability, artifact.parameter):
                    raise UnsafeOperation(
                        f"Artifact binding is not allowed for parameter {artifact.parameter}"
                    )
                if artifact.parameter in effective and effective[artifact.parameter] not in (None, ""):
                    raise ValueError(
                        f"Parameter {artifact.parameter} is already supplied and cannot also be artifact-bound"
                    )

                filename = Path(artifact.filename)
                if filename.name != artifact.filename or artifact.filename in {".", ".."}:
                    raise ValueError("Artifact filename must be a plain file name without path components")
                if artifact.filename in seen_filenames:
                    raise ValueError(f"Duplicate artifact filename: {artifact.filename}")
                seen_filenames.add(artifact.filename)

                payload = artifact.content.encode("utf-8")
                if len(payload) > MAX_ARTIFACT_BYTES:
                    raise ValueError(
                        f"Artifact {artifact.filename} exceeds the {MAX_ARTIFACT_BYTES}-byte limit"
                    )

                artifact_dir.mkdir(parents=True, exist_ok=True)
                path = artifact_dir / artifact.filename
                path.write_bytes(payload)
                sha256 = hashlib.sha256(payload).hexdigest()

                effective[artifact.parameter] = str(path)
                digests.append(
                    MutationArtifactDigest(
                        parameter=artifact.parameter,
                        filename=artifact.filename,
                        sha256=sha256,
                        size_bytes=len(payload),
                    )
                )
        except Exception:
            shutil.rmtree(artifact_dir, ignore_errors=True)
            raise

        return effective, digests

    def _verify_artifacts(self, plan: MutationPlan) -> None:
        for artifact in plan.artifacts:
            raw_path = plan.parameters.get(artifact.parameter)
            if not isinstance(raw_path, str) or not raw_path:
                raise UnsafeOperation(
                    f"Bound artifact path is missing for {artifact.parameter}"
                )

            path = Path(raw_path)
            expected_root = (ARTIFACT_ROOT / plan.plan_id).resolve()
            try:
                resolved = path.resolve(strict=True)
            except FileNotFoundError as exc:
                raise UnsafeOperation(
                    f"Bound artifact is missing: {artifact.filename}"
                ) from exc

            if expected_root not in resolved.parents:
                raise UnsafeOperation("Bound artifact path escaped the mutation artifact directory")

            payload = resolved.read_bytes()
            if len(payload) != artifact.size_bytes:
                raise UnsafeOperation(
                    f"Bound artifact size changed after approval: {artifact.filename}"
                )
            actual = hashlib.sha256(payload).hexdigest()
            if actual != artifact.sha256:
                raise UnsafeOperation(
                    f"Bound artifact content changed after approval: {artifact.filename}"
                )

    def create_plan(
        self,
        capability: Capability,
        parameters: dict[str, Any],
        artifacts: list[MutationArtifactRequest] | None = None,
    ) -> MutationPlan:
        session = runtime.status()
        if not session.connected or not session.tenant_id:
            raise UnsafeOperation("Connect to a Fabric tenant before creating a mutation plan")
        if capability.provider != "MicrosoftFabricMgmt":
            raise UnsafeOperation("Guarded writes currently require the MicrosoftFabricMgmt provider")
        if capability.risk != "write" or capability.execution_policy != "guarded-write":
            raise UnsafeOperation("Capability is not explicitly allowlisted for guarded writes")

        plan_id = str(uuid.uuid4())
        effective_parameters, artifact_digests = self._materialize_artifacts(
            plan_id,
            capability,
            parameters,
            artifacts or [],
        )

        try:
            self._validate_parameters(capability, effective_parameters)
            rendered = build_guarded_write_command(capability, effective_parameters)
            validation_command = (
                build_guarded_write_command(capability, effective_parameters, what_if=True)
                if capability.supports_whatif
                else None
            )
        except Exception:
            shutil.rmtree(ARTIFACT_ROOT / plan_id, ignore_errors=True)
            raise

        created = _utcnow()
        expires = created + timedelta(minutes=PLAN_TTL_MINUTES)
        canonical = json.dumps(
            {
                "capability_id": capability.id,
                "tenant_id": session.tenant_id,
                "parameters": effective_parameters,
                "artifacts": [artifact.model_dump() for artifact in artifact_digests],
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
            parameters=effective_parameters,
            artifacts=artifact_digests,
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

        self._verify_artifacts(plan)
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
        # Reject terminal or otherwise invalid lifecycle states before artifact/validation checks.
        # This preserves single-use semantics and returns the most accurate state error
        # when a caller retries an already executed/failed plan.
        if plan.status not in {"planned", "validated"}:
            raise UnsafeOperation(f"Mutation plan cannot execute in status {plan.status}")
        if capability.supports_whatif and plan.status != "validated":
            raise UnsafeOperation("Run upstream -WhatIf validation before applying this mutation")
        self._verify_artifacts(plan)

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
        finally:
            self._cleanup_artifacts(plan)


broker = MutationBroker()
