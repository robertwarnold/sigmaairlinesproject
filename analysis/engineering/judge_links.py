"""Private projection connecting immutable generator rows to imported judge trials."""
import hashlib
import json
import sqlite3

from analysis.round2.__main__ import private


def attach_judge_links(snapshot, registry_path):
    registry_path = private(registry_path)
    if not registry_path.is_file():
        return snapshot
    runs = {record['run_id']: record['metadata'] for record in snapshot['records']}
    if not runs:
        return snapshot
    connection = sqlite3.connect(registry_path.as_uri() + '?mode=ro', uri=True)
    try:
        evaluations = connection.execute('''
            SELECT g.id, g.payload, g.selected_evaluation, e.id, e.payload
            FROM generations g JOIN evaluations e ON e.generation_id=g.id
            ORDER BY e.created_at, e.id
        ''').fetchall()
    finally:
        connection.close()
    rows = {(record['run_id'],record['row_id']):record for record in snapshot['records']}
    resolved = {}
    for generation_id, generation_payload, selected, evaluation_id, evaluation_payload in evaluations:
        if generation_id not in resolved:
            generation = json.loads(generation_payload)
            try:
                content = private(generation['receipt_path']).read_bytes()
                if hashlib.sha256(content).hexdigest() != generation.get('receipt_sha256'):
                    continue
                receipt = json.loads(content)
                run_id = receipt['experiment_id'] + ':' + receipt['attempt_id']
                metadata = runs.get(run_id)
                hashes = {entry.get('sha256') for entry in receipt.get('artifacts', {}).values()}
                resolved[generation_id] = run_id if metadata and metadata['response_sha256'] in hashes else None
            except (KeyError, OSError, TypeError, ValueError):
                resolved[generation_id] = None
        run_id = resolved.get(generation_id)
        if not run_id:
            continue
        evaluation = json.loads(evaluation_payload)
        for item in evaluation['items']:
            record = rows.get((run_id,item.get('matched_row_id')))
            if record is None or item.get('found') is not True:
                continue
            record.setdefault('judge_matches',[]).append({
                'evaluation_id':evaluation_id,'generation_id':generation_id,'selected':evaluation_id==selected,
                'judge_version':evaluation.get('judge_skill_version'),'item':item})
    return snapshot
