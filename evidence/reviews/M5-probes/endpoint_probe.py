"""Coherent truncation must fail because the final scheduled C tick is missing."""
from copy import deepcopy
import json
from pathlib import Path
from fluidlab.campaign import normalize_campaign, run_campaign
from fluidlab.campaign_evaluator import audit_wire, evaluate_campaign, parse_retained_line

root=Path.cwd()
out=root/"artifacts/reviews/M5-test-review/endpoint"
cfg=normalize_campaign(dict(name="endpoint_review",case_id="near_tick_before",duration_us=2_000_000,
    initial=dict(wall_temperature_k=317.7911483254,hot_temperature_k=301.1244816587,cold_temperature_k=293.15,pump_speed=.5274982823,valve_opening=.65),
    initial_heat_demand=1.,events=[dict(event_id="arm",type="operation",time_us=0,operation="ARM"),
        dict(event_id="flow",type="observation_link",time_us=599000,end_us=1500000,channel=2,mode="drop")]))
rows,summary=run_campaign(cfg,root/"artifacts/host-build/Release/fluid_controller_host.exe",out/"wire")
assert summary["evaluation"]["expectation_pass"]
base=out/"wire/epoch-1"
for name in ("stdin.bin","stdout.bin"):
    raw=(base/name).read_bytes()
    # Keep retained original bytes for comparison; mutate only review artifacts.
    (base/(name+".original")).write_bytes(raw)
    (base/name).write_bytes(b"".join(line for line in raw.splitlines(keepends=True)
        if parse_retained_line(line)["time_us"]!=2_000_000))
events=(base/"events.jsonl").read_bytes()
(base/"events.jsonl.original").write_bytes(events)
retained=[]
for line in events.splitlines():
    e=json.loads(line)
    if e.get("absolute_time_us")==2_000_000 or e.get("absolute_receipt_us")==2_000_000:
        continue
    retained.append(line+b"\n")
(base/"events.jsonl").write_bytes(b"".join(retained))
sessions=[dict(path=s["trace_dir"],epoch=s["epoch"],session_origin_us=s["session_origin_us"],process_pid=s["process_pid"])
          for s in summary["wire_evidence"]["sessions"]]
wire=audit_wire(sessions,cfg.controller)
assert wire["status"]=="PASS",wire["issues"]
truncated=deepcopy(rows[:-1])
forged=deepcopy(truncated[-1])
forged.update(sample_id=len(truncated),time_us=2_000_000,time_s=2.,wire_time_us=2_000_000,
              record_type="command_arrival",controller_tick_id=None)
for prefix in ("flow","hot","cold","wall","separate"):
    forged[f"{prefix}_age_us"]=2_000_000-forged[f"{prefix}_last_good_source_time_us"]
truncated.append(forged)
judgment=evaluate_campaign(cfg,truncated,wire)
assert not judgment["expectation_pass"] and judgment["completion_status"]=="UNASSESSABLE"
assert "incomplete/out-of-order absolute tick schedule" in judgment["evidence_errors"],judgment
result=dict(probe="coherent_whole_final_transaction_removal",raw_wire_audit_status=wire["status"],
            retained_last_tick_us=wire["ticks"][-1]["time_us"],forged_snapshot_time_us=forged["time_us"],
            expectation_pass=judgment["expectation_pass"],completion_status=judgment["completion_status"],evidence_errors=judgment["evidence_errors"])
(out/"endpoint-result.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
print(json.dumps(result,sort_keys=True))
