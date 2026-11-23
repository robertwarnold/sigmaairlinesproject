"""Refresh from a controlled artifact directory; never scan reference worksheets."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analysis.research.__main__ import build
from analysis.round2.__main__ import private

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--incoming',required=True)
parser.add_argument('--output',required=True)
args=parser.parse_args(); incoming=private(args.incoming)
# Match explicit export names only; raw FMEAs and judge prose are never imported.
judges=sorted(incoming.rglob('*judge_import.json'))
receipts=sorted(incoming.rglob('*_execution.json'))
if not judges and not receipts: raise SystemExit('No recognized research import artifacts; previous snapshot unchanged')
build(judges,args.output,receipts=receipts)
