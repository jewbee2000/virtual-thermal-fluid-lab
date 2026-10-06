"""Validate frozen schemas and retained thermal exports without the runner.

Use the separately pinned audit tool: uv run --no-project --python 3.12
--with jsonschema==4.25.1 python scripts/audit_exports.py --run RUN_DIRECTORY
The simulation dependencies and lockfile are not changed.
"""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path, PurePosixPath
from jsonschema import Draft202012Validator
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError(f"nonfinite JSON token: {value}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique, parse_constant=invalid)


def allowed_types(definition):
    kind = definition.get("type")
    found = set(kind if isinstance(kind, list) else [kind] if kind else [])
    values = definition.get("enum", []) + ([definition["const"]] if "const" in definition else [])
    for value in values:
        found.add("null" if value is None else "boolean" if type(value) is bool else
                  "integer" if type(value) is int else "number" if type(value) is float else "string")
    for branch in definition.get("anyOf", []):
        found.update(allowed_types(branch))
    return found


def decode_cell(value, kinds):
    if value == "" and "null" in kinds:
        return None
    if "boolean" in kinds:
        return {"True": True, "False": False}[value]
    if "integer" in kinds:
        if "." not in value and "e" not in value.lower():
            return int(value)
        numeric = float(value)
        if not numeric.is_integer():
            raise ValueError(f"non-integral integer cell: {value}")
        return int(numeric)
    if "number" in kinds:
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError(f"nonfinite CSV cell: {value}")
        return numeric
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, action="append", default=[])
    parser.add_argument("--skip-rows", action="store_true", help="explicit summary/manifest-only audit")
    args = parser.parse_args()
    schemas, resources = {}, []
    for path in sorted((ROOT / "schemas").glob("*.schema.json")):
        value = read_json(path)
        Draft202012Validator.check_schema(value)
        value = {**value, "$id": path.as_uri()}
        schemas[path.name] = value
        resources.append((path.as_uri(), Resource.from_contents(value)))
    registry = Registry().with_resources(resources)
    validators = {name: Draft202012Validator(value, registry=registry) for name, value in schemas.items()}
    scenario_count = 0
    for path in sorted((ROOT / "scenarios" / "thermal").glob("*.json")):
        validators["thermal-campaign-v1.schema.json"].validate(read_json(path))
        scenario_count += 1
    kinds = {name: allowed_types(value) for name, value in schemas["thermal-telemetry-row-v1.schema.json"]["properties"].items()}
    run_count = row_count = artifact_count = 0
    for directory in args.run:
        before = run_count
        for path in sorted(directory.rglob("summary.json")):
            summary = read_json(path)
            if summary.get("topology") != "thermal_loop":
                continue
            manifest = read_json(path.with_name("manifest.json"))
            validators["thermal-summary-v1.schema.json"].validate(summary)
            validators["thermal-manifest-v1.schema.json"].validate(manifest)
            base = path.parent.resolve()
            for name, digest in manifest["artifacts"].items():
                relative = PurePosixPath(name)
                if relative.is_absolute() or ".." in relative.parts or "\\" in name:
                    raise ValueError(f"unsafe artifact path: {name}")
                target = base.joinpath(*relative.parts).resolve()
                if not target.is_relative_to(base) or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                    raise ValueError(f"artifact hash/path mismatch: {target}")
                artifact_count += 1
            if not args.skip_rows:
                with path.with_name("telemetry.csv").open(newline="", encoding="utf-8") as stream:
                    reader = csv.DictReader(stream)
                    if reader.fieldnames is None or len(set(reader.fieldnames)) != len(reader.fieldnames):
                        raise ValueError("missing or duplicate CSV columns")
                    for raw in reader:
                        row = {name: decode_cell(value, kinds[name]) for name, value in raw.items()}
                        validators["thermal-telemetry-row-v1.schema.json"].validate(row)
                        row_count += 1
            run_count += 1
        if run_count == before:
            raise ValueError(f"no retained thermal runs in {directory}")
    print(json.dumps(dict(jsonschema=importlib.metadata.version("jsonschema"), schemas=len(schemas),
        scenarios=scenario_count, thermal_runs=run_count, telemetry_rows=row_count,
        artifact_hashes=artifact_count, row_scope="SKIPPED" if args.skip_rows else "ALL_ROWS",
        status="PASS"), indent=2))


if __name__ == "__main__":
    main()
