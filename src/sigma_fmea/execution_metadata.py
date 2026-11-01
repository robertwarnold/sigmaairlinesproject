"""Provider-independent execution receipts; no financial assumptions or network calls."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def utc_now():
    """Return a zoned UTC event timestamp; elapsed clocks are recorded separately."""
    return datetime.now(timezone.utc).isoformat()


def file_hash(path):
    """Bind an artifact to its exact bytes, without interpreting engineering content."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_receipt(path, record, artifacts, stream=None):
    """Create a structured sidecar once; pricing remains unavailable until analysis."""
    # Separate timing/usage from FMEA rows; unknown billing is explicitly not zero.
    record["metadata_schema"] = "fmea-execution-1"
    record["estimated_api_expense_usd"] = None
    record["pricing_source"] = None
    record["pricing_status"] = "deferred_to_offline_financial_analysis_or_invoice"
    record["artifacts"] = {Path(p).name: {"sha256": file_hash(p), "bytes": Path(p).stat().st_size}
                           for p in artifacts if Path(p).is_file()}
    if stream is not None:
        # A generator may reserve its receipt before the request to prevent races.
        stream.seek(0)
        stream.truncate()
        json.dump(record, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
    else:
        with Path(path).open("x", encoding="utf-8", newline="\n") as destination:
            json.dump(record, destination, indent=2, allow_nan=False)
            destination.write("\n")
