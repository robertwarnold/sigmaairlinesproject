"""Print the frozen randomized schedule. This command makes no network/model calls."""
import argparse
import shlex
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analysis.round2.__main__ import private, read
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--manifest',required=True)
parser.add_argument('--start',type=int,default=1)
parser.add_argument('--count',type=int,default=20)
args=parser.parse_args(); data=read(private(args.manifest))
if data['schema']!='round2-v4-plan-1': raise SystemExit('V4 manifest required')
if not 1<=args.start<=20 or not 1<=args.count<=20 or args.start+args.count-1>20: raise SystemExit('Invalid schedule range')
print('# PREPARATION ONLY: verify frozen conditions, pilot acceptance, shared daily quota and explicit paid-call authorization before running commands.')
for run in data['runs'][args.start-1:args.start-1+args.count]:
    if run['skill_version']!='v4.0': raise SystemExit('Mixed treatment')
    print('gh workflow run generate-fmea.yml --ref feat/fmea-skill-v4-research-dashboard -f mode=single -f skill_version=v4.0 -f system=system_'+run['system']+' -f model='+shlex.quote(data['generator_model'])+' -f run_number='+str(run['replicate'])+' -f batch_id='+run['run_id']+' -f approved_calls=1')
