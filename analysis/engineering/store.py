"""Versioned V4 output adapter and append-only local engineering review storage.

No provider clients, reference worksheets, calibrated confidence or acceptance policy.
The frozen generator and research metric definitions are deliberately unchanged.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import json
import re
import sqlite3

from analysis.round2.__main__ import private
from fmea_generator import FIELDS, RATINGS, parse_fmea
from standalone_v4 import CATEGORIES, RESPONSE_VERSION, SCORING_PROFILE, audit, check_inventory, strict_read, validate

SCHEMA = 'engineering-workspace-1'
POLICY = 'standalone-1-to-10-v1'
STATES = ('NEEDS_REVIEW', 'APPROVED', 'REJECTED')
EDITABLE = frozenset(FIELDS + ['existing_detection', 'assumptions', 'operating_state', 'action_status', 'action_due_date', 'action_owner','judge_disposition'])
JUDGE_DISPOSITIONS = ('valid_additional','duplicate','technically_incorrect','insufficient_evidence','unresolved')
PLACEHOLDERS = {'', 'not provided', 'unknown', 'not specified', 'n/a'}


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def rating(value):
    return type(value) is int and 1 <= value <= 10


def rpn(row):
    return row['severity'] * row['occurrence'] * row['detection'] if all(rating(row.get(k)) for k in RATINGS) else None


def missing(value):
    return not isinstance(value, str) or value.strip().casefold() in PLACEHOLDERS


def findings(row, unit):
    """Structural errors and engineering-review flags; never semantic certification."""
    errors, flags = [], []
    for key in FIELDS:
        value = row.get(key)
        if key in RATINGS:
            if not rating(value): errors.append('Invalid or missing ' + key + ': integer 1-10 required')
        elif not isinstance(value, str) or not value.strip(): errors.append('Missing text: ' + key)
    for key in ('row_id', 'unit_id', 'category', 'operating_state', 'existing_detection', 'assumptions'):
        if not isinstance(row.get(key), str) or not row[key].strip(): errors.append('Missing traceability: ' + key)
    if unit is None or row.get('component') != unit['name']: errors.append('Component is not bound to an identified input unit')
    if row.get('category') not in CATEGORIES: errors.append('Unknown V4 failure category')
    if unit and unit.get('applicable_categories') is not None and row.get('category') not in unit['applicable_categories']:
        errors.append('Category excluded by reviewed inventory')
    if row.get('action_status') and row['action_status'] not in ('OPEN','IN_PROGRESS','COMPLETE'): errors.append('Invalid action status')
    if row.get('action_due_date'):
        from datetime import date
        try: date.fromisoformat(row['action_due_date'])
        except (ValueError,TypeError): errors.append('Invalid action due date')
    supplied = row.get('RPN')
    if supplied is not None and (type(supplied) is not int or supplied != rpn(row)):
        errors.append('Supplied RPN differs from valid S x O x D')
    for key in ('cause', 'local_effect', 'system_effect', 'recommended_action'):
        if missing(row.get(key)): flags.append('Engineering information unavailable: ' + key)
    if missing(row.get('evidence')): flags.append('No source citation; unsupported assertions require engineering review')
    if row.get('cause') == row.get('failure_mode') or row.get('cause') == row.get('system_effect'):
        flags.append('Cause, mode or effect may be conflated')
    if len(str(row.get('failure_mode', '')).split()) < 2: flags.append('Failure mode may be overly generic')
    if unit and row.get('existing_detection') not in (unit['detection_provisions'], 'Not provided'):
        flags.append('Detection provision differs from input; verify potential unsupported claim')
    if rating(row.get('severity')) and row['severity'] >= 9: flags.append('High severity: engineering attention independent of RPN')
    flags.append('Ratings, causal consistency and recommendations require human engineering verification')
    return {'structural_status': 'FAIL' if errors else 'PASS', 'errors': errors, 'review_flags': flags,
            'engineering_status': 'NOT_ENGINEERING_VALIDATED', 'computed_rpn': rpn(row)}


def normalize(raw, inventory, receipt, dataset_version, response_hash, inventory_hash):
    if not isinstance(receipt,dict) or not isinstance(inventory,dict): raise ValueError('Receipt and inventory must be objects')
    if receipt.get('workflow') != 'standalone_gemini' or receipt.get('prompt_version') != 'v4.0-inventory':
        raise ValueError('Only standalone Gemini V4 output is supported; canonical workflow remains separate')
    for key in ('attempt_id', 'experiment_id', 'system_id', 'system_sha256', 'skill_sha256', 'model', 'configuration', 'git_commit', 'started_at'):
        if key not in receipt or receipt[key] is None or receipt[key] == '': raise ValueError('Missing receipt provenance: ' + key)
        if key!='configuration' and not isinstance(receipt[key],str): raise ValueError('Receipt identity must be text: ' + key)
    if not isinstance(receipt['configuration'],dict): raise ValueError('Missing model configuration object')
    if receipt.get('status') not in ('success', 'failed'): raise ValueError('Generation outcome is not final')
    if not dataset_version.strip(): raise ValueError('Dataset version must be explicit')
    if inventory_hash != receipt.get('inventory_sha256') or inventory.get('system_sha256') != receipt['system_sha256']:
        raise ValueError('Inventory/source hash does not match receipt')
    if response_hash not in {v.get('sha256') for v in receipt.get('artifacts', {}).values()}:
        raise ValueError('Response bytes are not bound to this receipt')
    units = {u['unit_id']: u for u in check_inventory(inventory)}
    if not isinstance(raw, dict) or not isinstance(raw.get('rows'), list) or not raw['rows']:
        raise ValueError('Expected V4 object containing generated rows')
    if any(not isinstance(row, dict) for row in raw['rows']): raise ValueError('Rows must be objects')
    ids = [r.get('row_id') for r in raw['rows']]
    if any(not isinstance(i, str) or not i.strip() for i in ids) or len(ids) != len(set(ids)):
        raise ValueError('Missing or duplicate row IDs')
    # Reuse the V4 auditor. Malformed audit structures are rejected, not "passed".
    try: coverage = audit(raw, inventory)
    except (KeyError, TypeError, AttributeError) as exc: raise ValueError('Malformed V4 cases/inventory') from exc
    if receipt.get('response_contract') is not None or raw.get('schema_version') is not None:
        if receipt.get('response_contract')!=RESPONSE_VERSION or receipt.get('scoring_profile')!=SCORING_PROFILE:
            raise ValueError('Release response must be bound to a compatible receipt')
        if receipt['status']=='success':
            _,coverage=validate(json.dumps(raw),inventory,parse_fmea,require_release=True)
    run_id = receipt['experiment_id'] + ':' + receipt['attempt_id']
    settings = {k:v for k,v in receipt['configuration'].items() if k in ('temperature','top_p','top_k','seed','max_output_tokens','retry_attempts','response_mime_type')}
    if any(isinstance(v,(list,dict)) for v in settings.values()): raise ValueError('Configuration values must be scalar')
    meta = {'run_id': run_id, 'experiment_id': receipt['experiment_id'], 'system': receipt['system_id'],
            'dataset_id': receipt['system_sha256'], 'dataset_version': dataset_version,
            'workflow': 'standalone_gemini', 'skill_version': 'v4.0-inventory', 'skill_sha256': receipt['skill_sha256'],
            'generator_model': receipt['model'], 'generator_provider':'Gemini', 'configuration': settings, 'git_commit': receipt['git_commit'],
            'scoring_policy': POLICY, 'rating_range': [1, 10], 'generation_timestamp': receipt['started_at'],
            'generation_status': receipt['status'], 'response_sha256': response_hash, 'inventory_sha256': inventory_hash,
            'estimated_cost': receipt.get('estimated_cost'), 'generation_seconds': receipt.get('total_elapsed_seconds'),
            'coverage_status': coverage['structural_status'], 'data_origin': receipt.get('data_origin', 'private_generated_output')}
    return {'schema': SCHEMA, 'metadata': meta, 'rows': raw['rows'], 'units': units, 'coverage': coverage, 'v4_response':raw}


class EngineeringStore:
    def __init__(self, path='results/engineering/workspace.sqlite'):
        self.path = private(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
          PRAGMA foreign_keys=ON;
          CREATE TABLE IF NOT EXISTS engineering_runs(run_id TEXT PRIMARY KEY, content_hash TEXT NOT NULL, payload TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS engineering_rows(record_id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES engineering_runs(run_id),row_id TEXT NOT NULL,original TEXT NOT NULL,unit TEXT,UNIQUE(run_id,row_id));
          CREATE TABLE IF NOT EXISTS engineering_events(event_id INTEGER PRIMARY KEY,record_id TEXT NOT NULL REFERENCES engineering_rows(record_id),revision INTEGER NOT NULL,state TEXT NOT NULL,reviewer TEXT NOT NULL,note TEXT NOT NULL,corrections TEXT NOT NULL,basis TEXT,at TEXT NOT NULL,UNIQUE(record_id,revision));
        ''')

    def close(self): self.db.close()

    def ingest(self, response, inventory, receipt, dataset_version):
        # Explicit file selection only; no recursion or discovery of private worksheets.
        paths = [private(p) for p in (response, inventory, receipt)]
        raw, inv, rec = [strict_read(p.read_text(encoding='utf-8')) for p in paths]
        data = normalize(raw, inv, rec, dataset_version, file_digest(paths[0]), file_digest(paths[1]))
        key = data['metadata']['run_id']; sha = digest(data)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            old = self.db.execute('SELECT content_hash FROM engineering_runs WHERE run_id=?', (key,)).fetchone()
            if old:
                if old[0] != sha: raise ValueError('Run ID already exists with different immutable content')
                self.db.rollback(); return key
            self.db.execute('INSERT INTO engineering_runs VALUES(?,?,?)', (key, sha, encoded(data)))
            for row in data['rows']:
                record = digest([key, row['row_id']]); unit = data['units'].get(row.get('unit_id'))
                self.db.execute('INSERT INTO engineering_rows VALUES(?,?,?,?,?)', (record, key, row['row_id'], encoded(row), encoded(unit)))
                for revision, state in enumerate(('GENERATED', 'VALIDATION_PENDING', 'NEEDS_REVIEW')):
                    self.db.execute('INSERT INTO engineering_events(record_id,revision,state,reviewer,note,corrections,at) VALUES(?,?,?,?,?,?,?)',
                                    (record, revision, state, 'import', 'Post-generation validation; not engineering approval', '{}', now()))
            self.db.commit()
        except BaseException: self.db.rollback(); raise
        return key

    def records(self):
        result = []
        metadata = {r['run_id']:json.loads(r['payload'])['metadata'] for r in self.db.execute('SELECT * FROM engineering_runs')}
        history = {}
        for event in self.db.execute('SELECT * FROM engineering_events ORDER BY revision'):
            history.setdefault(event['record_id'],[]).append(dict(event))
        for row in self.db.execute('SELECT * FROM engineering_rows ORDER BY run_id,row_id'):
            events = history[row['record_id']]
            original = json.loads(row['original']); current = dict(original)
            for event in events: current.update(json.loads(event['corrections']))
            # Original arithmetic is preserved separately; reviewed RPN is always derived.
            current.pop('RPN', None)
            unit = json.loads(row['unit']); validation = findings(current, unit)
            meta = metadata[row['run_id']]
            latest = events[-1]
            if latest['state']=='APPROVED': validation['engineering_status']='HUMAN_APPROVED_SELF_ASSERTED'
            result.append({'record_id': row['record_id'], 'run_id': row['run_id'], 'row_id': row['row_id'], 'original': original,
                           'current': current, 'metadata': meta, 'unit': unit, 'validation': validation,
                           'original_validation': findings(original, unit), 'revision': latest['revision'],
                           'review_status': latest['state'], 'review_basis': latest['basis'], 'history': events,
                           'evidence_refs':[{'source_id':meta['dataset_id'],'unit_id':original.get('unit_id'),
                                             'locator':unit.get('source_line') if unit else None,
                                             'scope':'Input-package component facts, not verified failure consequences'}] if unit else []})
        return result

    def review(self, record_id, expected_revision, state, reviewer, note, corrections=None, basis=None, engineering_confirmed=False):
        if state not in STATES or not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(note, str) or not note.strip():
            raise ValueError('State, reviewer and substantive review note are required')
        corrections = {} if corrections is None else corrections
        if not isinstance(corrections, dict) or set(corrections) - EDITABLE: raise ValueError('Unknown or immutable correction fields')
        for k, v in corrections.items():
            if k in RATINGS:
                if v is not None and not rating(v): raise ValueError('Corrections require integer ratings 1-10 or null')
            elif not isinstance(v, str): raise ValueError('Text corrections must be strings')
        if corrections.get('action_status', '') not in ('', 'OPEN', 'IN_PROGRESS', 'COMPLETE'): raise ValueError('Invalid action status')
        if 'judge_disposition' in corrections and corrections['judge_disposition'] not in JUDGE_DISPOSITIONS:
            raise ValueError('Invalid engineering disposition')
        if corrections.get('action_due_date'):
            from datetime import date
            date.fromisoformat(corrections['action_due_date'])
        self.db.execute('BEGIN IMMEDIATE')
        try:
            record = next((r for r in self.records() if r['record_id'] == record_id), None)
            if record is None: raise ValueError('Unknown record')
            if type(expected_revision) is not int or record['revision'] != expected_revision: raise ValueError('Stale review; refresh before saving')
            if record['review_status'] in ('APPROVED', 'REJECTED') and state != 'NEEDS_REVIEW': raise ValueError('Reopen the record before revising an approval/rejection')
            candidate = {**record['current'], **corrections}
            if state == 'APPROVED':
                if findings(candidate, record['unit'])['structural_status'] != 'PASS': raise ValueError('Correct structural errors before approval')
                if engineering_confirmed is not True or basis not in ('source_verified', 'approved_inference'):
                    raise ValueError('Explicit engineering confirmation and review basis required')
                if basis == 'source_verified' and missing(candidate.get('evidence')): raise ValueError('Source verification requires a source citation')
                if any(missing(candidate.get(k)) for k in ('cause', 'local_effect', 'system_effect', 'recommended_action')):
                    raise ValueError('Resolve missing cause/effects/action before approval')
            self.db.execute('INSERT INTO engineering_events(record_id,revision,state,reviewer,note,corrections,basis,at) VALUES(?,?,?,?,?,?,?,?)',
                            (record_id, expected_revision+1, state, reviewer.strip(), note.strip(), encoded(corrections), basis, now()))
            self.db.commit()
        except BaseException: self.db.rollback(); raise

    def snapshot(self):
        records = self.records(); originals = [r['original'] for r in records]
        fingerprints = [tuple(re.sub(r'\s+', ' ', str(r.get(k, '')).strip().casefold()) for k in
                              ('unit_id', 'failure_mode', 'cause', 'local_effect', 'system_effect', 'operating_state')) for r in originals]
        # Fingerprints and rates are within run; no pooled duplicate metric across systems/experiments.
        keyed = [(r['run_id'], fp) for r, fp in zip(records, fingerprints)]
        count = len(records); valid = sum(r['original_validation']['structural_status'] == 'PASS' for r in records)
        duplicate_keys = Counter(keyed)
        for record, key in zip(records, keyed):
            if duplicate_keys[key] > 1: record['validation']['review_flags'].append('Duplicate original fingerprint within this run')
        summary = {'generated_rows': count, 'unique_rows_within_runs': len(set(keyed)),
                   'high_severity_rows': sum(rating(r.get('severity')) and r['severity'] >= 9 for r in originals),
                   'needs_review': sum(r['review_status'] == 'NEEDS_REVIEW' for r in records),
                   'original_structural_pass_percentage': 100*valid/count if count else None,
                   'cited_evidence_percentage': 100*sum(not missing(r.get('evidence')) for r in originals)/count if count else None,
                   'basis': 'Original imported rows; citation presence is not verified evidence coverage; S>=9 is visibility, not acceptance'}
        flat = []
        for r in records:
            row = r['current']; meta = r['metadata']; unit = r['unit'] or {}
            flat.append({'record_id': r['record_id'], 'run_id': r['run_id'], 'row_id': r['row_id'], 'system': meta['system'],
                         'subsystem': unit.get('parent_id') or 'Not provided',
                         **{k: row.get(k) if (rating(row.get(k)) if k in RATINGS else isinstance(row.get(k),str)) else None for k in FIELDS}, 'RPN': rpn(row), 'original_RPN': rpn(r['original']),
                         'review_status': r['review_status'], 'revision': r['revision'], 'skill_version': meta['skill_version'],
                         'evidence_status': r['review_basis'] if r['review_status']=='APPROVED' else 'missing' if missing(row.get('evidence')) else 'cited_unverified',
                         'structural_status': r['validation']['structural_status'], 'dataset_version': meta['dataset_version']})
        comparisons = []
        groups = {}
        for r in records: groups.setdefault(r['run_id'], []).append(r)
        for run_id, group in groups.items():
            meta = group[0]['metadata']; condition = {k: meta[k] for k in ('workflow','dataset_id','dataset_version','scoring_policy')}
            duplicate_count = len(group) - len({fp for key, fp in keyed if key == run_id})
            comparisons.append({**meta, 'comparison_key': digest(condition), 'generated_rows': len(group),
                                'duplicate_rows': duplicate_count, 'duplicate_percentage': 100*duplicate_count/len(group),
                                'approved_rows': sum(r['review_status']=='APPROVED' for r in group),
                                'reviewed_rows': sum(r['review_status'] in ('APPROVED','REJECTED') for r in group),
                                'recall': None, 'precision': None, 'unsupported_assertion_rate': None,
                                'note': 'Engineering review is separate from independent judge evaluation; no inferred quality scores'})
        risks = {}
        for basis in ('original', 'current'):
            matrix, histogram, subsystems, categories, actions = Counter(), Counter(), Counter(), Counter(), Counter()
            for record in records:
                row = record[basis]; score = rpn(row)
                if rating(row.get('severity')) and rating(row.get('occurrence')): matrix[(row['severity'],row['occurrence'])] += 1
                if score is not None: histogram[min(9,(score-1)//100)] += 1
                unit = record['unit'] or {}; subsystems[unit.get('parent_id') or 'Unassigned subsystem'] += 1
                categories[row.get('category') or 'Unclassified'] += 1
                if row.get('action_status'):
                    from datetime import date
                    state = row['action_status']
                    try:
                        if row.get('action_due_date') and state!='COMPLETE' and date.fromisoformat(row['action_due_date']) < date.today(): state='OVERDUE'
                    except (ValueError,TypeError): state='INVALID_ACTION_DATA'
                    actions[state] += 1
            risks[basis] = {'matrix':[{'severity':s,'occurrence':o,'count':n} for (s,o),n in sorted(matrix.items())],
                            'rpn_bins':[{'lower':k*100+1,'upper':(k+1)*100,'count':histogram[k]} for k in range(10)],
                            'subsystems':[{'name':k,'count':v} for k,v in sorted(subsystems.items())],
                            'categories':[{'name':k,'count':v} for k,v in categories.most_common()],
                            'actions':[{'state':k,'count':v} for k,v in sorted(actions.items())],
                            'missing_rpn_rows':sum(rpn(r[basis]) is None for r in records)}
        result = {'schema': SCHEMA, 'private': True, 'updated_at': now(), 'summary': summary, 'rows': flat, 'records': records, 'comparisons': comparisons, 'risk':risks,
                  'coverage_audits':{r['run_id']:json.loads(r['payload'])['coverage'] for r in self.db.execute('SELECT * FROM engineering_runs')},
                  'content_version': digest(records), 'limitations': 'Human identity is self-asserted; no source worksheet access, calibrated confidence, residual-risk inference or automatic risk acceptance.'}
        validate_workspace(result)
        return result


def validate_workspace(data):
    """Runtime invariants for normalized output; invalid original values remain forensic data."""
    if data.get('schema')!=SCHEMA or data.get('private') is not True: raise ValueError('Invalid workspace schema/privacy marker')
    ids=[r['record_id'] for r in data['rows']]
    if len(ids)!=len(set(ids)) or set(ids)!={r['record_id'] for r in data['records']}: raise ValueError('Record identities differ')
    for row in data['rows']:
        if any(row[k] is not None and not rating(row[k]) for k in RATINGS): raise ValueError('Invalid normalized rating')
        if row['RPN']!=rpn(row): raise ValueError('Normalized RPN mismatch')
        if row['review_status'] not in STATES: raise ValueError('Invalid review state')
    if data['content_version']!=digest(data['records']): raise ValueError('Workspace content hash mismatch')
    return data


def atomic_export(path, data):
    path = private(path); path.parent.mkdir(parents=True, exist_ok=True)
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as stream:
        stream.write(encoded(data)); temporary=Path(stream.name)
    try: temporary.replace(path)
    finally:
        if temporary.exists(): temporary.unlink()


def safe_cell(value):
    text = '' if value is None else str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text


def export_csv(snapshot, path, record_ids=None):
    path = private(path); path.parent.mkdir(parents=True, exist_ok=True)
    rows = snapshot['rows']
    if record_ids is not None: rows = [r for r in rows if r['record_id'] in record_ids]
    # Names fixed even for empty exports; no original/approval history is silently lost in JSON.
    fields = ['record_id','run_id','row_id','system','subsystem'] + FIELDS + ['RPN','original_RPN','review_status','revision','evidence_status','structural_status','skill_version','dataset_version']
    with path.open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        writer.writerows({k: safe_cell(r.get(k)) for k in fields} for r in rows)


def compare_keys(snapshot, run_ids):
    rows = [r for r in snapshot['comparisons'] if r['run_id'] in run_ids]
    if len(rows) != len(set(run_ids)): raise ValueError('Unknown comparison run')
    if len({r['comparison_key'] for r in rows}) > 1: raise ValueError('Incompatible datasets, workflows or scoring policies')
    return rows
