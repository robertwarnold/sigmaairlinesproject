"""Normalize existing standalone receipts/manifests into an idempotent offline metrics catalog."""
from datetime import datetime, timezone
import hashlib
import csv
import json
from pathlib import Path
import re
import tempfile
from analysis.financial_impact.data_schema import read_json
from analysis.financial_impact.ingest import import_attempts, sha256
from src.sigma_fmea.execution_metadata import characterize_csv

# Discovery is metadata-only. Raw response text and frozen/canonical worksheets are never searched.
RECEIPT_NAMES = ("*_execution.json", "recovery_metadata.json", "attempt_metadata.json", "manifest.json", "campaign_manifest.json", "campaign-manifest.json", "reconciliation_manifest.json")
EXCLUDED_PARTS = {"research_results", ".git", "source-review"}


def safe_path(path):
    """Keep frozen evidence and source-review/reference locations out of automatic discovery."""
    path = Path(path)
    if any(part in EXCLUDED_PARTS for part in path.parts):
        raise ValueError("Reporting sources must be generated standalone evidence, not frozen/reference directories")
    return path


def discover(sources):
    """Discover completed execution receipts without loading provider responses or canonical bundles."""
    found=set()
    for source in map(safe_path,sources):
        if source.is_file():found.add(source.resolve());continue
        for pattern in RECEIPT_NAMES:
            found.update(p.resolve() for p in source.rglob(pattern) if not any(x in EXCLUDED_PARTS for x in p.parts))
    return sorted(found)


def documents(paths):
    """Expand supported financial/reconciliation/legacy containers using their existing metadata."""
    records=[];excluded=[];seen=set()
    def visit(path):
        path=safe_path(path).resolve()
        if path in seen:return
        seen.add(path);doc=read_json(path)
        if doc.get("metadata_schema")=="fmea-execution-1":
            candidates=[doc]
        elif doc.get("financial_schema")=="reconciled-campaign-1":
            candidates=doc["attempts"]
        elif "plan" in doc and isinstance(doc.get("runs"),list):
            plan=doc["plan"];candidates=[]
            standalone_legacy=str(plan.get("prompt_version","")).startswith("v") and bool(plan.get("skill_sha256"))
            standalone_receipts=all(r.get("metadata_schema")=="fmea-execution-1" and r.get("workflow","standalone_gemini").startswith("standalone") for r in doc["runs"])
            if doc["runs"] and not (standalone_legacy or standalone_receipts):
                excluded.append({"source":str(path),"reason":"non-standalone legacy manifest"});return
            for run in doc["runs"]:
                if run.get("status")=="not_attempted":continue
                merged={**plan,**run,"experiment_id":run.get("experiment_id",plan.get("batch_id",plan.get("campaign_id"))),"metadata_schema":"fmea-execution-1"}
                if not merged.get("attempt_id"):
                    merged["attempt_id"]=f"{merged['system_id']}_{merged['prompt_version']}_run{int(merged['run_number']):02d}"
                candidates.append(merged)
        elif "plan" in doc and isinstance(doc["plan"].get("systems"),dict):
            for system in doc["plan"]["systems"]:
                sidecar=path.parent/system/f"{system}_{doc['plan']['prompt_version']}_run01_execution.json"
                if sidecar.exists():visit(sidecar)
                else:excluded.append({"source":str(sidecar),"reason":"campaign slot has no recoverable execution receipt"})
            return
        elif doc.get("recovery_campaign_id") and doc.get("attempt_id"):
            candidates=[{**doc,"metadata_schema":"fmea-execution-1","experiment_id":doc["recovery_campaign_id"],"total_elapsed_seconds":doc.get("elapsed_seconds")}]
        else:
            excluded.append({"source":str(path),"reason":"unsupported or canonical metadata format"});return
        for record in candidates:
            workflow=record.get("workflow","standalone_gemini")
            if not workflow.startswith("standalone"):
                excluded.append({"source":str(path),"reason":"canonical workflow intentionally excluded"});continue
            if not record.get("experiment_id") and record.get("recovery_campaign_id"):
                record={**record,"experiment_id":record["recovery_campaign_id"]}
            if record.get("status") in ("running","not_attempted",None):continue
            records.append((dict(record),path))
    for path in paths:visit(path)
    return records,excluded


def artifact_map(record):
    """Accept the existing engine hash objects and historical recovery string hashes."""
    combined={**record.get("outputs",{}),**record.get("artifacts",{})}
    return {name:(value.get("sha256") if isinstance(value,dict) else value) for name,value in combined.items()}


class Artifacts:
    """Resolve only named, hash-bound generated artifacts inside explicitly supplied directories."""
    def __init__(self,roots):
        self.roots=[safe_path(p).resolve() for p in roots];self.cache={}

    def locate(self,name,digest,source):
        """Require both a safe basename and exact SHA-256; identical copies are interchangeable."""
        if Path(name).name!=name or not digest:return None
        key=(name,digest)
        if key in self.cache:return self.cache[key]
        candidates=[source.parent/name]
        for root in self.roots:
            if root.is_file():root=root.parent
            candidates.extend(p for p in root.rglob(name) if not any(x in EXCLUDED_PARTS for x in p.parts))
        for candidate in sorted(set(candidates),key=lambda p:(len(str(p)),str(p))):
            if candidate.is_file() and sha256(candidate)==digest:
                self.cache[key]=candidate.resolve();return self.cache[key]
        self.cache[key]=None;return None


def normalize(record,source,artifacts):
    """Prefer measured engine timings while preserving richer recovery/retry/provider metadata."""
    raw=dict(record);mapping=artifact_map(raw);engine_path=None
    for name,digest in mapping.items():
        if name.endswith("_execution.json"):
            engine_path=artifacts.locate(name,digest,source)
            if engine_path:break
    if not engine_path and not source.name.endswith("_execution.json"):
        prefix=raw.get("source_attempt_id",raw.get("attempt_id",""))
        if raw.get("run_number") is not None:
            prefix=f"{raw['system_id']}_{raw['prompt_version']}_run{int(raw['run_number']):02d}"
        if re.fullmatch(r"[A-Za-z0-9_.-]+",str(prefix)):
            candidates=[]
            for root in artifacts.roots:
                candidates.extend((root if root.is_dir() else root.parent).rglob(str(prefix)+"_execution.json"))
            for candidate in sorted(set(candidates),key=lambda p:len(str(p))):
                if any(part in EXCLUDED_PARTS for part in candidate.parts):continue
                possible=read_json(candidate)
                if possible.get("experiment_id")==raw.get("experiment_id") and possible.get("attempt_id")==raw.get("attempt_id") and possible.get("started_at")==raw.get("started_at") and artifact_map(possible)==mapping:
                    engine_path=candidate;break
    if engine_path:
        engine=read_json(engine_path)
        if not engine.get("workflow","standalone_gemini").startswith("standalone"):raise ValueError("Canonical receipt embedded in standalone input")
        raw={**engine,**raw}
        # Wrapper waits/diagnostics complement the engine; they do not replace measured API/parse clocks.
        for key in ("started_at","finished_at","total_elapsed_seconds","api_request_seconds","parsing_validation_seconds","usage_metadata","configuration"):
            if key in engine:raw[key]=engine[key]
        engine_hash=sha256(engine_path)
    elif source.name.endswith("_execution.json"):
        engine_hash=sha256(source)
    else:engine_hash=raw.get("source_receipt_sha256")
    if not raw.get("experiment_id"):raise ValueError("Missing campaign identity")
    if raw["experiment_id"] in ("results","out","output"):
        raw["source_experiment_id"]=raw["experiment_id"]
        fingerprint=engine_hash or hashlib.sha256(json.dumps({k:raw.get(k) for k in ("attempt_id","system_id","started_at")},sort_keys=True).encode()).hexdigest()
        raw["experiment_id"]="standalone-"+fingerprint[:16]
    raw.setdefault("workflow","standalone_gemini");raw["metadata_schema"]="fmea-execution-1"
    raw.setdefault("total_elapsed_seconds",raw.get("elapsed_seconds",raw.get("duration_seconds")))
    # Legacy run numbers are stable within the original pilot, not new generated observations.
    if not raw.get("attempt_id"):
        raw["attempt_id"]=f"{raw['system_id']}_{raw['prompt_version']}_run{int(raw['run_number']):02d}"
    identity="engine:"+engine_hash if engine_hash else "attempt:"+str(raw["experiment_id"])+"/"+str(raw["attempt_id"])
    raw["source_receipt_sha256"]=engine_hash
    csv_path=None;csv_digest=None
    mapping=artifact_map(raw)
    for name,digest in mapping.items():
        if name.endswith(".csv"):
            csv_path=artifacts.locate(name,digest,source);csv_digest=digest
            if csv_path:break
    # Older, explicitly described receiptless CSVs also carry a hash-bound artifact map.
    metrics={"schema_valid":False,"observation_available":False}
    if raw["status"]=="success":
        if csv_path:
            try:
                metrics=characterize_csv(csv_path)
                # Schema validity alone cannot bind a worksheet to its intended experimental condition.
                with csv_path.open(encoding="utf-8-sig",newline="") as stream:
                    for row in csv.DictReader(stream):
                        if any(row[column]!=str(raw[field]) for column,field in (("case_id","system_id"),("version","prompt_version"),("model","model"))):
                            raise ValueError("CSV identity differs from execution receipt")
            except (ValueError,TypeError,KeyError) as error:metrics={"schema_valid":False,"validation_error_type":type(error).__name__}
        else:metrics={"schema_valid":False,"validation_error_type":"MissingOrHashMismatchedCSV"}
    raw["fmea_metrics"]=metrics
    if metrics.get("schema_valid"):raw["row_count"]=metrics["row_count"]
    # Provider outcomes remain operational observations, never FMEA rows or engineering decisions.
    raw.setdefault("engineering_review_status","unreviewed")
    raw.setdefault("retry_number",0);raw.setdefault("retry_wait_seconds",0)
    raw["dataset_included"]=bool(metrics.get("schema_valid"))
    priority=2 if record.get("supersedes_attempt_id") or record.get("source_attempt_id") else 1
    return {"identity":identity,"receipt":raw,"csv_path":str(csv_path) if csv_path else None,"csv_sha256":csv_digest,
        "sources":[{"path":str(source),"sha256":sha256(source)}],"priority":priority,
        "aliases":[[record.get("experiment_id"),record.get("attempt_id")]],"metrics":metrics}


def merge(old,new):
    """Idempotently enrich one physical request; conflicting identities or artifacts are errors."""
    for key in ("system_id","model","prompt_version","skill_sha256","system_sha256","status"):
        a,b=old["receipt"].get(key),new["receipt"].get(key)
        if a is not None and b is not None and a!=b:raise ValueError("Conflicting duplicate request: "+key)
    if old.get("csv_sha256") and new.get("csv_sha256") and old["csv_sha256"]!=new["csv_sha256"]:raise ValueError("Conflicting duplicate CSV artifact")
    winner,other=(new,old) if new["priority"]>old["priority"] else (old,new)
    merged={**winner,"receipt":dict(winner["receipt"])}
    for key,value in other["receipt"].items():
        if key not in merged["receipt"] or merged["receipt"][key] is None:merged["receipt"][key]=value
    # A later confirmed retry wait adds operational overhead without replacing request identity.
    merged["receipt"]["retry_wait_seconds"]=max(old["receipt"].get("retry_wait_seconds",0),new["receipt"].get("retry_wait_seconds",0))
    if not winner["metrics"].get("schema_valid") and other["metrics"].get("schema_valid"):
        merged.update(metrics=other["metrics"],csv_path=other["csv_path"],csv_sha256=other["csv_sha256"])
        merged["receipt"]["fmea_metrics"]=other["metrics"]
    merged["sources"]=list({x["path"]+x["sha256"]:x for x in old["sources"]+new["sources"]}.values())
    merged["aliases"]=list({tuple(x):x for x in old["aliases"]+new["aliases"]}.values())
    return merged


def _ingest(paths,artifact_roots,catalog_path=None,evidence_path=None):
    """Update a local catalog once per physical request; never mutate historical source files."""
    documents_raw,excluded=documents(paths);resolver=Artifacts(artifact_roots)
    entries={}
    if catalog_path and Path(catalog_path).exists():entries=read_json(catalog_path)["entries"]
    for raw,source in documents_raw:
        entry=normalize(raw,source,resolver);key=entry["identity"]
        entries[key]=merge(entries[key],entry) if key in entries else entry
    if evidence_path:
        evidence=read_json(evidence_path)
        for overlay in evidence:
            key="engine:"+overlay["source_receipt_sha256"]
            if key in entries:
                for field in ("http_status","provider_error_classification","provider_billing_tier_evidence","verification","workflow_run_id"):
                    if field in overlay:entries[key]["receipt"][field]=overlay[field]
                entries[key]["sources"].append({"path":str(Path(evidence_path).resolve()),"sha256":sha256(evidence_path)})
    for entry in entries.values():
        if entry.get("csv_path") and entry["metrics"].get("schema_valid"):
            path=Path(entry["csv_path"])
            if not path.is_file() or sha256(path)!=entry["csv_sha256"]:
                entry["metrics"]={"schema_valid":False,"validation_error_type":"CachedArtifactMissingOrChanged"}
                entry["receipt"]["fmea_metrics"]=entry["metrics"]
    logical={}
    for key,entry in entries.items():
        record=entry["receipt"];identity=(record["experiment_id"],record["attempt_id"])
        if identity in logical and logical[identity]!=key:raise ValueError("Duplicate logical attempt has different physical evidence")
        logical[identity]=key
    if catalog_path:
        path=Path(catalog_path);path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps({"schema":"fmea-execution-1-catalog","entries":entries,"excluded":excluded},indent=2,allow_nan=False)+"\n",encoding="utf-8")
        temporary.replace(path)
    return sorted(entries.values(),key=lambda x:(x["receipt"].get("started_at") or x["receipt"].get("observed_at") or "",x["identity"])),excluded


def select(entries,index_path=None):
    """Retain A pilot replications and reconciled B-E selections without replacing them with new replicas."""
    index=read_json(index_path) if index_path else None
    selected={};pilot_campaign=None
    if index:
        for row in index["systems"]:
            if row.get("effective_attempt_id"):selected[row["system_id"]]=(row.get("source_campaign"),row["effective_attempt_id"],row.get("csv_sha256"))
        pilot_campaign=selected.get("system_A",(None,None,None))[0]
    result=[]
    for source in entries:
        entry={**source,"receipt":dict(source["receipt"])};record=entry["receipt"];valid=entry["metrics"].get("schema_valid") and record["status"]=="success"
        choice=selected.get(record["system_id"])
        aliases=[(record["experiment_id"],record["attempt_id"]),*map(tuple,entry["aliases"])]
        representative=bool(valid and choice and (choice[0],choice[1]) in aliases and (not choice[2] or choice[2]==entry["csv_sha256"]))
        a_pilot=bool(valid and pilot_campaign and record["system_id"]=="system_A" and record["experiment_id"]==pilot_campaign)
        primary=bool(valid and (representative or a_pilot or index is None))
        entry.update(primary=primary,representative=representative,role="primary_reconciled_or_A_pilot" if primary else "additional_valid_replication" if valid else "operational_only")
        record["dataset_included"]=primary
        result.append(entry)
    if index and any(not any(e["representative"] and e["receipt"]["system_id"]==s for e in result) for s in selected):
        raise ValueError("A reconciled effective selection is missing or no longer validates")
    return result


def financial_rows(entries,assumptions,tier="standard_paid",invoices=None):
    """Reuse the existing financial importer, including all original campaign identities and unknowns."""
    with tempfile.TemporaryDirectory() as temporary:
        path=Path(temporary)/"manifest.json"
        path.write_text(json.dumps({"plan":{"batch_id":"catalog"},"runs":[e["receipt"] for e in entries]}),encoding="utf-8")
        return import_attempts(path,assumptions,tier,invoices=invoices)


def ingest(paths,artifact_roots,catalog_path=None,evidence_path=None):
    """Serialize catalog upserts so concurrent offline reports cannot lose another request."""
    if not catalog_path:return _ingest(paths,artifact_roots,None,evidence_path)
    path=Path(catalog_path);path.parent.mkdir(parents=True,exist_ok=True)
    lock=path.with_suffix(".lock")
    # A collision is visible and recoverable from receipts; never silently overwrite a concurrent writer.
    with lock.open("x",encoding="utf-8") as stream:stream.write(str(__import__("os").getpid()))
    try:return _ingest(paths,artifact_roots,path,evidence_path)
    finally:lock.unlink()
