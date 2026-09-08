"""Bounded structured audit. Provider text and parameter values are never durable."""
import json
import math
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path.home() / '.fabric-ops-studio'
ACTIVITY_FILE = DATA_DIR / 'activity.jsonl'
MAX_RECORD_BYTES = 4096
MAX_FILE_BYTES = 10 * 1024 * 1024
ROTATIONS = 5
READ_BUDGET = 1024 * 1024
MAX_RESULTS = 1000
BOOT_ID = str(uuid.uuid4())
_LOCK = threading.Lock()
ACTIONS = {'session.connect','capability.execute','mutation.plan','mutation.validate','mutation.execute','request'}
STATUSES = {'started','succeeded','rejected','failed','planned','validating','validated','executing','executed','validation_failed','expired','invalidated','applied_unverified','outcome_unknown','interrupted_unknown'}


def _summary(event):
    record = {'action': event.get('action') if event.get('action') in ACTIONS else 'request',
              'status': event.get('status') if event.get('status') in STATUSES else 'succeeded'}
    for key in ('run_id','attempt_id','plan_id','boot_id'):
        value = event.get(key)
        if isinstance(value,str):
            try: record[key] = str(uuid.UUID(value))
            except ValueError: pass
    for key in ('duration_ms','http_status'):
        value=event.get(key)
        if type(value) in (int,float) and math.isfinite(value) and 0<=value<=1e12:
            record[key]=value
    return record


def append_activity(event):
    record = {**_summary(event), 'timestamp':datetime.now(timezone.utc).isoformat(), 'boot_id':BOOT_ID}
    encoded=(json.dumps(record,separators=(',',':'))+'\n').encode()
    if len(encoded)>MAX_RECORD_BYTES: raise ValueError('Activity record exceeds limit')
    with _LOCK:
        ACTIVITY_FILE.parent.mkdir(parents=True,exist_ok=True)
        if ACTIVITY_FILE.exists() and ACTIVITY_FILE.stat().st_size+len(encoded)>MAX_FILE_BYTES:
            oldest=ACTIVITY_FILE.with_suffix(f'.jsonl.{ROTATIONS}')
            oldest.unlink(missing_ok=True)
            for index in range(ROTATIONS-1,0,-1):
                source=ACTIVITY_FILE.with_suffix(f'.jsonl.{index}')
                if source.exists(): source.replace(ACTIVITY_FILE.with_suffix(f'.jsonl.{index+1}'))
            ACTIVITY_FILE.replace(ACTIVITY_FILE.with_suffix('.jsonl.1'))
        with ACTIVITY_FILE.open('ab') as handle:
            handle.write(encoded)
            handle.flush()
    return record


def read_activity(limit=200):
    limit=max(1,min(limit,MAX_RESULTS))
    records=[]
    budget=READ_BUDGET
    with _LOCK:
        for path in [ACTIVITY_FILE]+[ACTIVITY_FILE.with_suffix(f'.jsonl.{i}') for i in range(1,ROTATIONS+1)]:
            if not path.exists() or budget<=0: continue
            with path.open('rb') as handle:
                size=path.stat().st_size
                start=max(0,size-budget)
                handle.seek(start)
                content=handle.read(budget)
                budget-=len(content)
            lines=content.splitlines()
            if start: lines=lines[1:]
            for line in reversed(lines):
                if len(line)>MAX_RECORD_BYTES: continue
                try:
                    event=json.loads(line)
                    if not isinstance(event,dict): continue
                    record=_summary(event)
                    stamp=event.get('timestamp','')
                    try: record['timestamp']=datetime.fromisoformat(stamp).isoformat()
                    except (ValueError,TypeError): continue
                    records.append(record)
                except (ValueError,UnicodeError): continue
    completed={r.get('attempt_id') or r.get('run_id') for r in records if r['status']!='started'}
    for r in records:
        if r['status']=='started' and (r.get('attempt_id') or r.get('run_id')) not in completed and r.get('boot_id')!=BOOT_ID:
            r['status']='interrupted_unknown'
    return records[:limit]
