"""Offline private FMEA workstation. No model calls, reference imports or public endpoints."""
import argparse
import json
from pathlib import Path
from analysis.round2.__main__ import private
from standalone_v4 import strict_read
from .store import EngineeringStore, atomic_export, compare_keys, export_csv
from .analytics import selected_analytics, operational_activity


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database', default='results/engineering/workspace.sqlite')
    sub = p.add_subparsers(dest='command', required=True)
    imp = sub.add_parser('import-v4')
    for arg in ('response', 'inventory', 'receipt', 'dataset-version'): imp.add_argument('--'+arg, required=True)
    snap = sub.add_parser('snapshot'); snap.add_argument('--output', required=True)
    snap.add_argument('--research-registry')
    analytics = sub.add_parser('analytics'); analytics.add_argument('--selection', required=True); analytics.add_argument('--output', required=True)
    operations = sub.add_parser('operations'); operations.add_argument('--input',required=True); operations.add_argument('--output',required=True)
    rev = sub.add_parser('review'); rev.add_argument('--request', required=True)
    exp = sub.add_parser('export'); exp.add_argument('--output', required=True); exp.add_argument('--format', choices=('json','csv'), default='json'); exp.add_argument('--selection')
    comp = sub.add_parser('compare'); comp.add_argument('--run-id', action='append', required=True); comp.add_argument('--output', required=True)
    args = p.parse_args()
    if args.command=='operations':
        rows=strict_read(private(args.input).read_text(encoding='utf-8'))
        if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows): raise ValueError('Expected generation receipt array')
        atomic_export(args.output,operational_activity(rows)); return
    store = EngineeringStore(args.database)
    try:
        if args.command == 'import-v4':
            key = store.ingest(args.response, args.inventory, args.receipt, args.dataset_version); print('Imported one immutable V4 run; engineering review required')
        elif args.command == 'review':
            request = strict_read(private(args.request).read_text(encoding='utf-8')); store.review(**request)
            print('Review event appended; original assessment preserved')
        else:
            data = store.snapshot()
            if args.command == 'analytics':
                ids = strict_read(private(args.selection).read_text(encoding='utf-8'))
                if not isinstance(ids,list) or any(not isinstance(i,str) for i in ids): raise ValueError('Selection must contain record IDs')
                atomic_export(args.output,selected_analytics(data,ids)); return
            ids = None
            if args.command == 'export' and args.selection:
                ids = strict_read(private(args.selection).read_text(encoding='utf-8'))
                if not isinstance(ids,list) or any(not isinstance(i,str) for i in ids) or len(ids)!=len(set(ids)) or set(ids)-{r['record_id'] for r in data['rows']}:
                    raise ValueError('Invalid export selection')
            if args.command == 'compare': atomic_export(args.output, {'schema':'engineering-comparison-1','runs':compare_keys(data,args.run_id)})
            elif args.command == 'export' and args.format == 'csv': export_csv(data,args.output,ids)
            elif args.command == 'export' and ids is not None:
                selected_runs={r['run_id'] for r in data['rows'] if r['record_id'] in ids}
                atomic_export(args.output,{'schema':'engineering-record-export-1','private':True,'scope':'selected_record_ids',
                  'rows':[r for r in data['rows'] if r['record_id'] in ids],
                  'records':[r for r in data['records'] if r['record_id'] in ids],
                  'coverage_audits':{k:v for k,v in data['coverage_audits'].items() if k in selected_runs},
                  'metric_scope':'Selected records only; no inferred research metrics'})
            else:
                if args.command == 'snapshot' and args.research_registry:
                    from .judge_links import attach_judge_links
                    attach_judge_links(data,args.research_registry)
                atomic_export(args.output,data)
    finally: store.close()


if __name__ == '__main__': main()
