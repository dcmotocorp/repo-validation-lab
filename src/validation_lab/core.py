"""Pure validation logic with actionable error codes."""
from __future__ import annotations
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    line: int | None = None

@dataclass(frozen=True)
class Report:
    records: int
    sha256: str
    findings: tuple[Finding, ...]

    @property
    def valid(self) -> bool:
        return not self.findings

    def as_dict(self) -> dict[str, Any]:
        return {"valid": self.valid, "records": self.records, "sha256": self.sha256,
                "findings": [{k: v for k, v in asdict(f).items() if v is not None} for f in self.findings]}

def _timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None

def validate(dataset: Path, manifest_path: Path) -> Report:
    raw = dataset.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return Report(0, digest, (Finding("manifest_json", f"Invalid manifest: {exc}"),))
    if not isinstance(manifest, dict):
        return Report(0, digest, (Finding("manifest_shape", "Manifest must be an object"),))
    errors: list[Finding] = []
    if manifest.get("schema_version") != 1 or type(manifest.get("schema_version")) is not int:
        errors.append(Finding("schema_version", "schema_version must be 1"))
    if not isinstance(manifest.get("source"), str) or not manifest["source"].strip():
        errors.append(Finding("source", "source must be a nonempty string"))
    if not _timestamp(manifest.get("generated_at")):
        errors.append(Finding("generated_at", "generated_at must contain an ISO 8601 timezone"))
    checksum = manifest.get("sha256")
    if not isinstance(checksum, str) or len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
        errors.append(Finding("sha256", "sha256 must be 64 lowercase hex characters"))
    elif checksum != digest:
        errors.append(Finding("checksum", "Dataset SHA-256 differs from manifest"))
    expected = manifest.get("record_count")
    if type(expected) is not int or expected < 0:
        errors.append(Finding("record_count", "record_count must be a nonnegative integer"))
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        errors.append(Finding("encoding", f"Dataset must be UTF-8: {exc}"))
        return Report(0, digest, tuple(errors))
    seen: set[str] = set()
    count = 0
    for number, line in enumerate(lines, 1):
        if not line.strip():
            errors.append(Finding("blank_line", "Blank JSONL record", number))
            continue
        count += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(Finding("record_json", f"Invalid JSON: {exc.msg}", number))
            continue
        if not isinstance(row, dict):
            errors.append(Finding("record_shape", "Record must be an object", number))
            continue
        identifier = row.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            errors.append(Finding("id", "id must be a nonempty string", number))
        elif identifier in seen:
            errors.append(Finding("duplicate_id", f"Duplicate id: {identifier}", number))
        else:
            seen.add(identifier)
        if not _timestamp(row.get("observed_at")):
            errors.append(Finding("observed_at", "observed_at needs an ISO 8601 timezone", number))
        if not isinstance(row.get("metric"), str) or not row["metric"].strip():
            errors.append(Finding("metric", "metric must be a nonempty string", number))
        value = row.get("value")
        if type(value) not in (int, float) or not 0 <= value <= 1_000_000:
            errors.append(Finding("value", "value must be numeric from 0 to 1000000", number))
    if type(expected) is int and count != expected:
        errors.append(Finding("count", f"Expected {expected} records, found {count}"))
    return Report(count, digest, tuple(errors))
