"""Immutable offline experiment dashboards and explicit aggregate-publication staging."""
from collections import Counter,defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid
from . import REPORT_VERSION
from .catalog import discover, ingest, select, financial_rows
from .figures import render, outcome, groups
from analysis.financial_impact.data_schema import read_json
from analysis.financial_impact.ingest import read_log, sha256
from analysis.financial_impact.report import CONFIG, data_audit

ROOT=Path(__file__).resolve().parents[2]


def write_json(path,value):
    """Create finite UTF-8 JSON once; prior report packages remain immutable."""
    with Path(path).open("x",encoding="utf-8") as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write("\n")


def write_table(path,rows,fields):
    """Write aggregate/operational CSVs, preserving missing values rather than inventing zeros."""
    with Path(path).open("x",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction="ignore");writer.writeheader()
        for row in rows:
            encoded={k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in row.items()}
            writer.writerow({k:"'"+v if isinstance(v,str) and v.lstrip().startswith(("=","+","-","@")) else v for k,v in encoded.items()})


def attach_reviews(entries,financial,quality):
    """Use only explicit AI-assisted case/attempt matches with identical financial condition identity."""
    lookup={(r['experiment_id'],r['attempt_id']):r for r in financial}
    for entry in entries:
        record=entry['receipt'];row=lookup[(record['experiment_id'],record['attempt_id'])]
        matches=[q for q in quality if q['method']=='ai_assisted' and q['case_id']==record['attempt_id'] and str(q.get('independent_review')).lower()=='true' and all(q[k]==row[k] for k in ('experiment_id','system_id','input_hash','workflow','skill_version','skill_hash','model','configuration_id'))]
        decisions={q['decision'] for q in matches}
        if len(decisions)>1:raise ValueError("Conflicting review decisions for one FMEA")
        entry['review_status']=next(iter(decisions)) if decisions else 'unreviewed'


def summarize(entries,financial):
    """Return separate campaign, request-history, validated-output, risk and cost tables."""
    lookup={(r['experiment_id'],r['attempt_id']):r for r in financial};campaigns=defaultdict(list)
    history=[];effective=[];risk=[]
    for e in entries:
        raw=e['receipt'];f=lookup[(raw['experiment_id'],raw['attempt_id'])];key=raw['experiment_id']+'/'+raw['attempt_id']
        row={**f,'catalog_identity':e['identity'],'csv_path':e['csv_path'],'csv_sha256':e['csv_sha256'],
            'generation_status':raw['status'],'outcome_class':outcome(e),'schema_valid':e['metrics'].get('schema_valid',False),
            'primary_dataset':e.get('primary',False),'representative':e.get('representative',False),'dataset_role':e.get('role'),
            'engineering_review_status':e.get('review_status','unreviewed'),'source_receipt_sha256':raw.get('source_receipt_sha256'),
            'provider_error_classification':raw.get('provider_error_classification'),'condition_verification':raw.get('condition_verification','recorded receipt/manifest'),
            'other_usage':{k:v for k,v in (f.get('usage') or {}).items() if k not in ('prompt_token_count','candidates_token_count','thoughts_token_count')},
            'source_records':e['sources']}
        history.append(row);campaigns[(f['experiment_id'],f['system_id'],f['skill_version'],f['configuration_id'])].append(row)
        if outcome(e)=='valid':
            m=e['metrics'];effective.append({k:row[k] for k in ('experiment_id','attempt_id','system_id','model','skill_version','configuration_id','duration_seconds','api_request_seconds','retry_number','dataset_role','primary_dataset','representative','csv_path','csv_sha256','engineering_review_status')}|{'row_count':m['row_count'],'distinct_component_count':m['distinct_component_count'],'failure_modes_per_component':m['failure_modes_per_component'],'potential_duplicate_rows':m['potential_duplicate_rows'],'coverage_fraction':None})
            for metric,counts in m['rating_distributions'].items():
                values=sorted(int(score) for score,n in counts.items() for _ in range(n))
                import statistics
                risk.append({'experiment_id':raw['experiment_id'],'attempt_id':raw['attempt_id'],'system_id':raw['system_id'],'metric':metric,'n_rows':len(values),'minimum':min(values),'median':statistics.median(values),'maximum':max(values),'sample_sd':statistics.stdev(values) if len(values)>1 else None,'distribution':counts,'rating_status':'provisional_unreviewed'})
    campaign_rows=[];cost_rows=[]
    for number,(key,rows) in enumerate(sorted(campaigns.items(),key=lambda item:(item[0][1],item[0][0],item[0][2],item[0][3])),1):
        campaign,system,version,configuration=key;valid=sum(r['schema_valid'] and r['generation_status']=='success' for r in rows)
        common={'campaign_key':f'C{number:02d}','experiment_id':campaign,'system_id':system,'skill_version':version,'configuration_id':configuration,'n_attempts':len(rows),'n_valid_drafts':valid}
        campaign_rows.append({**common,'provider_failures':sum(r['outcome_class']=='provider' for r in rows),'other_failures':sum(r['outcome_class']=='other' for r in rows),'retry_requests':sum(r['retry_number']>0 for r in rows),'retry_wait_seconds':sum(r['retry_wait_seconds'] for r in rows),'recorded_elapsed_seconds':sum(r['duration_seconds'] for r in rows if r['duration_seconds'] is not None),'missing_duration_attempts':sum(r['duration_seconds'] is None for r in rows)})
        known=sum(r['cost_usd'] for r in rows if r['cost_usd'] is not None);unpriced=sum(r['cost_usd'] is None for r in rows)
        cost_rows.append({**common,'invoice_subtotal_usd':sum(r['cost_usd'] for r in rows if r['cost_basis']=='invoice'),'assumed_tariff_estimate_subtotal_usd':sum(r['cost_usd'] for r in rows if r['cost_usd'] is not None and r['cost_basis'].startswith('estimated')),'unknown_actual_billing_attempts':sum(r['cost_basis']!='invoice' for r in rows),'unpriced_attempts':unpriced,'complete_priced_expense_per_valid_output_usd':known/valid if valid and not unpriced else None,'actual_total_billed_usd':known if all(r['cost_basis']=='invoice' for r in rows) else None})
    return campaign_rows,history,effective,risk,cost_rows


def create_report(paths,artifact_roots,output_root,catalog_path=None,effective_index=None,evidence_path=None,analysis_id=None,
                  labor_path=None,quality_path=None,invoices_path=None,scenario_path=None,tier='standard_paid',skip_empty=False):
    """Create an offline dashboard and execute the existing financial CLI on deduplicated real receipts."""
    if catalog_path:
        settings=Path(catalog_path).with_name("report_settings.json")
        settings.parent.mkdir(parents=True,exist_ok=True)
        # Persist selection/lookup scope for automatic follow-up reports, without storing any credentials.
        previous=read_json(settings) if settings.exists() else {}
        configured={"effective_index":str(effective_index) if effective_index else previous.get("effective_index"),
            "provider_evidence":str(evidence_path) if evidence_path else previous.get("provider_evidence"),
            "artifact_roots":list(dict.fromkeys(previous.get("artifact_roots",[])+[str(Path(p).resolve()) for p in artifact_roots]))}
        temp=settings.with_suffix(".json.tmp");temp.write_text(json.dumps(configured,indent=2),encoding="utf-8");temp.replace(settings)
    entries,excluded=ingest(paths,artifact_roots,catalog_path,evidence_path)
    entries=select(entries,effective_index)
    assumptions=read_json(CONFIG/'assumptions.json');invoices=read_json(invoices_path) if invoices_path else {}
    financial=financial_rows(entries,assumptions,tier,invoices)
    labor=read_log(labor_path,'labor');quality=read_log(quality_path,'quality');attach_reviews(entries,financial,quality)
    audit=data_audit(financial,labor,quality,len(paths));audit.update(validated_csv_outputs=sum(outcome(e)=='valid' for e in entries),primary_dataset_outputs=sum(e['primary'] for e in entries),representative_outputs=sum(e['representative'] for e in entries),canonical_attempts_included=0)
    print('EXPERIMENT DATA AUDIT: '+json.dumps(audit,sort_keys=True),flush=True)
    root=Path(output_root);root.mkdir(parents=True,exist_ok=True)
    analysis_id=analysis_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    if not re.fullmatch(r'[A-Za-z0-9_-]+',analysis_id):raise ValueError('Unsafe analysis ID')
    target=root/analysis_id
    if target.exists():raise FileExistsError(target)
    lock=root/('.'+analysis_id+'.lock')
    with lock.open('x') as stream:stream.write(str(os.getpid()))
    staging=root/('.'+analysis_id+'.staging')
    try:
        staging.mkdir(exist_ok=False)
        write_json(staging/'data_audit.json',audit)
        write_json(staging/'financial_input.json',{'plan':{'batch_id':analysis_id},'runs':[e['receipt'] for e in entries]})
        write_json(staging/'source_provenance.json',{'inputs':[{'path':str(Path(p).resolve()),'sha256':sha256(p)} for p in paths],
            'effective_index':{'path':str(Path(effective_index).resolve()),'sha256':sha256(effective_index)} if effective_index else None,'excluded':excluded,
            'note':'No source file, prompt, historical report or frozen evidence was modified.'})
        campaign,history,effective,risk,cost=summarize(entries,financial)
        tables=[('campaign_summary.csv',campaign,['experiment_id','system_id','n_attempts','n_valid_drafts']),('attempt_history.csv',history,['experiment_id','attempt_id','system_id','status']),
            ('effective_fmea_summary.csv',effective,['experiment_id','attempt_id','system_id','row_count','dataset_role']),('provisional_risk_summary.csv',risk,['experiment_id','attempt_id','system_id','metric','n_rows']),('cost_summary.csv',cost,['experiment_id','system_id','n_attempts','actual_total_billed_usd'])]
        for name,rows,empty_fields in tables:write_table(staging/name,rows,list(rows[0]) if rows else empty_fields)
        captions={} if skip_empty and not entries else render(entries,financial,staging/'figures')
        # This is the existing public financial entry point, executed with no provider credentials.
        command=[sys.executable,'-m','analysis.financial_impact','--manifest',str((staging/'financial_input.json').resolve()),'--output-root',str((staging/'financial').resolve()),'--analysis-id','financial-v1','--tier',tier]
        for option,value in (('--labor',labor_path),('--quality',quality_path),('--invoices',invoices_path),('--scenario',scenario_path)):
            if value:command.extend([option,str(Path(value).resolve())])
        env=dict(os.environ)
        for name in ('GEMINI_API_KEY','GOOGLE_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY'):env.pop(name,None)
        with (staging/'financial_execution.log').open('x',encoding='utf-8') as stream:
            execution=subprocess.run(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=180)
        if execution.returncode:raise RuntimeError('Financial CLI failed; inspect retained financial_execution.log')
        actual_finance=read_json(staging/'financial/financial-v1/metrics.json')
        if len(actual_finance['attempts'])!=len(entries):raise ValueError('Financial ingestion dropped or duplicated attempts')
        lines=['# Standalone FMEA experiment dashboard','', '**Preliminary AI-assisted analytical working report; engineering ratings remain provisional.**','',
            f"Attempts: **{len(entries)}**; validated drafts: **{audit['validated_csv_outputs']}**; primary dataset outputs: **{audit['primary_dataset_outputs']}**; selected five-system representatives: **{audit['representative_outputs']}**.",
            'The primary dataset preserves all successful A pilot replications and the latest reconciled B-E selections. Additional B/D/E replications and the earlier receiptless A run remain separate observations. Canonical research is excluded.',
            'A pilot run 3 is the chronological representative where supplied by the A-E index. Unknown legacy settings are separate conditions. Provider failures have no FMEA ratings or engineering-review denominator.','',
            '## Data audit','', '| Input | Count |','|---|---:|',*[f'| {k} | {v} |' for k,v in audit.items() if not isinstance(v,list)],'',
            '## Observed operational dashboard','']
        for name,caption in captions.items():lines.extend([f'### {name.replace("_"," ")}',f'![{name}](figures/{name}.png)',caption,''])
        lines.extend(['## Financial evidence and missing inputs','',
            '[Financial report](financial/financial-v1/Financial_Impacts.md) / [Financial data/figures](financial/financial-v1/manifest.json).',
            'Known token counts can be scaled by the configured paid tariff as an explicit estimate. Provider free-tier quota evidence is retained; paid-tariff amounts are not observed invoices. Unknown failed usage and actual billing are never zero.',
            'Empirical economics require closed manual development/review/approval time, AI preparation/supervision/review/rework time, equivalent scope/criteria and independently accepted matched cases, invoice reconciliation, skill maintenance/development expense and annual workload. Elapsed generation time is not active labor.',
            'No approved complete financial scenario is supplied by default. Fill the editable scenario template and explicitly pass --scenario to reuse the existing Monte Carlo, sensitivity and break-even model. Simulation intervals are not empirical confidence intervals.',
            '## Reproducibility','', 'Tables preserve every attempted request and separate validated outputs from primary selections. Artifacts are SHA-256 checked. No coverage fraction is inferred without a validated denominator. No reference FMEA was read.',''])
        (staging/'dashboard.md').write_text('\n'.join(lines),encoding='utf-8')
        (staging/'README.md').write_text('# Versioned experiment dashboard\n\nOpen [dashboard.md](dashboard.md). Raw FMEA worksheets and provider responses are not copied into this package. Tables contain aggregate/operational metadata; source files stay in ignored local storage.\n\n'+f'Attempts {len(entries)}; validated outputs {audit["validated_csv_outputs"]}; all ratings provisional.\n',encoding='utf-8')
        (staging/'run_summary.md').write_text(f'# Offline reporting summary\n\nImported {len(entries)} unique standalone attempts; {audit["validated_csv_outputs"]} schema-valid outputs. No generation requests were made.\n\nDashboard: {target.resolve()}/dashboard.md\nFinancial report: {target.resolve()}/financial/financial-v1/Financial_Impacts.md\n',encoding='utf-8')
        manifest={'schema':'fmea-experiment-dashboard-1','report_version':REPORT_VERSION,'analysis_id':analysis_id,'created_at':datetime.now(timezone.utc).isoformat(),
            'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'reporting_code_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):sha256(p) for p in Path(__file__).parent.glob('*.py')},'data_audit':audit,
            'figure_captions':captions,'financial_report':'financial/financial-v1','scenario_status':actual_finance['simulation']['status'],
            'condition_groups':{name:{'attempts':len(values),'system_id':values[0]['receipt']['system_id'],'example_configuration':values[0]['receipt'].get('configuration')} for name,values in groups(entries)},
            'artifacts':{str(p.relative_to(staging)).replace('\\','/'):sha256(p) for p in staging.rglob('*') if p.is_file()}}
        write_json(staging/'dashboard_manifest.json',manifest);staging.rename(target)
    finally:lock.unlink(missing_ok=True)
    latest=root/'latest.json';temporary=root/('.latest-'+uuid.uuid4().hex+'.json')
    write_json(temporary,{'analysis_id':analysis_id,'dashboard':str((target/'dashboard.md').resolve()),'manifest_sha256':sha256(target/'dashboard_manifest.json')});temporary.replace(latest)
    return target


def post_generation(source):
    """Default automatic local reporting discovers completed metadata; it never invokes generation."""
    source=Path(source).resolve();paths=discover([source])
    if not paths:return None
    try:source.relative_to(ROOT/'results');base=ROOT/'results/experiment_metrics'
    except ValueError:base=source.parent/'experiment_metrics'
    roots=[source if source.is_dir() else source.parent]
    settings=read_json(base/'report_settings.json') if (base/'report_settings.json').exists() else {}
    roots+=list(map(Path,settings.get('artifact_roots',[])))
    return create_report(paths,roots,base/'reports',base/'catalog.json',settings.get('effective_index'),settings.get('provider_evidence'),skip_empty=True)


def publish_stage(report,output):
    """Stage only aggregate PNGs and a figure gallery for human review; never copy raw tables or auto-push."""
    report=Path(report);manifest=read_json(report/'dashboard_manifest.json');output=Path(output)
    output.mkdir(parents=True,exist_ok=False);(output/'figures').mkdir()
    lines=['# Aggregate figure publication review','', 'Review labels/captions and approve before committing. No raw FMEAs, attempt tables, invoices or reviewer logs are staged.','']
    for name,caption in manifest['figure_captions'].items():
        source=report/'figures'/(name+'.png')
        if sha256(source)!=manifest['artifacts'][str(source.relative_to(report)).replace('\\','/')]:raise ValueError('Figure hash mismatch')
        shutil.copy2(source,output/'figures'/source.name);lines.extend([f'![{name}](figures/{source.name})',caption,''])
    finance=report/'financial/financial-v1'
    if (finance/'manifest.json').exists():
        fm=read_json(finance/'manifest.json');destination=output/'financial-figures';destination.mkdir()
        for source in sorted((finance/'figures').glob('*.png')):
            if not re.match(r"(?:0[789]|1[0-4])_",source.name):continue
            key=str(source.relative_to(finance)).replace('\\','/')
            if sha256(source)!=fm['artifacts'][key]:raise ValueError('Financial figure hash mismatch')
            shutil.copy2(source,destination/source.name)
            lines.extend([f'![{source.stem}](financial-figures/{source.name})','Observed operational/tariff-estimate panel; any scenario panel remains explicitly illustrative.',''])
    (output/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    write_json(output/'publication_manifest.json',{'source_report_sha256':sha256(report/'dashboard_manifest.json'),'approval_status':'pending_human_review','files':{str(p.relative_to(output)).replace('\\','/'):sha256(p) for p in output.rglob('*') if p.is_file()}})
    return output
