"""Authoritative private workflow/generation/evaluation registry for dashboard 4.1.

SQLite transactions protect acceptance; immutable raw exports and events retain
provenance. Research calculations remain in the existing validated importer.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile

from analysis.round2.__main__ import private, read, ingest

VERSIONS=('v2.0','v3.0','v3.0-audit','v4.0')
STATES=('PLANNED','QUEUED','RUNNING','GENERATION_FAILED','GENERATED','AWAITING_JUDGE',
        'JUDGE_IMPORTED','VALIDATION_FAILED','EVALUATED','HUMAN_REVIEW_PENDING','COMPLETE')


def now(): return datetime.now(timezone.utc).isoformat()
def encoded(value): return json.dumps(value,sort_keys=True,allow_nan=False)
def digest(value): return hashlib.sha256(encoded(value).encode()).hexdigest()


def workflow_key(repository, run_id, attempt):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository): raise ValueError('Invalid repository')
    if not str(run_id).isdigit() or int(run_id)<1 or type(attempt) is not int or attempt<1: raise ValueError('Invalid workflow identity')
    return f'{repository}/{run_id}/{attempt}'


class Registry:
    def __init__(self,path='results/research/registry.sqlite'):
        self.path=private(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.raw=self.path.parent/'private'/'registry-raw'; self.raw.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path,timeout=30,isolation_level=None)
        self.db.row_factory=sqlite3.Row
        self.db.executescript('''
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS workflows(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS generations(id TEXT PRIMARY KEY,workflow_id TEXT REFERENCES workflows(id),payload TEXT NOT NULL,state TEXT NOT NULL,selected_evaluation TEXT);
            CREATE TABLE IF NOT EXISTS aliases(alias TEXT NOT NULL,generation_id TEXT REFERENCES generations(id),PRIMARY KEY(alias,generation_id));
            CREATE TABLE IF NOT EXISTS evaluations(id TEXT PRIMARY KEY,generation_id TEXT REFERENCES generations(id),payload TEXT NOT NULL,source_hash TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,object_type TEXT NOT NULL,object_id TEXT NOT NULL,state TEXT NOT NULL,at TEXT NOT NULL,details TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY,workflow_id TEXT REFERENCES workflows(id),payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sync_runs(execution_id TEXT PRIMARY KEY,updated_at TEXT,artifacts_complete INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS sync_state(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL);
        ''')

    def close(self): self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try: yield; self.db.execute('COMMIT')
        except BaseException: self.db.execute('ROLLBACK'); raise

    def event(self,kind,identity,state,details=None):
        previous=self.db.execute('SELECT state,details FROM events WHERE object_type=? AND object_id=? ORDER BY id DESC LIMIT 1',(kind,identity)).fetchone()
        text=encoded(details or {})
        if not previous or previous['state']!=state or previous['details']!=text:
            self.db.execute('INSERT INTO events(object_type,object_id,state,at,details) VALUES(?,?,?,?,?)',(kind,identity,state,now(),text))

    def transition(self,gid,state,details=None):
        if state not in STATES: raise ValueError('Invalid lifecycle')
        current=self.generation(gid)
        if current is None: raise ValueError('Unknown generation')
        allowed={
            'PLANNED':{'QUEUED','RUNNING','GENERATED','GENERATION_FAILED','VALIDATION_FAILED'},
            'QUEUED':{'RUNNING','GENERATED','GENERATION_FAILED','VALIDATION_FAILED'},
            'RUNNING':{'GENERATED','GENERATION_FAILED','VALIDATION_FAILED'},
            'GENERATION_FAILED':{'QUEUED','RUNNING','GENERATED'},
            'GENERATED':{'AWAITING_JUDGE','GENERATION_FAILED'},
            'AWAITING_JUDGE':{'JUDGE_IMPORTED','VALIDATION_FAILED'},
            'JUDGE_IMPORTED':{'EVALUATED','VALIDATION_FAILED'},
            'VALIDATION_FAILED':{'JUDGE_IMPORTED','AWAITING_JUDGE'},
            'EVALUATED':{'HUMAN_REVIEW_PENDING','JUDGE_IMPORTED'},
            'HUMAN_REVIEW_PENDING':{'COMPLETE','JUDGE_IMPORTED'},
            'COMPLETE':{'HUMAN_REVIEW_PENDING','JUDGE_IMPORTED'}}
        if current['state']!=state and state not in allowed[current['state']]: raise ValueError('Invalid lifecycle transition')
        self.db.execute('UPDATE generations SET state=? WHERE id=?',(state,gid)); self.event('generation',gid,state,details)

    def workflow(self,repository,record):
        attempt=int(record.get('run_attempt',1)); key=workflow_key(repository,record['id'],attempt)
        payload={'execution_id':key,'repository':repository,'workflow_name':record.get('name'),
                 'workflow_run_id':str(record['id']),'run_attempt':attempt,'job_ids':record.get('job_ids',[]),
                 'git_commit':record.get('head_sha'),'branch':record.get('head_branch'),'event':record.get('event'),
                 'created_at':record.get('created_at'),'started_at':record.get('run_started_at'),
                 'completed_at':record.get('completed_at') or (record.get('updated_at') if record.get('status')=='completed' else None),
                 'status':record.get('status'),'conclusion':record.get('conclusion'),'url':record.get('html_url')}
        if payload['url'] and not payload['url'].startswith(f'https://github.com/{repository}/actions/runs/'): raise ValueError('Unexpected workflow URL')
        self.db.execute('INSERT INTO workflows VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(key,encoded(payload)))
        self.event('workflow',key,payload['status'] or 'unknown',{'conclusion':payload['conclusion']})
        return key

    def generation(self,gid):
        row=self.db.execute('SELECT * FROM generations WHERE id=?',(gid,)).fetchone()
        return {**json.loads(row['payload']),'generation_id':row['id'],'state':row['state'],'selected_evaluation':row['selected_evaluation']} if row else None

    def resolve(self,alias):
        if self.generation(alias): return alias
        rows=self.db.execute('SELECT generation_id FROM aliases WHERE alias=?',(alias,)).fetchall()
        if len(rows)!=1: raise ValueError('Unknown or ambiguous FMEA run ID; use stable generation_id')
        return rows[0][0]

    def receipt(self,path,workflow_id=None,artifact=None):
        path=private(path); receipt=read(path)
        if receipt.get('workflow')!='standalone_gemini' or receipt.get('prompt_version') not in VERSIONS: raise ValueError('Not a supported standalone generation')
        source_id=receipt.get('source_attempt_id') or receipt.get('attempt_id')
        if not source_id or not receipt.get('experiment_id'): raise ValueError('Receipt identity unavailable')
        identity={'workflow_execution':workflow_id or receipt.get('github_execution_id'),
                  'experiment_id':receipt['experiment_id'],'attempt_id':receipt.get('attempt_id',source_id),
                  'source_attempt_id':source_id,'started_at':receipt.get('started_at')}
        gid=receipt.get('generation_id') or 'fmea-'+digest(identity)[:32]
        alias=receipt.get('study_run_id') or receipt['experiment_id'] if str(receipt.get('study_run_id') or receipt['experiment_id']).startswith('round2-') else receipt['experiment_id']+':'+receipt.get('attempt_id',source_id)
        # A queued plan retains its stable identity when actual receipt evidence arrives.
        planned=self.db.execute("SELECT g.id FROM aliases a JOIN generations g ON g.id=a.generation_id WHERE a.alias=? AND g.state IN ('PLANNED','QUEUED')",(alias,)).fetchall()
        if len(planned)==1: gid=planned[0][0]
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        for prior in self.db.execute('SELECT id,payload FROM generations'):
            payload=json.loads(prior['payload'])
            if payload.get('receipt_sha256')==sha:
                parts=path.relative_to(Path('results').resolve()).parts
                if not payload.get('parent_workflow_run_id') and len(parts)>2 and parts[0]=='github' and parts[1].isdigit():
                    payload['parent_workflow_run_id']=parts[1]; payload['workflow_attempt']=None
                    self.db.execute('UPDATE generations SET payload=? WHERE id=?',(encoded(payload),prior['id']))
                return prior['id']
        if not re.fullmatch(r'[A-Za-z0-9:._/-]{1,160}',gid): raise ValueError('Unsafe generation ID')
        old=self.generation(gid)
        status=receipt.get('status')
        if status not in ('running','success','failed'): raise ValueError('Invalid generation status')
        if old and old['generation_status']=='success' and status=='running': return gid
        if old and old['generation_status'] in ('success','failed'):
            if status!=old['generation_status'] or (old['system'],old['skill_version'],old['generator_model'],old.get('generated_rows'))!=(receipt['system_id'].removeprefix('system_'),receipt['prompt_version'],receipt['model'],receipt.get('row_count')):
                raise ValueError('Conflicting finalized receipt')
        coverage=receipt.get('completeness',{}); config=receipt.get('configuration',{})
        rows=receipt.get('row_count')
        if rows is not None and (type(rows) is not int or rows<0): raise ValueError('Invalid row count')
        if status=='success' and (rows is None or rows<1): raise ValueError('Successful generation needs rows')
        parent_run=receipt.get('github',{}).get('workflow_run_id')
        parts=path.relative_to(Path('results').resolve()).parts
        if parent_run is None and len(parts)>2 and parts[0]=='github' and parts[1].isdigit(): parent_run=parts[1]
        payload={'parent_workflow_run_id':str(parent_run) if parent_run else None,'workflow_attempt':receipt.get('github',{}).get('run_attempt'),'run_id':alias,'system':receipt['system_id'].removeprefix('system_'),
                 'skill_version':receipt['prompt_version'],'replicate':receipt.get('run_number'),
                 'batch':receipt['experiment_id'],'workflow_execution_id':workflow_id,
                 'skill_sha256':receipt.get('skill_sha256'),'git_commit':receipt.get('git_commit'),
                 'generator_model':receipt.get('model'),'configuration':config,
                 'generation_timestamp':receipt.get('started_at'),'generation_finished_at':receipt.get('finished_at'),
                 'generation_seconds':receipt.get('api_request_seconds',receipt.get('total_elapsed_seconds')),
                 'generation_status':status,'generated_rows':rows,'structural_status':coverage.get('structural_status','PENDING'),
                 'duplicate_rows':len(coverage.get('duplicate_rows',[])) if 'duplicate_rows' in coverage else receipt.get('fmea_metrics',{}).get('potential_duplicate_rows'),
                 'traceability_status':'PASS' if coverage.get('row_traceability') else 'PENDING',
                 'token_usage':receipt.get('usage_metadata'),'actual_cost':receipt.get('invoice_expense_usd'),
                 'estimated_cost':receipt.get('estimated_api_expense_usd'),
                 'api_calls':receipt.get('execution',{}).get('request_invocations'),
                 'artifact_reference':artifact,'receipt_path':str(path),'receipt_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                 'data_origin':receipt.get('data_origin','experimental')}
        if payload['system'] not in 'ABCDE' or len(payload['system'])!=1: raise ValueError('Unsupported study system')
        _,archived=self.archive(path)
        payload['receipt_path']=archived
        payload['receipt_original_path']=str(path)
        self.db.execute('INSERT INTO generations VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                        (gid,workflow_id,encoded(payload),'PLANNED',None))
        self.db.execute('INSERT OR IGNORE INTO aliases VALUES(?,?)',(alias,gid))
        if not old or old['generation_status'] in ('planned','queued','running'):
            target='RUNNING' if status=='running' else 'GENERATION_FAILED' if status=='failed' else 'GENERATED'
            if status=='failed' and receipt.get('failure_classification') in ('validation_failure','truncation','blocked'): target='VALIDATION_FAILED'
            self.transition(gid,target)
            if status=='success': self.transition(gid,'AWAITING_JUDGE')
        return gid

    def archive(self,path):
        path=private(path); content=path.read_bytes(); sha=hashlib.sha256(content).hexdigest()
        destination=self.raw/(sha+path.suffix.lower())
        if not destination.exists(): destination.write_bytes(content)
        return sha,str(destination)

    def plan(self,manifest):
        data=read(private(manifest))
        for run in data['runs']:
            alias=run['run_id']; gid='plan-'+digest(alias)[:32]
            if self.db.execute('SELECT 1 FROM aliases WHERE alias=?',(alias,)).fetchone(): continue
            payload={'run_id':alias,'system':run['system'],'skill_version':run['skill_version'],
                     'replicate':run.get('replicate'),'batch':data.get('experiment_id','planned'),
                     'generator_model':data.get('generator_model'),'generation_status':'planned'}
            self.db.execute('INSERT INTO generations VALUES(?,?,?,?,?)',(gid,None,encoded(payload),'PLANNED',None))
            self.db.execute('INSERT INTO aliases VALUES(?,?)',(alias,gid)); self.event('generation',gid,'PLANNED')

    def selected(self,replacement=None):
        records=[]
        for row in self.db.execute('SELECT g.id,e.payload FROM generations g JOIN evaluations e ON e.id=g.selected_evaluation'):
            if replacement and row['id'] in replacement: continue
            run=json.loads(row['payload']); run['run_id']=row['id']; records.append(run)
        if replacement:
            for gid,run in replacement.items(): records.append({**run,'run_id':gid})
        return records

    def validate_cohort(self,records):
        if not records: return [],[]
        with tempfile.TemporaryDirectory(dir=self.path.parent) as temp:
            path=Path(temp)/'judge_import.json'; path.write_text(encoded({'schema':'standalone-judge-import-1','workflow':'standalone_gemini','runs':records}),encoding='utf-8')
            runs,items,_,_=ingest([path])
        return runs,items

    def preview(self,data):
        if data.get('schema')!='standalone-judge-import-1' or data.get('workflow')!='standalone_gemini': raise ValueError('Existing judge schema required')
        previews=[]; replacements={}; identifiers=set()
        for run in data['runs']:
            gid=self.resolve(run.get('generation_id',run['run_id'])); generation=self.generation(gid)
            if generation['generation_status']!='success': raise ValueError('Judge result requires a successful generation')
            if (run['system'],run['skill_version'],run['generated_rows'])!=(generation['system'],generation['skill_version'],generation['generated_rows']): raise ValueError('Judge/generation system, version or row count mismatch')
            run=dict(run)
            if run.get('skill_sha256') and generation.get('skill_sha256') and run['skill_sha256']!=generation['skill_sha256']: raise ValueError('Judge/generation skill hash mismatch')
            if run.get('generation_receipt_path'):
                supplied=str(private(run['generation_receipt_path']))
                expected={str(private(generation['receipt_path']))}
                if generation.get('receipt_original_path'): expected.add(str(private(generation['receipt_original_path'])))
                if supplied not in expected: raise ValueError('Judge receipt is not the registered generation receipt')
                run['generation_receipt_path']=generation['receipt_path']
            if run['generator_model']!=generation['generator_model']: raise ValueError('Judge/generation model mismatch')
            if any(k in generation.get('configuration',{}) and generation['configuration'][k]!=v for k,v in run['settings'].items()): raise ValueError('Judge/generation settings mismatch')
            eid=run.get('evaluation_id') or 'eval-'+digest({'generation':gid,'judge_export':run})[:32]
            if eid in identifiers: raise ValueError('Duplicate evaluation in import')
            identifiers.add(eid)
            existing=self.db.execute('SELECT payload,generation_id FROM evaluations WHERE id=?',(eid,)).fetchone()
            if existing and (existing['generation_id']!=gid or json.loads(existing['payload'])!=run): raise ValueError('Conflicting evaluation ID')
            self.validate_cohort([{**run,'run_id':gid}])
            select=not generation['selected_evaluation'] and gid not in replacements
            if select: replacements[gid]=run
            previews.append({'evaluation_id':eid,'generation_id':gid,'run_id':run['run_id'],'duplicate':bool(existing),
                             'selected':select,'record':run})
        self.validate_cohort(self.selected(replacements))
        return previews

    def accept(self,data,source):
        with self.transaction():
            previews=self.preview(data); sha,_=self.archive(source)
            for preview in previews:
                if preview['duplicate']:
                    self.event('import',sha,'DUPLICATE',{'evaluation_id':preview['evaluation_id']})
                    continue
                gid=preview['generation_id']; eid=preview['evaluation_id']
                self.db.execute('INSERT INTO evaluations VALUES(?,?,?,?,?)',(eid,gid,encoded(preview['record']),sha,now()))
                self.transition(gid,'JUDGE_IMPORTED',{'evaluation_id':eid})
                self.transition(gid,'EVALUATED',{'evaluation_id':eid})
                self.transition(gid,'HUMAN_REVIEW_PENDING',{'evaluation_id':eid})
                if preview['selected']: self.db.execute('UPDATE generations SET selected_evaluation=? WHERE id=?',(eid,gid))
        return previews

    def select(self,gid,eid):
        with self.transaction():
            row=self.db.execute('SELECT payload FROM evaluations WHERE id=? AND generation_id=?',(eid,gid)).fetchone()
            if not row: raise ValueError('Evaluation is not linked to this generation')
            self.validate_cohort(self.selected({gid:json.loads(row[0])}))
            self.db.execute('UPDATE generations SET selected_evaluation=? WHERE id=?',(eid,gid))
            self.event('selection',gid,'SELECTED',{'evaluation_id':eid})

    def human_review(self,gid,event_id,outcome,reviewed_at,minutes=None):
        if outcome not in ('complete','pending') or not event_id: raise ValueError('Invalid engineer review event')
        datetime.fromisoformat(reviewed_at.replace('Z','+00:00'))
        if minutes is not None and (type(minutes) not in (int,float) or minutes<0): raise ValueError('Invalid review duration')
        previous=self.db.execute("SELECT details FROM events WHERE object_type='human_review' AND object_id=?",(event_id,)).fetchone()
        details={'generation_id':gid,'outcome':outcome,'reviewed_at':reviewed_at,'review_minutes':minutes}
        if previous:
            if json.loads(previous[0])!=details: raise ValueError('Conflicting review event ID')
            return
        with self.transaction():
            generation=self.generation(gid)
            if not generation or not generation['selected_evaluation']: raise ValueError('Independent evaluation required before completion')
            self.event('human_review',event_id,'RECORDED',details)
            self.transition(gid,'COMPLETE' if outcome=='complete' else 'HUMAN_REVIEW_PENDING',{'review_event_id':event_id})

    def reconcile(self):
        generations=[self.generation(r[0]) for r in self.db.execute('SELECT id FROM generations')]
        artifacts=[json.loads(r[0]) for r in self.db.execute('SELECT payload FROM artifacts')]
        return {'schema':'registry-reconciliation-4.1','duplicate_imports':self.db.execute("SELECT count(*) FROM events WHERE object_type='import' AND state='DUPLICATE'").fetchone()[0],'workflow_executions':self.db.execute('SELECT count(*) FROM workflows').fetchone()[0],
                'generations':len(generations),'awaiting_judge':[g['generation_id'] for g in generations if g['state']=='AWAITING_JUDGE'],
                'incomplete_generations':[g['generation_id'] for g in generations if g['generation_status']=='running'],
                'missing_artifacts':[a['artifact_id'] for a in artifacts if a.get('expired') or a.get('download_status')!='downloaded'],
                'orphaned_artifacts':[a['artifact_id'] for a in artifacts if not any(g.get('artifact_reference')==a['artifact_id'] for g in generations)],
                'evaluations_without_generation':self.db.execute('SELECT count(*) FROM evaluations e LEFT JOIN generations g ON e.generation_id=g.id WHERE g.id IS NULL').fetchone()[0],
                'unregistered_workflows':[w[0] for w in self.db.execute('SELECT id FROM workflows w WHERE NOT EXISTS(SELECT 1 FROM generations g WHERE g.workflow_id=w.id)')],
                'unverified_parent_workflows':[g['generation_id'] for g in generations if g.get('parent_workflow_run_id') and not g.get('workflow_execution_id')],
                'ambiguous_run_aliases':[r[0] for r in self.db.execute('SELECT alias FROM aliases GROUP BY alias HAVING count(*)>1')]}
