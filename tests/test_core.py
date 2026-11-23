import hashlib
import json
from pathlib import Path
import pytest
from validation_lab.cli import main
from validation_lab.core import validate

ROW = {"id": "r1", "observed_at": "2026-11-23T12:00:00Z", "metric": "latency_ms", "value": 25.5}

def inputs(tmp_path: Path, rows=None, **changes):
    dataset = tmp_path / "events.jsonl"
    dataset.write_text("\n".join(rows if rows is not None else [json.dumps(ROW)]) + "\n", encoding="utf-8")
    manifest = {"schema_version": 1, "source": "synthetic-example",
                "generated_at": "2026-11-23T12:30:00+00:00",
                "record_count": len(rows) if rows is not None else 1,
                "sha256": hashlib.sha256(dataset.read_bytes()).hexdigest()}
    manifest.update(changes)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return dataset, path

def codes(report):
    return {f.code for f in report.findings}

def test_valid_dataset_and_cli(tmp_path, capsys):
    dataset, manifest = inputs(tmp_path)
    assert validate(dataset, manifest).valid
    assert main([str(dataset), str(manifest)]) == 0
    assert json.loads(capsys.readouterr().out)["records"] == 1

def test_checksum_detects_tampering(tmp_path):
    dataset, manifest = inputs(tmp_path)
    dataset.write_text(dataset.read_text().replace("25.5", "30.5"))
    assert "checksum" in codes(validate(dataset, manifest))

def test_duplicate_ids_have_line_numbers(tmp_path):
    dataset, manifest = inputs(tmp_path, [json.dumps(ROW), json.dumps(ROW)])
    assert ("duplicate_id", 2) in {(f.code, f.line) for f in validate(dataset, manifest).findings}

@pytest.mark.parametrize("change,code", [
    ({"schema_version": 2}, "schema_version"), ({"record_count": True}, "record_count"),
    ({"source": ""}, "source"), ({"generated_at": "2026-11-23T12:00:00"}, "generated_at")])
def test_bad_manifest_fields(tmp_path, change, code):
    assert code in codes(validate(*inputs(tmp_path, **change)))

@pytest.mark.parametrize("row,code", [
    ({**ROW, "id": ""}, "id"), ({**ROW, "observed_at": "yesterday"}, "observed_at"),
    ({**ROW, "value": True}, "value"), ({**ROW, "value": -1}, "value"),
    ({**ROW, "metric": ""}, "metric")])
def test_invalid_rows(tmp_path, row, code):
    assert code in codes(validate(*inputs(tmp_path, rows=[json.dumps(row)])))

def test_bad_json_and_count(tmp_path):
    assert {"record_json", "count"} <= codes(validate(*inputs(tmp_path, rows=["{bad", json.dumps(ROW)], record_count=1)))

def test_invalid_utf8_and_manifest_json(tmp_path):
    dataset, manifest = inputs(tmp_path)
    dataset.write_bytes(b"\xff")
    assert "encoding" in codes(validate(dataset, manifest))
    manifest.write_text("{")
    assert codes(validate(dataset, manifest)) == {"manifest_json"}

def test_missing_input_exits_two(tmp_path, capsys):
    assert main([str(tmp_path / "missing"), str(tmp_path / "manifest")]) == 2
    assert json.loads(capsys.readouterr().err)["valid"] is False
