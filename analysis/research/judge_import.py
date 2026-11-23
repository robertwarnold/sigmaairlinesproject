"""Adapters to the existing identifier-only judge schema, not a new judge rubric."""
import csv
import json
import tempfile
from pathlib import Path
import zipfile
from analysis.round2.__main__ import read, private, QUALITY

ITEM_FIELDS={'item_id','found','matched_row_id','miss_category','review_status','judge_notes',*QUALITY}
JSON_FIELDS={'settings','usage','token_usage'}
BOOL_FIELDS={'found','cause_correct','end_effect_correct'}
INT_FIELDS={'generated_rows','extra_unmatched_rows','severity_difference','occurrence_difference','detection_difference'}
MAX_BYTES = 20_000_000
MAX_EXPANDED_BYTES = 80_000_000


def bounded(path):
    source = private(path)
    if source.stat().st_size > MAX_BYTES:
        raise ValueError('Judge result exceeds 20 MB')
    return source


def check_archive(archive):
    entries = archive.infolist()
    if (len(entries) > 2048 or sum(entry.file_size for entry in entries) > MAX_EXPANDED_BYTES
            or len({entry.filename for entry in entries}) != len(entries)
            or any(entry.flag_bits & 1 for entry in entries)):
        raise ValueError('Archive exceeds expansion limits or has duplicate or encrypted members')


def adapt_zip(source):
    with zipfile.ZipFile(source) as archive:
        check_archive(archive)
        members = {entry.filename for entry in archive.infolist() if not entry.is_dir()}
        singles = {'judge.json', 'judge.xlsx'}
        if members == {'runs.csv', 'items.csv'}:
            primary, items = 'runs.csv', 'items.csv'
        elif len(members) == 1 and members <= singles:
            primary, items = next(iter(members)), None
        else:
            raise ValueError('ZIP must contain judge.json, judge.xlsx, or runs.csv and items.csv at its root')
        with tempfile.TemporaryDirectory(dir=source.parent) as temp:
            for name in members:
                with archive.open(name) as stream:
                    payload = stream.read(MAX_BYTES + 1)
                if len(payload) > MAX_BYTES:
                    raise ValueError('Judge result exceeds 20 MB')
                (Path(temp) / name).write_bytes(payload)
            return adapt(Path(temp) / primary, Path(temp) / items if items else None)


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
    with bounded(path).open(encoding='utf-8-sig',newline='') as stream:
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
    source=bounded(source)
    suffix=source.suffix.lower()
    if items_source and suffix != '.csv':
        raise ValueError('A separate items file requires CSV')
    if suffix=='.json': return read(source)
    if suffix=='.zip': return adapt_zip(source)
    if source.suffix.lower()=='.csv':
        if not items_source: raise ValueError('CSV requires --items with item-level opportunities')
        runs=csv_rows(source); items=csv_rows(items_source)
    elif source.suffix.lower()=='.xlsx':
        with zipfile.ZipFile(source) as archive:
            check_archive(archive)
        import pandas as pd
        with pd.ExcelFile(source) as workbook:
            if not {'runs','items'}<=set(workbook.sheet_names): raise ValueError('Only validated research runs/items workbooks supported')
            runs=pd.read_excel(workbook,'runs',keep_default_na=False).to_dict('records')
            items=pd.read_excel(workbook,'items',keep_default_na=False).to_dict('records')
    else: raise ValueError('Supported formats: JSON, paired CSV, validated analysis XLSX, ZIP')
    def trial_key(row):
        return row.get('run_id'), row.get('evaluation_id') or None

    trials_by_run = {}
    for row in runs:
        run_id, evaluation_id = trial_key(row)
        trials_by_run.setdefault(run_id, []).append(evaluation_id)
    rows_by_trial = {}
    for item in items:
        run_id, evaluation_id = trial_key(item)
        available = trials_by_run.get(run_id, [])
        if evaluation_id is None and len(available) == 1:
            evaluation_id = available[0]
        rows_by_trial.setdefault((run_id, evaluation_id), []).append(
            {key: cell(key,value) for key,value in item.items() if key in ITEM_FIELDS})
    output=[]
    known=set()
    for row in runs:
        run={k:cell(k,v) for k,v in row.items() if v is not None and v!=''}
        if not run.get('run_id'): raise ValueError('Missing FMEA run ID')
        key=trial_key(row)
        if key in known: raise ValueError('Multiple trials require distinct evaluation IDs in both tables')
        known.add(key)
        run['items']=rows_by_trial.get(key,[])
        output.append(run)
    if rows_by_trial.keys()-known: raise ValueError('Item records have no matching run and evaluation metadata')
    return {'schema':'standalone-judge-import-1','workflow':'standalone_gemini','runs':output}
