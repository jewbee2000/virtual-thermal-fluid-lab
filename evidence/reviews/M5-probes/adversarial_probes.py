"""Read-only source review probes; all mutations are retained review artifacts."""
from copy import deepcopy
from dataclasses import asdict
import binascii
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

from fluidlab.campaign import case_config, normalize_campaign, run_campaign, write_campaign
from fluidlab.campaign_evaluator import audit_wire, evaluate_campaign
from fluidlab.c_controller import CController
from fluidlab.protocol import Configuration

ROOT = Path.cwd()
OUT = ROOT / "artifacts/reviews/M5-test-review"
HOST = ROOT / "artifacts/host-build/Release/fluid_controller_host.exe"
results = []


def record(name, **evidence):
    item = dict(probe=name, **evidence)
    results.append(item)
    print(json.dumps(item, sort_keys=True), flush=True)
    (OUT / "adversarial-results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


def literal(frame):
    body = "|".join(map(str, ("F", 1, frame["type"], frame["epoch"], frame["sequence"], frame["clock"], frame["time_us"], *frame["payload"]))).encode("ascii")
    return body + f"*{binascii.crc_hqx(body, 0):04X}\n".encode("ascii")


def short(case, fault):
    return normalize_campaign(dict(name="independent_review_fixture", case_id=case, duration_us=2_000_000,
        initial=dict(wall_temperature_k=317.7911483254, hot_temperature_k=301.1244816587, cold_temperature_k=293.15,
                     pump_speed=.5274982823, valve_opening=.65), initial_heat_demand=1.,
        events=[dict(event_id="arm", type="operation", time_us=0, operation="ARM"), fault]))


def sessions(summary):
    return [dict(path=s["trace_dir"], epoch=s["epoch"], session_origin_us=s["session_origin_us"], process_pid=s["process_pid"])
            for s in summary["wire_evidence"]["sessions"]]


cfg = short("near_tick_before", dict(event_id="flow", type="observation_link", time_us=599000,
                                     end_us=1500000, channel=2, mode="drop"))
run = OUT / "near-tick"
run.mkdir(exist_ok=False)
rows, summary = run_campaign(cfg, HOST, run / "wire")
assert summary["evaluation"]["expectation_pass"]
assert summary["metrics"]["first_trip_time_us"] == 900000
manifest = write_campaign(run, cfg, rows, summary, HOST)
assert summary["execution"]["configuration_scope"] == "VARIANT"
assert all(type(s["process_pid"]) is int and s["process_pid"] > 0 for s in summary["wire_evidence"]["sessions"])
assert all(Path(p).is_file() for p in [run / name for name in manifest["artifacts"]])
record("actual_near_tick_positive", expectation_pass=True, first_trip_time_us=900000,
       configuration_scope=summary["execution"]["configuration_scope"], actual_c_pids=[s["process_pid"] for s in summary["wire_evidence"]["sessions"]])

before = next(i for i, r in enumerate(rows) if r["event_phase"] == "before")
mutations = [(before, "observed_hot_temperature_k", 301.), (before, "controller_state", "DISARMED"),
             (before, "requested_pump_command", 0.), (before, "operation_result", 2),
             (before, "flow_value_i", 99999), (before, "reply_time_us", 400000),
             (1, "epoch", True), (1, "observed_separate_trip", float("inf")), (1, "time_us", True)]
for index, field, value in mutations:
    corrupted = deepcopy(rows)
    corrupted[index][field] = value
    judgment = evaluate_campaign(cfg, corrupted, summary["wire_evidence"])
    assert judgment["completion_status"] == "UNASSESSABLE" and not judgment["expectation_pass"], (field, judgment)
record("tick_and_snapshot_mutations", rejected=len(mutations), status="UNASSESSABLE")

base = run / "wire/epoch-1"
original_events = (base / "events.jsonl").read_bytes()
events = [json.loads(line) for line in original_events.splitlines()]
disposition = next(e for e in events if e["event"] == "command_disposition")
disposition["accepted"] = not disposition["accepted"]
(base / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
audit = audit_wire(sessions(summary), cfg.controller)
assert audit["status"] == "UNASSESSABLE" and any("independent lease" in s for s in audit["issues"])
(base / "events.jsonl").write_bytes(original_events)
record("contradictory_command_acceptance_label", status=audit["status"], issues=audit["issues"])

original_stdout = (base / "stdout.bin").read_bytes()
(base / "stdout.bin").write_bytes(b"".join(original_stdout.splitlines(keepends=True)[:-1]))
audit = audit_wire(sessions(summary), cfg.controller)
assert audit["status"] == "UNASSESSABLE" and not evaluate_campaign(cfg, rows, audit)["expectation_pass"]
(base / "stdout.bin").write_bytes(original_stdout)
record("actual_retained_final_reply_removed", status=audit["status"], issues=audit["issues"])

future = OUT / "future-error-wire"
configuration = Configuration.thermal()
c = CController(HOST, configuration, trace_dir=future)
pid = c.process.pid
for tick in range(5):
    at = tick * 100000
    observations = [(ch, tick, at, 1, value) for ch, value in ((3,301124),(4,293150),(5,317791),(6,0))]
    if tick == 0:
        observations.append((2, 0, 0, 1, 150000))
    elif tick == 1:
        observations.append((2, 10, 200000, 1, 100000))  # Future sample cannot refresh.
    elif tick == 2:
        observations.append((2, 2, 100000, 0, 99999))  # Error quality retains last-good source0.
    elif tick == 3:
        observations.append((2, 3, 0, 1, 150000))  # New sequence cannot regress source time.
    c.step(at, observations, operation=1 if tick == 0 else 0)
c.close()
audit = audit_wire([dict(path=str(future), epoch=1, session_origin_us=0, process_pid=pid)], configuration)
assert audit["status"] == "PASS", audit
flow = [d for d in audit["observation_dispositions"] if d["frame"]["payload"][0] == 2]
assert [d["accepted"] for d in flow] == [True, False, True, False]
last = audit["ticks"][-1]
assert last["cache"]["2"]["last_good_source_time_us"] == 0
assert last["cache"]["2"]["quality"] == 0
assert last["reply"]["payload"][1:3] == [2, 4]
assert last["reply"]["payload"][5] == 400000
record("actual_future_error_quality_last_good", audit_status="PASS", acceptance=[True, False, True, False],
       final_last_good_source_time_us=0, final_max_age_us=400000, state="TRIPPED", trip_reason="invalid_input")

ackcfg = short("dropped_ack", dict(event_id="ack", type="command_link", time_us=500000, end_us=1000000, mode="drop_ack"))
ackrun = OUT / "dropped-ack"
ackrun.mkdir(exist_ok=False)
ackrows, acksummary = run_campaign(ackcfg, HOST, ackrun / "wire")
assert acksummary["evaluation"]["rules"]["TH08"]["status"] == "PASS"
ackbase = ackrun / "wire/epoch-1"
ackevents = [json.loads(line) for line in (ackbase / "events.jsonl").read_bytes().splitlines()]
drop = next(e for e in ackevents if e["event"] == "ack_dropped")
ackstdin = (ackbase / "stdin.bin").read_bytes()
(ackbase / "stdin.bin").write_bytes(ackstdin + literal(drop["frame"]))
audit = audit_wire(sessions(acksummary), ackcfg.controller)
assert audit["status"] == "UNASSESSABLE" and any("ACK declared dropped" in s for s in audit["issues"])
(ackbase / "stdin.bin").write_bytes(ackstdin)
record("contradictory_ack_drop_raw_bytes", status=audit["status"], issues=audit["issues"])

sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("review_run_campaign", ROOT / "scripts/run_campaign.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
modified = case_config("nominal_heat_step").to_dict()
modified["controller"]["wall_trip_mK"] -= 1000
variant = normalize_campaign(modified)
with patch.object(release, "load_campaign", return_value=variant), patch.object(release, "run_campaign") as execute, \
     patch.object(sys, "argv", ["run_campaign.py", "--exe", str(HOST), "--out", str(OUT / "release-guard"), "--case", "nominal_heat_step", "--skip-tank"]):
    try:
        release.main()
    except ValueError as exc:
        assert "cannot satisfy frozen release campaign" in str(exc)
    else:
        raise AssertionError("modified trip threshold passed release guard")
    execute.assert_not_called()
record("changed_trip_threshold_release_guard", rejected_before_execution=True, variant_wall_trip_mK=variant.controller.wall_trip_mK)
record("all_independent_review_probes", status="PASS", count=len(results))
