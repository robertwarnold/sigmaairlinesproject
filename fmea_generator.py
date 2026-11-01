"""Generate FMEA CSV files with the official Google Gen AI Python SDK."""
import argparse
import csv
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = "gemini-2.5-flash"
PROMPT_VERSION = "v2.0"
FIELDS = ["component", "function", "failure_mode", "cause", "local_effect",
          "system_effect", "recommended_action", "severity", "occurrence",
          "detection", "rating_rationale", "evidence", "review_flag"]
RATINGS = ("severity", "occurrence", "detection")
CSV_FIELDS = ["case_id", "version", "run", "model", "generation_minutes"] + FIELDS + ["RPN"]
RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "min_items": 1,
    "items": {
        "type": "OBJECT",
        "required": FIELDS.copy(),
        "properties": {
            field: ({"type": "INTEGER", "minimum": 1, "maximum": 10}
                    if field in RATINGS else {"type": "STRING"})
            for field in FIELDS
        },
    },
}


def load_local_env(path=None):
    """Read optional .env without overriding environment variables already set."""
    path = Path(path) if path else ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_fmea(raw):
    """Validate model response and calculate RPN locally, never trust AI arithmetic."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    items = json.loads(cleaned)
    if not isinstance(items, list) or not items:
        raise ValueError("Expected a nonempty JSON array of FMEA rows")
    output = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Row {index}: expected a JSON object")
        missing = [field for field in FIELDS if field not in item]
        if missing:
            raise ValueError(f"Row {index}: missing fields: {', '.join(missing)}")
        row = {}
        for field in FIELDS:
            value = item[field]
            if field in RATINGS:
                if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 10:
                    raise ValueError(f"Row {index}: {field} must be an integer 1–10")
            elif not isinstance(value, str):
                raise ValueError(f"Row {index}: {field} must be text")
            elif not value.strip():
                raise ValueError(f"Row {index}: {field} is empty; the skill requires text such as \"Not provided\"")
            row[field] = value
        row["RPN"] = row["severity"] * row["occurrence"] * row["detection"]
        output.append(row)
    return output


def call_gemini(system_text, model=None):
    """Return the raw text, finish reason and output cap; the caller saves raw text before judging it."""
    load_local_env()
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY missing. Set it in the environment or local .env; "
                           "on GitHub Actions, configure the GEMINI_API_KEY repository secret.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Install dependencies: python -m pip install -r requirements.txt") from exc
    model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    instructions = (ROOT / "skill" / "fmea_instructions.md").read_text(encoding="utf-8")
    client = genai.Client(api_key=key)
    try:
        # Use the selected model's own maximum; long one-row-per-unit sheets exceed fixed caps.
        max_output_tokens = client.models.get(model=model).output_token_limit
        if not max_output_tokens:
            raise RuntimeError(f"Could not read the output token limit for {model}; no generation request made")
        response = client.models.generate_content(
            model=model,
            contents="SYSTEM DESCRIPTION:\n" + system_text,
            config=types.GenerateContentConfig(
                system_instruction=instructions,
                temperature=0,
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
                max_output_tokens=max_output_tokens,
            ),
        )
        candidates = response.candidates or []
        finish = candidates[0].finish_reason if candidates else None
        return {"text": response.text or "", "finish_reason": str(getattr(finish, "value", finish)),
                "max_output_tokens": max_output_tokens}
    finally:
        client.close()


def generate_fmea(system_file, case_id, version=PROMPT_VERSION, run=1,
                  output_dir=None, model=None):
    system_file = Path(system_file)
    if not system_file.is_file():
        raise FileNotFoundError(f"Missing system description: {system_file}")
    system_text = system_file.read_text(encoding="utf-8").strip()
    if not system_text:
        raise ValueError("System description is empty")
    output_dir = Path(output_dir) if output_dir else ROOT / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    start = time.monotonic()
    result = call_gemini(system_text, model=model)
    minutes = round((time.monotonic() - start) / 60, 5)
    safe_case = re.sub(r"[^a-zA-Z0-9_-]", "_", case_id)
    safe_version = re.sub(r"[^a-zA-Z0-9._-]", "_", version)
    prefix = f"{safe_case}_{safe_version}_run{run:02d}"
    raw_path = output_dir / f"{prefix}_raw.txt"
    raw_path.write_text(result["text"], encoding="utf-8")
    if result["finish_reason"] == "MAX_TOKENS":
        raise ValueError(f"Gemini response truncated at the {result['max_output_tokens']}-token limit; "
                         f"partial output saved to {raw_path.name}, no CSV written")
    if result["finish_reason"] != "STOP":
        raise ValueError(f"Gemini stopped with finish reason {result['finish_reason']}; "
                         f"output saved to {raw_path.name}, no CSV written")
    if not result["text"].strip():
        raise ValueError("Gemini returned no text (possibly blocked)")
    rows = parse_fmea(result["text"])
    csv_path = output_dir / f"{prefix}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({"case_id": case_id, "version": version, "run": run,
                             "model": model, "generation_minutes": minutes, **row})
    print(f"Saved {len(rows)} FMEA rows to {csv_path}")
    return rows


def main():
    parser = argparse.ArgumentParser(description="Generate an FMEA using Gemini")
    parser.add_argument("--system", default=str(ROOT / "system_descriptions" / "system_1.txt"))
    parser.add_argument("--case-id", default="system_1")
    parser.add_argument("--version", default=PROMPT_VERSION)
    parser.add_argument("--run", type=int, default=1)
    parser.add_argument("--model", default=None)
    args = parser.parse_args()
    generate_fmea(args.system, args.case_id, args.version, args.run, model=args.model)


if __name__ == "__main__":
    main()
