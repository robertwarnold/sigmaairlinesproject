"""Structural audit of model-declared inventory; not an independent engineering judge."""
import json
from collections import Counter

CATEGORIES = ('failure to start/operate', 'failure during operation', 'partial/degraded performance',
              'unintended operation', 'failure to stop', 'failure to connect/engage',
              'failure to disconnect/disengage', 'fail-open', 'fail-closed',
              'loss of transmission/flow', 'seizure/blockage', 'contained failure',
              'propagating/cascading failure')


def response_schema(row_schema):
    string = {'type': 'STRING'}
    strings = {'type': 'ARRAY', 'items': string}
    case = {'type': 'OBJECT', 'required': ['category', 'applicable', 'rationale', 'row_ids'],
            'properties': {'category': {'type': 'STRING', 'enum': list(CATEGORIES)},
                           'applicable': {'type': 'BOOLEAN'}, 'rationale': string, 'row_ids': strings}}
    unit = {'type': 'OBJECT', 'required': ['unit_id', 'name', 'kind', 'evidence', 'relationships', 'cases'],
            'properties': {**{k: string for k in ('unit_id', 'name', 'kind', 'evidence')},
                           'relationships': strings, 'cases': {'type': 'ARRAY', 'items': case}}}
    row = row_schema['items']
    row = {**row, 'required': row['required'] + ['row_id', 'unit_id'],
           'properties': {**row['properties'], 'row_id': string, 'unit_id': string}}
    return {'type': 'OBJECT', 'required': ['inventory', 'rows', 'review_flags', 'complete'],
            'properties': {'inventory': {'type': 'ARRAY', 'items': unit},
                           'rows': {'type': 'ARRAY', 'items': row},
                           'review_flags': strings, 'complete': {'type': 'BOOLEAN'}}}


def validate(raw, parse_rows):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result:
                raise ValueError('Duplicate JSON key')
            result[k] = v
        return result
    data = json.loads(raw, object_pairs_hook=unique)
    if not isinstance(data, dict) or data.get('complete') is not True:
        raise ValueError('Incomplete v3 response; manual continuation requires separate authorization')
    inventory, source = data['inventory'], data['rows']
    if not inventory or not source:
        raise ValueError('Inventory and rows must be nonempty')
    rows = parse_rows(json.dumps(source))
    units, row_ids = {}, {}
    for unit in inventory:
        for field in ('unit_id', 'name', 'kind', 'evidence'):
            if not isinstance(unit.get(field), str) or not unit[field].strip():
                raise ValueError('Invalid inventory field')
        if unit['unit_id'] in units or unit['kind'] not in ('component', 'subassembly', 'connection'):
            raise ValueError('Duplicate unit or invalid kind')
        units[unit['unit_id']] = unit
    duplicates = Counter(tuple(r[k].strip().casefold() for k in ('component', 'failure_mode', 'cause', 'local_effect', 'system_effect')) for r in source)
    if any(n > 1 for n in duplicates.values()):
        raise ValueError('Duplicate FMEA rows')
    for row in source:
        if not isinstance(row.get('row_id'), str) or not row['row_id'].strip() or row['row_id'] in row_ids or row.get('unit_id') not in units:
            raise ValueError('Duplicate row ID or unknown unit')
        row_ids[row['row_id']] = row['unit_id']
    considered = 0
    for uid, unit in units.items():
        if not isinstance(unit['relationships'], list) or any(r not in units for r in unit['relationships']):
            raise ValueError('Unknown relationship')
        cases = unit['cases']
        if Counter(c['category'] for c in cases) != Counter(CATEGORIES):
            raise ValueError('Each failure direction must be considered once')
        linked = set()
        for case in cases:
            if type(case['applicable']) is not bool or not isinstance(case['rationale'], str) or not case['rationale'].strip() or not isinstance(case['row_ids'], list):
                raise ValueError('Invalid candidate case')
            ids = case['row_ids']
            if bool(ids) != case['applicable'] or len(ids) != len(set(ids)) or any(row_ids.get(r) != uid for r in ids):
                raise ValueError('Applicable case requires matching unit rows')
            linked.update(ids)
            considered += 1
        if not linked or linked != {r for r, u in row_ids.items() if u == uid}:
            raise ValueError('Unit without coverage or unlinked rows')
    flags = data['review_flags']
    if not isinstance(flags, list) or any(not isinstance(f, str) or not f.strip() for f in flags):
        raise ValueError('Invalid review flags')
    report = {'identified_unit_count': len(units), 'units_covered': list(units),
              'units_without_coverage': [], 'candidate_failure_cases_considered': considered,
              'generated_failure_mode_count': len(rows), 'duplicate_or_suspicious_rows': [],
              'outstanding_review_flags': flags, 'inventory': inventory,
              'row_unit_links': row_ids, 'status': 'structurally_valid_model_declared_inventory',
              'limitation': 'Package inventory completeness and semantic applicability require human review'}
    return rows, report
