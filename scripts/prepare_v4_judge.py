"""Prepare one external judge task without reading reference contents or calling AI."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analysis.research.__main__ import atomic_json
from analysis.round2.__main__ import private, read
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--manifest',required=True); parser.add_argument('--run-id',required=True)
parser.add_argument('--output',required=True); parser.add_argument('--generation-receipt',required=True)
args=parser.parse_args(); manifest=read(private(args.manifest)); receipt=read(private(args.generation_receipt))
run=next((r for r in manifest['runs'] if r['run_id']==args.run_id),None)
if not run or receipt.get('prompt_version')!='v4.0' or receipt.get('status')!='success': raise SystemExit('Successful matching V4 receipt required')
if receipt['system_id'].removeprefix('system_')!=run['system'] or receipt['run_number']!=run['replicate']: raise SystemExit('Generation identity mismatch')
path=private(args.output)
if path.exists(): raise FileExistsError(path)
atomic_json(path,{'schema':'external-judge-task-4','run':run,'generation_receipt':str(private(args.generation_receipt)),
                 'judge_model':manifest['judge_model'],'judge_skill_version':manifest['judge_skill_version'],
                 'status':'AWAITING_EXTERNAL_EVALUATION','instructions':'Use the unchanged human-controlled judge v1.2 and ground-truth revision. Export standalone-judge-import-1 identifier records. Do not supply reference contents to this software agent.',
                 'paid_calls_executed':0})
