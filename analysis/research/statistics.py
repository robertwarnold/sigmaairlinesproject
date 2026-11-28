"""Run-level, system-stratified inference. No synthetic observations are injected."""
from statistics import mean, stdev
import numpy as np
from scipy import stats

VERSIONS=('v2.0','v3.0','v3.0-audit','v4.0-inventory')
SYSTEMS=tuple('ABCDE')


def bootstrap(runs, versions, draws=2000, seed=5300):
    """Resample runs within each version/system, then average five system means.

    Equal system weighting is maintained even for unbalanced replication. This is
    an independent-run (not paired-item) percentile bootstrap. At least two runs
    per cell are required; sparse cells do not produce misleading zero-width CIs.
    """
    runs=[r for r in runs if r.get('comparison_eligible',True)]
    groups={(v,s):[r['missed_percentage'] for r in runs if r['skill_version']==v and r['system']==s] for v in versions for s in SYSTEMS}
    if any(len(x)<2 for x in groups.values()): return {'status':'INSUFFICIENT_DATA','reason':'Need at least two independent runs in every version/system cell'}
    rng=np.random.default_rng(seed)
    estimates={v:np.zeros(draws) for v in versions}
    for (v,s),values in groups.items():
        estimates[v]+=rng.choice(values,size=(draws,len(values)),replace=True).mean(axis=1)/len(SYSTEMS)
    means={v:float(mean(mean(groups[v,s]) for s in SYSTEMS)) for v in versions}
    result={'status':'PASS','method':'system-stratified independent-run percentile bootstrap; equal 1/5 system weights','seed':seed,'draws':draws,
            'means':{v:{'mean':means[v],'ci_low':float(np.quantile(x,.025)),'ci_high':float(np.quantile(x,.975))} for v,x in estimates.items()}}
    if len(versions)==2:
        delta=estimates[versions[0]]-estimates[versions[1]]
        result['improvement']={'percentage_points':means[versions[0]]-means[versions[1]],'ci_low':float(np.quantile(delta,.025)),'ci_high':float(np.quantile(delta,.975))}
    return result


def anova(runs, versions):
    """Partial skill-version F test: full additive model versus system-only model.

    Version terms are tested jointly for the exploratory three-version model.
    This is equivalent to an R partial model comparison; no interaction is fitted.
    """
    selected=[r for r in runs if r['skill_version'] in versions and r.get('comparison_eligible',True)]
    if any(not any(r['system']==s and r['skill_version']==v for r in selected) for v in versions for s in SYSTEMS):
        return {'status':'INSUFFICIENT_DATA','reason':'All five systems required in every compared version'}
    y=np.array([r['missed_percentage'] for r in selected],dtype=float)
    if not np.isfinite(y).all() or ((y<0)|(y>100)).any(): raise ValueError('Invalid ANOVA rates')
    reduced=np.array([[1]+[int(r['system']==s) for s in SYSTEMS[1:]] for r in selected],dtype=float)
    full=np.column_stack([reduced]+[[int(r['skill_version']==v) for r in selected] for v in versions[1:]])
    rank=np.linalg.matrix_rank(full); df=len(y)-rank; numerator=rank-np.linalg.matrix_rank(reduced)
    if rank!=5+len(versions)-1 or df<=0: return {'status':'INSUFFICIENT_DATA','reason':'Rank deficient or no residual degrees of freedom'}
    fitted=full@np.linalg.lstsq(full,y,rcond=None)[0]; residual=y-fitted
    rss1=float(residual@residual); residual0=y-reduced@np.linalg.lstsq(reduced,y,rcond=None)[0]; rss0=float(residual0@residual0)
    if rss1<1e-12: return {'status':'INSUFFICIENT_DATA','reason':'Residual variance is zero; F test undefined'}
    f=max(0,(rss0-rss1)/numerator)/(rss1/df)
    groups=[y[[r['system']==s and r['skill_version']==v for r in selected]] for v in versions for s in SYSTEMS]
    levene=stats.levene(*groups,center='median') if all(len(g)>1 for g in groups) else None
    shapiro=stats.shapiro(residual) if 3<=len(residual)<=5000 else None
    finite=lambda value: float(value) if value is not None and np.isfinite(value) else None
    return {'status':'PASS','model':'missed_percentage ~ skill_version + system','versions':list(versions),
            'F':float(f),'p':float(stats.f.sf(f,numerator,df)),'df_version':int(numerator),'df_residual':int(df),
            'diagnostics':{'residual_sd':float(stdev(residual)),'shapiro_p':finite(shapiro.pvalue) if shapiro else None,'levene_median_p':finite(levene.pvalue) if levene else None},
            'assumptions':['independent generations','additive effects','approximately normal homoscedastic residuals; bounded rates and small samples limit inference']}


def compare(runs):
    """Designated primary contrast is always V2 versus V4, never V3 substituted."""
    primary=anova(runs,('v2.0','v4.0-inventory'))
    ci=bootstrap(runs,('v2.0','v4.0-inventory'))
    criteria={k:'PENDING' for k in ('mean_below_20','version_p_below_0_05','four_systems_improve','no_system_worsens_over_5pp','extra_rows_at_most_4_8','structural_completeness','valid_format','unsupported_inflation_acceptable')}
    v4=[r for r in runs if r['skill_version']=='v4.0-inventory']
    # Criteria are not declared PASS on an incomplete 20-run experiment.
    ready=all(r.get('comparison_eligible',True) for r in v4) and all(sum(r['system']==s for r in v4)>=4 for s in SYSTEMS)
    status=lambda value:'PASS' if value else 'FAIL'
    if v4:
        for name,field in [('structural_completeness','structural_status'),('valid_format','format_status'),('unsupported_inflation_acceptable','unsupported_inflation_review')]:
            values=[r.get(field) for r in v4]
            criteria[name]='FAIL' if 'FAIL' in values else 'PASS' if ready and all(v=='PASS' for v in values) else 'INSUFFICIENT_DATA'
    if ready:
        criteria['mean_below_20']=status(mean(r['missed_percentage'] for r in v4)<20)
        criteria['extra_rows_at_most_4_8']=status(mean(r['extra_unmatched_rows'] for r in v4)<=4.8)
        criteria['version_p_below_0_05']=status(primary['p']<.05) if primary['status']=='PASS' else 'INSUFFICIENT_DATA'
        if all(any(r['skill_version']=='v2.0' and r['system']==s for r in runs) for s in SYSTEMS):
            deltas={s:mean(r['missed_percentage'] for r in runs if r['skill_version']=='v2.0' and r['system']==s)-mean(r['missed_percentage'] for r in v4 if r['system']==s) for s in SYSTEMS}
            criteria['four_systems_improve']=status(sum(d>0 for d in deltas.values())>=4)
            criteria['no_system_worsens_over_5pp']=status(min(deltas.values())>=-5)
        else:
            criteria['four_systems_improve']=criteria['no_system_worsens_over_5pp']='INSUFFICIENT_DATA'
    return {'primary_comparison':'v2.0 vs v4.0-inventory','anova':primary,'confidence_intervals':ci,'criteria':criteria,
            'secondary_v3_vs_v4':{'anova':anova(runs,('v3.0','v4.0-inventory')),'confidence_intervals':bootstrap(runs,('v3.0','v4.0-inventory'))},
            'exploratory_three_version':anova(runs,('v2.0','v3.0','v4.0-inventory')),'exploratory_four_version':anova(runs,VERSIONS),'planned_v4_runs':20,'evaluated_v4_runs':len(v4),
            'research_status':'PENDING_LIVE_EVALUATION' if not v4 else 'EVALUATED_DATA_AVAILABLE',
            'limitations':'Report-derived pooled V2 baseline cannot support run means, CIs or ANOVA. Bootstrap is exploratory with four runs/cell; no item-independence claim. Engineering review remains required.'}
