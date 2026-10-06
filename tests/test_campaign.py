"""Independent timing/transport oracles and corrupted evidence probes for M5."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import binascii
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from fluidlab.campaign import (CASE_IDS, INPUT_FIELDS, MANIFEST_FIELDS, SUMMARY_FIELDS, TELEMETRY_FIELDS,
    case_config, load_campaign, normalize_campaign, run_campaign, write_campaign)
from fluidlab.campaign_evaluator import audit_wire, campaign_metrics, dropout_oracle_us, evaluate_campaign, parse_retained_line
from fluidlab.c_controller import CController, ControllerProcessFailure
from fluidlab.protocol import Configuration
from fluidlab.provenance import PROJECT_ROOT, SOURCE_EXCLUSION, execution_provenance, source_hash
with patch.object(sys,"path",[str(PROJECT_ROOT/"scripts"),*sys.path]):
    from refine_campaign import boundary_comparison, common_prefix_peak
    from benchmark_campaign import retained_process_pids


DEFAULT_HOST = PROJECT_ROOT/("artifacts/host-build/Release/fluid_controller_host.exe" if os.name=="nt" else "artifacts/host-build/fluid_controller_host")
HOST = Path(os.environ.get("FL_CONTROLLER_HOST",DEFAULT_HOST))


def literal(body):
    body = body.encode("ascii")
    return body+f"*{binascii.crc_hqx(body,0):04X}\n".encode("ascii")


def short(case="nominal_heat_step",**changes):
    cfg = dict(name="fixture",case_id=case,duration_us=2_000_000,
               initial=dict(wall_temperature_k=317.7911483254,hot_temperature_k=301.1244816587,cold_temperature_k=293.15,pump_speed=.5274982823,valve_opening=.65),
               initial_heat_demand=1.,events=[dict(event_id="arm",type="operation",time_us=0,operation="ARM")])
    cfg.update(changes)
    return normalize_campaign(cfg)


def observations(tick,flow=True):
    now = tick*100000
    return [(ch,tick,now,1,val) for ch,val in ((2,150000),(3,301124),(4,293150),(5,317791),(6,0)) if ch!=2 or flow]


class CampaignContractTests(unittest.TestCase):
    def test_recursive_actual_pid_coverage_includes_tank_and_rejects_bad_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            paths=[root/"nominal_heat_step/wire/epoch-1",root/"tank/nominal/wire"]
            records=[]
            for index,path in enumerate(paths):
                path.mkdir(parents=True)
                session=dict(event="session",host_monotonic_s=1.,epoch=1,session_origin_us=0)
                start=dict(event="process_started",host_monotonic_s=1.1,process_pid=100+index,
                           command=["controller.exe"],epoch=1,session_origin_us=0)
                raw="".join(json.dumps(e)+"\n" for e in (session,start))
                (path/"events.jsonl").write_text(raw,encoding="utf-8")
                (path/"stdin.bin").write_bytes(b"actual capture")
                records.append((session,start,raw))
            self.assertEqual(sorted(retained_process_pids(root)[0]),[100,101])
            self.assertEqual(retained_process_pids(root)[1],[])
            session,start,raw=records[1]
            for changed in ({**start,"process_pid":True},{**start,"process_pid":None},
                            {**start,"epoch":2},{**start,"command":[]}):
                (paths[1]/"events.jsonl").write_text(json.dumps(session)+"\n"+json.dumps(changed)+"\n",encoding="utf-8")
                self.assertTrue(retained_process_pids(root)[1])
            for changed in (json.dumps(session)+"\n",raw+"{partial",raw+json.dumps(start)+"\n"):
                (paths[1]/"events.jsonl").write_text(changed,encoding="utf-8")
                self.assertTrue(retained_process_pids(root)[1])
            (paths[1]/"events.jsonl").unlink()
            self.assertTrue(retained_process_pids(root)[1])

    def test_common_prefix_rejects_synthetic_equal_cap_false_convergence(self):
        thermal=lambda t,value,kind="controller_tick":dict(time_s=t,time_us=int(t*1e6),record_type=kind,event_phase=None,
                                                           wall_temperature_k=value,hot_temperature_k=300.,cold_temperature_k=290.)
        a=[thermal(0,300),thermal(.1,350),thermal(.19,368.15,"terminal_boundary")]
        b=[thermal(0,300),thermal(.1,351),thermal(.2,368.15,"terminal_boundary")]
        self.assertEqual(max(r["wall_temperature_k"] for r in a),max(r["wall_temperature_k"] for r in b))
        result=common_prefix_peak(a,b,topology="thermal")
        self.assertEqual(result["last_time_s"],.1)
        self.assertEqual(result["matching_samples"],2)
        self.assertAlmostEqual(result["peak_bound_delta"],1.,places=12)
        self.assertGreater(result["peak_bound_delta"],.1)
        tank=lambda t,h,kind="controller_tick":dict(time_s=str(t),record_type=kind,level_m=str(h))
        a=[tank(0,.5),tank(.1,.95),tank(.19,1.,"terminal_boundary")]
        b=[tank(0,.5),tank(.1,.96),tank(.2,1.,"terminal_boundary")]
        result=common_prefix_peak(a,b,topology="tank")
        self.assertAlmostEqual(result["peak_bound_delta"],.01,places=12)
        self.assertGreater(result["peak_bound_delta"],.002)
        initial=[thermal(0,300),{**thermal(0,300),"record_type":"event_boundary","event_phase":"after"}]
        self.assertEqual(common_prefix_peak(initial,initial,topology="thermal")["status"],"UNASSESSABLE")

    def test_terminal_presence_kind_and_raw_fractional_time_gate(self):
        rows=lambda t:[dict(time_s=t,time_us=None,record_type="terminal_boundary")]
        full=dict(boundary="full")
        okay=boundary_comparison(rows("10.0123456789"),full,rows("10.1123456788"),full,topology="tank")
        self.assertEqual(okay["status"],"PASS")
        self.assertAlmostEqual(okay["boundary_time_delta_s"],.0999999999,places=10)
        self.assertEqual(boundary_comparison(rows(10.),full,[],dict(boundary=None),topology="tank")["status"],"FAIL")
        self.assertEqual(boundary_comparison(rows(10.),full,rows(10.),dict(boundary="empty"),topology="tank")["status"],"FAIL")
        self.assertEqual(boundary_comparison(rows(10.),full,rows(10.1001),full,topology="tank")["status"],"FAIL")
        self.assertEqual(boundary_comparison(rows(10.),full,[],full,topology="tank")["status"],"FAIL")
        self.assertEqual(boundary_comparison(rows(10.),dict(boundary=None),rows(10.),dict(boundary=None),topology="tank")["status"],"FAIL")

    def test_closed_file_direct_normalization_immutable(self):
        cfg = short()
        self.assertEqual(set(cfg.to_dict()),set(INPUT_FIELDS))
        with self.assertRaises(FrozenInstanceError):
            cfg.tick_us=1
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/"input.json"
            p.write_text(json.dumps(cfg.to_dict()),encoding="utf-8")
            self.assertEqual(load_campaign(p),normalize_campaign(cfg))
            p.write_text('{"name":"nominal_heat_step","seed":1,"seed":2}',encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"duplicate"):
                load_campaign(p)
        for change in (dict(seed=True),dict(duration_us=float("nan")),dict(tick_us=100000.0),dict(unknown=1),
                       dict(model=dict(max_heat_w=True)),dict(initial=dict(pump_speed=True)),dict(sensor_adapter=dict(separate_wall_trip_k=float("inf"))),
                       dict(events=[dict(event_id="a",type="command_link",time_us=100001,end_us=200000,mode="drop")])):
            with self.subTest(change=change),self.assertRaises(ValueError):
                normalize_campaign({**cfg.to_dict(),**change})

    def test_event_spans_order_overlap_and_nonfinite(self):
        base = short().to_dict()
        invalid = [dict(event_id="bad",type="observation_link",time_us=100000,end_us=100000,channel=2,mode="drop"),
                   dict(event_id="bad",type="model_coefficients",time_us=100000,sink_conductance_w_k=float("nan")),
                   dict(event_id="bad",type="observation_override",time_us=100000,channels=[3.,5],mode="bias",bias_k=-20),
                   dict(event_id="bad",type="restart",time_us=100001,epoch=2),
                   dict(event_id="bad",type="heat_demand",time_us=100000,command=2)]
        for event in invalid:
            with self.subTest(event=event),self.assertRaises(ValueError):
                normalize_campaign({**base,"events":[event]})
        one = dict(event_id="a",type="observation_link",time_us=100000,end_us=500000,channel=2,mode="drop")
        two = {**one,"event_id":"b","time_us":200000}
        with self.assertRaisesRegex(ValueError,"overlapping"):
            normalize_campaign({**base,"events":[one,two]})

    def test_frozen_cases_and_schema_fieldsets(self):
        self.assertEqual(len(CASE_IDS),17)
        for name in CASE_IDS:
            cfg = case_config(name)
            self.assertEqual(cfg,load_campaign(PROJECT_ROOT/"scenarios/thermal"/(name+".json")))
        for filename,actual in (("thermal-campaign-v1.schema.json",INPUT_FIELDS),("thermal-telemetry-row-v1.schema.json",TELEMETRY_FIELDS)):
            schema = json.loads((PROJECT_ROOT/"schemas"/filename).read_text())
            self.assertEqual(set(actual),set(schema["properties"]))
            self.assertEqual(set(actual),set(schema["required"]))

    def test_independent_stale_oracles_all_tick_ladder(self):
        # Literal expected times derived from last actual acquisition and strict
        # age>300000; equality remains fresh. No controller/ODE helper is called.
        expected = {200000:(60200000,60400000,60400000),100000:(60300000,60400000,60500000),50000:(60300000,60400000,60450000)}
        for tick,values in expected.items():
            self.assertEqual(tuple(dropout_oracle_us(at,tick,300000) for at in (60000000,60099000,60101000)),values)

    def test_retained_parser_literal_crc_not_roundtrip(self):
        raw = b"F|1|O|1|0|V|0|6|1|0*0FE2\n"
        self.assertEqual(parse_retained_line(raw)["payload"],[6,1,0])
        for invalid in (raw.replace(b"0FE2",b"0fe2"),raw.replace(b"|0*",b"|1*"),raw[:-1],raw.replace(b"\n",b"\r\n"),literal("F|1|O|1|0|V|0|2|2|1")):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                parse_retained_line(invalid)

    def test_expanded_hash_covers_firmware_and_build_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {"firmware/core/core.c":b"int a;\n","firmware/pico/CMakeLists.txt":b"project(a)\n",
                     "firmware/pico/toolchain.cmake":b"set(a 1)\n","scripts/build.ps1":b"a\n","CMakeLists.txt":b"project(a)\n"}
            for name,raw in files.items():
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
            before,paths = source_hash(root)
            self.assertEqual(set(paths),set(files))
            (root/"firmware/core/core.c").write_bytes(b"int b;\n")
            self.assertNotEqual(before,source_hash(root)[0])
            for component in ("vendor","third_party","generated","build","artifacts","out","cmake-build-debug"):
                p=root/"firmware/target"/component/"nested/excluded.c"
                p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b"generated\n")
            p=root/"firmware/core/vendor.c";p.write_bytes(b"project\n")
            self.assertEqual(set(source_hash(root)[1]),set(files)|{"firmware/core/vendor.c"})
            self.assertEqual(execution_provenance(root)["source_exclusion"],list(SOURCE_EXCLUSION))


@unittest.skipUnless(HOST.is_file(),"build actual C host first")
class RealCampaignTests(unittest.TestCase):
    def test_actual_raw_corrupt_and_lf_truncated_recovery(self):
        for mode in ("corrupt","truncate"):
            with tempfile.TemporaryDirectory() as directory,self.subTest(mode=mode):
                c=CController(HOST,Configuration.thermal(),trace_dir=Path(directory)/"wire")
                c.step(0,observations(0),operation=1,heat_demand_ppm=1000000)
                raw=literal("F|1|O|1|1|V|100000|2|1|100000")
                raw=raw.replace(b"|100000*",b"|100001*") if mode=="corrupt" else raw[:raw.index(b"*")-2]+b"\n"
                r=c.step(100000,observations(1,False),raw_observations=[raw],heat_demand_ppm=1000000)
                self.assertEqual(r.status.payload[1:3],(1,0))
                self.assertEqual(r.status.payload[5],100000)
                # Actual Q establishes unchanged cached target flow; accepting
                # corrupted100000 would instead request >=627498 ppm.
                self.assertEqual(r.raw_command.payload[2],527498)
                self.assertEqual(c.step(200000,observations(2),heat_demand_ppm=1000000).status.payload[5],0)
                c.close()
                self.assertIn(raw,(Path(directory)/"wire/stdin.bin").read_bytes())
                self.assertIn(b"rejected frame",(Path(directory)/"wire/stderr.bin").read_bytes())

    def test_no_lf_swallows_step_bounded_failure_last_reply_reaped(self):
        with tempfile.TemporaryDirectory() as directory:
            c=CController(HOST,Configuration.thermal(),trace_dir=Path(directory)/"wire",step_timeout_s=.2)
            old=c.step(0,observations(0),operation=1)
            raw=literal("F|1|O|1|1|V|100000|2|1|150000")[:-1]
            started=time.monotonic()
            with self.assertRaises(ControllerProcessFailure):
                c.step(100000,observations(1,False),raw_observations=[raw])
            self.assertLess(time.monotonic()-started,2.)
            self.assertEqual(c.last_reply,old)
            self.assertIsNotNone(c.process.poll())
            self.assertIn("process_reaped",(Path(directory)/"wire/events.jsonl").read_text())

    def test_exact_near_tick_stale_trip_and_partial_evidence_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg=short("near_tick_before",events=[dict(event_id="arm",type="operation",time_us=0,operation="ARM"),
                dict(event_id="flow",type="observation_link",time_us=599000,end_us=1500000,channel=2,mode="drop")])
            rows,summary=run_campaign(cfg,HOST,Path(directory)/"wire")
            self.assertEqual(summary["wire_evidence"]["status"],"PASS")
            self.assertEqual(summary["metrics"]["first_trip_time_us"],900000)
            self.assertEqual(summary["evaluation"]["rules"]["TH05"]["status"],"PASS")
            event=[r for r in rows if r["time_us"]==599000]
            self.assertEqual([r["event_phase"] for r in event],["before","after"])
            self.assertEqual(len([r for r in event if r["record_type"]=="controller_tick"]),0)
            bad=evaluate_campaign(cfg,rows[:-1],summary["wire_evidence"])
            self.assertFalse(bad["expectation_pass"])
            self.assertEqual(bad["completion_status"],"UNASSESSABLE")
            for key,value in (("observed_flow_m3_s",float("nan")),("observed_flow_m3_s",.000149),("controller_state","TRIPPED"),
                              ("trip_reason","wall_hot"),("operation_result",2),("operation",0),("reply_time_us",1),
                              ("flow_sequence",True),("flow_receipt_time_us",-1),("time_s",None),("record_type","fabricated"),
                              ("lease_heat_command",0.),("command_expires_us",900000000)):
                corrupt=deepcopy(rows);corrupt[1][key]=value
                result=evaluate_campaign(cfg,corrupt,summary["wire_evidence"])
                self.assertFalse(result["expectation_pass"])
                self.assertEqual(result["completion_status"],"UNASSESSABLE")
            corrupt=deepcopy(rows);corrupt[1].pop("flow_age_us")
            self.assertFalse(evaluate_campaign(cfg,corrupt,summary["wire_evidence"])["expectation_pass"])
            corrupt=deepcopy(rows);corrupt.pop(4)
            for index,r in enumerate(corrupt):
                r["sample_id"]=index
            self.assertEqual(evaluate_campaign(cfg,corrupt,summary["wire_evidence"])["completion_status"],"UNASSESSABLE")
            before_index=next(i for i,r in enumerate(rows) if r["event_phase"]=="before")
            for key,value in (("observed_flow_m3_s",.0001),("controller_state","DISARMED"),("trip_reason","range_input")):
                corrupt=deepcopy(rows);corrupt[before_index][key]=value
                self.assertEqual(evaluate_campaign(cfg,corrupt,summary["wire_evidence"])["completion_status"],"UNASSESSABLE")

    def test_lease_expiry_between_ticks_and_fault_after_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            d=short("dropped_command").to_dict();d["controller"]["lease_us"]=250000
            d["events"] += [dict(event_id="command",type="command_link",time_us=500000,end_us=1000000,mode="drop"),
                            dict(event_id="stuck",type="actuator_override",time_us=500000,heat_command=1.)]
            d["events"].sort(key=lambda e:(e["time_us"],e["event_id"]))
            cfg=normalize_campaign(d)
            rows,summary=run_campaign(cfg,HOST,Path(directory)/"wire")
            at=next(r for r in rows if r["record_type"]=="command_expiry" and r["time_us"]==650000)
            self.assertTrue(at["command_expired"])
            self.assertEqual((at["lease_heat_command"],at["lease_pump_command"],at["lease_valve_command"]),(0,1,1))
            self.assertEqual(at["fault_heat_command"],1.)
            self.assertEqual(at["applied_heat_w"],5000.)

    def test_unexpected_death_keeps_partial_trace_and_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            original=CController.step
            def killed(c,now,*args,**kw):
                if now==100000:
                    c.process.kill()
                return original(c,now,*args,**kw)
            with patch.object(CController,"step",killed):
                rows,summary=run_campaign(short(),HOST,Path(directory)/"wire")
            self.assertEqual(summary["run_failure"]["kind"],"controller_process_failure")
            self.assertEqual(rows[-1]["record_type"],"solver_failure")
            self.assertEqual(rows[-1]["flow_source_time_us"],0)
            self.assertFalse(summary["evaluation"]["expectation_pass"])
            self.assertTrue(all(s["child_reaped"] for s in summary["wire_evidence"]["sessions"]))

    def test_export_executed_solver_and_exact_fieldsets(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory);cfg=short()
            rows,summary=run_campaign(cfg,HOST,out/"wire")
            manifest=write_campaign(out,cfg,rows,summary,HOST)
            self.assertEqual(set(rows[0]),set(TELEMETRY_FIELDS))
            self.assertEqual(set(summary),set(SUMMARY_FIELDS))
            self.assertEqual(set(manifest),set(MANIFEST_FIELDS))
            self.assertEqual(summary["solver"]["atol"],[1e-8,1e-8,1e-8,1e-10,1e-10,1e-5,1e-5])
            self.assertTrue(any(k.endswith("stdin.bin") for k in manifest["artifacts"]))
            self.assertEqual(summary["execution"]["configuration_scope"],"VARIANT")
            self.assertTrue(all(type(s["process_pid"]) is int for s in summary["wire_evidence"]["sessions"]))
            retained_pids,pid_issues=retained_process_pids(out)
            self.assertEqual(pid_issues,[])
            self.assertEqual(retained_pids,[s["process_pid"] for s in summary["wire_evidence"]["sessions"]])
            changed=cfg.to_dict();changed["seed"]=2
            with self.assertRaisesRegex(ValueError,"does not match"):
                write_campaign(out,normalize_campaign(changed),rows,summary,HOST)
            with self.assertRaisesRegex(ValueError,"out/wire"):
                write_campaign(out/"external",cfg,rows,summary,HOST)
            coverage=summary["metrics"]["peak_bound_coverage"]
            self.assertEqual(coverage,dict(start_time_us=0,end_time_us=2000000,requested_end_time_us=2000000,
                                          retained_samples=len(rows),discarded_rows=0,scope="FULL_RETAINED_HORIZON"))
            prefix=campaign_metrics(cfg,rows[:-1])
            self.assertEqual(prefix["peak_bound_coverage"]["scope"],"RETAINED_PREFIX")
            self.assertEqual(prefix["peak_bound_coverage"]["end_time_us"],1900000)
            for corrupted in ([*rows,None],[rows[1],rows[0],*rows[2:]],deepcopy(rows)):
                if len(corrupted)==len(rows) and corrupted[0]["sample_id"]==0:
                    corrupted[1]["observed_flow_m3_s"]=float("nan")
                metrics=campaign_metrics(cfg,corrupted)
                self.assertIsNone(metrics["global_peak_upper_bound_k"])
                self.assertEqual(metrics["peak_bound_coverage"]["scope"],"UNAVAILABLE")

    def test_audit_rejects_raw_extra_output_config_and_malformed_events(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg=short();out=Path(directory)
            rows,summary=run_campaign(cfg,HOST,out/"wire")
            sessions=[dict(path=s["trace_dir"],epoch=s["epoch"],session_origin_us=s["session_origin_us"],process_pid=s["process_pid"]) for s in summary["wire_evidence"]["sessions"]]
            base=out/"wire/epoch-1"
            original={name:(base/name).read_bytes() for name in ("stdin.bin","stdout.bin","events.jsonl")}
            mutations=[("stdout.bin",original["stdout.bin"]+original["stdout.bin"].splitlines(keepends=True)[-1]),
                       ("stdout.bin",original["stdout.bin"]+literal("F|1|R|1|99|V|2000000|20|3|0|62|1|0|0")),
                       ("stdin.bin",original["stdin.bin"].replace(b"|C|1|0|V|0|2|1|2|",b"|C|1|0|V|0|2|1|3|")),
                       ("events.jsonl",original["events.jsonl"]+b'{"event":"command_disposition"}\n'),
                       ("events.jsonl",original["events.jsonl"]+b'{partial')]
            for name,raw in mutations:
                with self.subTest(name=name):
                    (base/name).write_bytes(raw)
                    audit=audit_wire(sessions,cfg.controller)
                    self.assertEqual(audit["status"],"UNASSESSABLE")
                    self.assertFalse(evaluate_campaign(cfg,rows,audit)["expectation_pass"])
                    (base/name).write_bytes(original[name])

    def test_coherent_final_tick_removal_and_forged_snapshot_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg=short();rows,summary=run_campaign(cfg,HOST,Path(directory)/"wire")
            corrupt=deepcopy(rows[:-1]);forged=deepcopy(corrupt[-1])
            forged.update(sample_id=len(corrupt),time_us=2000000,time_s=2.,wire_time_us=2000000,
                          record_type="command_expiry",controller_tick_id=None,reply_time_us=1900000)
            for prefix in ("flow","hot","cold","wall","separate"):
                forged[f"{prefix}_age_us"]=100000
            corrupt.append(forged)
            wire=deepcopy(summary["wire_evidence"]);wire["ticks"].pop()
            result=evaluate_campaign(cfg,corrupt,wire)
            self.assertFalse(result["expectation_pass"])
            self.assertEqual(result["completion_status"],"UNASSESSABLE")

    def test_valid_explicit_reset_requires_subsequent_arm(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg=short("flow_dropout",events=[dict(event_id="arm",type="operation",time_us=0,operation="ARM"),
                dict(event_id="flow",type="observation_link",time_us=400000,end_us=900000,channel=2,mode="drop"),
                dict(event_id="reset",type="operation",time_us=900000,operation="RESET"),
                dict(event_id="rearm",type="operation",time_us=1000000,operation="ARM")])
            rows,summary=run_campaign(cfg,HOST,Path(directory)/"wire")
            ticks={r["time_us"]:r for r in rows if r["record_type"]=="controller_tick"}
            self.assertEqual(ticks[700000]["controller_state"],"TRIPPED")
            self.assertEqual(ticks[900000]["controller_state"],"DISARMED")
            self.assertEqual(ticks[1000000]["controller_state"],"RUNNING")
            self.assertEqual(summary["evaluation"]["rules"]["TH04"]["status"],"PASS")

    def test_short_bad_link_variants_retain_actual_wire_audit(self):
        for case,typ,mode in (("delayed_flow","observation_link","delay"),("reordered_flow","observation_link","reorder"),
                              ("corrupt_flow","observation_link","corrupt"),("truncated_flow","observation_link","truncate"),
                              ("delayed_command","command_link","delay"),("dropped_ack","command_link","drop_ack")):
            with tempfile.TemporaryDirectory() as directory,self.subTest(case=case):
                fault=dict(event_id="fault",type=typ,time_us=500000,mode=mode)
                if typ=="observation_link":fault["channel"]=2
                if mode in ("delay","drop_ack"):fault["end_us"]=1000000
                if mode=="delay":fault["delay_us"]=400000
                cfg=short(case,events=[dict(event_id="arm",type="operation",time_us=0,operation="ARM"),fault])
                rows,summary=run_campaign(cfg,HOST,Path(directory)/"wire")
                self.assertEqual(summary["wire_evidence"]["status"],"PASS")
                self.assertEqual(summary["evaluation"]["rules"]["TH08"]["status"],"PASS",summary["evaluation"])

    def test_off_tick_demand_waits_for_next_reliable_step(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg=short(events=[dict(event_id="arm",type="operation",time_us=0,operation="ARM"),
                              dict(event_id="heat",type="heat_demand",time_us=550000,command=0.)])
            rows,summary=run_campaign(cfg,HOST,Path(directory)/"wire")
            event=next(r for r in rows if r["time_us"]==550000 and r["event_phase"]=="after")
            following=next(r for r in rows if r["time_us"]==600000 and r["record_type"]=="controller_tick")
            self.assertEqual(event["heat_demand_command"],0.)
            self.assertEqual(event["requested_heat_command"],1.)
            self.assertEqual(event["lease_heat_command"],1.)
            self.assertEqual(event["applied_heat_w"],5000.)
            self.assertEqual(following["requested_heat_command"],0.)
            self.assertEqual(following["applied_heat_w"],0.)
            self.assertEqual(summary["wire_evidence"]["status"],"PASS")


if __name__=="__main__":
    unittest.main()
