"""Ten descriptive 300-dpi experiment figures; no inference of coverage, acceptance or repeatability."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics
import textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

COLORS={"valid":"#287a91","provider":"#ad4a3b","other":"#c38a20","estimate":"#75629b"}


def outcome(entry):
    """Classify operational failure separately from valid FMEA observations."""
    r=entry["receipt"]
    if r["status"]=="success" and entry["metrics"].get("schema_valid"):return "valid"
    provider=r.get("http_status") is not None or r.get("error_type") in ("ServerError","ClientError","RemoteProtocolError","ReadTimeout","ConnectError","ConnectionError") or "provider" in str(r.get("failure_classification", ""))
    return "provider" if provider else "other"


def groups(entries):
    """Separate systems, input/skill hashes and generation settings; never pool unknown legacy settings."""
    grouped=defaultdict(list)
    for entry in entries:
        r=entry["receipt"];config=r.get("configuration",{})
        # A hash of the known source condition keeps undocumented legacy settings in a separate cohort.
        def normalize_schema(value):
            if isinstance(value,list):return [normalize_schema(v) for v in value]
            if not isinstance(value,dict):return value
            return {k:normalize_schema(v) for k,v in value.items() if not (k=="property_ordering" and v==value.get("required"))}
        schema_hash=r.get("response_schema_sha256")
        if schema_hash is None and config.get("response_schema"):
            schema_hash=hashlib.sha256(json.dumps(normalize_schema(config["response_schema"]),sort_keys=True).encode()).hexdigest()
        settings={k:v for k,v in config.items() if k!="response_schema"}
        for field in ("temperature","max_output_tokens","response_mime_type","retry_attempts"):
            settings.setdefault(field,r.get(field))
        settings["response_schema_sha256"]=schema_hash
        signature=(r["system_id"],r["prompt_version"],r.get("skill_sha256"),r.get("system_sha256"),r["model"],json.dumps(settings,sort_keys=True),bool(r.get("condition_verification")))
        grouped[signature].append(entry)
    items=sorted(grouped.items(),key=lambda x:(x[0][0],str(x[0][1:])));counts=Counter(k[0] for k,_ in items);seen=Counter();result=[]
    for key,values in items:
        seen[key[0]]+=1
        label=key[0].replace("system_","")+(f" / c{seen[key[0]]}" if counts[key[0]]>1 else "")
        result.append((label,values))
    return result


def expand(values,metric):
    """Expand histogram counts for descriptive boxplots; generated rows remain nested in drafts."""
    return [int(score) for entry in values if outcome(entry)=="valid" for score,count in entry["metrics"]["rating_distributions"][metric].items() for _ in range(count)]


def render(entries,financial,output):
    """Render all required dashboard figures using actual observations or explicitly labeled gaps."""
    output=Path(output);output.mkdir(exist_ok=False)
    cohorts=groups(entries);labels=[name for name,_ in cohorts];positions=np.arange(len(cohorts));captions={}
    cost_lookup={(r["experiment_id"],r["attempt_id"]):r for r in financial}
    n=len(entries);valid=sum(outcome(e)=="valid" for e in entries)
    source=f"Standalone receipts: attempts n={n}; validated drafts n={valid}. No canonical data. Cohort suffixes separate recorded/unknown settings."
    def canvas(title,ylabel,panels=1):
        fig,axes=plt.subplots(1,panels,figsize=(max(10,len(cohorts)*1.5)*(1 if panels==1 else 1.6),6),squeeze=False)
        fig.suptitle(title);fig.subplots_adjust(bottom=.28,top=.86,wspace=.3)
        for ax in axes.flat:
            ax.set_ylabel(ylabel);ax.set_xlabel("System / recorded condition")
            ax.set_xticks(positions,labels)
            if not cohorts:ax.text(.5,.5,"No observed standalone attempts",ha="center",transform=ax.transAxes)
        return fig,list(axes.flat)
    def save(fig,name,caption):
        fig.text(.05,.055,textwrap.fill(source+" "+caption,110 if fig.get_figwidth()<12 else 170),fontsize=9)
        fig.savefig(output/(name+".png"),dpi=300);plt.close(fig);captions[name]=caption
    def missing(ax,message):
        ax.text(.5,.5,textwrap.fill(message,60),ha="center",va="center",transform=ax.transAxes)
    def amounts(values):
        return [cost_lookup[(e["receipt"]["experiment_id"],e["receipt"]["attempt_id"])] for e in values]
    # 1. Successful CSV validation is distinct from a successful HTTP exchange and from engineering acceptance.
    fig,(ax,)=canvas("Generation outcomes by system","Attempts (count)")
    bottoms=np.zeros(len(cohorts))
    for kind,label in (("valid","Schema-valid success"),("provider","Provider failure"),("other","Other/invalid outcome")):
        values=[sum(outcome(e)==kind for e in group) for _,group in cohorts]
        ax.bar(positions,values,bottom=bottoms,label=label,color=COLORS[kind]);bottoms+=values
    ax.legend(loc="upper center",bbox_to_anchor=(.5,1.12),ncol=3,fontsize=9);ax.margins(y=.12);save(fig,"01_generation_success","Provider failures contribute only to operational history. Each bar counts requests; no engineering correctness is inferred.")
    # 2. Show every available clock, retaining the older CSV timing definition explicitly.
    fig,(ax,)=canvas("Recorded generation/attempt durations","Elapsed seconds / attempt")
    for x,(_,values) in enumerate(cohorts):
        for offset,e in zip(np.linspace(-.2,.2,len(values)),values):
            r=cost_lookup[(e["receipt"]["experiment_id"],e["receipt"]["attempt_id"])];duration=r["duration_seconds"]
            if duration is not None:ax.scatter(x+offset,duration,marker="D" if r["duration_kind"].startswith("legacy") else "o" if outcome(e)=="valid" else "x",color=COLORS[outcome(e)])
    ax.legend(handles=[Line2D([],[],marker="o",linestyle="",color=COLORS['valid'],label="Valid output"),Line2D([],[],marker="x",linestyle="",color=COLORS['provider'],label="Failed request"),Line2D([],[],marker="D",linestyle="",color="#777",label="Legacy recorded minutes")])
    save(fig,"02_generation_duration","Each marker is one observed attempt. Legacy generation_minutes is retained as a separate timing definition; API/parse times are not inferred.")
    # 3. Drafts and repetitions stay separate; five-system representatives are outlined, not pooled.
    fig,(ax,)=canvas("Valid failure-mode row counts per draft","FMEA rows / validated draft")
    for x,(_,values) in enumerate(cohorts):
        success=[e for e in values if outcome(e)=="valid"]
        for offset,e in zip(np.linspace(-.18,.18,len(success)),success):
            ax.scatter(x+offset,e["metrics"]["row_count"],marker="o" if e.get("primary") else "^",color=COLORS['valid'] if e.get("primary") else "#777",s=60)
            if e.get("representative"):ax.scatter(x+offset,e["metrics"]["row_count"],marker="s",facecolors="none",edgecolors="#222",s=140)
    ax.legend(handles=[Line2D([],[],marker="o",linestyle="",color=COLORS['valid'],label="Reconciled / A pilot"),Line2D([],[],marker="^",linestyle="",color="#777",label="Additional replication"),Line2D([],[],marker="s",linestyle="",markerfacecolor="none",color="#222",label="Representative")])
    save(fig,"03_fmea_rows","All validated drafts are shown separately. A pilot run 3 is the chronological representative; other A successes are preserved.")
    # 4-5. Rating rows are nested within drafts: boxplots describe provisional values, not independent cases.
    for metrics,name,title in ((("severity","occurrence","detection"),"04_sod_distributions","Provisional S/O/D distributions"),(("RPN",),"05_rpn_distributions","Provisional RPN distributions")):
        fig,axes=canvas(title,"Provisional score (1-10)" if len(metrics)>1 else "Provisional RPN (S * O * D)",len(metrics))
        for ax,metric in zip(axes,metrics):
            for x,(_,values) in enumerate(cohorts):
                data=expand(values,metric)
                if data:ax.boxplot([data],positions=[x],widths=.5,whis=(0,100),showfliers=False)
                ax.text(x,.96,f"n={sum(outcome(e)=='valid' for e in values)}/{len(data)}",ha="center",fontsize=8,transform=ax.get_xaxis_transform())
            ax.set_title(metric);ax.set_xticks(positions,labels);ax.margins(y=.22)
        save(fig,name,"n=drafts/rows. Boxes show medians, quartiles and full ranges. Generated rows are nested within drafts; ratings are provisional and no confidence intervals or quality claim are supplied.")
    # 6. Literal component representation has no validated completeness denominator.
    fig,axes=canvas("Component and failure-mode representation","Literal components / draft",2)
    for x,(_,values) in enumerate(cohorts):
        for offset,e in zip(np.linspace(-.18,.18,len(values)),values):
            if outcome(e)=="valid":axes[0].scatter(x+offset,e["metrics"]["distinct_component_count"],color=COLORS['valid'])
        data=[count for e in values if outcome(e)=="valid" for count in e["metrics"]["failure_modes_per_component"].values()]
        if data:axes[1].boxplot([data],positions=[x],widths=.5,whis=(0,100),showfliers=False)
    axes[1].set_ylabel("Generated failure-mode rows / literal component");axes[1].set_xticks(positions,labels)
    save(fig,"06_component_representation","Literal labels are representation counts, not semantic component coverage or failure-mode completeness. No validated denominator is available.")
    # 7. Count all failures without treating them as engineering observations; throughput includes overhead.
    fig,axes=canvas("Provider reliability, recovery and request overhead","Requests / outcomes (count)",2)
    bottoms=np.zeros(len(cohorts))
    for label,predicate,color in (("Initial valid success",lambda e:outcome(e)=="valid" and not (e['receipt'].get('supersedes_attempt_id') or e['receipt'].get('retry_number',0)>0),COLORS['valid']),
        ("Recovery valid success",lambda e:outcome(e)=="valid" and bool(e['receipt'].get('supersedes_attempt_id') or e['receipt'].get('retry_number',0)>0),"#527a51"),
        ("Verified HTTP503",lambda e:e['receipt'].get('http_status')==503,COLORS['provider']),
        ("Other failed/invalid",lambda e:outcome(e)!="valid" and e['receipt'].get('http_status')!=503,COLORS['other'])):
        values=[sum(predicate(e) for e in group) for _,group in cohorts];axes[0].bar(positions,values,bottom=bottoms,label=label,color=color);bottoms+=values
    axes[0].legend(fontsize=8)
    for x,(_,values) in enumerate(cohorts):
        denominator=sum(outcome(e)=="valid" for e in values)
        if denominator:axes[1].bar(x,len(values)/denominator,color=COLORS['valid'])
        else:axes[1].text(x,0,"unavailable",rotation=90)
    axes[1].set_ylabel("All requests / validated draft (ratio)")
    save(fig,"07_provider_reliability","Initial/recovery labels follow recorded linkage/retry numbers. Request/valid-output ratios include failures and are descriptive throughput, not a quality rate.")
    # 8. Monetary amounts and unavailable billing are separate, with explicit system/campaign keys.
    grouped=defaultdict(list)
    for row in financial:grouped[(row['system_id'],row['experiment_id'],row['skill_version'],row['configuration_id'])].append(row)
    fig,(ax,)=canvas("API expense by system and campaign","USD (invoice or assumed paid-tariff estimate)")
    campaign_keys=sorted(grouped);x=np.arange(len(campaign_keys))
    for shift,basis,label,color in ((-.18,"invoice","Known invoice",COLORS['valid']),(.18,"estimated_standard_paid_tokens","Assumed paid-tariff estimate",COLORS['estimate'])):
        ax.bar(x+shift,[sum(r['cost_usd'] for r in grouped[k] if r['cost_usd'] is not None and r['cost_basis']==basis) for k in campaign_keys],width=.35,label=label,color=color)
    ax.set_xticks(x,[k[0].replace('system_','')+f" / C{i+1:02d}" for i,k in enumerate(campaign_keys)],rotation=35)
    for i,k in enumerate(campaign_keys):ax.text(i,.97,f"{sum(r['cost_basis']!='invoice' for r in grouped[k])} bills unknown",transform=ax.get_xaxis_transform(),ha='center',rotation=90,fontsize=7,va='top')
    ax.legend();save(fig,"08_api_expense","Campaign C01-Cnn keys map to cost_summary.csv. Token-scaled paid tariffs are assumptions, not invoices; provider free-tier evidence means actual charges remain unverified. Missing failed usage is not zero expense.")
    # 9. Compare measurable timing with the known-usage monetary subset, never accepted-FMEA cost.
    fig,axes=canvas("Generation efficiency per schema-valid output","Recorded seconds / valid output",2)
    for x,(_,values) in enumerate(cohorts):
        comparable=[e for e in values if not cost_lookup[(e['receipt']['experiment_id'],e['receipt']['attempt_id'])]['duration_kind'].startswith('legacy')]
        rows=amounts(comparable);denominator=sum(outcome(e)=='valid' for e in comparable)
        if denominator and all(r['duration_seconds'] is not None for r in rows):axes[0].bar(x,sum(r['duration_seconds'] for r in rows)/denominator,color=COLORS['valid'])
        valid_rows=amounts([e for e in values if outcome(e)=='valid']);priced=[r['cost_usd'] for r in valid_rows if r['cost_usd'] is not None]
        if priced:axes[1].bar(x,statistics.mean(priced),color=COLORS['estimate'])
        else:axes[1].text(x,0,"unavailable",rotation=90)
        axes[1].text(x,.96,f"{len(priced)}/{len(valid_rows)} priced",transform=axes[1].get_xaxis_transform(),ha='center',fontsize=8)
    axes[1].set_ylabel("USD / priced valid response (tariff estimate subset)")
    save(fig,"09_generation_efficiency","Timing includes observed failure overhead but excludes incomparable legacy timing. Monetary bars use only priced successful responses; complete-history expense per valid output is unavailable when any bill is unresolved. Not cost per engineering-accepted FMEA.")
    # 10. No independent decision becomes 'accepted' merely because a CSV validates.
    fig,(ax,)=canvas("Engineering review evidence for validated drafts","Validated drafts (count)")
    bottoms=np.zeros(len(cohorts))
    for status,color in (("accepted","#527a51"),("rejected",COLORS['provider']),("pending",COLORS['other']),("unreviewed","#92999f")):
        values=[sum(e.get('review_status','unreviewed')==status and outcome(e)=='valid' for e in group) for _,group in cohorts]
        ax.bar(positions,values,bottom=bottoms,label=status,color=color);bottoms+=values
    ax.legend();save(fig,"10_engineering_review","Only explicitly matched independent review records supply accepted/rejected/pending decisions. With no review observations, all validated drafts are unreviewed; no acceptance rate is inferred.")
    return captions
