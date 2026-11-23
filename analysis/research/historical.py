"""Run-level historical comparisons from the human-prepared aggregate CSV."""

import csv
import hashlib
import io
import math
import statistics
import zipfile


MEMBER = 'Aggregated Results/Round 2/runs_both.csv'
FIELDS = ['version', 'system', 'rep', 'gt_items', 'missed', 'missed_pct', 'extra_rows', 'gen_rows']
MAX_CSV_BYTES = 1_000_000
MAX_ZIP_BYTES = 20_000_000


def load_comparison(path):
    """Read the comparison member only, without opening any worksheet."""
    content = comparison_content(path)
    return parse_comparison(content)


def comparison_content(path):
    if path.suffix.lower() == '.zip':
        if path.stat().st_size > MAX_ZIP_BYTES:
            raise ValueError('Historical archive exceeds size limit')
        with zipfile.ZipFile(path) as archive:
            entries = [entry for entry in archive.infolist() if entry.filename == MEMBER]
            if len(entries) != 1 or entries[0].file_size > MAX_CSV_BYTES:
                raise ValueError('Expected one bounded historical comparison CSV')
            with archive.open(entries[0]) as stream:
                content = stream.read(MAX_CSV_BYTES + 1)
    else:
        if path.suffix.lower() != '.csv':
            raise ValueError('Expected historical comparison CSV or archive')
        with path.open('rb') as stream:
            content = stream.read(MAX_CSV_BYTES + 1)
    return content


def import_comparison(path, output):
    from .__main__ import atomic_json
    from analysis.round2.__main__ import private

    content = comparison_content(path)
    rows = parse_comparison(content)
    sha = hashlib.sha256(content).hexdigest()
    output = private(output)
    raw = output.parent / 'private' / 'historical-raw' / (sha + '.csv')
    raw.parent.mkdir(parents=True, exist_ok=True)
    try:
        with raw.open('xb') as stream:
            stream.write(content)
    except FileExistsError:
        if raw.read_bytes() != content:
            raise ValueError('Stored historical source differs from its content hash')
    systems = sorted({row['system'] for row in rows})
    result = {'schema': 'historical-comparison-1', 'source_sha256': sha,
              'source_member': MEMBER if path.suffix.lower() == '.zip' else None,
              'metrics': comparison_metrics(rows),
              'metrics_by_system': {system: comparison_metrics([row for row in rows if row['system'] == system])
                                    for system in systems},
              'runs': rows}
    atomic_json(output, result)
    return result['metrics']


def parse_comparison(content):
    if len(content) > MAX_CSV_BYTES:
        raise ValueError('Historical comparison exceeds size limit')
    reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig'), newline=''), strict=True)
    if reader.fieldnames != FIELDS:
        raise ValueError('Unrecognized historical comparison columns')
    records = {}
    for row in reader:
        if None in row or None in row.values():
            raise ValueError(f'Malformed record on line {reader.line_num}')
        version, system = row['version'], row['system']
        rep, opportunities, missed, extra, generated = (
            int(row[field]) for field in ('rep', 'gt_items', 'missed', 'extra_rows', 'gen_rows')
        )
        rate = float(row['missed_pct'])
        if (not version or not system or rep < 1 or opportunities < 1
                or not 0 <= missed <= opportunities or not 0 <= extra <= generated
                or not math.isclose(rate, 100 * missed / opportunities, abs_tol=0.00500001)):
            raise ValueError(f'Invalid counts or percentage on line {reader.line_num}')
        identity = (version, system, rep)
        if identity in records:
            raise ValueError(f'Duplicate historical run on line {reader.line_num}')
        records[identity] = {'version': version, 'system': system, 'replicate': rep,
                             'opportunities': opportunities, 'missed': missed,
                             'unmatched_generated': extra, 'generated': generated}
    if not records:
        raise ValueError('Historical comparison contains no runs')
    return list(records.values())


def comparison_metrics(records):
    versions = sorted({row['version'] for row in records})
    result = {}
    for version in versions:
        rows = [row for row in records if row['version'] == version]
        missed = sum(row['missed'] for row in rows)
        opportunities = sum(row['opportunities'] for row in rows)
        system_rates = {}
        for row in rows:
            system_rates.setdefault(row['system'], []).append(row['missed'] / row['opportunities'])
        result[version] = {
            'runs': len(rows),
            'missed': missed,
            'opportunities': opportunities,
            'pooled_missed_rate': missed / opportunities,
            'mean_run_missed_rate': statistics.mean(rate for rates in system_rates.values() for rate in rates),
            'equal_system_mean_missed_rate': statistics.mean(statistics.mean(rates) for rates in system_rates.values()),
            'mean_unmatched_generated_per_run': statistics.mean(row['unmatched_generated'] for row in rows),
        }
    return result
