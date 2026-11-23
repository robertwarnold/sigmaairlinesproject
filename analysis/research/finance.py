"""Quality-linked financial adapter reusing the project's cost and simulation engines."""
import math
from statistics import mean
import numpy as np
from analysis.financial_impact.cost_model import comparison
from analysis.financial_impact.uncertainty import simulate

DEFAULTS={'annual_volume':50,'labor_rate':92.71,'manual_hours':43851/(50*92.71),
          'setup_hours':.5,'matched_review_minutes':3,'missed_reconstruction_minutes':20,
          'extra_review_minutes':5,'approval_hours':1,'development_usd':3500,'maintenance_usd':0,
          'api_usd_per_attempt':1,'success_probability':.8,'uncertainty_fraction':.2}


def scenario_comparison(generations, runs, baseline, assumptions):
    """Standard review-effort sensitivity around the supplied assumptions."""
    fields = ('matched_review_minutes', 'missed_reconstruction_minutes', 'extra_review_minutes')
    scenarios = []
    for label, factor in (('Higher review effort', 1.25), ('Selected assumptions', 1), ('Lower review effort', .75)):
        selected = {**assumptions, **{field: assumptions[field]*factor for field in fields}}
        result = model(generations,runs,baseline,selected)['modeled']
        scenarios.append({'scenario':label, 'net_benefit':result['first_year_net_savings'],
                          'cost_per_fmea':result['ai_per_fmea'], 'break_even':result['break_even_fmeas']})
    return scenarios
HISTORICAL={'status':'HISTORICAL_PLANNING_SCENARIO_NOT_MEASURED','annual_volume':50,'labor_rate':92.71,
            'manual_annual_usd_approximate':43851,'ai_annual_operating_usd_approximate':34800,
            'first_year_net_savings_usd_approximate':5551,'simulation_interval95_usd_reported':[-9475,21483],
            'provenance':'User-supplied earlier planning scenario; original preliminary assumptions not reconstructed'}


def validate_assumptions(values):
    if set(values)!=set(DEFAULTS): raise ValueError('All documented scenario assumptions required')
    for k,v in values.items():
        if type(v) not in (int,float) or not math.isfinite(v) or v<0: raise ValueError('Invalid assumption '+k)
    if values['annual_volume']<=0 or not 0<values['success_probability']<=1 or values['uncertainty_fraction']>.8: raise ValueError('Invalid volume/probability/uncertainty')
    return values


def model(generations,runs,baseline,assumptions=None,seed=5300):
    assumptions=validate_assumptions(dict(DEFAULTS if assumptions is None else assumptions))
    observed=[g for g in generations if g.get('generation_status') in ('success','failed')]
    actual=[g['actual_cost'] for g in observed if g.get('actual_cost') is not None]
    estimated=[g['estimated_cost'] for g in observed if g.get('estimated_cost') is not None]
    for cost in actual+estimated:
        if type(cost) not in (int,float) or not math.isfinite(cost) or cost<0: raise ValueError('Invalid recorded cost')
    complete=bool(observed) and len(actual)==len(observed)
    total=sum(actual) if complete else None
    successful=sum(g.get('generation_status')=='success' for g in observed)
    review_times=[g['recorded_review_minutes'] for g in generations if g.get('recorded_review_minutes') is not None]
    measured={'recorded_review_minutes':sum(review_times) if review_times else None,'review_time_generations':len(review_times),'actual_api_spending':total,'known_billed_subtotal':sum(actual) if actual else None,
              'billed_attempts':len(actual),'total_attempts':len(observed),'billing_complete':complete,
              'estimated_api_spending':sum(estimated) if observed and len(estimated)==len(observed) else None,
              'api_cost_per_attempt':total/len(observed) if complete else None,
              'api_cost_per_success':total/successful if complete and successful else None,
              'api_cost_per_evaluated':total/len(runs) if complete and runs else None,
              'verified_savings':None,'verified_savings_status':'Unavailable: no matched accepted manual/AI labor records'}
    if runs:
        found=mean(r['found'] for r in runs); missed=mean(r['missed'] for r in runs); extra=mean(r['extra_unmatched_rows'] for r in runs)
        basis='Validated selected independent judge evaluations; per-run mean item counts'
    else:
        missed=baseline['missed']/baseline['total_runs']; found=(baseline['opportunities']-baseline['missed'])/baseline['total_runs']; extra=baseline['extra_unmatched_rows']/baseline['total_runs']
        basis='Report-derived historical V2 aggregate item counts per run; not measured labor or V4 quality'
    a=assumptions; rate=a['labor_rate']
    activities={'Setup':a['setup_hours'],'Matched-item review':found*a['matched_review_minutes']/60,
                'Missed-item reconstruction':missed*a['missed_reconstruction_minutes']/60,
                'Extra-row review':extra*a['extra_review_minutes']/60,'Final approval':a['approval_hours']}
    ai_hours=sum(activities.values()); api=a['api_usd_per_attempt']/a['success_probability']
    manual=rate*a['manual_hours']; ai=rate*ai_hours+api
    deterministic=comparison(manual,ai,a['development_usd'],a['maintenance_usd'],a['annual_volume'])
    uncertainty=a['uncertainty_fraction']
    def distribution(v): return {'distribution':'triangular','low':v*(1-uncertainty),'mode':v,'high':v*(1+uncertainty)} if uncertainty and v else {'distribution':'constant','value':v}
    distributions={k:distribution(v) for k,v in {'labor_rate':rate,'manual_hours':a['manual_hours'],'ai_hours':ai_hours,'api_usd_per_attempt':a['api_usd_per_attempt'],'maintenance_usd':a['maintenance_usd'],'development_usd':a['development_usd']}.items()}
    distributions.update(success_probability={'distribution':'constant','value':a['success_probability']},annual_volume={'distribution':'constant','value':a['annual_volume']})
    simulation=simulate({'rationale':'Editable quality-linked planning assumptions; not measured or verified savings','distributions':distributions},iterations=10000,seed=seed)
    annual=np.asarray(simulation['draws'])*a['annual_volume']
    heights,edges=np.histogram(annual,bins=40)
    tornado=[]
    for key in ('labor_rate','manual_hours','missed_reconstruction_minutes','matched_review_minutes','annual_volume'):
        outcomes=[]
        for multiplier in (.8,1.2):
            changed={**a,key:a[key]*multiplier}
            hours=changed['setup_hours']+found*changed['matched_review_minutes']/60+missed*changed['missed_reconstruction_minutes']/60+extra*changed['extra_review_minutes']/60+changed['approval_hours']
            outcomes.append((changed['labor_rate']*changed['manual_hours']-changed['labor_rate']*hours-api)*changed['annual_volume']-changed['development_usd']-changed['maintenance_usd'])
        tornado.append({'assumption':key,'low':min(outcomes),'high':max(outcomes)})
    spending=[]; cumulative=0; complete_prefix=True; known_invoices=0
    for generation in sorted(observed,key=lambda g:g.get('generation_timestamp') or ''):
        cost=generation.get('actual_cost')
        if cost is None: complete_prefix=False
        else: cumulative+=cost; known_invoices+=1
        spending.append({'generation_timestamp':generation.get('generation_timestamp'),
                         'known_billed_subtotal':cumulative if known_invoices else None,'complete_cumulative_actual':cumulative if complete_prefix else None})
    by_version=[]
    for version in sorted({r['skill_version'] for r in runs}):
        selected=[r for r in runs if r['skill_version']==version]
        cost=rate*mean((r['found']*a['matched_review_minutes']+r['missed']*a['missed_reconstruction_minutes']+r['extra_unmatched_rows']*a['extra_review_minutes'])/60 for r in selected)
        by_version.append({'skill_version':version,'evaluated_fmeas':len(selected),'modeled_mean_review_cost':cost})
    return {'status':'MODELED_NOT_MEASURED','basis':basis,'assumptions':a,'historical_scenario':HISTORICAL,
            'measured':measured,'modeled':{**deterministic,'manual_per_fmea':manual,'ai_per_fmea':ai,
            'manual_annual_cost':manual*a['annual_volume'],'ai_annual_operating_cost':ai*a['annual_volume']+a['maintenance_usd'],
            'first_year_net_savings':deterministic['net_annual_savings_usd'],'annual_operating_savings':(manual-ai)*a['annual_volume']-a['maintenance_usd'],
            'review_cost_per_fmea':rate*(activities['Matched-item review']+activities['Missed-item reconstruction']+activities['Extra-row review'])},
            'activities':[{'activity':k,'hours_per_fmea':v,'cost_per_fmea':v*rate} for k,v in activities.items()]+[{'activity':'Assumed API attempts','hours_per_fmea':None,'cost_per_fmea':api}],
            'simulation':{'method':simulation['interval_kind'],'iterations':10000,'seed':seed,'median_annual_net_savings':float(np.median(annual)),
                          'interval95_annual_usd':np.quantile(annual,[.025,.975]).tolist(),
                          'histogram':[{'midpoint':float((edges[i]+edges[i+1])/2),'count':int(n)} for i,n in enumerate(heights)]},
            'sensitivity':tornado,'observed_spending':spending,'version_review_costs':by_version,
            'quality_review_estimates':[{'system':r['system'],'skill_version':r['skill_version'],'run_id':r['run_id'],
                'estimated_review_cost':rate*(r['found']*a['matched_review_minutes']+r['missed']*a['missed_reconstruction_minutes']+r['extra_unmatched_rows']*a['extra_review_minutes'])/60} for r in runs]}
