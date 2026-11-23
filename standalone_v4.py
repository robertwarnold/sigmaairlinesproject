"""Independent input inventory and deterministic V4 coverage verification.

The inventory contains input facts, never reference failure modes. Applicability can
be explicitly reviewed; unknown applicability remains a visible review requirement.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

CATEGORIES = ('failure to start', 'failure during operation', 'failure to stop',
              'partial performance', 'degraded performance', 'unintended operation',
              'fail-open', 'fail-closed', 'electrical open circuit', 'electrical short circuit',
              'loss of signal', 'incorrect signal', 'intermittent operation', 'blockage',
              'leakage', 'seizure', 'interface failure', 'propagating failure')
KINDS = ('system', 'subsystem', 'assembly', 'component', 'interface', 'connection')
RESPONSE_VERSION = 'standalone-fmea-v4.0-response-2'
DIAGNOSTICS_VERSION = 'standalone-fmea-v4.0-diagnostics-1'
SCORING_PROFILE = 'standalone-1-to-10-v1'
RELEASE_CATEGORIES = CATEGORIES + ('incorrect timing', 'incorrect sequence', 'incorrect direction',
                                   'failure to maintain state', 'common-cause or dependent failure')
RELEASE_FIELDS = ('higher_level_effect', 'existing_prevention', 'severity_rationale')


def strict_read(raw):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result: raise ValueError('Duplicate JSON key')
            result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def extract_inventory(system_file, system_id):
    """Expand explicit pipe-table quantities without inferring narrative quantities.

    For any other input format, supply the same JSON contract manually. Connections,
    operating states and functions need explicit human input review, never a guessed
    engineering answer. No hidden benchmark is accessed.
    """
    source = Path(system_file).read_text(encoding='utf-8')
    units = []
    sections=[]
    for line_no, line in enumerate(source.splitlines(), 1):
        heading=re.match(r'^\s*\d+\.\s+([A-Z][A-Z0-9 :/-]+)\s*$',line)
        if heading:
            sections.append({'title':heading[1].strip(),'source_line':line_no})
        cells = [s.strip() for s in line.strip().strip('|').lstrip('- ').split('|')]
        if len(cells) < 3 or not cells[1].isdigit(): continue
        quantity = int(cells[1])
        if not 1 <= quantity <= 10000: raise ValueError('Ambiguous/unsafe quantity; input review required')
        group = f'line-{line_no}'
        kind='interface' if re.search(r'\b(interface|connector|terminal|harness)\b',cells[0],re.I) else 'component'
        for number in range(1, quantity+1):
            units.append({'unit_id': f'{group}-unit-{number}',
                          'name': cells[0] + (f' {number}' if quantity > 1 else ''),
                          'kind': kind, 'parent_id': None, 'relationships': [],
                          'function': 'Not provided: input review required', 'operating_states': [],
                          'evidence': line.strip(), 'source_line': line_no,
                          'repeat_group': group, 'repeat_index': number, 'repeat_quantity': quantity,
                          'detection_provisions': cells[3] if len(cells)>3 else 'Not provided',
                          'applicable_categories': None})
    if not units: raise ValueError('No explicit quantity table found; prepare inventory JSON from input facts')
    return {'schema': 'input-inventory-4', 'system_id': system_id,
            'system_sha256': hashlib.sha256(Path(system_file).read_bytes()).hexdigest(),
            'review_status': 'unreviewed', 'units': units,'source_sections':sections,
            'review_flags': ['Narrative interfaces, hierarchy, functions and operating states require human reconciliation.',
                             'Failure applicability has not been independently reviewed.']}


def load_inventory(path, system_file):
    if not path: raise ValueError('V4 requires --inventory independently prepared from input facts')
    inventory = strict_read(Path(path).read_text(encoding='utf-8'))
    if inventory.get('schema') != 'input-inventory-4': raise ValueError('Unsupported inventory schema')
    if inventory.get('system_sha256') != hashlib.sha256(Path(system_file).read_bytes()).hexdigest():
        raise ValueError('Inventory does not match input package hash')
    check_inventory(inventory)
    return inventory


def check_inventory(inventory):
    units = inventory['units']; ids = set(); groups = {}
    if not isinstance(units, list) or not units: raise ValueError('Empty inventory')
    for unit in units:
        for key in ('unit_id','name','function','evidence','detection_provisions'):
            if not isinstance(unit.get(key),str) or not unit[key].strip(): raise ValueError('Missing inventory '+key)
        uid=unit['unit_id']
        if uid in ids or unit['kind'] not in KINDS: raise ValueError('Duplicate unit or invalid kind')
        ids.add(uid)
        if not isinstance(unit['relationships'],list) or not isinstance(unit['operating_states'],list): raise ValueError('Invalid inventory links/states')
        applicable = unit.get('applicable_categories')
        if applicable is not None and (not isinstance(applicable,list) or len(applicable)!=len(set(applicable)) or set(applicable)-set(RELEASE_CATEGORIES)): raise ValueError('Invalid applicability list')
        quantity=unit.get('repeat_quantity',1); index=unit.get('repeat_index',1)
        if type(quantity) is not int or type(index) is not int or not 1<=index<=quantity: raise ValueError('Invalid repeated-unit count')
        group=unit.get('repeat_group',uid)
        groups.setdefault(group,[]).append((index,quantity))
    for entries in groups.values():
        quantity=entries[0][1]
        if any(q!=quantity for _,q in entries) or sorted(i for i,_ in entries)!=list(range(1,quantity+1)):
            raise ValueError('Repeated inventory units omitted or duplicated')
    for unit in units:
        if unit.get('parent_id') is not None and unit['parent_id'] not in ids: raise ValueError('Unknown parent')
        if any(i not in ids for i in unit['relationships']): raise ValueError('Unknown relationship')
        trail=set(); current=unit
        while current.get('parent_id'):
            if current['unit_id'] in trail: raise ValueError('Cyclic hierarchy')
            trail.add(current['unit_id']); current=next(u for u in units if u['unit_id']==current['parent_id'])
    return units


def response_schema(base):
    string={'type':'STRING'}; strings={'type':'ARRAY','items':string}
    extra=('row_id','unit_id','category','operating_state','existing_detection','assumptions',*RELEASE_FIELDS)
    properties={**base['items']['properties'],**{k:string for k in extra}}
    for field in ('severity','occurrence','detection'):
        properties[field]={**properties[field],'nullable':True}
    row={**base['items'],'required':base['items']['required']+list(extra),
         'properties':properties}
    case={'type':'OBJECT','required':['unit_id','category','applicable','rationale','row_ids'],
          'properties':{'unit_id':string,'category':{'type':'STRING','enum':list(RELEASE_CATEGORIES)},
                        'applicable':{'type':'BOOLEAN'},'rationale':string,'row_ids':strings}}
    return {'type':'OBJECT','required':['schema_version','rows','cases','review_flags','complete'],
            'properties':{'schema_version':{'type':'STRING','enum':[RESPONSE_VERSION]},
                          'rows':{'type':'ARRAY','items':row},'cases':{'type':'ARRAY','items':case},
                          'review_flags':strings,'complete':{'type':'BOOLEAN'}}}


def audit(data, inventory):
    """Audit supplied IDs, independent applicability and content heuristics; no semantic certification."""
    units={u['unit_id']:u for u in check_inventory(inventory)}
    release=data.get('schema_version')==RESPONSE_VERSION
    categories=RELEASE_CATEGORIES if release else CATEGORIES
    missing=[]; unsupported=[]; suspicious=[]; duplicates=[]; flags=list(inventory.get('review_flags',[]))
    duplicate_pairs=[]; rating_findings=[]
    rows=data.get('rows',[]); ids={}; fingerprints={}; considered={}
    cases=data.get('cases',[])
    if any(not isinstance(items,list) or any(not isinstance(item,dict) for item in items) for items in (rows,cases)):
        raise ValueError('V4 rows and cases must be object arrays')
    for n,row in enumerate(rows,1):
        rid=row.get('row_id'); uid=row.get('unit_id')
        if not isinstance(rid,str) or not rid.strip() or rid in ids: duplicates.append(rid or f'row-{n}')
        ids[rid]=row
        if uid not in units: unsupported.append({'row_id':rid,'reason':'unknown input unit'})
        elif row.get('component')!=units[uid]['name']: unsupported.append({'row_id':rid,'reason':'component name not bound to input unit'})
        category=row.get('category')
        if category not in categories: unsupported.append({'row_id':rid,'reason':'unknown failure category'})
        elif uid in units and units[uid].get('applicable_categories') is not None and category not in units[uid]['applicable_categories']:
            unsupported.append({'row_id':rid,'reason':'category excluded by reviewed input inventory'})
        for key in ('operating_state','existing_detection','assumptions',*(RELEASE_FIELDS if release else ())):
            if not isinstance(row.get(key),str) or not row[key].strip(): missing.append({'row_id':rid,'field':key})
        fields=('unit_id','failure_mode','cause','local_effect','system_effect','operating_state')
        if release: fields+=('function','higher_level_effect')
        fp=tuple(re.sub(r'\s+',' ',str(row.get(k,'')).strip().casefold()) for k in fields)
        if fp in fingerprints:
            duplicates.append(rid)
            duplicate_pairs.append({'row_id':rid,'first_row_id':fingerprints[fp]})
        else:
            fingerprints[fp]=rid
        for field in ('severity','occurrence','detection'):
            value=row.get(field)
            if type(value) is not int or not 1<=value<=10:
                reason='unrated; obtain engineering basis' if release and value is None else 'expected integer from 1 to 10'
                rating_findings.append({'row_id':rid,'field':field,'reason':reason})
        mode=str(row.get('failure_mode','')).casefold()
        if len(mode.split())<2 or re.search(r'\b(fails or|failure or|various|all failures)\b',mode): suspicious.append({'row_id':rid,'reason':'generic or combined failure-mode wording'})
        if row.get('cause')==row.get('system_effect'): suspicious.append({'row_id':rid,'reason':'cause equals end effect; review causal chain'})
        if uid in units:
            unit=units[uid]
            provisions=unit['detection_provisions']
            if row.get('existing_detection') not in (provisions,'Not provided'):
                suspicious.append({'row_id':rid,'reason':'detection text differs from input; verify no invented provision'})
            if release:
                states=unit['operating_states']
                if row.get('operating_state')!='Not provided' and row.get('operating_state') not in states:
                    suspicious.append({'row_id':rid,'reason':'operating state is not established by inventory'})
                if row.get('existing_prevention') not in ('Not provided',unit.get('prevention_provisions')):
                    suspicious.append({'row_id':rid,'reason':'prevention is not established by inventory'})
                if row.get('severity') is not None and str(row.get('severity_rationale','')).strip().casefold() in ('','not provided','none'):
                    missing.append({'row_id':rid,'unit_id':uid,'field':'severity_rationale'})
                for effect in ('local_effect','higher_level_effect','system_effect'):
                    if str(row.get(effect,'')).strip().casefold() in ('','not provided','unknown'):
                        suspicious.append({'row_id':rid,'reason':f'{effect} requires propagation evidence'})
    for case in cases:
        key=(case.get('unit_id'),case.get('category'))
        if key in considered: duplicates.append('case:'+str(key))
        considered[key]=case
        links=case.get('row_ids',[])
        if key[0] not in units or key[1] not in categories or type(case.get('applicable')) is not bool or not isinstance(links,list) or not isinstance(case.get('rationale'),str) or not case['rationale'].strip():
            missing.append({'case':str(key),'reason':'invalid case decision'}); continue
        if bool(links)!=case['applicable'] or len(links)!=len(set(links)):
            missing.append({'case':str(key),'reason':'applicability/row links inconsistent'})
        for rid in links:
            if rid not in ids or (ids[rid].get('unit_id'),ids[rid].get('category'))!=key:
                missing.append({'case':str(key),'row_id':rid,'reason':'invalid case link'})
        independently_applicable=units[key[0]].get('applicable_categories')
        if independently_applicable is not None and case['applicable']!=(key[1] in independently_applicable):
            missing.append({'unit_id':key[0],'category':key[1],'reason':'independent applicability mismatch'})
    for uid in units:
        for category in categories:
            if (uid,category) not in considered: missing.append({'unit_id':uid,'category':category,'reason':'case not considered'})
    linked={rid for c in considered.values() for rid in c.get('row_ids',[]) if isinstance(rid,str)}
    for rid in ids:
        if rid not in linked: missing.append({'row_id':rid,'reason':'row not linked to a case'})
    covered={r.get('unit_id') for r in rows}&set(units)
    explicitly_inapplicable={uid for uid,unit in units.items() if unit.get('applicable_categories')==[]}
    uncovered=sorted(set(units)-covered-(explicitly_inapplicable if release else set()))
    for uid in uncovered: missing.append({'unit_id':uid,'reason':'no failure coverage'})
    for uid,unit in units.items():
        if unit.get('applicable_categories') is None: flags.append(f'{uid}: applicability not independently reviewed')
        if not unit['operating_states']: flags.append(f'{uid}: operating states unspecified')
    structural=not (missing or unsupported or duplicates) and data.get('complete') is True
    report={'schema':'coverage-audit-4','structural_status':'PASS' if structural else 'FAIL',
            'engineering_status':'engineering_review_required','identified_unit_count':len(units),
            'units_covered':sorted(covered),'units_without_coverage':uncovered,
            'interfaces_identified':sum(u['kind'] in ('interface','connection') for u in units.values()),
            'units_considered':sorted({uid for uid,_ in considered if uid in units}),
            'interfaces_considered':sorted({uid for uid,_ in considered if uid in units and units[uid]['kind'] in ('interface','connection')}),
            'candidate_failure_cases_considered':len(considered),'generated_failure_mode_count':len(rows),
            'verified_coverage':{'input_unit_ids_represented':sorted(covered),'basis':'Independent input inventory, not model completeness claim'},
            'suspected_gaps':missing,'unsupported_rows':unsupported,'duplicate_rows':duplicates,
            'duplicate_pairs':duplicate_pairs,'rating_findings':rating_findings,
            'suspicious_rows':suspicious,'unresolved_assumptions':flags+data.get('review_flags',[]),
            'remediation':{'missing_unit_ids':uncovered,'missing_cases':missing,
                           'instructions':'Return only corrections for these IDs/cases. Preserve original artifact and bind corrections to its hash. Separate authorization is required for every paid remediation call.'}}
    if release:
        report['diagnostics']=release_diagnostics(data,units,report,explicitly_inapplicable)
    return report


def release_diagnostics(data, units, report, inapplicable):
    """Describe one bounded review pass without removing or silently rewriting rows."""
    checks=candidate_diagnostics(data,{'units':list(units.values())},report)
    indexed={uid:[] for uid in units}
    for row in data['rows']:
        if row.get('unit_id') in indexed:
            indexed[row['unit_id']].append(row.get('row_id'))
    affected={gap.get('unit_id') for gap in report['suspected_gaps']}
    by_unit=[]
    for uid, unit in units.items():
        ids=indexed[uid]
        status=('not_applicable' if uid in inapplicable and not ids else
                'potentially_incomplete' if uid in affected else
                'covered' if ids else 'insufficient_information')
        by_unit.append({'unit_id':uid,'kind':unit['kind'],'row_ids':ids,'status':status,
                        'evidence':unit['evidence'],'assumptions':[] if unit['operating_states'] else ['Operating states unspecified'],
                        'review_action':'Review case applicability and architecture evidence' if status!='covered' else 'Verify proposed effects and controls'})
    suspicious={item.get('row_id') for item in report['suspicious_rows']}
    flagged={item.get('row_id') for item in report['unsupported_rows']}
    duplicates={row_id for group in checks['potential_overlaps'] for row_id in group}
    duplicates.update(report['duplicate_rows'])
    invalid={item.get('row_id') for item in report['rating_findings'] if item['reason'].startswith('expected')}
    incomplete={item.get('row_id') for item in report['suspected_gaps']}
    decisions=[]
    for row in data['rows']:
        rid=row.get('row_id')
        fingerprint=tuple(' '.join(str(row.get(key,'')).casefold().split()) for key in
                          ('unit_id','function','failure_mode','operating_state','system_effect'))
        status=('rejected_by_validation' if rid in flagged or rid in invalid else
                'potential_duplicate' if rid in duplicates else 'incomplete' if rid in incomplete else
                'engineering_hypothesis')
        decisions.append({'row_id':rid,'fingerprint':hashlib.sha256(json.dumps(fingerprint).encode()).hexdigest(),
                          'classification':status,'review_evidence':rid in suspicious})
    summary={'inventory_elements':len(units),'instances_covered':len(report['units_covered']),
             'components_covered':sum(item['kind']=='component' and item['status']=='covered' for item in by_unit),
             'components_identified':sum(unit['kind']=='component' for unit in units.values()),
             'interfaces_covered':sum(item['kind'] in ('interface','connection') and item['status']=='covered' for item in by_unit),
             'interfaces_identified':report['interfaces_identified'],
             'candidate_rows':len(decisions),'potential_duplicates':len(duplicates),
             'unsupported_flags':len(report['unsupported_rows'])+sum('inventory' in item['reason'] for item in report['suspicious_rows']),
             'completeness_warnings':len(report['suspected_gaps']),
             'severity_review_flags':len(checks['high_severity_review'])+sum(item['field']=='severity' for item in report['rating_findings'])}
    return {'schema':DIAGNOSTICS_VERSION,'response_schema':RESPONSE_VERSION,'review_passes':1,
            'disposition':'candidates_retained','inventory':by_unit,'rows':decisions,
            'review_checks':checks,'summary':summary}


def validate(raw, inventory, parse_rows, require_release=False):
    data=strict_read(raw)
    if not isinstance(data,dict): raise ValueError('V4 response must be an object')
    if require_release and data.get('schema_version')!=RESPONSE_VERSION:
        raise ValueError('Official V4.0 response schema identifier required')
    report=audit(data,inventory)
    if report['structural_status']!='PASS':
        error=ValueError('V4 deterministic coverage audit failed'); error.coverage_report=report; raise error
    try:
        if data.get('schema_version')==RESPONSE_VERSION:
            rows=parse_rows(json.dumps(data['rows']),allow_unrated=True)
            rows=[{**converted,**{key:original[key] for key in ('row_id','unit_id','operating_state','existing_detection','assumptions',*RELEASE_FIELDS)},
                   'scoring_profile':SCORING_PROFILE,'review_status':'engineering_review_required'}
                  for converted,original in zip(rows,data['rows'],strict=True)]
        else:
            rows=parse_rows(json.dumps(data['rows']))
    except (ValueError, KeyError, TypeError) as exc:
        report['structural_status']='FAIL'
        report['suspected_gaps'].append({'reason':'required FMEA fields or ratings invalid'})
        error=ValueError('V4 required fields/ratings invalid'); error.coverage_report=report; raise error from exc
    report['row_traceability']={r['row_id']:{k:r[k] for k in ('unit_id','category','operating_state','existing_detection','assumptions')} for r in data['rows']}
    return rows,report


def candidate_diagnostics(data, inventory, report):
    """Optional V4-C1 review findings. The active V4 prompt and pass criteria are unchanged."""
    repeated_units = {}
    for unit in check_inventory(inventory):
        signature = (unit.get('parent_id'), unit['kind'], unit.get('function'))
        if signature[2]:
            repeated_units.setdefault(signature, []).append(unit['unit_id'])
    covered = set(report.get('units_covered', []))
    repeated_gaps = [sorted(set(group)-covered) for group in repeated_units.values()
                     if len(group)>1 and set(group)-covered]
    overlapping = {}
    severity_review = []
    separation = []
    for row in data.get('rows', []):
        row_id = row.get('row_id')
        clauses = [' '.join(str(row.get(key, '')).casefold().split())
                   for key in ('cause','failure_mode','local_effect','system_effect')]
        if clauses[0] and clauses[0] in clauses[1:]:
            separation.append(row_id)
        key = (row.get('unit_id'), row.get('operating_state'), clauses[1], clauses[3])
        if clauses[1] and clauses[3]:
            overlapping.setdefault(key, []).append(row_id)
        severity = row.get('severity')
        if type(severity) is int and severity>=9:
            severity_review.append({'row_id':row_id,'severity':severity,
                'checks':['system end effect','propagation','redundancy','containment','severity rubric'],
                'assumptions':row.get('assumptions')})
    return {'schema':'v4-c1-review-1','repeated_unit_coverage_gaps':repeated_gaps,
            'potential_overlaps':[group for group in overlapping.values() if len(group)>1],
            'causal_separation_review':separation,'high_severity_review':severity_review}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--system',required=True); parser.add_argument('--system-id',default='unspecified'); parser.add_argument('--output',required=True)
    parser.add_argument('--inventory'); parser.add_argument('--response')
    parser.add_argument('--candidate-review',action='store_true')
    args=parser.parse_args()
    if args.candidate_review and not args.response:
        parser.error('--candidate-review requires an existing --response')
    if args.response:
        from fmea_generator import parse_fmea
        inventory=load_inventory(args.inventory,args.system)
        raw=Path(args.response).read_text(encoding='utf-8')
        try:
            _,result=validate(raw,inventory,parse_fmea)
        except ValueError as exc:
            if not hasattr(exc,'coverage_report'): raise
            result=exc.coverage_report
        if args.candidate_review:
            result['candidate_review']=candidate_diagnostics(strict_read(raw),inventory,result)
    else:
        result=extract_inventory(args.system,args.system_id)
    path=Path(args.output); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8',newline='\n') as stream: json.dump(result,stream,indent=2)

if __name__=='__main__': main()
