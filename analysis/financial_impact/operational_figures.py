"""Observed operational finance panels that do not require invented manual labor or acceptance."""
from collections import defaultdict
from pathlib import Path
import statistics
import textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def figures(metrics,output):
    """Render durations, tokens, overhead, retries, expenses and valid-response efficiency at 300 dpi."""
    output=Path(output);attempts=metrics["attempts"];groups=defaultdict(list)
    for r in attempts:groups[r["system_id"]].append(r)
    systems=sorted(groups);labels=[s.replace("system_","") for s in systems];x=np.arange(len(systems));captions={}
    source=f"Observed standalone records n={len(attempts)}; successful generations n={metrics['observed']['n_successful_generations']}. Monetary estimates assume the selected tariff, not account billing."
    def canvas(title,ylabel,panels=1):
        fig,axes=plt.subplots(1,panels,figsize=(10*panels,6),squeeze=False);fig.suptitle(title);fig.subplots_adjust(bottom=.28,top=.86,wspace=.3)
        for ax in axes.flat:
            ax.set_xlabel("System (separate engineering conditions)");ax.set_ylabel(ylabel);ax.set_xticks(x,labels)
            if not attempts:ax.text(.5,.5,"No observed attempts",ha="center",transform=ax.transAxes)
        return fig,list(axes.flat)
    def save(fig,name,caption):
        fig.text(.06,.06,textwrap.fill(source+" "+caption,110 if fig.get_figwidth()<12 else 170),fontsize=9);fig.savefig(output/(name+".png"),dpi=300);plt.close(fig);captions[name]=caption
    # A. Observed clocks include both success and failure, without equating wait time with labor.
    fig,(ax,)=canvas("Observed attempt durations by system","Recorded seconds / attempt")
    for i,system in enumerate(systems):
        for offset,r in zip(np.linspace(-.2,.2,len(groups[system])),groups[system]):
            if r["duration_seconds"] is not None:ax.scatter(i+offset,r["duration_seconds"],marker="o" if r["status"]=="success" else "x",color="#287a91" if r["status"]=="success" else "#ad4a3b")
    ax.scatter([],[],marker="o",color="#287a91",label="Success");ax.scatter([],[],marker="x",color="#ad4a3b",label="Failed/uncertain");ax.legend()
    save(fig,"08_observed_duration","Individual recorded durations; legacy CSV timing definitions remain identified in the attempt table. No labor substitution or confidence interval.")
    fig,(ax,)=canvas("Recorded model token usage","Tokens (count; known buckets only)")
    bottom=np.zeros(len(systems))
    for field,label in (("prompt_token_count","Input"),("candidates_token_count","Output"),("thoughts_token_count","Thinking")):
        values=[sum((r.get('usage') or {}).get(field,0) or 0 for r in groups[s]) for s in systems]
        ax.bar(x,values,bottom=bottom,label=label);bottom+=values
    for i,s in enumerate(systems):ax.text(i,.98,f"{sum(r.get('usage') is None for r in groups[s])} usage unknown",transform=ax.get_xaxis_transform(),ha='center',va='top',fontsize=8)
    ax.legend();save(fig,"09_observed_tokens","Only recorded token buckets are summed. Unknown failure usage is not assumed zero; input/output/thinking counts are not billed twice.")
    fig,(ax,)=canvas("Provider/execution failure overhead and retry waiting","Recorded elapsed seconds (not engineering labor)")
    for offset,kind,label,color in ((-.25,"success","Successful attempts","#287a91"),(0,"failure","Failed/uncertain attempts","#ad4a3b"),(.25,"wait","Explicit retry waiting","#c38a20")):
        values=[sum(r.get('retry_wait_seconds',0) if kind=='wait' else (r['duration_seconds'] or 0) if (r['status']=='success')==(kind=='success') else 0 for r in groups[s]) for s in systems]
        ax.bar(x+offset,values,width=.25,label=label,color=color)
    ax.legend();save(fig,"10_observed_failure_overhead","Elapsed overhead is measured separately from active labor. Missing API/parse components stay unavailable; no financial value is invented.")
    fig,(ax,)=canvas("Observed requests, recoveries and explicit retries","Requests (count)")
    for offset,key,label in ((-.25,"all","All requests"),(0,"recovery","Recorded recovery requests"),(.25,"retry","Retry number > 0")):
        ax.bar(x+offset,[len(groups[s]) if key=='all' else sum(bool(r.get('is_recovery')) for r in groups[s]) if key=='recovery' else sum(r.get('retry_number',0)>0 for r in groups[s]) for s in systems],width=.25,label=label)
    ax.legend();save(fig,"11_observed_retries","A planned independent pilot/replicate is not relabeled as a retry. Recovery linkage and explicit retry numbers remain different fields.")
    fig,(ax,)=canvas("Invoice evidence and token-based tariff estimates","USD (known amount or explicit tariff assumption)")
    for offset,basis,label in ((-.18,"invoice","Known invoice"),(.18,"estimated_standard_paid_tokens","Assumed paid-tariff token estimate")):
        ax.bar(x+offset,[sum(r['cost_usd'] for r in groups[s] if r['cost_usd'] is not None and r['cost_basis']==basis) for s in systems],width=.35,label=label)
    for i,s in enumerate(systems):ax.text(i,.98,f"{sum(r['cost_basis']!='invoice' for r in groups[s])} actual bills unknown",transform=ax.get_xaxis_transform(),ha='center',va='top',rotation=90,fontsize=8)
    ax.legend(loc="upper center",bbox_to_anchor=(.5,1.12),ncol=2,fontsize=9);ax.margins(y=.12)
    save(fig,"12_observed_api_expense","Tariff-scaled measured tokens are not invoices. Free-tier quota evidence is retained; missing/unknown billing never becomes a free request or complete campaign expense.")
    fig,axes=canvas("Schema-valid generation efficiency","Recorded seconds / valid output",2)
    for i,s in enumerate(systems):
        rows=groups[s];valid=[r for r in rows if r.get('schema_valid') is True and r['status']=='success']
        comparable=[r for r in rows if not r.get('duration_kind','').startswith('legacy')]
        nvalid=sum(r.get('schema_valid') is True and r['status']=='success' for r in comparable)
        if nvalid and all(r['duration_seconds'] is not None for r in comparable):axes[0].bar(i,sum(r['duration_seconds'] for r in comparable)/nvalid,color='#287a91')
        priced=[r['cost_usd'] for r in valid if r['cost_usd'] is not None]
        if priced:axes[1].bar(i,statistics.mean(priced),color='#75629b')
        else:axes[1].text(i,0,"unavailable",rotation=90)
        axes[1].text(i,.98,f"{len(priced)}/{len(valid)} priced",transform=axes[1].get_xaxis_transform(),ha='center',va='top')
    axes[1].set_ylabel("USD / priced valid response (known-usage subset)")
    save(fig,"13_observed_generation_efficiency","Duration includes failed-request overhead and excludes incomparable legacy timing. Monetary subset excludes unknown bills; complete cost per valid generation requires every applicable expense. Not accepted-FMEA cost.")
    # C. Run the existing simulation only when a complete explicit scenario was supplied.
    simulation=metrics.get("simulation",{})
    if simulation.get("status")=="scenario":
        fig,(ax,)=canvas("Illustrative financial scenario - Monte Carlo","Simulation draws (count)")
        ax.set_xlabel("Assumption-driven net savings (USD / FMEA)");ax.hist(simulation['draws'],bins=40,color='#75629b');ax.axvline(0,color='#ad4a3b',linestyle='--')
        save(fig,"14_scenario_monte_carlo","Explicitly configured assumptions only; 95% simulation interval, not an empirical confidence interval or observed project saving.")
    return captions
