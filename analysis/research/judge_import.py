"""Adapters to the existing identifier-only judge schema, not a new judge rubric."""
import csv
import json
from pathlib import Path
from analysis.round2.__main__ import read, private, QUALITY

ITEM_FIELDS={'item_id','found','matched_row_id','miss_category','review_status','judge_notes',*QUALITY}
JSON_FIELDS={'settings','usage','token_usage'}
BOOL_FIELDS={'found','cause_correct','end_effect_correct'}
INT_FIELDS={'generated_rows','extra_unmatched_rows','severity_difference','occurrence_difference','detection_difference'}


def cell(key,value):
    if value is None or value=='': return None
    if not isinstance(value,str): return value
    if key in JSON_FIELDS: return json.loads(value)
    if key in BOOL_FIELDS:
        if value.lower() not in ('true','false'): raise ValueError('Expected boolean '+key)
        return value.lower()=='true'
    if key in INT_FIELDS: return int(value)
    if key=='rpn_relative_difference': return float(value)
    return value


def csv_rows(path):
    with private(path).open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream,strict=True)
        if not reader.fieldnames or len(reader.fieldnames)!=len(set(reader.fieldnames)): raise ValueError('Missing or duplicate CSV headers')
        rows=list(reader)
    if any(None in row or None in row.values() for row in rows): raise ValueError('Malformed CSV row width')
    return rows


def adapt(source,items_source=None):
    """Accept existing JSON, paired run/item CSVs, or the validated research workbook.

    No source FMECA workbook format is accepted or inspected. Workbook support is
    explicitly limited to the repository's runs/items analysis export.
    """
    source=private(source)
    if source.suffix.lower()=='.json': return read(source)
    if source.suffix.lower()=='.csv':
        if not items_source: raise ValueError('CSV requires --items with item-level opportunities')
        runs=csv_rows(source); items=csv_rows(items_source)
    elif source.suffix.lower()=='.xlsx':
        import pandas as pd
        with pd.ExcelFile(source) as workbook:
            if not {'runs','items'}<=set(workbook.sheet_names): raise ValueError('Only validated research runs/items workbooks supported')
            runs=pd.read_excel(workbook,'runs',keep_default_na=False).to_dict('records')
            items=pd.read_excel(workbook,'items',keep_default_na=False).to_dict('records')
    else: raise ValueError('Supported formats: JSON, paired CSV, validated analysis XLSX')
    output=[]
    for row in runs:
        run={k:cell(k,v) for k,v in row.items() if v is not None and v!=''}
        if not run.get('run_id'): raise ValueError('Missing FMEA run ID')
        run['items']=[{k:cell(k,v) for k,v in item.items() if k in ITEM_FIELDS} for item in items if item.get('run_id')==run['run_id']]
        output.append(run)
    unknown={i.get('run_id') for i in items}-{r['run_id'] for r in output}
    if unknown: raise ValueError('Item records have no matching run metadata')
    return {'schema':'standalone-judge-import-1','workflow':'standalone_gemini','runs':output}
