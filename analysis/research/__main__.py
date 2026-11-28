"""Research data layers, atomic dashboard snapshots and offline experiment preparation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from analysis.round2.__main__ import aggregate, ingest, private, read, write_csv
from .statistics import bootstrap, compare, VERSIONS, SYSTEMS

ROOT=Path(__file__).resolve().parents[2]
SCHEMA='sigma-dashboard-4'
BASELINE=ROOT/'analysis/round2/round1_baseline.json'
SAFE_RUN_FIELDS=('run_id','system','skill_version','generator_model','judge_model','judge_skill_version',
                 'generation_timestamp','evaluation_timestamp','generation_status','evaluation_status',
                 'ground_truth_count','found','missed','missed_percentage','coverage_percentage','dpmo','generated_rows',
                 'extra_unmatched_rows','generation_seconds','evaluation_seconds','estimated_cost',
                 'cause_correct_fraction','end_effect_correct_fraction','severity_difference_fraction',
                 'occurrence_difference_fraction','detection_difference_fraction','rpn_relative_difference_fraction',
                 'structural_status','format_status','unsupported_inflation_review','data_quality_status')


def stamp(): return datetime.now(timezone.utc).isoformat()


def atomic_json(path, data):
    """Publish a complete JSON file with one same-filesystem replace."""
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    encoded=json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n'
    fd, tmp=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def safe_run(run):
    result={k:run.get(k) for k in SAFE_RUN_FIELDS}
    # Never export free-form reviewer text, paths, item IDs, evidence or raw usage.
    for field in ('run_id','system','skill_version','generator_model','judge_model','judge_skill_version'):
        value=result.get(field)
        if value is not None and (not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9 ._:/+-]{1,120}',value)):
            raise ValueError('Unsafe dashboard metadata '+field)
    result['generation_status']=run.get('generation_status','success')
    result['evaluation_status']=run.get('evaluation_status','evaluated')
    result['data_quality_status']=run.get('data_quality_status','validated_identifier_import')
    return result


def validate_snapshot(data):
    if data.get("schema")=="sigma-dashboard-4.1":
        from .platform import validate_extended
        return validate_extended(data)
    required={'schema','data_version','last_updated','validation_status','research_status','baseline','runs','registry','per_system','per_version','pareto','statistics','review_summary','coverage_summary'}
    if set(data)!=required or data['schema']!=SCHEMA or data['validation_status']!='VALIDATED': raise ValueError('Invalid dashboard envelope')
    if not re.fullmatch('[0-9a-f]{64}',data['data_version']): raise ValueError('Invalid data version')
    datetime.fromisoformat(data['last_updated'])
    for key in ('runs','registry','per_system','per_version','pareto','coverage_summary'):
        if not isinstance(data[key],list): raise ValueError('Invalid dashboard table')
    baseline=data['baseline']
    if not isinstance(baseline,dict) or any(type(baseline.get(k)) is not int or baseline[k]<0 for k in ('total_runs','opportunities','missed')) or baseline['missed']>baseline['opportunities']:
        raise ValueError('Invalid baseline aggregates')
    registry_fields={'run_id','system','skill_version','generator_model','generation_status','evaluation_status','generation_timestamp','generated_rows','skill_sha256','git_commit','structural_status'} | set(SAFE_RUN_FIELDS)
    for row in data['registry']:
        if set(row)-registry_fields or row.get('skill_version') not in VERSIONS or row.get('system') not in SYSTEMS: raise ValueError('Unsafe registry metadata')
        for key in ('run_id','generator_model'):
            if not isinstance(row.get(key),str) or not re.fullmatch(r'[A-Za-z0-9 ._:/+-]{1,160}',row[key]): raise ValueError('Unsafe registry identifier')
    for row in data['pareto']:
        if set(row)!={'skill_version','miss_category','count','percentage','cumulative_percentage'} or row['skill_version'] not in VERSIONS or row['miss_category'] not in ('Repeated unit skipped','Sub-case not split out','Part never covered','Wrong failure direction','Unclassified') or type(row['count']) is not int or row['count']<0:
            raise ValueError('Invalid Pareto data')
    for table in ('per_system','per_version'):
        for row in data[table]:
            if row.get('skill_version') not in VERSIONS or (table=='per_system' and row.get('system') not in SYSTEMS): raise ValueError('Invalid summary identity')
            for key in ('pooled_missed_percentage','mean_run_missed_percentage'):
                if type(row.get(key)) not in (int,float) or not 0<=row[key]<=100: raise ValueError('Invalid summary rate')
    if set(data['statistics'].get('criteria',{}).values())-{'PASS','FAIL','PENDING','INSUFFICIENT_DATA'}: raise ValueError('Invalid criterion status')
    ids=set()
    for row in data['runs']:
        if set(row)-set(SAFE_RUN_FIELDS) or row.get('skill_version') not in VERSIONS or row.get('system') not in SYSTEMS: raise ValueError('Unsafe dashboard run')
        if row['run_id'] in ids: raise ValueError('Duplicate dashboard run')
        ids.add(row['run_id'])
        if not isinstance(row.get('missed_percentage'),(int,float)) or not 0<=row['missed_percentage']<=100: raise ValueError('Invalid dashboard rate')
    return data


def empty_snapshot():
    stats=compare([])
    data={'schema':SCHEMA,'last_updated':stamp(),'validation_status':'VALIDATED',
          'research_status':'REPORT_DERIVED_BASELINE_ONLY','baseline':read(BASELINE),
          'runs':[],'registry':[],'per_system':[],'per_version':[],'pareto':[],
          'statistics':stats,'review_summary':{'status':'PENDING','events':0},'coverage_summary':[]}
    counts=data['baseline']['miss_categories']
    total=sum(counts.values()); running=0
    data['baseline']['miss_category_percentages']={}
    data['baseline']['miss_category_cumulative_percentages']={}
    for key,value in counts.items():
        running+=value
        data['baseline']['miss_category_percentages'][key]=100*value/total
        data['baseline']['miss_category_cumulative_percentages'][key]=100*running/total
    data['data_version']=hashlib.sha256(json.dumps({k:v for k,v in data.items() if k!='last_updated'},sort_keys=True).encode()).hexdigest()
    return data


def review_events(paths, runs, items):
    """Append-only review events compare AI and engineer decisions, never mutate AI inputs."""
    known={(i['run_id'],i['item_id']):i for i in items}; run_ids={r['run_id'] for r in runs}
    events=[]; seen=set()
    for path in sorted(set(map(private,paths))):
        data=read(path)
        if data.get('schema')!='engineering-review-1': raise ValueError('Invalid review schema')
        for event in data['events']:
            required=('event_id','run_id','sample_type','ai_result','engineer_result','adjudication_status','reviewed_at')
            if any(event.get(k) in (None,'') for k in required) or event['event_id'] in seen: raise ValueError('Invalid or duplicate review event')
            if event['run_id'] not in run_ids or event['sample_type'] not in ('correct_match','missed','extra','severity_disagreement','ambiguous_classification'): raise ValueError('Unknown review target/type')
            if event['sample_type']!='extra' and (event['run_id'],event.get('item_id')) not in known: raise ValueError('Unknown review item')
            datetime.fromisoformat(event['reviewed_at'])
            if event['adjudication_status'] not in ('pending','agreed','adjudicated','unresolved'): raise ValueError('Invalid adjudication')
            minutes=event.get('review_minutes')
            if minutes is not None and (type(minutes) not in (int,float) or not 0<=minutes<100000): raise ValueError('Invalid review time')
            seen.add(event['event_id']); events.append({**event,'agreement':event['ai_result']==event['engineer_result']})
    return events


def registry_from_receipts(paths):
    registry=[]; seen=set()
    for path in sorted(set(map(private,paths))):
        receipt=read(path)
        if receipt.get('workflow')!='standalone_gemini': raise ValueError('Canonical receipt excluded')
        version=receipt['prompt_version']
        if version not in VERSIONS: continue
        rid=receipt.get('study_run_id') or (receipt.get('experiment_id') if str(receipt.get('experiment_id','')).startswith('round2-v4-') else receipt.get('experiment_id','')+':'+receipt['attempt_id'])
        if rid in seen: raise ValueError('Duplicate generation identity')
        seen.add(rid)
        registry.append({'run_id':rid,'system':receipt['system_id'].removeprefix('system_'),
                         'skill_version':version,'generator_model':receipt['model'],
                         'generation_status':receipt['status'],'evaluation_status':'awaiting_evaluation',
                         'generation_timestamp':receipt.get('started_at'),'generated_rows':receipt.get('row_count'),
                         'skill_sha256':receipt.get('skill_sha256'),'git_commit':receipt.get('git_commit'),
                         'structural_status':receipt.get('completeness',{}).get('structural_status','PENDING')})
    return registry


def unique_sources(paths):
    # A path and its archived byte-identical copy are one source, not duplicate runs.
    by_hash={}
    for source in sorted(set(map(private,paths))):
        by_hash.setdefault(hashlib.sha256(source.read_bytes()).hexdigest(),str(source))
    return list(by_hash.values())


def build(judges, output, receipts=(), reviews=(), render=True):
    """One workflow: validate -> aggregate -> inference -> sanitize -> render -> publish.

    Output folders are immutable. current.json is updated only after all requested
    exports succeed; failed validation/rendering leaves the last known good intact.
    """
    output=private(output)
    if output.exists(): raise FileExistsError('Choose a new immutable research build directory')
    output.parent.mkdir(parents=True,exist_ok=True)
    catalog_path=output.parent/'import_catalog.json'
    catalog=read(catalog_path) if catalog_path.exists() else {'judges':[], 'receipts':[], 'reviews':[]}
    all_judges=unique_sources(list(judges)+catalog['judges'])
    all_receipts=unique_sources(list(receipts)+catalog['receipts'])
    all_reviews=unique_sources(list(reviews)+catalog['reviews'])
    stage=Path(tempfile.mkdtemp(prefix='.research-',dir=output.parent))
    try:
        result=aggregate(all_judges,stage/'validated',treatment='v4.0-inventory')
        runs,items,provenance,missing=ingest(all_judges)
        events=review_events(all_reviews,runs,items)
        write_csv(stage/'validated'/'engineering_review.csv',events)
        data=empty_snapshot(); data['runs']=[safe_run(r) for r in runs]
        data['statistics']=result['comparison']
        data['registry']=registry_from_receipts(all_receipts)
        for run in runs:
            existing=next((x for x in data['registry'] if x['run_id']==run['run_id']),None)
            if existing is not None: existing['evaluation_status']='evaluated'
            if existing is None:
                data['registry'].append({k:v for k,v in safe_run(run).items() if v is not None})
        # Registry generation identities may differ from imported study IDs; explicit
        # study_run_id in new receipts binds them, otherwise reconciliation is human.
        data['per_system']=read_csv(stage/'validated/per_system.csv')
        data['per_version']=read_csv(stage/'validated/per_version.csv')
        for row in data['per_version']:
            row.update(ci_low=None,ci_high=None,system_weighted_mean=None)
        for v in VERSIONS:
            ci=bootstrap(runs,(v,))
            if ci['status']=='PASS':
                for row in data['per_version']:
                    if row['skill_version']==v:
                        row.update(ci_low=ci['means'][v]['ci_low'],ci_high=ci['means'][v]['ci_high'],system_weighted_mean=ci['means'][v]['mean'])
        # Cell-level run bootstrap, kept in Python so Shiny only plots supplied intervals.
        import numpy as np
        rng=np.random.default_rng(5300)
        for row in data['per_system']:
            values=[r['missed_percentage'] for r in runs if r['skill_version']==row['skill_version'] and r['system']==row['system']]
            row['ci_low']=row['ci_high']=None
            if len(values)>=2:
                boot=rng.choice(values,size=(2000,len(values)),replace=True).mean(axis=1)
                row['ci_low']=float(np.quantile(boot,.025)); row['ci_high']=float(np.quantile(boot,.975))
        counts=read_csv(stage/'validated/pareto.csv'); pareto=[]
        for v in VERSIONS:
            entries=sorted([r for r in counts if r['skill_version']==v],key=lambda r:(-int(r['count']),r['miss_category']))
            total=sum(int(r['count']) for r in entries); cumulative=0
            for row in entries:
                row['count']=int(row['count']); cumulative+=row['count']
                row.update(percentage=100*row['count']/total if total else 0,cumulative_percentage=100*cumulative/total if total else 0)
                pareto.append(row)
        data['pareto']=pareto
        data['coverage_summary']=[]
        for receipt_path in all_receipts:
            receipt=read(private(receipt_path)); coverage=receipt.get('completeness',{})
            if coverage.get('schema')=='coverage-audit-4':
                data['coverage_summary'].append({'system':receipt['system_id'].removeprefix('system_'),'skill_version':receipt['prompt_version'],
                    'identified_unit_count':coverage['identified_unit_count'],'units_covered_count':len(coverage['units_covered']),
                    'uncovered_unit_count':len(coverage['units_without_coverage']),'structural_status':coverage['structural_status'],
                    'unsupported_row_count':len(coverage['unsupported_rows']),'duplicate_row_count':len(coverage['duplicate_rows'])})
        origins={r.get('data_origin','experimental') for r in runs}
        if len(origins)>1: raise ValueError('Cannot mix synthetic test observations and research observations')
        data['research_status']='SYNTHETIC_TEST_ONLY' if origins=={'synthetic_test'} else 'EVALUATED_DATA_AVAILABLE' if runs else 'REPORT_DERIVED_BASELINE_ONLY'
        data['review_summary']={'status':'REVIEW_EVENTS_AVAILABLE' if events else 'PENDING','events':len(events),
                                'agreements':sum(e['agreement'] for e in events),'disagreements':sum(not e['agreement'] for e in events),
                                'pending_adjudications':sum(e['adjudication_status'] in ('pending','unresolved') for e in events)}
        data['last_updated']=stamp()
        data['data_version']=hashlib.sha256(json.dumps({k:v for k,v in data.items() if k not in ('last_updated','data_version')},sort_keys=True).encode()).hexdigest()
        validate_snapshot(data)
        atomic_json(stage/'dashboard.json',data)
        atomic_json(stage/'validated/statistical_results.json',data['statistics'])
        baseline=data['baseline']
        (stage/'presenter-notes.md').write_text(
            '# AI-assisted two-minute presentation draft\n\n'
            '0:00-0:20 Research question: can input-bound engineering coverage reduce missed modes without inflating unsupported rows?\n\n'
            f'0:20-0:45 Data: the V2 report contains {baseline["total_runs"]} runs, {baseline["opportunities"]} opportunities and {baseline["missed"]} misses. Pooled missed percentage is {baseline["pooled_missed_percentage_reported"]}%. These aggregates do not reconstruct run-level evidence.\n\n'
            '0:45-1:15 Method: V4 adds independent inventory verification and targeted gap reports. Freeze generation conditions and the original external judge. Use sampled human validation.\n\n'
            f'1:15-1:40 Results status: {data["research_status"]}. Show only validated observations. The primary comparison is V2 versus V4 with system-stratified intervals and additive ANOVA when evidence permits.\n\n'
            '1:40-2:00 Implications: software structure is not engineering acceptance. Review extras and ratings. Do not claim efficacy without evaluated evidence.\n\n'
            'Presenter: open Poster presentation, explain the two ggplots, switch to Experiment explorer, then demonstrate Refresh data and Export poster PDF. Students must verify and rewrite submitted prose.\n',encoding='utf-8')
        # Both figures and the poster use exactly this snapshot. No private data is
        # supplied to R, a hosting service, or the browser.
        if render:
            subprocess.run(['Rscript',str(ROOT/'dashboard/export.R'),str(stage/'dashboard.json'),str(stage/'presentation')],check=True,cwd=ROOT)
        # Persist private imports in durable local storage; Actions artifacts are only transport.
        archived={'judges':[], 'receipts':[], 'reviews':[]}
        for kind,paths in [('judges',all_judges),('receipts',all_receipts),('reviews',all_reviews)]:
            for source in paths:
                source=private(source); digest=hashlib.sha256(source.read_bytes()).hexdigest()
                destination=output.parent/'private'/kind/(digest+'.json')
                destination.parent.mkdir(parents=True,exist_ok=True)
                if not destination.exists(): shutil.copyfile(source,destination)
                archived[kind].append(str(destination.resolve()))
        stage.rename(output)
        atomic_json(catalog_path,archived)
        atomic_json(output.parent/'current.json',data)
        return data
    finally:
        if stage.exists(): shutil.rmtree(stage)


def read_csv(path):
    import csv
    with path.open(encoding='utf-8',newline='') as stream:
        rows=list(csv.DictReader(stream))
    for row in rows:
        for key,value in list(row.items()):
            if value=='': row[key]=None
            elif key not in ('skill_version','system','miss_category'):
                try: row[key]=float(value)
                except (TypeError,ValueError): pass
    return rows


def plan(output, model, seed=5300):
    from analysis.round2.__main__ import plan as old_plan
    from standalone_v4 import DIAGNOSTICS_VERSION, RESPONSE_VERSION, SCORING_PROFILE
    manifest=old_plan(output,model,seed)
    manifest['schema']='round2-v4-plan-1'; manifest['git_commit']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    manifest['skill_sha256']=hashlib.sha256((ROOT/'skill/fmea_instructions_v4_inventory.md').read_bytes()).hexdigest()
    manifest.update(prepared_at=stamp(),response_contract=RESPONSE_VERSION,diagnostics_schema=DIAGNOSTICS_VERSION,
                    scoring_profile=SCORING_PROFILE,provider='Gemini',
                    generator_source_sha256=hashlib.sha256((ROOT/'fmea_generator.py').read_bytes()).hexdigest(),
                    validator_source_sha256=hashlib.sha256((ROOT/'standalone_v4.py').read_bytes()).hexdigest())
    manifest['settings']['response_mime_type']='application/json'
    manifest['settings']['max_output_tokens']='Resolve from explicitly selected model and record in each receipt'
    manifest['condition_status']='Planned only. Freeze inputs, inventory, model, and identifier-only judge provenance before execution.'
    for run in manifest['runs']:
        run['skill_version']='v4.0-inventory'; run['run_id']=run['run_id'].replace('round2-','round2-v4-')
        run.update(generation_timestamp=None,evaluation_timestamp=None,artifacts=[],git_commit=manifest['git_commit'],skill_sha256=manifest['skill_sha256'])
    atomic_json(private(output)/'experiment_manifest.json',manifest)
    atomic_json(private(output)/'judging_manifest.json',{'schema':'judging-queue-4','judge_model':manifest['judge_model'],'judge_skill_version':manifest['judge_skill_version'],'methodology_status':'unchanged_external_judge_required','runs':manifest['runs']})
    return manifest


def register(receipt_path, output):
    """Generation event updates progress only; existing judged metrics are retained."""
    output=private(output)
    if output.exists() and read(output).get('schema')=='sigma-dashboard-4.1':
        from .registry import Registry
        from .platform import snapshot
        registry=Registry(output.parent/'registry.sqlite')
        try:
            with registry.transaction(): registry.receipt(receipt_path)
            return snapshot(registry,output,render=False)
        finally: registry.close()
    # Use exclusive process lock to prevent lost updates; caller can retry OFFLINE.
    lock=output.with_suffix('.lock'); lock.parent.mkdir(parents=True,exist_ok=True)
    lock.open('x').close()
    try:
        data=read(output) if output.exists() else empty_snapshot()
        validate_snapshot(data)
        row=registry_from_receipts([receipt_path])[0]
        previous=next((r for r in data['registry'] if r['run_id']==row['run_id']),None)
        if previous and previous.get('evaluation_status')=='evaluated': row['evaluation_status']='evaluated'
        data['registry']=[r for r in data['registry'] if r['run_id']!=row['run_id']]+[row]
        data['last_updated']=stamp()
        data['data_version']=hashlib.sha256(json.dumps(data['registry'],sort_keys=True).encode()).hexdigest()
        validate_snapshot(data); atomic_json(output,data)
    finally:
        lock.unlink(missing_ok=True)
    return data


def review_sample(paths, output, seed=5300):
    """Deterministic review queue from actual imported judgments, never reference prose."""
    import random
    runs,items,_,_=ingest(paths); rng=random.Random(seed); tasks=[]
    groups={
        'correct_match':[i for i in items if i['found']],
        'missed':[i for i in items if not i['found']],
        'severity_disagreement':[i for i in items if i.get('severity_difference') is not None and abs(i['severity_difference'])>1],
        'ambiguous_classification':[i for i in items if not i['found'] and not i.get('miss_category')]}
    for kind,candidates in groups.items():
        if candidates:
            selected=rng.choice(sorted(candidates,key=lambda i:(i['run_id'],i['item_id'])))
            tasks.append({'sample_type':kind,'run_id':selected['run_id'],'item_id':selected['item_id'],
                          'ai_result':selected['found'],'engineer_result':None,'adjudication_status':'pending'})
    extras=[r for r in runs if r['extra_unmatched_rows']>0]
    if extras:
        selected=rng.choice(extras)
        tasks.append({'sample_type':'extra','run_id':selected['run_id'],'generated_item_id':None,
                      'ai_result':'unmatched_extra','engineer_result':None,'adjudication_status':'pending',
                      'review_flag':'Human must select the generated-row ID; importer has no unmatched-row identifiers'})
    destination=private(output)
    if destination.exists(): raise FileExistsError(destination)
    atomic_json(destination,{'schema':'engineering-review-queue-1','seed':seed,'tasks':tasks,
                             'empty_strata':[k for k,v in groups.items() if not v]})
    return tasks


def main():
    import sys
    if any(command in sys.argv[1:2] for command in ("sync","import-historical","register-generation","register-plan","preview-judge","accept-judge","select-evaluation","reconcile","refresh","watch","finance","record-review","migrate")) or "--database" in sys.argv:
        from .platform import main as platform_main
        return platform_main()
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('plan'); p.add_argument('--output',required=True); p.add_argument('--model',required=True); p.add_argument('--seed',type=int,default=5300)
    b=sub.add_parser('build'); b.add_argument('--judge',action='append',default=[]); b.add_argument('--receipt',action='append',default=[]); b.add_argument('--review',action='append',default=[]); b.add_argument('--output',required=True); b.add_argument('--no-render',action='store_true')
    r=sub.add_parser('register'); r.add_argument('--receipt',required=True); r.add_argument('--output',default='results/research/current.json')
    sample=sub.add_parser('review-sample'); sample.add_argument('--judge',action='append',required=True); sample.add_argument('--output',required=True)
    args=parser.parse_args()
    if args.command=='plan': plan(args.output,args.model,args.seed)
    elif args.command=='review-sample': review_sample(args.judge,args.output)
    elif args.command=='register': register(args.receipt,args.output)
    else: build(args.judge,args.output,args.receipt,args.review,not args.no_render)

if __name__=='__main__': main()
