"""Authoritative descriptive analytics for an explicitly selected private record set.

No reference scores, causal categories, residual risk or calibrated confidence inferred.
"""
from collections import Counter, defaultdict
from statistics import mean, median, stdev
from datetime import date
import json
from .store import rating, rpn, missing, digest


def selected_analytics(snapshot, record_ids):
    known={r['record_id'] for r in snapshot['records']}
    if len(record_ids)!=len(set(record_ids)) or set(record_ids)-known:
        raise ValueError('Invalid analytics selection')
    ids=set(record_ids); records=[r for r in snapshot['records'] if r['record_id'] in ids]
    n=len(records); rows=[r['current'] for r in records]
    scores=[rpn(r) for r in rows if rpn(r) is not None]
    reviewed=[r for r in records if r['review_status'] in ('APPROVED','REJECTED')]
    high=[r['record_id'] for r in records if rating(r['current'].get('severity')) and r['current']['severity']>=9]
    uncited=[r['record_id'] for r in records if missing(r['current'].get('evidence'))]
    invalid=[r['record_id'] for r in records if rpn(r['current']) is None]
    structural=[r for r in records if r['validation']['structural_status']=='PASS']
    fingerprints=[(r['run_id'],tuple(' '.join(str(r['original'].get(k,'')).casefold().split()) for k in
        ('unit_id','failure_mode','cause','local_effect','system_effect','operating_state'))) for r in records]
    counts=Counter(fingerprints)
    duplicates=[r['record_id'] for r,k in zip(records,fingerprints) if counts[k]>1]
    def rate(value): return 100*value/n if n else None
    kpis={'total':n,'high_severity':len(high),'average_rpn':mean(scores) if scores else None,
          'valid_rpn_count':len(scores),'cited_evidence_percentage':rate(n-len(uncited)),
          'validation_percentage':rate(len(structural)),'reviewed':len(reviewed)}
    attention=[]
    for name,label,selection in (
        ('high','High-severity records awaiting engineering decision',[r['record_id'] for r in records if r['record_id'] in high and r['review_status']=='NEEDS_REVIEW']),
        ('ratings','Records with missing or invalid ratings',invalid),('evidence','Records without a usable evidence citation',uncited),
        ('duplicates','Rows sharing an original within-run fingerprint',duplicates)):
        if selection: attention.append({'key':name,'label':label,'count':len(selection),'record_ids':selection})
    matrix=Counter(); subs=Counter(); causes=Counter(); evidence=Counter(); actions=Counter(); bins=Counter(); agreement={k:[] for k in ('severity','occurrence','detection')}
    grouped=defaultdict(list)
    for r in records:
        row=r['current']; s=row.get('severity'); o=row.get('occurrence'); score=rpn(row)
        if rating(s) and rating(o): matrix[(s,o)]+=1
        band='High (9-10)' if rating(s) and s>=9 else 'Other valid (1-8)' if rating(s) else 'Unrated'
        subs[((r['unit'] or {}).get('parent_id') or 'Not provided',band)]+=1
        # Explicit original/corrected cause category only; failure category is not cause taxonomy.
        causes[row.get('cause_category') if isinstance(row.get('cause_category'),str) and row['cause_category'].strip() else 'Not categorized']+=1
        ev='Human-verified citation' if r['review_status']=='APPROVED' and r['review_basis']=='source_verified' else 'Human-approved inference' if r['review_status']=='APPROVED' else 'Missing citation' if missing(row.get('evidence')) else 'Pending verification'
        evidence[ev]+=1
        if score is not None: bins[(score-1)//100]+=1
        if row.get('action_status'):
            status=row['action_status']
            try:
                if status!='COMPLETE' and row.get('action_due_date') and date.fromisoformat(row['action_due_date'])<date.today(): status='OVERDUE'
            except (ValueError,TypeError): status='INVALID_ACTION_DATA'
            actions[status]+=1
        for k in agreement:
            # Only explicit, decided human corrections provide independent reviewed ratings.
            if r['review_status'] in ('APPROVED','REJECTED') and any(k in json.loads(e['corrections']) for e in r['history']) and rating(row.get(k)) and rating(r['original'].get(k)):
                agreement[k].append(abs(row[k]-r['original'][k]))
        grouped[r['run_id']].append(r)
    runs=[]
    for key,group in sorted(grouped.items()):
        meta=group[0]['metadata']; total=len(group)
        fps=[k for r,k in zip(records,fingerprints) if r['run_id']==key]
        decided=sum(r['review_status'] in ('APPROVED','REJECTED') for r in group)
        approved=sum(r['review_status']=='APPROVED' for r in group)
        runs.append({**meta,'selected_rows':total,'validation_percentage':100*sum(r['validation']['structural_status']=='PASS' for r in group)/total,
          'approved_rows':approved,'reviewed_rows':decided,'acceptance_percentage':100*approved/decided if decided else None,
          'duplicate_percentage':100*(len(fps)-len(set(fps)))/total,
          'validation_failure_percentage':100*sum(r['validation']['structural_status']!='PASS' for r in group)/total,
          'comparison_key':digest({k:meta[k] for k in ('workflow','dataset_id','dataset_version','scoring_policy')})})
    timings=[r['generation_seconds'] for r in runs if r.get('generation_status')=='success' and isinstance(r.get('generation_seconds'),(int,float)) and not isinstance(r['generation_seconds'],bool) and r['generation_seconds']>=0]
    priorities=[{'record_id':r['record_id'],'run_id':r['run_id'],'label':r['metadata']['system']+' / '+str(r['current'].get('component',''))+' / '+str(r['current'].get('failure_mode','')),
                 'severity':r['current'].get('severity') if rating(r['current'].get('severity')) else None,'RPN':rpn(r['current'])} for r in records]
    subsystem_totals=Counter()
    for (subsystem,band),count in subs.items(): subsystem_totals[subsystem]+=count
    subsystem_scale=max(subsystem_totals.values(),default=1)
    return {'schema':'engineering-analytics-1','private':True,'selection_count':n,'kpis':kpis,'attention':attention,
      'matrix':[{'severity':s,'occurrence':o,'count':c} for (s,o),c in sorted(matrix.items())],
      'subsystems':[{'subsystem':s,'severity_band':b,'count':c,'width_percentage':100*c/subsystem_scale} for (s,b),c in sorted(subs.items())],
      'cause_categories':[{'category':k,'count':c} for k,c in causes.most_common()],
      'evidence':[{'status':k,'count':c,'percentage':rate(c)} for k,c in evidence.items()],
      'actions':[{'status':k,'count':c} for k,c in sorted(actions.items())],
      'rpn_bins':[{'lower':100*k+1,'upper':100*(k+1),'count':bins[k]} for k in range(10)],
      'priorities':priorities,'runs':runs,
      'agreement':[{'rating':k,'n':len(v),'within_one_percentage':100*sum(d<=1 for d in v)/len(v) if len(v)>=2 else None} for k,v in agreement.items()],
      'timing_summary':{'n':len(timings),'mean':mean(timings) if timings else None,'median':median(timings) if timings else None,'sd':stdev(timings) if len(timings)>1 else None},
      'limitations':'Citation presence is not verified support. Human review is self-asserted. Counts are rows within selected runs; independent replicas are not merged. No inferred cause classification or judge scores.'}


def operational_activity(rows):
    """Filtered sanitized generation receipts; retries with the same ID count once."""
    unique={}
    for r in rows:
        key=r.get('generation_id') or r.get('run_id')
        if not isinstance(key,str) or not key: raise ValueError('Generation identity missing')
        if key in unique and unique[key]!=r: raise ValueError('Conflicting generation identity')
        unique[key]=r
    counts=Counter((str(r.get('generation_timestamp') or '')[:10],r.get('generation_status') or 'unknown') for r in unique.values())
    return {'generation_activity':[{'date':day or 'Undated','generation_status':status,'count':count} for (day,status),count in sorted(counts.items())],
            'awaiting_judge':sum(r.get('generation_status')=='success' and r.get('evaluation_status')!='evaluated' for r in unique.values()),'registered_generations':len(unique)}
