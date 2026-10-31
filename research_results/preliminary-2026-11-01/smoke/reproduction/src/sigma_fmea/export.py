"""Publish complete immutable bundles; never overwrite an earlier analysis."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile

from .integrity import load_json, validate_json
from .models import FMEADraft
from .conversion import verify_report


def safe_cell(value):
    if isinstance(value, str) and (value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@"))):
        return "'" + value
    return value


def json_bytes(data):
    validate_json(data)
    return (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def csv_bytes(data):
    stream = io.StringIO(newline="")
    columns = list(data["rows"][0])
    envelope = {k: data[k] for k in ("artifact_id", "artifact_version", "schema_version", "profile_id", "profile_version", "approval_status")}
    envelope["analysis_id"] = data["context"]["analysis_id"]
    envelope["mapping_version"] = data["metadata"].get("conversion_mapping_version", "")
    writer = csv.DictWriter(stream, fieldnames=[*envelope, *columns])
    writer.writeheader()
    for row in data["rows"]:
        cells = {k: json.dumps(v, ensure_ascii=False, allow_nan=False) if isinstance(v, (dict, list)) else v for k, v in row.items()}
        writer.writerow({k: safe_cell(v) for k, v in {**envelope, **cells}.items()})
    return stream.getvalue().encode("utf-8")


def _write_bytes(path, data):
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def export(draft, output, report=None):
    data = draft.to_dict()
    converted = "conversion_mapping_version" in draft.metadata
    if converted != (report is not None):
        raise ValueError("Converted drafts require their report; generated drafts cannot carry one")
    if report is not None:
        verify_report(draft, report)
    output = Path(output).absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    lock = output.parent / ("." + output.name + ".lock")
    lock.mkdir()  # fail closed for concurrent writers or an interrupted lock
    staging = None
    try:
        if output.exists():
            raise FileExistsError(f"Output already exists; select a new directory: {output}")
        staging = Path(tempfile.mkdtemp(prefix="." + output.name + ".staging-", dir=output.parent))
        files = {"fmea.json": json_bytes(data), "fmea.csv": csv_bytes(data)}
        if report is not None:
            files["conversion_report.json"] = json_bytes(report)
        manifest = {"bundle_version": "0.2", "artifact_id": draft.artifact_id,
                    "artifact_version": draft.artifact_version,
                    "mapping_version": draft.metadata.get("conversion_mapping_version"),
                    "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}}
        for name, content in files.items():
            _write_bytes(staging / name, content)
        _write_bytes(staging / "manifest.json", json_bytes(manifest))
        verify_bundle(staging)
        os.rename(staging, output)  # same filesystem; no visible partial bundle
        staging = None
    finally:
        if staging is not None:
            resolved = staging.resolve()
            if resolved.parent == output.parent.resolve() and resolved.name.startswith("." + output.name + ".staging-"):
                shutil.rmtree(resolved)
        lock.rmdir()


def verify_bundle(output):
    output = Path(output)
    manifest = load_json(output / "manifest.json")
    draft = FMEADraft.from_dict(load_json(output / "fmea.json"))
    converted = "conversion_mapping_version" in draft.metadata
    expected = {"fmea.json", "fmea.csv"} | ({"conversion_report.json"} if converted else set())
    if not isinstance(manifest, dict) or manifest.get("bundle_version") != "0.2" or set(manifest.get("files", {})) != expected:
        raise ValueError("Invalid bundle manifest/file set")
    if {p.name for p in output.iterdir()} != expected | {"manifest.json"}:
        raise ValueError("Unexpected or stale files in bundle")
    if manifest.get("artifact_id") != draft.artifact_id or manifest.get("artifact_version") != draft.artifact_version or manifest.get("mapping_version") != draft.metadata.get("conversion_mapping_version"):
        raise ValueError("Bundle artifact/mapping version mismatch")
    for name in expected:
        if hashlib.sha256((output / name).read_bytes()).hexdigest() != manifest["files"][name]:
            raise ValueError(f"Bundle file checksum mismatch: {name}")
    if (output / "fmea.csv").read_bytes() != csv_bytes(draft.to_dict()):
        raise ValueError("CSV differs from canonical FMEA")
    if converted:
        verify_report(draft, load_json(output / "conversion_report.json"))
    return draft
