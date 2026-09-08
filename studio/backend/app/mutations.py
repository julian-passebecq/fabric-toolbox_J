from __future__ import annotations

import hashlib
import json
import threading
import uuid
import time
from datetime import datetime, timedelta, timezone

from .catalog import combined_catalog
from .contracts import validate_parameters
from .models import MutationPlan, MutationValidationResult, MutationExecutionResult, SessionStatus
from .providers.microsoftfabricmgmt import UnsafeOperation, build_guarded_write_command, runtime
from .providers.outcomes import InvocationFailure
from .activity import append_activity

PLAN_TTL_MINUTES = 10
TERMINAL = {'validation_failed','expired','invalidated','executed','applied_unverified','failed','outcome_unknown'}


def _utcnow():
    return datetime.now(timezone.utc)


def _iso(value):
    return value.isoformat().replace('+00:00','Z')


def _digest(snapshot):
    return hashlib.sha256(json.dumps(snapshot,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()).hexdigest()


class MutationBroker:
    """Short bookkeeping claims; I/O outside the lock. DTOs never alias approvals."""
    def __init__(self):
        self._plans = {}
        self._snapshots = {}
        self._lock = threading.RLock()

    def _capability(self, capability_id):
        for item in combined_catalog():
            if item.id == capability_id:
                return item
        raise ValueError('Capability not found')

    def _expire(self, plan):
        if plan.status in {'planned','validated'} and _utcnow() >= datetime.fromisoformat(plan.expires_at.replace('Z','+00:00')):
            plan.status = 'expired'
        return plan

    def create_plan(self, capability, parameters, *, expected=None):
        session = expected or runtime.status()
        if not session.connected or not session.tenant_id:
            raise UnsafeOperation('Connect to a Fabric tenant before creating a mutation plan')
        parameters = validate_parameters(capability,parameters)
        rendered = build_guarded_write_command(capability,parameters)
        validation = build_guarded_write_command(capability,parameters,what_if=True)
        artifact_identity=runtime.bind_artifact(session)
        if not artifact_identity:
            raise UnsafeOperation('Loaded provider identity is unavailable')
        created = _utcnow()
        plan_id = str(uuid.uuid4())
        plan = MutationPlan(plan_id=plan_id,capability_id=capability.id,capability_title=capability.title,
            provider=capability.provider,risk=capability.risk,tenant_id=session.tenant_id,
            session_generation=session.generation,artifact_identity=artifact_identity,parameters=parameters,rendered_command=rendered,
            validation_command=validation,supports_validation=True,confirmation_text=f'APPLY {plan_id[:8].upper()}',
            digest='',created_at=_iso(created),expires_at=_iso(created+timedelta(minutes=PLAN_TTL_MINUTES)))
        snapshot = {'plan': self._approval_fields(plan), 'capability': capability.model_dump(),
                    'verification': self._capability(capability.verification_capability_id).model_dump()}
        plan.digest = _digest(snapshot)
        # Canonical JSON is the immutable internal approval. Decode to detached values.
        with self._lock:
            self._snapshots[plan_id] = json.dumps(snapshot,sort_keys=True,separators=(',', ':'),allow_nan=False)
            self._plans[plan_id] = plan.model_copy(deep=True)
        return plan.model_copy(deep=True)

    @staticmethod
    def _approval_fields(plan):
        return plan.model_dump(exclude={'digest','status','attempt_id','stage','apply_outcome','verification_outcome','reason','audit_warning'})

    def get(self, plan_id):
        with self._lock:
            if plan_id not in self._plans:
                raise ValueError('Mutation plan not found')
            return self._expire(self._plans[plan_id]).model_copy(deep=True)

    def list(self):
        with self._lock:
            return sorted([self._expire(p).model_copy(deep=True) for p in self._plans.values()],key=lambda p:p.created_at,reverse=True)

    def _check(self, plan, capability, verification):
        snapshot = json.loads(self._snapshots[plan.plan_id])
        current = {'plan':self._approval_fields(plan),'capability':capability.model_dump(),'verification':verification.model_dump()}
        if _digest(snapshot) != plan.digest or current != snapshot:
            raise UnsafeOperation('Approval snapshot or admitted source changed')
        if _utcnow() >= datetime.fromisoformat(plan.expires_at.replace('Z','+00:00')):
            raise UnsafeOperation('Mutation plan has expired; create a new plan')
        session=runtime.status()
        if not session.connected or (session.tenant_id,session.generation)!=(plan.tenant_id,plan.session_generation):
            raise UnsafeOperation('Mutation plan belongs to a different Fabric tenant/session generation')
        if runtime.artifact_fingerprint()!=plan.artifact_identity:
            raise UnsafeOperation('Loaded provider artifact identity changed')

    def _claim(self, plan_id, stage, confirmation=None):
        # Resolve/hash catalog before short lock; recheck at dispatch as well.
        detached=self.get(plan_id)
        capability=self._capability(detached.capability_id)
        verification=self._capability(capability.verification_capability_id)
        with self._lock:
            plan=self._plans[plan_id]
            allowed='planned' if stage=='validate' else 'validated'
            if plan.status != allowed:
                raise UnsafeOperation(f'Mutation plan cannot {stage} in status {plan.status}; run WhatIf validation on a new plan')
            if stage=='apply' and confirmation != plan.confirmation_text:
                raise UnsafeOperation('Confirmation text does not match the mutation plan')
            try:
                self._check(plan,capability,verification)
            except UnsafeOperation:
                plan.status='expired' if _utcnow()>=datetime.fromisoformat(plan.expires_at.replace('Z','+00:00')) else 'invalidated'
                raise
            plan.status='validating' if stage=='validate' else 'executing'
            plan.stage=stage
            plan.attempt_id=str(uuid.uuid4())
            return plan.model_copy(deep=True),capability

    def _before_dispatch(self, claimed):
        capability=self._capability(claimed.capability_id)
        verification=self._capability(capability.verification_capability_id)
        with self._lock:
            plan=self._plans[claimed.plan_id]
            if plan.attempt_id!=claimed.attempt_id or plan.status!=claimed.status:
                raise UnsafeOperation('Attempt no longer owns this plan')
            self._check(plan,capability,verification)

    def _finish(self, claimed, status, **fields):
        with self._lock:
            plan=self._plans[claimed.plan_id]
            if plan.attempt_id!=claimed.attempt_id or plan.status!=claimed.status:
                raise UnsafeOperation('Attempt completion does not own this plan')
            plan.status=status
            for key,value in fields.items():
                setattr(plan,key,value)
            return plan.model_copy(deep=True)

    @staticmethod
    def _expected(plan):
        return SessionStatus(connected=True,tenant_id=plan.tenant_id,generation=plan.session_generation)

    def validate(self, plan_id):
        claimed,capability=self._claim(plan_id,'validate')
        started=time.monotonic()
        try:
            append_activity({'action':'mutation.validate','plan_id':plan_id,'attempt_id':claimed.attempt_id,'status':'started'})
            result=runtime.validate_guarded_write(capability,claimed.parameters,expected=self._expected(claimed),before_dispatch=lambda:self._before_dispatch(claimed))
            if result.get('studio_envelope')!=1 or result.get('success') is not True or result.get('mode')!='what-if':
                raise InvocationFailure('Invalid validation outcome')
            plan=self._finish(claimed,'validated')
        except Exception:
            plan=self._finish(claimed,'validation_failed',reason='Validation failed; create a new plan')
            result={'success':False,'error':'validation_failed'}
        plan=self._audit_end(plan,started)
        return MutationValidationResult(plan=plan,result=result)

    def _audit_end(self, plan, started):
        try:
            append_activity({'action':'mutation.validate' if plan.stage=='validate' else 'mutation.execute','plan_id':plan.plan_id,'attempt_id':plan.attempt_id,'status':plan.status,'duration_ms':round((time.monotonic()-started)*1000,2)})
        except OSError:
            with self._lock:
                self._plans[plan.plan_id].audit_warning='Outcome audit failed; do not replay a write'
                plan=self._plans[plan.plan_id].model_copy(deep=True)
        return plan

    def _verify(self, capability, claimed, result):
        data=result.get('data',[])
        workspace_id=claimed.parameters.get('WorkspaceId')
        if capability.command=='New-FabricWorkspace':
            if len(data)!=1 or not isinstance(data[0],dict) or not isinstance(data[0].get('id'),str) or not data[0]['id']:
                return {'verified':False,'reason':'Create did not return one unique workspace ID'}
            workspace_id=data[0]['id']
        verification=self._capability(capability.verification_capability_id)
        read=runtime.execute_read(verification,{'WorkspaceId':workspace_id},expected=self._expected(claimed))
        rows=read.get('data',[])
        expected_fields={target:claimed.parameters[source] for source,target in [('WorkspaceName','displayName'),('WorkspaceDescription','description')] if source in claimed.parameters}
        matches=(read.get('success') is True and len(rows)==1 and isinstance(rows[0],dict)
            and rows[0].get('id')==workspace_id and all(rows[0].get(k)==v for k,v in expected_fields.items()))
        return {'verified':bool(matches),'data':rows,'reason':None if matches else 'Read-back identity or requested fields did not match'}

    def execute(self, plan_id, confirmation):
        claimed,capability=self._claim(plan_id,'apply',confirmation)
        started=time.monotonic()
        dispatched=False
        def before():
            nonlocal dispatched
            self._before_dispatch(claimed)
            append_activity({'action':'mutation.execute','plan_id':plan_id,'attempt_id':claimed.attempt_id,'status':'started'})
            dispatched=True
        try:
            result=runtime.execute_guarded_write(capability,claimed.parameters,expected=self._expected(claimed),before_dispatch=before)
            if result.get('studio_envelope')!=1 or result.get('success') is not True or result.get('mode')!='apply':
                raise InvocationFailure('Provider apply failed')
        except Exception as exc:
            status='failed' if isinstance(exc,InvocationFailure) or not dispatched else 'outcome_unknown'
            plan=self._finish(claimed,status,apply_outcome=status,reason='Inspect remote state before creating another plan' if status=='outcome_unknown' else 'Apply was not confirmed successful')
            return MutationExecutionResult(plan=self._audit_end(plan,started),result={'success':False,'error':status})
        try:
            verification=self._verify(capability,claimed,result)
        except Exception:
            verification={'verified':False,'reason':'Read-back failed; inspect remote state'}
        status='executed' if verification['verified'] else 'applied_unverified'
        plan=self._finish(claimed,status,apply_outcome='succeeded',verification_outcome='verified' if verification['verified'] else 'unverified')
        return MutationExecutionResult(plan=self._audit_end(plan,started),result=result,verification=verification)


broker=MutationBroker()
