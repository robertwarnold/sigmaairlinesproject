"""Strict input boundaries and content hashes (not digital signatures)."""
import hashlib
import json
import math
from pathlib import Path
import unicodedata


def validate_json(value):
    def visit(node, active):
        if node is None or type(node) in (str, bool, int):
            return
        if type(node) is float:
            if not math.isfinite(node):
                raise ValueError("Nonfinite JSON number")
            return
        if type(node) not in (dict, list):
            raise ValueError(f"Non-JSON value: {type(node).__name__}")
        if id(node) in active:
            raise ValueError("Cyclic JSON data")
        active.add(id(node))
        if type(node) is dict:
            for key, child in node.items():
                if type(key) is not str:
                    raise ValueError("JSON object keys must be strings")
                visit(child, active)
        else:
            for child in node:
                visit(child, active)
        active.remove(id(node))
    visit(value, set())


def canonical_json(data):
    validate_json(data)
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(data):
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def normalize_header(header):
    return unicodedata.normalize("NFKC", header).strip().casefold().replace(" ", "_")


def strict_loads(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError(f"Nonfinite JSON number: {value}")
    result = json.loads(text, object_pairs_hook=unique, parse_constant=invalid)
    validate_json(result)
    return result


def load_json(path):
    return strict_loads(Path(path).read_text(encoding="utf-8-sig"))
