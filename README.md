# Repo Validation Lab

A runnable Python **fail-closed data quality gate**. It validates newline-delimited
JSON telemetry, a versioned manifest, record IDs, timezone-aware timestamps,
record counts, and a SHA-256 provenance digest. It returns independent findings
as JSON and exits nonzero on validation failure.

This is a **synthetic portfolio example**, not employer or client code. No
production dataset, confidential implementation, or claim of external use.

## Run

```bash
python -m pip install -e '.[test]'
validate-dataset examples/events.jsonl examples/manifest.json
python -m pytest -q
```

With Docker:

```bash
docker build -t repo-validation-lab .
docker run --rm -v "$PWD/examples:/data:ro" repo-validation-lab /data/events.jsonl /data/manifest.json
```

Exit status: `0` valid, `1` validation errors, `2` unreadable input.
The JSON report includes error codes and line numbers. The sample checksum
covers exact UTF-8 bytes, including the final newline. Editing the dataset
requires recalculating the manifest checksum.

## Data contract

The manifest has `schema_version: 1`, nonempty `source`, timezone-aware
`generated_at`, nonnegative `record_count`, and lowercase SHA-256 `sha256`.
Each record has unique nonempty `id`, timezone-aware `observed_at`, nonempty
`metric`, and numeric `value` from 0 to 1,000,000. Missing fields, invalid
JSON, blank lines, duplicate IDs, and tampering are rejected.

## Engineering walkthrough

1. Run the tests and Docker smoke check in CI.
2. Show a one-character dataset edit failing checksum validation with exit 1.
3. Explain why checksums protect integrity but do not authenticate the source.
4. Show the duplicate ID error with its line number, then discuss schema v2.

The current implementation reads the full dataset into memory. Production use
on large datasets should stream bytes while hashing and validate incrementally.
