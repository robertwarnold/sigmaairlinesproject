"""V4.1 orchestration, extending V4 aggregation rather than duplicating research math."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from .registry import Registry, encoded, now
from .github_sync import discover_branches, synchronize
from .judge_import import adapt
from .finance import model, DEFAULTS
from analysis.round2.__main__ import private, read, write_csv, QUALITY

EXTRA_FIELDS={'workflow_executions','evaluations','operations','lifecycle_events','financial','field_accuracy'}


def snapshot(store,output,render=True):
    # Keep registry, selected evaluations and counters on one consistent SQLite view.
    with store.transaction():
        return _snapshot(store,output,render)


def _snapshot(store,output,render=True):
    """Validate/render in isolated staging and replace current only on success."""
    from .__main__ import build, atomic_json, validate_snapshot
    output=private(output)
    generations=[store.generation(r[0]) for r in store.db.execute('SELECT id FROM generations ORDER BY id')]
    records=store.selected(); validated,items=store.validate_cohort(records)
    with tempfile.TemporaryDirectory(dir=store.path.parent,prefix='.snapshot-') as temp:
        root=Path(temp); paths=[]
        if records:
            source=root/'judge_import.json'; atomic_json(source,{'schema':'standalone-judge-import-1','workflow':'standalone_gemini','runs':records}); paths=[source]
        data=build(paths,root/'build',render=False)
        data['schema']='sigma-dashboard-4.1'
        quality={r['run_id']:r for r in data['runs']}
        registry=[]
        for generation in generations:
            gid=generation['generation_id']; evaluated=quality.get(gid)
            row={k:generation.get(k) for k in ('generation_id','run_id','system','skill_version','replicate','batch','generator_model',
                 'engineering_run_id','original_filename',
                 'workflow_execution_id','parent_workflow_run_id','workflow_attempt','generation_timestamp','generation_finished_at','generation_seconds','generation_status',
                 'generated_rows','structural_status','duplicate_rows','traceability_status','artifact_reference','git_commit','skill_sha256','actual_cost','estimated_cost')}
            row.update(state=generation['state'],evaluation_status='evaluated' if evaluated else 'awaiting_evaluation' if generation['generation_status']=='success' else 'not_evaluated',
                       evaluation_label='Evaluated' if evaluated else 'Awaiting Independent Evaluation' if generation['generation_status']=='success' else generation['state'],
                       missed_percentage=evaluated['missed_percentage'] if evaluated else None,
                       selected_evaluation=generation['selected_evaluation'])
            registry.append(row)
        data['registry']=registry
        data['workflow_executions']=[json.loads(r[0]) for r in store.db.execute('SELECT payload FROM workflows ORDER BY id')]
        data['evaluations']=[{'evaluation_id':r['id'],'generation_id':r['generation_id'],'accepted_at':r['created_at'],
                             'selected':any(g['selected_evaluation']==r['id'] for g in generations),
                             'judge_timestamp':json.loads(r['payload']).get('evaluation_timestamp'),
                             'judge_model':json.loads(r['payload'])['judge_model'],'judge_skill_version':json.loads(r['payload'])['judge_skill_version']} for r in store.db.execute('SELECT * FROM evaluations ORDER BY id')]
        success=[g for g in generations if g['generation_status']=='success']; failures=[g for g in generations if g['generation_status']=='failed']
        sync=store.db.execute('SELECT payload FROM sync_state WHERE id=1').fetchone()
        times=[g['generation_seconds'] for g in success if g.get('generation_seconds') is not None]
        calls=[g.get('api_calls') for g in generations]
        tokens=[g.get('token_usage',{}).get('total_token_count') if isinstance(g.get('token_usage'),dict) else None for g in generations]
        latest=sorted(data['workflow_executions'],key=lambda w:w.get('created_at') or '')
        turnaround=[]
        from datetime import datetime
        for generation in generations:
            if generation['selected_evaluation'] and generation.get('generation_finished_at'):
                evaluation=store.db.execute('SELECT payload FROM evaluations WHERE id=?',(generation['selected_evaluation'],)).fetchone()
                timestamp=json.loads(evaluation[0]).get('evaluation_timestamp')
                if timestamp:
                    try:
                        seconds=(datetime.fromisoformat(timestamp.replace('Z','+00:00'))-datetime.fromisoformat(generation['generation_finished_at'].replace('Z','+00:00'))).total_seconds()
                        if seconds>=0: turnaround.append(seconds)
                    except (ValueError,TypeError): pass
        from collections import Counter
        activity=Counter((g['generation_timestamp'][:10],g['generation_status']) for g in generations if g.get('generation_timestamp'))
        data['operations']={'generation_activity':[{'date':date,'generation_status':state,'count':count} for (date,state),count in sorted(activity.items())],'mean_evaluation_turnaround_seconds':sum(turnaround)/len(turnaround) if turnaround else None,'turnaround_denominator':len(turnaround),'registered_generations':len(generations),'total_generated':len(success),'failed_generations':len(failures),
                            'evaluated_fmeas':len(validated),'completed_evaluations':len(data['evaluations']),
                            'awaiting_judge':sum(r['evaluation_status']=='awaiting_evaluation' for r in registry),
                            'generation_success_percentage':100*len(success)/(len(success)+len(failures)) if success or failures else None,
                            'mean_success_generation_seconds':sum(times)/len(times) if times else None,
                            'timing_denominator':len(times),'api_calls':sum(calls) if calls and all(type(v) is int for v in calls) else None,
                            'total_tokens':sum(tokens) if tokens and all(type(v) is int for v in tokens) else None,
                            'sync':json.loads(sync[0]) if sync else {'last_successful_sync':None,'status':'OFFLINE'},
                            'latest_workflow':latest[-1] if latest else None}
        # Conditional field accuracy uses each field's observed matched-item denominator.
        accuracy=[]
        for version in ('v2.0','v3.0','v3.0-audit','v4.0'):
            rows=[r for r in validated if r['skill_version']==version]
            for field in QUALITY:
                denominator=sum(r[field+'_denominator'] for r in rows)
                numerator=sum(r[field+'_fraction']*r[field+'_denominator'] for r in rows if r[field+'_fraction'] is not None)
                accuracy.append({'skill_version':version,'field':field,'denominator':denominator,'accuracy_percentage':100*numerator/denominator if denominator else None})
        data['field_accuracy']=accuracy
        for generation in generations:
            minutes=[]
            for event in store.db.execute("SELECT details FROM events WHERE object_type='human_review'"):
                review=json.loads(event[0])
                if review['generation_id']==generation['generation_id'] and review.get('review_minutes') is not None: minutes.append(review['review_minutes'])
            generation['recorded_review_minutes']=sum(minutes) if minutes else None
        data['financial']=model(generations,validated,data['baseline'])
        events=store.db.execute('SELECT object_type,object_id,state,at FROM events ORDER BY id DESC LIMIT 100').fetchall()
        data['lifecycle_events']=[dict(e) for e in events]
        data['last_updated']=now(); data['data_version']=hashlib.sha256(encoded({k:v for k,v in data.items() if k not in ('last_updated','data_version')}).encode()).hexdigest()
        validate_snapshot(data)
        staged=root/'dashboard.json'; atomic_json(staged,data)
        if render:
            destination=output.parent/'exports'/data['data_version']
            subprocess.run(['Rscript','dashboard/export.R',str(staged),str(destination)],check=True)
            notes=root/'build/presenter-notes.md'
            if notes.exists():
                text=notes.read_text(encoding='utf-8').replace('Poster presentation','Presentation mode')
                text+=f"\nRegistry evidence: {len(generations)} attempts; {len(success)} successful generations; {len(failures)} failed; {len(validated)} evaluated FMEAs. Synchronization status: {data['operations']['sync']['status']}.\n"
                (destination/'presenter-notes.md').write_text(text,encoding='utf-8')
        # Validated internal metrics retain items separately from browser data.
        internal=store.path.parent/'validated'; internal.mkdir(exist_ok=True)
        write_csv(internal/'selected_runs.csv',validated); write_csv(internal/'selected_items.csv',items)
        (internal/'analysis.xlsx').write_bytes((root/'build/validated/analysis.xlsx').read_bytes())
        atomic_json(output,data)
    return data


def validate_extended(data):
    """Reduce an allowlisted 4.1 envelope through the existing V4 validator."""
    from .__main__ import validate_snapshot, SAFE_RUN_FIELDS, SCHEMA
    if set(data)-EXTRA_FIELDS != {'schema','data_version','last_updated','validation_status','research_status','baseline','runs','registry','per_system','per_version','pareto','statistics','review_summary','coverage_summary'}: raise ValueError('Invalid 4.1 envelope')
    allowed={'generation_id','run_id','system','skill_version','replicate','batch','generator_model','workflow_execution_id',
             'engineering_run_id','original_filename',
             'parent_workflow_run_id','workflow_attempt','generation_timestamp','generation_finished_at','generation_seconds','generation_status','generated_rows','structural_status',
             'duplicate_rows','traceability_status','artifact_reference','git_commit','skill_sha256','actual_cost','estimated_cost',
             'state','evaluation_status','evaluation_label','missed_percentage','selected_evaluation'}
    for row in data['registry']:
        if set(row)-allowed: raise ValueError('Unsafe generation registry field')
        if row['evaluation_status']!='evaluated' and row['missed_percentage'] is not None: raise ValueError('Unevaluated generation cannot have quality metrics')
    base={k:v for k,v in data.items() if k not in EXTRA_FIELDS}; base['schema']=SCHEMA
    base['registry']=[{k:v for k,v in r.items() if k in SAFE_RUN_FIELDS or k in ('git_commit','skill_sha256')} for r in data['registry']]
    validate_snapshot(base)
    if data['operations']['evaluated_fmeas']!=len(data['runs']): raise ValueError('Evaluation count mismatch')
    return data


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--database',default='results/research/registry.sqlite')
    sub=parser.add_subparsers(dest='command',required=True)
    s=sub.add_parser('sync'); s.add_argument('--repository',default='robertwarnold/sigmaairlinesproject'); s.add_argument('--run-id'); s.add_argument('--metadata-only',action='store_true')
    s.add_argument('--branch', action='append', default=[])
    s.add_argument('--list-branches', action='store_true')
    s.add_argument('--no-render', action='store_true')
    s.add_argument('--engineering-database')
    h=sub.add_parser('import-historical')
    h.add_argument('--file',required=True,type=Path)
    r=sub.add_parser('register-generation'); r.add_argument('--receipt',required=True)
    p=sub.add_parser('register-plan'); p.add_argument('--manifest',required=True)
    for name in ('preview-judge','accept-judge'):
        j=sub.add_parser(name); j.add_argument('--file',required=True); j.add_argument('--items'); j.add_argument('--confirm-sha256')
        j.add_argument('--no-render',action='store_true')
    select=sub.add_parser('select-evaluation'); select.add_argument('--generation-id',required=True); select.add_argument('--evaluation-id',required=True)
    review=sub.add_parser('record-review'); review.add_argument('--generation-id',required=True); review.add_argument('--event-id',required=True); review.add_argument('--outcome',choices=['complete','pending'],required=True); review.add_argument('--reviewed-at',required=True); review.add_argument('--minutes',type=float)
    migrate=sub.add_parser('migrate'); migrate.add_argument('--receipts',nargs='+',required=True)
    sub.add_parser('reconcile')
    refresh=sub.add_parser('refresh'); refresh.add_argument('--output',default=None); refresh.add_argument('--no-render',action='store_true')
    watch=sub.add_parser('watch'); watch.add_argument('--repository',default='robertwarnold/sigmaairlinesproject'); watch.add_argument('--interval',type=int,default=60); watch.add_argument('--once',action='store_true'); watch.add_argument('--output',default='results/research/current.json')
    finance=sub.add_parser('finance'); finance.add_argument('--snapshot',required=True); finance.add_argument('--assumptions',required=True); finance.add_argument('--output',required=True)
    finance.add_argument('--compare-scenarios',action='store_true')
    args=parser.parse_args()
    if args.command=='import-historical':
        from .historical import import_comparison
        print(encoded(import_comparison(args.file,private(args.database).parent/'historical-comparison.json')))
        return
    if args.command=='finance':
        from .__main__ import atomic_json
        data=read(private(args.snapshot)); values=read(private(args.assumptions))
        result=model(data.get('registry',[]),data['runs'],data['baseline'],values)
        if args.compare_scenarios:
            from .finance import scenario_comparison
            result['scenario_comparison']=scenario_comparison(data.get('registry',[]),data['runs'],data['baseline'],values)
        atomic_json(private(args.output),result); return
    store=Registry(args.database)
    try:
        if args.command=='sync':
            if args.list_branches:
                print(encoded(discover_branches(args.repository)))
            else:
                from contextlib import ExitStack, closing
                with ExitStack() as stack:
                    engineering=None
                    if args.engineering_database:
                        from analysis.engineering.store import EngineeringStore
                        engineering=stack.enter_context(closing(EngineeringStore(args.engineering_database)))
                    result=synchronize(store,args.repository,run_id=args.run_id,download=not args.metadata_only,branches=args.branch,engineering=engineering)
                print(encoded(result))
                snapshot(store,store.path.parent/'current.json',not args.no_render)
        elif args.command=='register-generation':
            with store.transaction(): print(store.receipt(args.receipt))
            snapshot(store,store.path.parent/'current.json')
        elif args.command=='register-plan':
            with store.transaction(): store.plan(args.manifest)
            snapshot(store,store.path.parent/'current.json')
        elif args.command in ('preview-judge','accept-judge'):
            data=adapt(args.file,args.items); sha=hashlib.sha256(private(args.file).read_bytes()).hexdigest()
            if args.items: sha=hashlib.sha256((sha+hashlib.sha256(private(args.items).read_bytes()).hexdigest()).encode()).hexdigest()
            if args.command=='preview-judge': previews=store.preview(data)
            else:
                if args.confirm_sha256!=sha: raise ValueError('Acceptance requires exact preview --confirm-sha256 digest')
                previews=store.accept(data,args.file)
                if args.items: store.archive(args.items)
                snapshot(store,store.path.parent/'current.json',not args.no_render)
            print(encoded({'confirmation_sha256':sha,'records':[{k:v for k,v in p.items() if k!='record'} for p in previews]}))
        elif args.command=='select-evaluation': store.select(args.generation_id,args.evaluation_id); snapshot(store,store.path.parent/'current.json')
        elif args.command=='record-review': store.human_review(args.generation_id,args.event_id,args.outcome,args.reviewed_at,args.minutes); snapshot(store,store.path.parent/'current.json')
        elif args.command=='migrate':
            with store.transaction():
                for source in args.receipts: store.receipt(source)
            snapshot(store,store.path.parent/'current.json')
        elif args.command=='reconcile': print(encoded(store.reconcile()))
        elif args.command=='refresh': snapshot(store,args.output or store.path.parent/'current.json',not args.no_render)
        elif args.command=='watch':
            if args.interval<30: raise ValueError('Polling interval must be at least 30 seconds')
            while True:
                delay=args.interval
                try:
                    result=synchronize(store,args.repository); snapshot(store,args.output)
                    if result['status']=='RATE_LIMITED' and str(result.get('retry_after','')).isdigit():
                        value=int(result['retry_after'])
                        delay=max(delay,int(value-time.time())+1 if value>1000000000 else value)
                except Exception as exc: print('SYNC_ERROR '+type(exc).__name__,flush=True)
                if args.once: break
                # Respect reset/retry-after with interruptible waits; no model request is retried.
                for _ in range(delay): time.sleep(1)
    finally: store.close()

if __name__=='__main__': main()
