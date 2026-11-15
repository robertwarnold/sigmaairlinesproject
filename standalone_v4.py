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
    for line_no, line in enumerate(source.splitlines(), 1):
        cells = [s.strip() for s in line.strip().strip('|').lstrip('- ').split('|')]
        if len(cells) < 3 or not cells[1].isdigit(): continue
        quantity = int(cells[1])
        if not 1 <= quantity <= 10000: raise ValueError('Ambiguous/unsafe quantity; input review required')
        group = f'line-{line_no}'
        for number in range(1, quantity+1):
            units.append({'unit_id': f'{group}-unit-{number}',
                          'name': cells[0] + (f' {number}' if quantity > 1 else ''),
                          'kind': 'component', 'parent_id': None, 'relationships': [],
                          'function': 'Not provided: input review required', 'operating_states': [],
                          'evidence': line.strip(), 'source_line': line_no,
                          'repeat_group': group, 'repeat_index': number, 'repeat_quantity': quantity,
                          'detection_provisions': cells[3] if len(cells)>3 else 'Not provided',
                          'applicable_categories': None})
    if not units: raise ValueError('No explicit quantity table found; prepare inventory JSON from input facts')
    return {'schema': 'input-inventory-4', 'system_id': system_id,
            'system_sha256': hashlib.sha256(Path(system_file).read_bytes()).hexdigest(),
            'review_status': 'unreviewed', 'units': units,
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
        if applicable is not None and (not isinstance(applicable,list) or len(applicable)!=len(set(applicable)) or set(applicable)-set(CATEGORIES)): raise ValueError('Invalid applicability list')
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
    extra=('row_id','unit_id','category','operating_state','existing_detection','assumptions')
    row={**base['items'],'required':base['items']['required']+list(extra),
         'properties':{**base['items']['properties'],**{k:string for k in extra}}}
    case={'type':'OBJECT','required':['unit_id','category','applicable','rationale','row_ids'],
          'properties':{'unit_id':string,'category':{'type':'STRING','enum':list(CATEGORIES)},
                        'applicable':{'type':'BOOLEAN'},'rationale':string,'row_ids':strings}}
    return {'type':'OBJECT','required':['rows','cases','review_flags','complete'],
            'properties':{'rows':{'type':'ARRAY','items':row},'cases':{'type':'ARRAY','items':case},
                          'review_flags':strings,'complete':{'type':'BOOLEAN'}}}


def audit(data, inventory):
    """Audit supplied IDs, independent applicability and content heuristics; no semantic certification."""
    units={u['unit_id']:u for u in check_inventory(inventory)}
    missing=[]; unsupported=[]; suspicious=[]; duplicates=[]; flags=list(inventory.get('review_flags',[]))
    rows=data.get('rows',[]); ids={}; fingerprints={}; considered={}
    for n,row in enumerate(rows,1):
        rid=row.get('row_id'); uid=row.get('unit_id')
        if not isinstance(rid,str) or not rid.strip() or rid in ids: duplicates.append(rid or f'row-{n}')
        ids[rid]=row
        if uid not in units: unsupported.append({'row_id':rid,'reason':'unknown input unit'})
        elif row.get('component')!=units[uid]['name']: unsupported.append({'row_id':rid,'reason':'component name not bound to input unit'})
        category=row.get('category')
        if category not in CATEGORIES: unsupported.append({'row_id':rid,'reason':'unknown failure category'})
        elif uid in units and units[uid].get('applicable_categories') is not None and category not in units[uid]['applicable_categories']:
            unsupported.append({'row_id':rid,'reason':'category excluded by reviewed input inventory'})
        for key in ('operating_state','existing_detection','assumptions'):
            if not isinstance(row.get(key),str) or not row[key].strip(): missing.append({'row_id':rid,'field':key})
        fp=tuple(re.sub(r'\s+',' ',str(row.get(k,'')).strip().casefold()) for k in ('unit_id','failure_mode','cause','local_effect','system_effect','operating_state'))
        if fp in fingerprints: duplicates.append(rid)
        fingerprints[fp]=rid
        mode=str(row.get('failure_mode','')).casefold()
        if len(mode.split())<2 or re.search(r'\b(fails or|failure or|various|all failures)\b',mode): suspicious.append({'row_id':rid,'reason':'generic or combined failure-mode wording'})
        if row.get('cause')==row.get('system_effect'): suspicious.append({'row_id':rid,'reason':'cause equals end effect; review causal chain'})
        if uid in units:
            provisions=units[uid]['detection_provisions']
            if row.get('existing_detection') not in (provisions,'Not provided'):
                suspicious.append({'row_id':rid,'reason':'detection text differs from input; verify no invented provision'})
    for case in data.get('cases',[]):
        key=(case.get('unit_id'),case.get('category'))
        if key in considered: duplicates.append('case:'+str(key))
        considered[key]=case
        links=case.get('row_ids',[])
        if key[0] not in units or key[1] not in CATEGORIES or type(case.get('applicable')) is not bool or not isinstance(links,list) or not isinstance(case.get('rationale'),str) or not case['rationale'].strip():
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
        for category in CATEGORIES:
            if (uid,category) not in considered: missing.append({'unit_id':uid,'category':category,'reason':'case not considered'})
    linked={rid for c in considered.values() for rid in c.get('row_ids',[]) if isinstance(rid,str)}
    for rid in ids:
        if rid not in linked: missing.append({'row_id':rid,'reason':'row not linked to a case'})
    covered={r.get('unit_id') for r in rows}&set(units)
    uncovered=sorted(set(units)-covered)
    for uid in uncovered: missing.append({'unit_id':uid,'reason':'no failure coverage'})
    for uid,unit in units.items():
        if unit.get('applicable_categories') is None: flags.append(f'{uid}: applicability not independently reviewed')
        if not unit['operating_states']: flags.append(f'{uid}: operating states unspecified')
    structural=not (missing or unsupported or duplicates) and data.get('complete') is True
    return {'schema':'coverage-audit-4','structural_status':'PASS' if structural else 'FAIL',
            'engineering_status':'engineering_review_required','identified_unit_count':len(units),
            'units_covered':sorted(covered),'units_without_coverage':uncovered,
            'interfaces_identified':sum(u['kind'] in ('interface','connection') for u in units.values()),
            'candidate_failure_cases_considered':len(considered),'generated_failure_mode_count':len(rows),
            'verified_coverage':{'input_unit_ids_represented':sorted(covered),'basis':'Independent input inventory, not model completeness claim'},
            'suspected_gaps':missing,'unsupported_rows':unsupported,'duplicate_rows':duplicates,
            'suspicious_rows':suspicious,'unresolved_assumptions':flags+data.get('review_flags',[]),
            'remediation':{'missing_unit_ids':uncovered,'missing_cases':missing,
                           'instructions':'Return only corrections for these IDs/cases. Preserve original artifact and bind corrections to its hash. Separate authorization is required for every paid remediation call.'}}


def validate(raw, inventory, parse_rows):
    data=strict_read(raw)
    if not isinstance(data,dict): raise ValueError('V4 response must be an object')
    report=audit(data,inventory)
    if report['structural_status']!='PASS':
        error=ValueError('V4 deterministic coverage audit failed'); error.coverage_report=report; raise error
    try:
        rows=parse_rows(json.dumps(data['rows']))
    except (ValueError, KeyError, TypeError) as exc:
        report['structural_status']='FAIL'
        report['suspected_gaps'].append({'reason':'required FMEA fields or ratings invalid'})
        error=ValueError('V4 required fields/ratings invalid'); error.coverage_report=report; raise error from exc
    report['row_traceability']={r['row_id']:{k:r[k] for k in ('unit_id','category','operating_state','existing_detection','assumptions')} for r in data['rows']}
    return rows,report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--system',required=True); parser.add_argument('--system-id',default='unspecified'); parser.add_argument('--output',required=True)
    parser.add_argument('--inventory'); parser.add_argument('--response')
    args=parser.parse_args()
    if args.response:
        from fmea_generator import parse_fmea
        inventory=load_inventory(args.inventory,args.system)
        try:
            _,result=validate(Path(args.response).read_text(encoding='utf-8'),inventory,parse_fmea)
        except ValueError as exc:
            if not hasattr(exc,'coverage_report'): raise
            result=exc.coverage_report
    else:
        result=extract_inventory(args.system,args.system_id)
    path=Path(args.output); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream: json.dump(result,stream,indent=2)

if __name__=='__main__': main()
