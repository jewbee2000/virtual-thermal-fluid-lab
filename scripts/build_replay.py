"""Export retained SIL evidence as a self-contained, offline static replay.

This is a presentation adapter, not a second evaluator. Original files are copied
as bytes after checking the executed manifest. Display unit conversions do not
change raw evidence, criteria, timestamps or evaluator outcomes.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
THERMAL_FIELDS = (
    "sample_id", "record_type", "time_s", "time_us", "epoch", "session_origin_us",
    "reply_time_us", "controller_state", "trip_reason", "event_ids", "event_phase",
    "wall_temperature_k", "hot_temperature_k", "cold_temperature_k", "flow_m3_s",
    "observed_wall_temperature_k", "observed_hot_temperature_k", "observed_cold_temperature_k",
    "observed_flow_m3_s", "observed_separate_trip", "pump_speed", "valve_opening",
    "requested_heat_command", "requested_pump_command", "requested_valve_command",
    "lease_heat_command", "lease_pump_command", "lease_valve_command",
    "fault_heat_command", "fault_pump_command", "fault_valve_command", "applied_heat_w",
    "command_expires_us", "command_expired", "terminal_boundary", "energy_residual_j",
    *(f"{p}_{f}" for p in ("flow", "hot", "cold", "wall", "separate") for f in
      ("quality", "source_time_us", "receipt_time_us", "last_good_source_time_us", "age_us")),
)
TANK_FIELDS = ("sample_id", "record_type", "time_s", "time_us", "level_m", "measured_level_m",
               "flow_m3_s", "pump_command", "requested_valve_command", "applied_pump_command",
               "applied_valve_command", "valve_opening", "target_m", "trip", "sensor_valid",
               "sample_time_s", "receipt_time_s", "measurement_age_s", "volume_residual_m3",
               "controller_state", "lease_pump_command", "lease_valve_command", "command_expired")
TEXT_FIELDS = {"record_type", "controller_state", "trip_reason", "event_ids", "event_phase",
               "terminal_boundary", "trip"}
BOOL_FIELDS = {"command_expired", "sensor_valid"}
REQUIRED_THERMAL = {"sample_id", "record_type", "time_s", "time_us", "wall_temperature_k",
                    "hot_temperature_k", "cold_temperature_k", "flow_m3_s",
                    "requested_heat_command", "requested_pump_command", "requested_valve_command",
                    "lease_heat_command", "lease_pump_command", "lease_valve_command",
                    "fault_heat_command", "fault_pump_command", "fault_valve_command",
                    "pump_speed", "valve_opening", "controller_state", "trip_reason"}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                      parse_constant=lambda v: (_ for _ in ()).throw(ValueError(f"nonfinite JSON: {v}")))


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _safe_relative(name):
    if not isinstance(name, str) or "\\" in name:
        raise ValueError("artifact paths must be relative POSIX paths")
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(p in ("..", ".") or ":" in p for p in path.parts):
        raise ValueError(f"unsafe artifact path: {name}")
    return path


def _cell(name, value):
    if value == "":
        return None
    if name in TEXT_FIELDS:
        return value
    if name in BOOL_FIELDS:
        if value.lower() not in ("true", "false", "0", "1"):
            raise ValueError(f"invalid boolean in {name}")
        return value.lower() in ("true", "1")
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"invalid numeric cell in {name}") from exc
    if not math.isfinite(number):
        raise ValueError(f"nonfinite telemetry in {name}")
    return int(value) if re.fullmatch(r"-?[0-9]+", value) else number


def read_run(source, *, allow_ui_fixture=False):
    """Verify an input run without executing or reassessing its controller."""
    source = Path(source).resolve()
    raw_manifest = (source / "manifest.json").read_bytes()
    manifest = _read_json(raw_manifest)
    hashes = manifest.get("artifacts", manifest.get("artifact_sha256"))
    if not isinstance(hashes, dict) or not {"telemetry.csv", "summary.json"} <= hashes.keys():
        raise ValueError("manifest must hash telemetry.csv and summary.json")
    assets = {"manifest.json": raw_manifest}
    for name, expected in hashes.items():
        relative = _safe_relative(name)
        path = source.joinpath(*relative.parts).resolve()
        if not path.is_relative_to(source):
            raise ValueError("artifact symlink leaves run directory")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
            raise ValueError(f"invalid SHA256 for {name}")
        raw = path.read_bytes()
        if _digest(raw) != expected.lower():
            raise ValueError(f"artifact SHA256 mismatch: {name}")
        assets[name] = raw
    summary = _read_json(assets["summary.json"])
    fixture = summary.get("execution", {}).get("evidence_level") == "UI_FIXTURE"
    if fixture and not allow_ui_fixture:
        raise ValueError("UI_FIXTURE is not verification; pass --allow-ui-fixture only for development")
    thermal = summary.get("topology") == "thermal_loop"
    topology = "thermal_loop" if thermal else "atmospheric_tank"
    if summary.get("topology") not in (None, topology):
        raise ValueError("unsupported topology")
    reader = csv.DictReader(io.StringIO(assets["telemetry.csv"].decode("utf-8"), newline=""))
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError("missing or duplicate telemetry columns")
    required = REQUIRED_THERMAL if thermal else {"time_s", "level_m", "measured_level_m", "pump_command"}
    if not required <= set(reader.fieldnames):
        raise ValueError(f"missing replay telemetry columns: {sorted(required-set(reader.fieldnames))}")
    fields = [f for f in (THERMAL_FIELDS if thermal else TANK_FIELDS) if f in reader.fieldnames]
    rows = []
    previous_time = -math.inf
    previous_id = None
    for raw_row in reader:
        if None in raw_row or any(v is None for v in raw_row.values()):
            raise ValueError("malformed CSV row")
        row = {name: _cell(name, raw_row[name]) for name in fields}
        now = row.get("time_s")
        if isinstance(now, bool) or not isinstance(now, (int, float)) or now < 0 or now < previous_time:
            raise ValueError("telemetry time must be finite, nonnegative and nondecreasing")
        sample_id = row.get("sample_id")
        if thermal and (type(sample_id) is not int or sample_id < 0 or
                        (previous_id is not None and sample_id <= previous_id)):
            raise ValueError("thermal sample_id must strictly increase, including duplicate event times")
        if thermal and abs(row["time_us"] / 1e6 - now) > 1e-9:
            raise ValueError("telemetry clocks disagree")
        previous_time, previous_id = now, sample_id
        rows.append(row)
    if not rows and not summary.get("run_failure"):
        raise ValueError("empty telemetry without an explicit run failure")
    name = summary.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,96}", name):
        raise ValueError("run name must be a short filename-safe identifier")
    embedded_summary = {key: value for key, value in summary.items()
                        if key not in ("solver_diagnostics", "wire_evidence")}
    wire = summary.get("wire_evidence")
    if isinstance(wire, dict):
        embedded_summary["wire_evidence"] = {
            "status": wire.get("status"), "issues": wire.get("issues"),
            "counts": {key: len(value) for key, value in wire.items() if isinstance(value, list)}}
    # Column arrays avoid repeating JSON keys. Every source row is preserved,
    # including event duplicates and terminal roots; no decimation is applied.
    return dict(name=name, topology=topology, evidence_level="UI_FIXTURE NOT_VERIFICATION" if fixture else "RETAINED_SIL_EVIDENCE",
                fields=fields, columns=[[row[f] for row in rows] for f in fields], summary=embedded_summary,
                manifest=manifest, raw_hashes={k: _digest(v) for k, v in assets.items()}), assets, rows


def _fallback(run, rows, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(10, 7.5), sharex=True, constrained_layout=True)
    times = [row["time_s"] for row in rows]
    thermal = run["topology"] == "thermal_loop"
    if thermal:
        for prefix, color in (("wall", "#ad3c19"), ("hot", "#b77300"), ("cold", "#1266a2")):
            axes[0].plot(times, [r[prefix+"_temperature_k"] - 273.15 for r in rows], label=prefix+" truth", color=color)
            stale = run["summary"].get("controller", {}).get("stale_us", 300000)
            values = [r.get("observed_"+prefix+"_temperature_k") for r in rows]
            values = [v - 273.15 if v is not None and r.get(prefix+"_quality") == 1 and
                      r.get(prefix+"_age_us") is not None and r[prefix+"_age_us"] <= stale else math.nan
                      for r, v in zip(rows, values)]
            axes[0].step(times, values, where="post", label=prefix+" observed", color=color, linestyle="--")
        cfg = run["summary"].get("controller", {})
        for key, label in (("hot_trip_mK", "hot trip"), ("wall_trip_mK", "wall trip")):
            value = cfg.get(key)
            if value is not None:
                axes[0].axhline(value/1000-273.15, color="#666666", linestyle=":", label=label)
        axes[0].set_ylabel("Temperature (°C)")
        axes[1].plot(times, [r["flow_m3_s"]*60000 for r in rows], color="#1266a2", label="flow truth")
        axes[1].set_ylabel("Flow (L/min)")
        for field, label, style in (("requested_heat_command", "heat requested", "-"),
                                    ("lease_heat_command", "heat leased", "--"),
                                    ("fault_heat_command", "heat applied", ":"),
                                    ("pump_speed", "pump actual", "-")):
            axes[2].step(times, [r.get(field, math.nan) for r in rows], where="post", label=label, linestyle=style)
    else:
        axes[0].plot(times, [r["level_m"] for r in rows], label="level truth")
        axes[0].step(times, [r["measured_level_m"] if r.get("sensor_valid", True) and r.get("measurement_age_s", 0) <= .3
                            else math.nan for r in rows], where="post", label="level observed", linestyle="--")
        axes[0].set_ylabel("Level (m)")
        axes[1].plot(times, [r.get("flow_m3_s", math.nan)*60000 for r in rows], label="pump inflow truth")
        axes[1].set_ylabel("Flow (L/min)")
        for field, label in (("pump_command", "pump requested"), ("applied_pump_command", "pump applied")):
            axes[2].step(times, [r.get(field, math.nan) for r in rows], where="post", label=label)
    for axis in axes:
        axis.grid(alpha=.2)
        handles, _ = axis.get_legend_handles_labels()
        if handles:
            axis.legend(loc="best", fontsize=8, ncols=3)
    axes[2].set_ylabel("Normalized (0–1)")
    axes[2].set_xlabel("Absolute simulation time (s); source rows, no inserted samples")
    evaluation = run["summary"].get("evaluation", {})
    containment = evaluation.get("containment_status", run["summary"].get("containment", "unavailable"))
    fig.suptitle(f"{run['name']} · {run['evidence_level']} · containment: {containment}\nAssumed model; physical validation NOT_STARTED; board NOT_EXECUTED", fontsize=11)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def _pack_download(name, raw, compress_raw):
    """Lossless download packaging; no source bytes or displayed rows change."""
    compressed = compress_raw and (name == "summary.json" or PurePosixPath(name).parts[0] == "wire")
    if not compressed:
        return name, raw, "identity"
    buffer = io.BytesIO()
    # Explicit empty filename and mtime=0 make headers deterministic. GzipFile
    # also emits a platform-independent OS header rather than the fast-path
    # gzip.compress(mtime=0) header used by some Python/zlib combinations.
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, compresslevel=6, mtime=0) as stream:
        stream.write(raw)
    return name + ".gz", buffer.getvalue(), "gzip"


def build_replay(sources, out, *, allow_ui_fixture=False, screenshots=True, compress_raw=False):
    out = Path(out).resolve()
    sources = [Path(source).resolve() for source in sources]
    if not sources:
        raise ValueError("at least one retained run is required")
    if out.exists():
        raise ValueError("output must be a new directory; existing evidence is never replaced")
    if any(out.is_relative_to(source) or source.is_relative_to(out) for source in sources):
        raise ValueError("output must be separate from input evidence")
    prepared = [read_run(source, allow_ui_fixture=allow_ui_fixture) for source in sources]
    names = [run[0]["name"] for run in prepared]
    if len(set(names)) != len(names):
        raise ValueError("run names must be unique")
    for _, assets, _ in prepared:
        packaged_names = [str(PurePosixPath(name + ".gz" if compress_raw and
                          (name == "summary.json" or PurePosixPath(name).parts[0] == "wire") else name))
                          for name in assets]
        if len(set(packaged_names)) != len(packaged_names):
            raise ValueError("download packaging paths collide; no source artifact may be omitted")
    # Inputs are all checked before the output directory is created.
    shutil.copytree(ROOT / "web", out)
    # The standalone bundle redistributes project-authored HTML/CSS/JS. Retain
    # their actual root license as bytes, alongside the vendored uPlot license.
    (out / "LICENSE.txt").write_bytes((ROOT / "LICENSE").read_bytes())
    runs = []
    for run, assets, rows in prepared:
        raw_dir = out / "raw" / run["name"]
        run["downloads"] = {}
        run["download_metadata"] = {}
        for name, raw in assets.items():
            packaged_name, packaged, encoding = _pack_download(name, raw, compress_raw)
            relative = f"raw/{run['name']}/{packaged_name}"
            target = raw_dir.joinpath(*PurePosixPath(packaged_name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(packaged)
            run["downloads"][name] = relative
            run["download_metadata"][name] = dict(path=relative, encoding=encoding,
                filename=PurePosixPath(packaged_name).name, label=name + (" (gzip)" if encoding == "gzip" else ""),
                original_sha256=run["raw_hashes"][name], file_sha256=_digest(packaged))
        if screenshots:
            target = out / "fallback" / (run["name"] + ".png")
            target.parent.mkdir(parents=True, exist_ok=True)
            _fallback(run, rows, target)
            run["screenshot"] = f"fallback/{run['name']}.png"
        runs.append(run)
    payload = dict(schema_version=1, display_policy="full source rows; no decimation; absolute simulation seconds; no inserted/interpolated samples",
                   raw_packaging="plain_or_lossless_gzip" if compress_raw else "plain",
                   physical_validation="NOT_STARTED", board_execution="NOT_EXECUTED", runs=runs)
    if screenshots:
        index_path = out / "index.html"
        html = index_path.read_text(encoding="utf-8")
        first = runs[0]["screenshot"]
        html = html.replace('<a href="fallback/">static figures</a>',
                            f'<a href="{first}">static figure</a>')
        index_path.write_text(html, encoding="utf-8", newline="\n")
    (out / "data.js").write_text("window.FLUIDLAB_REPLAY=" + json.dumps(payload, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + ";\n", encoding="utf-8", newline="\n")
    index = dict(schema_version=1, runs=names, display_policy=payload["display_policy"],
                 raw_packaging=payload["raw_packaging"],
                 gzip_settings=dict(mtime=0, filename="", compresslevel=6) if compress_raw else None,
                 artifacts={p.relative_to(out).as_posix(): _digest(p.read_bytes()) for p in sorted(out.rglob("*")) if p.is_file()})
    (out / "replay-manifest.json").write_text(json.dumps(index, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, action="append", required=True, help="run folder containing manifest, summary and telemetry; repeat to compare")
    parser.add_argument("--out", type=Path, required=True, help="new output directory")
    parser.add_argument("--allow-ui-fixture", action="store_true")
    parser.add_argument("--no-screenshots", action="store_true", help="skip static PNG fallbacks for development only")
    parser.add_argument("--compress-raw", action="store_true", help="hosted-site option: lossless deterministic gzip for summary.json and wire/** downloads; CSV/manifests/configs remain plain")
    args = parser.parse_args()
    result = build_replay(args.run, args.out, allow_ui_fixture=args.allow_ui_fixture,
                          screenshots=not args.no_screenshots, compress_raw=args.compress_raw)
    print(json.dumps({"runs": result["runs"], "artifacts": len(result["artifacts"]), "index": str(args.out / "index.html")}, indent=2))


if __name__ == "__main__":
    main()
