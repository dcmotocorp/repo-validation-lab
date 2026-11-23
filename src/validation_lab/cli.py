"""CLI exits 0 for valid, 1 for validation failure, 2 for unreadable input."""
import argparse
import json
import sys
from pathlib import Path
from validation_lab.core import validate

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate JSONL telemetry and a provenance manifest")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        report = validate(args.dataset, args.manifest)
    except OSError as exc:
        print(json.dumps({"valid": False, "error": f"Cannot read input: {exc}"}), file=sys.stderr)
        return 2
    print(json.dumps(report.as_dict(), indent=2))
    return 0 if report.valid else 1

if __name__ == "__main__":
    raise SystemExit(main())
