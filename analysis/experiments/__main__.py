"""Offline dashboard/financial execution and explicit review-only aggregate staging."""
import argparse
from pathlib import Path
from .catalog import discover
from .report import create_report,publish_stage
from analysis.financial_impact.data_schema import read_json


def main():
    """Accept explicit generated-data sources; reporting has no generation subcommand or provider key."""
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest="command",required=True)
    report=sub.add_parser("report");report.add_argument("--registry",type=Path);report.add_argument("--source",type=Path,action="append",default=[])
    report.add_argument("--manifest",type=Path,action="append",default=[]);report.add_argument("--artifact-root",type=Path,action="append",default=[])
    report.add_argument("--output-root",type=Path,default=Path("results/experiment_reports"));report.add_argument("--catalog",type=Path,default=Path("results/experiment_metrics/catalog.json"))
    report.add_argument("--effective-index",type=Path);report.add_argument("--provider-evidence",type=Path);report.add_argument("--analysis-id")
    report.add_argument("--labor",type=Path);report.add_argument("--quality",type=Path);report.add_argument("--invoices",type=Path);report.add_argument("--scenario",type=Path)
    report.add_argument("--tier",default="standard_paid");report.add_argument("--skip-empty",action="store_true");report.add_argument("--summary-file",type=Path)
    publish=sub.add_parser("publish-stage");publish.add_argument("--report",type=Path,required=True);publish.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.command=="publish-stage":print(publish_stage(args.report,args.output));return
    registry=read_json(args.registry) if args.registry else {}
    paths=list(map(Path,registry.get("manifests",[])))+args.manifest+discover(args.source)
    paths=list(dict.fromkeys(paths))
    roots=list(map(Path,registry.get("artifact_roots",[])))+args.artifact_root+args.source+[p.parent for p in paths]
    if not paths and not args.source:parser.error("Supply --registry, --manifest or --source")
    output=create_report(paths,roots,args.output_root,args.catalog,args.effective_index or registry.get("effective_index"),
        args.provider_evidence or registry.get("provider_evidence"),args.analysis_id,args.labor,args.quality,args.invoices,args.scenario,args.tier,args.skip_empty)
    if args.summary_file:
        with args.summary_file.open("a",encoding="utf-8") as stream:stream.write((output/"run_summary.md").read_text(encoding="utf-8"))
    print("Dashboard: "+str(output.resolve()/"dashboard.md"))
    print("Financial: "+str(output.resolve()/"financial/financial-v1/Financial_Impacts.md"))


if __name__=="__main__":main()
