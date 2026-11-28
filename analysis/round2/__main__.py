"""Offline, identifier-only judge import. Never reads reference worksheets."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import random
from statistics import NormalDist, mean, stdev

CATEGORIES = ('Repeated unit skipped', 'Sub-case not split out', 'Part never covered', 'Wrong failure direction')
CONDITIONS = ('generator_model', 'settings', 'judge_model', 'judge_skill_version', 'ground_truth_version', 'classification_rules_version')
QUALITY = ('cause_correct', 'end_effect_correct', 'severity_difference', 'occurrence_difference', 'detection_difference', 'rpn_relative_difference')


def private(path):
    path = Path(path).resolve()
    root = Path('results').resolve()
    if not path.is_relative_to(root):
        raise ValueError('Private imports and analysis must be under ignored results/')
    return path


def read(path):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError('Duplicate JSON key')
            obj[key] = value
        return obj
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def metrics(items):
    n = len(items)
    if not n:
        raise ValueError('Empty opportunity denominator')
    missed = sum(not i['found'] for i in items)
    return {'ground_truth_count': n, 'found': n-missed, 'missed': missed,
            'missed_percentage': 100*missed/n, 'coverage_percentage':100*(n-missed)/n, 'dpmo': 1000000*missed/n}


def summarize(runs, keys):
    groups = {}
    for run in runs:
        groups.setdefault(tuple(run[k] for k in keys), []).append(run)
    output = []
    for key, group in sorted(groups.items()):
        n = sum(r['ground_truth_count'] for r in group)
        missed = sum(r['missed'] for r in group)
        p = missed/n
        output.append({**dict(zip(keys, key)), 'runs': len(group), 'opportunities': n,
                       'missed': missed, 'pooled_missed_percentage': 100*p, 'pooled_coverage_percentage':100*(1-p), 'mean_run_coverage_percentage':100-mean(r['missed_percentage'] for r in group), 'dpmo': p*1e6,
                       'sigma_1_5_shift': NormalDist().inv_cdf(1-p)+1.5 if 0 < p < 1 else None,
                       'mean_run_missed_percentage': mean(r['missed_percentage'] for r in group),
                       'run_sd_percentage_points': stdev(r['missed_percentage'] for r in group) if len(group)>1 else None,
                       'mean_extra_rows': mean(r['extra_unmatched_rows'] for r in group)})
    return output


def ingest(paths):
    runs, items, provenance, missing = [], [], [], []
    seen, conditions, denominators = set(), set(), {}
    skill_hashes, input_hashes = {}, {}
    for path in sorted(set(map(private, paths))):
        data = read(path)
        if data.get('schema') != 'standalone-judge-import-1' or data.get('workflow') != 'standalone_gemini':
            raise ValueError('Unsupported judge import; canonical conditions are excluded')
        provenance.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        for run in data['runs']:
            rid = run['run_id']
            if not isinstance(rid, str) or not rid.strip() or rid in seen:
                raise ValueError('Duplicate or empty run ID')
            seen.add(rid)
            if run['system'] not in list('ABCDE') or run['skill_version'] not in ('v2.0', 'v3.0', 'v3.0-audit', 'v4.0-inventory'):
                raise ValueError('Unknown system/version')
            if any(run.get(k) in (None, '', {}) for k in CONDITIONS):
                raise ValueError('Missing experimental conditions')
            if run['judge_model'] != 'Claude Sonnet 5.5' or run['judge_skill_version'] != 'v1.2':
                raise ValueError('Incompatible judge')
            conditions.add(json.dumps({k:run[k] for k in CONDITIONS}, sort_keys=True))
            if run.get('status') != 'validated':
                raise ValueError('Only validated generation/evaluation pairs may be analyzed')
            if run.get('generation_receipt_path'):
                receipt_path = private(run['generation_receipt_path'])
                receipt = read(receipt_path)
                if (receipt.get('workflow') != 'standalone_gemini' or receipt.get('status') != 'success'
                    or receipt.get('prompt_version') != run['skill_version']
                    or receipt.get('model') != run['generator_model']
                    or receipt.get('system_id') not in (run['system'], 'system_'+run['system'])
                    or receipt.get('row_count') != run['generated_rows']):
                    raise ValueError('Generation receipt identity/status mismatch')
                run = dict(run)
                run['generation_seconds'] = receipt.get('api_request_seconds')
                run['usage'] = receipt.get('usage_metadata')
                run['skill_sha256'] = receipt.get('skill_sha256')
                run['system_sha256'] = receipt.get('system_sha256')
                run['receipt_attempt_id'] = receipt.get('attempt_id')
                provenance.append({'path': str(receipt_path), 'sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest()})
            else:
                missing.append({'run_id':rid,'field':'generation_receipt_path','status':'human-exported metadata; not independently receipt-verified'})
            for key, identity, registry in [('skill_sha256',run['skill_version'],skill_hashes), ('system_sha256',run['system'],input_hashes)]:
                if run.get(key):
                    if identity in registry and registry[identity]!=run[key]: raise ValueError('Incompatible skill/input hash cohort')
                    registry[identity]=run[key]
            run=dict(run)
            run['comparison_eligible']=(run.get('comparison_review_status')=='human_confirmed' and bool(run.get('skill_sha256')) and bool(run.get('system_sha256')) and bool(run.get('judge_instruction_sha256')) and bool(run.get('ground_truth_sha256')))
            if not run['comparison_eligible']:
                missing.append({'run_id':rid,'field':'comparison_provenance','status':'INSUFFICIENT_DATA until condition/hash review'})
            nrows, extra = run['generated_rows'], run['extra_unmatched_rows']
            if any(type(v) is not int or v < 0 for v in (nrows, extra)) or extra > nrows:
                raise ValueError('Invalid generated/extra count')
            records, ids, matched = [], set(), set()
            for item in run['items']:
                allowed = {'item_id', 'found', 'matched_row_id', 'miss_category', 'review_status', 'judge_notes', *QUALITY}
                if item.get('judge_notes') is not None and not isinstance(item['judge_notes'], str):
                    raise ValueError('Judge notes must be text; human must remove reference quotations')
                if set(item)-allowed:
                    raise ValueError('Only identifier-level judge fields allowed; omit confidential text/notes')
                iid = item['item_id']
                if not isinstance(iid, str) or not iid.strip() or iid in ids or type(item['found']) is not bool:
                    raise ValueError('Invalid/duplicate item ID or found result')
                ids.add(iid)
                match = item.get('matched_row_id')
                if item['found']:
                    if not isinstance(match, str) or not match.strip() or match in matched:
                        raise ValueError('Found item requires unique generated-row match')
                    matched.add(match)
                elif match is not None:
                    raise ValueError('Missed item cannot have a row match')
                category = item.get('miss_category')
                if category is not None and (category not in CATEGORIES or item['found']):
                    raise ValueError('Invalid miss category')
                if not item['found'] and category is None:
                    missing.append({'run_id':rid,'item_id':iid,'field':'miss_category'})
                for field in QUALITY:
                    value = item.get(field)
                    if value is None:
                        missing.append({'run_id':rid,'item_id':iid,'field':field})
                    elif field.endswith('correct'):
                        if type(value) is not bool: raise ValueError('Quality correctness must be boolean')
                    elif type(value) not in (int,float) or not math.isfinite(value) or (field == 'rpn_relative_difference' and value < 0):
                        raise ValueError('Invalid rating difference')
                records.append({'run_id':rid,'system':run['system'],'skill_version':run['skill_version'], **item})
            # Same reviewed opportunity IDs per system across all comparable runs.
            identity = frozenset(ids)
            if run['system'] in denominators and denominators[run['system']] != identity:
                raise ValueError('Incompatible per-system opportunity IDs')
            denominators[run['system']] = identity
            if len(matched)+extra != nrows:
                raise ValueError('Matched plus unmatched rows must equal generated rows')
            m = metrics(records)
            summary = {k:v for k,v in run.items() if k != 'items'}
            summary.update(m)
            for field in QUALITY:
                values = [i[field] for i in records if i['found'] and i.get(field) is not None]
                limit = .25 if field == 'rpn_relative_difference' else 1
                summary[field+'_fraction'] = mean((v if field.endswith('correct') else abs(v)<=limit) for v in values) if values else None
                summary[field+'_denominator'] = len(values)
            for field in ('generation_seconds', 'evaluation_seconds', 'usage', 'estimated_cost', 'generation_timestamp', 'evaluation_timestamp', 'generation_status', 'evaluation_status', 'structural_status', 'format_status', 'unsupported_inflation_review'):
                if summary.get(field) is None: missing.append({'run_id':rid,'field':field})
            runs.append(summary)
            items.extend(records)
    if len(conditions)>1:
        raise ValueError('Incompatible generator/settings/judge/ground truth/classification conditions')
    return sorted(runs,key=lambda r:r['run_id']), items, provenance, missing


def write_csv(path, rows):
    keys = sorted({k for r in rows for k in r}) or ['status']
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer = csv.DictWriter(stream,fieldnames=keys); writer.writeheader()
        for row in rows:
            cells = {k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in row.items()}
            writer.writerow({k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v) for k,v in cells.items()})


def comparison(runs, systems, versions, treatment="v3.0"):
    if treatment == "v4.0-inventory":
        from analysis.research.statistics import compare
        return compare(runs)
    result = {'anova_status':'awaiting comparable actual v2.0 and v3.0 item-level results',
              'criteria':{k:'awaiting data' for k in ('mean_below_20','version_p_below_0_05','four_systems_improve','no_system_worsens_over_5pp','extra_rows_at_most_4_8')},
              'dmaic':'Improve: explicit inventory and distinct cases. Control: freeze conditions, validate every run, review omissions and extras; no efficacy claim before judge results.',
              'additional_runs':'Collect four validated v3 runs per system and actual comparable v2 run/item records. Aggregate baseline cannot support ANOVA.'}
    v3 = [r for r in runs if r['skill_version']=='v3.0']
    if v3:
        result['criteria']['mean_below_20'] = mean(r['missed_percentage'] for r in v3)<20
        result['criteria']['extra_rows_at_most_4_8'] = mean(r['extra_unmatched_rows'] for r in v3)<=4.8
    cells = {(s['skill_version'],s['system']):s for s in systems}
    if all((v,s) in cells for v in ('v2.0','v3.0') for s in 'ABCDE'):
        delta = {s:cells['v2.0',s]['mean_run_missed_percentage']-cells['v3.0',s]['mean_run_missed_percentage'] for s in 'ABCDE'}
        result['coverage_improvement_percentage_points'] = delta
        result['criteria']['four_systems_improve'] = sum(v>0 for v in delta.values())>=4
        result['criteria']['no_system_worsens_over_5pp'] = min(delta.values())>=-5
        # Equivalent to R: anova(lm(missed_percentage ~ system + skill_version));
        # partial version effect, appropriate for unbalanced counts, no interaction.
        import numpy as np
        from scipy.stats import f
        y=np.array([r['missed_percentage'] for r in runs])
        reduced=np.array([[1]+[int(r['system']==s) for s in 'BCDE'] for r in runs],dtype=float)
        full=np.column_stack((reduced,[int(r['skill_version']=='v3.0') for r in runs]))
        rank=np.linalg.matrix_rank(full); df=len(y)-rank
        if rank==6 and df>0:
            rss0=float(sum((y-reduced@np.linalg.lstsq(reduced,y,rcond=None)[0])**2))
            rss1=float(sum((y-full@np.linalg.lstsq(full,y,rcond=None)[0])**2))
            if rss1>1e-12:
                statistic=max(0,(rss0-rss1))/(rss1/df); p=float(f.sf(statistic,1,df))
                result.update(anova_status='computed additive OLS partial version F test',anova={'F':statistic,'p':p,'df_version':1,'df_residual':int(df)})
                result['criteria']['version_p_below_0_05']=p<.05
    result['limitations']='Run is experimental unit; bounded percentages, independence, variance and residual assumptions require review. Sigma uses conventional +1.5 shift, not process certification.'
    return result


def aggregate(paths, output, treatment="v3.0"):
    runs, items, provenance, missing = ingest(paths)
    output=private(output); output.mkdir(parents=True,exist_ok=True)
    systems=summarize(runs,['skill_version','system']); versions=summarize(runs,['skill_version'])
    pareto=[]
    for version in sorted({r['skill_version'] for r in runs}):
        for category in (*CATEGORIES,'Unclassified'):
            pareto.append({'skill_version':version,'miss_category':category,'count':sum(not i['found'] and (i.get('miss_category') or 'Unclassified')==category and i['skill_version']==version for i in items)})
    tables={'runs':runs,'items':items,'per_system':systems,'per_version':versions,'pareto':pareto}
    analysis=comparison(runs,systems,versions,treatment)
    for name,rows in tables.items(): write_csv(output/(name+'.csv'),rows)
    audit={'sources':provenance,'missing_data':missing,'run_count':len(runs),'item_count':len(items),'report_derived_baseline':read(Path(__file__).with_name('round1_baseline.json')),'comparison':analysis,
           'privacy':'Identifier-only private imports; no reference text or raw judge text ingested. Do not commit results.'}
    (output/'data_quality_provenance.json').write_text(json.dumps(audit,indent=2,sort_keys=True)+'\n')
    import pandas as pd
    with pd.ExcelWriter(output/'analysis.xlsx',engine='xlsxwriter',engine_kwargs={'options':{'strings_to_formulas':False,'strings_to_urls':False}}) as writer:
        pd.DataFrame([{'metric':k,'value':json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v} for k,v in audit['report_derived_baseline'].items()]).to_excel(writer,sheet_name='round1_report_baseline',index=False)
        for name,rows in tables.items():
            pd.DataFrame([{k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows]).to_excel(writer,sheet_name=name,index=False)
        pd.DataFrame([{'criterion':k,'result':v} for k,v in analysis['criteria'].items()]).to_excel(writer,sheet_name='criteria',index=False)
        pd.DataFrame([{'quantity':k,'result':json.dumps(v,sort_keys=True)} for k,v in analysis.items()]).to_excel(writer,sheet_name='statistical_results',index=False)
        pd.DataFrame(missing).to_excel(writer,sheet_name='missing_data',index=False)
    if pareto:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,ax=plt.subplots(figsize=(10,5))
        ordered=sorted(pareto,key=lambda r:(r['skill_version'],-r['count'],r['miss_category']))
        ax.bar([r['skill_version']+' '+r['miss_category'] for r in ordered],[r['count'] for r in ordered]); ax.tick_params(axis='x',labelrotation=70); ax.set_ylabel('Missed opportunities'); fig.tight_layout(); fig.savefig(output/'pareto.png',dpi=180); plt.close(fig)
    return audit


def plan(output, model, seed=20261115):
    output=private(output); output.mkdir(parents=True,exist_ok=True)
    runs=[{'run_id':f'round2-{s}-r{r:02d}','system':s,'replicate':r,'skill_version':'v3.0','status':'awaiting_generation','evaluation_status':'awaiting_evaluation'} for s in 'ABCDE' for r in range(1,5)]
    random.Random(seed).shuffle(runs)
    for n,run in enumerate(runs,1): run['execution_order']=n
    manifest={'schema':'round2-plan-1','seed':seed,'workflow':'standalone_gemini','generator_model':model,'settings':{'temperature':0,'retry_attempts':1,'max_output_tokens':'model maximum; verify against Round 1 receipts'},'judge_model':'Claude Sonnet 5.5','judge_skill_version':'v1.2','ground_truth_version':None,'skill_sha256':hashlib.sha256(Path('skill/fmea_instructions_v3.md').read_bytes()).hexdigest(),'input_sha256':{s:hashlib.sha256(Path(f'system_descriptions/system_{s}.txt').read_bytes()).hexdigest() for s in 'ABCDE'},'daily_attempt_limit':20,'condition_status':'Awaiting human confirmation against Round 1 receipts and frozen ground-truth/judge hashes','runs':runs}
    for name,data in [('experiment_manifest.json',manifest),('judging_manifest.json',{'schema':'judging-queue-1','judge_model':manifest['judge_model'],'judge_skill_version':'v1.2','runs':runs})]:
        path=output/name
        with path.open('x',encoding='utf-8') as f: json.dump(data,f,indent=2)
    return manifest


def merge(paths, output):
    """Combine separately authorized completed batches; no model calls or inferred links."""
    from fmea_generator import parse_v3
    combined = {'inventory': [], 'rows': [], 'review_flags': [], 'complete': True}
    for path in map(private, paths):
        batch = read(path)
        if batch.get('complete') is not True:
            raise ValueError('Incomplete batch; explicit continuation required')
        for key in ('inventory', 'rows', 'review_flags'):
            combined[key].extend(batch[key])
    rows, audit = parse_v3(json.dumps(combined))
    destination = private(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x', encoding='utf-8') as stream:
        json.dump({'response': combined, 'completeness': audit,
                   'status': 'combined_structural_draft_requires_boundary_review'}, stream, indent=2)
    return rows, audit


def main():
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    a=sub.add_parser('aggregate'); a.add_argument('--judge',action='append',default=[]); a.add_argument('--output',required=True)
    p=sub.add_parser('plan'); p.add_argument('--output',required=True); p.add_argument('--model',required=True); p.add_argument('--seed',type=int,default=20261115)
    m=sub.add_parser('merge'); m.add_argument('--batch',action='append',required=True); m.add_argument('--output',required=True)
    args=parser.parse_args()
    if args.command=='aggregate': aggregate(args.judge,args.output)
    elif args.command=='merge': merge(args.batch,args.output)
    else: plan(args.output,args.model,args.seed)

if __name__=='__main__': main()
