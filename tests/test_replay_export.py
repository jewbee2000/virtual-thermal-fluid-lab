"""Independent replay boundary checks: byte fidelity, gaps and time semantics."""
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_replay", ROOT / "scripts/build_replay.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


class ReplayExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def fixture(self, *, name="ui_fixture", thermal=True, fixture=True):
        run = self.base / name
        run.mkdir()
        if thermal:
            fields = list(replay.THERMAL_FIELDS)
            rows = []
            # Independent literal sequence: two event rows at1 s, then a raw
            # fractional numerical root. Values are UI fixtures, not SIL results.
            for sid, now, phase in ((0,0,None),(1,1,"before"),(2,1,"after"),(3,1.23456789,None)):
                row = dict.fromkeys(fields)
                row.update(sample_id=sid,record_type="event_boundary" if phase else "controller_tick",
                           time_s=now,time_us=now*1e6,epoch=1,session_origin_us=0,controller_state="RUNNING",
                           trip_reason="",event_phase=phase,event_ids="fault" if phase else "",
                           wall_temperature_k=300.,hot_temperature_k=295.,cold_temperature_k=293.15,
                           flow_m3_s=.00015,pump_speed=.527498, valve_opening=.65,
                           requested_heat_command=1.,requested_pump_command=.527498,requested_valve_command=.65,
                           lease_heat_command=1.,lease_pump_command=.527498,lease_valve_command=.65,
                           fault_heat_command=1.,fault_pump_command=.527498,fault_valve_command=.65,
                           observed_separate_trip=0.0,command_expired=False)
                rows.append(row)
            summary = dict(name=name,schema_version=1,topology="thermal_loop",execution={"evidence_level":"UI_FIXTURE"} if fixture else {},
                           evaluation={"expectation_pass":False,"containment_status":"FAILED","completion_status":"FAIL",
                                       "rules":{"TH10":{"status":"FAIL","evidence":{"uncontained":True}}}},
                           run_failure=None,controller={"stale_us":300000},metrics={})
        else:
            fields = ["time_s","level_m","measured_level_m","pump_command","sensor_valid","measurement_age_s"]
            rows = [dict(time_s=0,level_m=.25,measured_level_m=.25,pump_command=.75,sensor_valid=True,measurement_age_s=0),
                    dict(time_s=.1,level_m=.26,measured_level_m=.25,pump_command=.7,sensor_valid=True,measurement_age_s=.1)]
            summary = dict(name=name,checks={"R02_volume_balance":True},all_checks_pass=False,containment="FAILED",execution={})
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream,fields,lineterminator="\r\n")
        writer.writeheader();writer.writerows(rows)
        (run/"telemetry.csv").write_bytes(stream.getvalue().encode())
        (run/"summary.json").write_bytes(json.dumps(summary).encode())
        (run/"wire").mkdir()
        (run/"wire"/"stdin.bin").write_bytes(b"\x00F|bad\r\n\xff\n")
        self.rehash(run)
        return run

    def rehash(self, run, *, artifacts=None):
        hashes = artifacts if artifacts is not None else {
            path.relative_to(run).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
            for path in run.rglob("*") if path.is_file() and path.name!="manifest.json"}
        (run/"manifest.json").write_text(json.dumps({"artifacts":hashes}),encoding="utf-8")

    def test_preserves_raw_bytes_duplicate_times_fractional_root_and_failure(self):
        source=self.fixture()
        out=self.base/"replay"
        replay.build_replay([source],out,allow_ui_fixture=True,screenshots=False)
        for path in source.rglob("*"):
            if path.is_file():
                self.assertEqual(path.read_bytes(),(out/"raw"/"ui_fixture"/path.relative_to(source)).read_bytes())
        payload=json.loads((out/"data.js").read_text()[len("window.FLUIDLAB_REPLAY="):-2])
        run=payload["runs"][0]
        self.assertEqual([0,1,1,1.23456789],run["columns"][run["fields"].index("time_s")])
        self.assertEqual([0,1,2,3],run["columns"][run["fields"].index("sample_id")])
        self.assertEqual("FAILED",run["summary"]["evaluation"]["containment_status"])
        self.assertFalse(run["summary"]["evaluation"]["expectation_pass"])
        self.assertEqual("UI_FIXTURE NOT_VERIFICATION",run["evidence_level"])
        manifest=json.loads((out/"replay-manifest.json").read_text())
        self.assertEqual(hashlib.sha256((out/"data.js").read_bytes()).hexdigest(),manifest["artifacts"]["data.js"])
        license_bytes=(ROOT/"LICENSE").read_bytes()
        self.assertEqual(license_bytes,(out/"LICENSE.txt").read_bytes())
        self.assertEqual(hashlib.sha256(license_bytes).hexdigest(),manifest["artifacts"]["LICENSE.txt"])

    def test_fixture_requires_explicit_development_opt_in(self):
        with self.assertRaisesRegex(ValueError,"UI_FIXTURE"):
            replay.read_run(self.fixture())

    def test_corrupt_artifact_rejected_before_output_creation(self):
        source=self.fixture()
        (source/"telemetry.csv").write_bytes((source/"telemetry.csv").read_bytes()+b"corrupt")
        out=self.base/"out"
        with self.assertRaisesRegex(ValueError,"SHA256 mismatch"):
            replay.build_replay([source],out,allow_ui_fixture=True,screenshots=False)
        self.assertFalse(out.exists())

    def test_missing_manifest_asset_rejected(self):
        source=self.fixture()
        (source/"wire"/"stdin.bin").unlink()
        with self.assertRaises(FileNotFoundError):replay.read_run(source,allow_ui_fixture=True)

    def test_artifact_traversal_and_drive_escape_rejected(self):
        for path in ("../outside.bin","C:/outside.bin","wire\\outside.bin","/outside.bin"):
            with self.subTest(path=path):
                source=self.fixture(name="probe"+str(len(list(self.base.iterdir()))))
                manifest=json.loads((source/"manifest.json").read_text())
                manifest["artifacts"][path]="0"*64
                (source/"manifest.json").write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError,"artifact path|relative POSIX"):
                    replay.read_run(source,allow_ui_fixture=True)

    def test_output_cannot_replace_or_nest_evidence(self):
        source=self.fixture()
        for out in (source,source/"export",self.base):
            with self.subTest(out=out),self.assertRaises(ValueError):
                replay.build_replay([source],out,allow_ui_fixture=True,screenshots=False)

    def test_decreasing_time_and_duplicate_sample_id_rejected(self):
        for field,value in (("time_s","-1"),("sample_id","1")):
            with self.subTest(field=field):
                source=self.fixture(name="bad"+field)
                reader=csv.DictReader(io.StringIO((source/"telemetry.csv").read_text(),newline=""))
                fields=reader.fieldnames;rows=list(reader);rows[2][field]=value
                stream=io.StringIO();writer=csv.DictWriter(stream,fields);writer.writeheader();writer.writerows(rows)
                (source/"telemetry.csv").write_bytes(stream.getvalue().encode());self.rehash(source)
                with self.assertRaisesRegex(ValueError,"telemetry time|sample_id"):
                    replay.read_run(source,allow_ui_fixture=True)

    def test_numeric_nonfinite_and_unknown_topology_rejected(self):
        source=self.fixture()
        raw=(source/"telemetry.csv").read_text().replace("300.0","nan",1)
        (source/"telemetry.csv").write_text(raw);self.rehash(source)
        with self.assertRaisesRegex(ValueError,"nonfinite telemetry"):replay.read_run(source,allow_ui_fixture=True)
        source=self.fixture(name="badtopology")
        summary=json.loads((source/"summary.json").read_text());summary["topology"]="other"
        (source/"summary.json").write_text(json.dumps(summary));self.rehash(source)
        with self.assertRaisesRegex(ValueError,"unsupported topology"):replay.read_run(source,allow_ui_fixture=True)

    def test_explicit_tank_mapping_retains_missing_lease(self):
        run,_,rows=replay.read_run(self.fixture(name="tank",thermal=False))
        self.assertEqual("atmospheric_tank",run["topology"])
        self.assertNotIn("lease_pump_command",run["fields"])
        self.assertEqual(.26,rows[-1]["level_m"])
        self.assertTrue(rows[-1]["sensor_valid"])

    def test_peak_bound_coverage_metadata_retained_without_horizon_extension(self):
        source=self.fixture()
        summary=json.loads((source/"summary.json").read_text())
        coverage=dict(start_time_us=0,end_time_us=1_234_567.89,requested_end_time_us=1_200_000_000,
                      retained_samples=4,discarded_rows=0,scope="RETAINED_PREFIX")
        summary["metrics"]={"global_peak_upper_bound_k":300.05,"peak_bound_coverage":coverage}
        raw=json.dumps(summary,indent=2).encode()
        (source/"summary.json").write_bytes(raw);self.rehash(source)
        out=self.base/"prefix-export"
        replay.build_replay([source],out,allow_ui_fixture=True,screenshots=False)
        payload=json.loads((out/"data.js").read_text()[len("window.FLUIDLAB_REPLAY="):-2])
        self.assertEqual(coverage,payload["runs"][0]["summary"]["metrics"]["peak_bound_coverage"])
        self.assertEqual(raw,(out/"raw/ui_fixture/summary.json").read_bytes())

    @unittest.skipUnless(shutil.which("node"),"Node needed for browser-independent replay helper checks")
    def test_observation_gap_equality_and_duplicate_time_cursor_oracles(self):
        # Literal oracle: equality300000us fresh,300001us stale; invalid/missing
        # are gaps even with finite values; duplicate time selects final row.
        script=r'''
const assert=require("node:assert/strict");
const m=require(process.argv[1]);
const fresh={flow_quality:1,flow_age_us:300000,observed_flow_m3_s:0.00015};
assert.equal(m.observedValue(fresh,"observed_flow_m3_s","flow",300000),0.00015);
for(const patch of [{flow_age_us:300001},{flow_quality:0},{flow_quality:2},{flow_age_us:null}])
 assert.equal(m.observedValue({...fresh,...patch},"observed_flow_m3_s","flow",300000),null);
assert.equal(m.indexAt([{time_s:0},{time_s:1},{time_s:1},{time_s:2}],1),2);
assert.equal(m.indexAt([{time_s:0},{time_s:1},{time_s:1},{time_s:2}],0.9),0);
assert.equal(m.tankObservedValue({sensor_valid:true,measurement_age_s:0.3,measured_level_m:0.5},0.3),0.5);
assert.equal(m.tankObservedValue({sensor_valid:true,measurement_age_s:0.300001,measured_level_m:0.5},0.3),null);
console.log("Independent gap/time literals passed");
'''
        result=subprocess.run([shutil.which("node"),"-e",script,str(ROOT/"web/replay-model.js")],capture_output=True,text=True,timeout=15)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)

    @unittest.skipUnless(shutil.which("node"),"Node needed for browser-independent coverage display checks")
    def test_peak_bound_scope_fractional_prefix_and_unavailable_display_oracles(self):
        script=r'''
const assert=require("node:assert/strict");
const m=require(process.argv[1]);
const coverage={start_time_us:0,end_time_us:1234567.89,requested_end_time_us:1200000000,
 retained_samples:4,discarded_rows:0,scope:"RETAINED_PREFIX"};
const metrics={global_peak_upper_bound_k:300.05,peak_bound_coverage:coverage};
const prefix=m.peakBoundDisplay(metrics);
assert.equal(prefix.value_k,300.05);assert.equal(prefix.scope,"RETAINED_PREFIX");
assert.match(prefix.detail,/retained 0–1\.23456789 s; requested end 1200 s/);
const full=m.peakBoundDisplay({...metrics,peak_bound_coverage:{...coverage,end_time_us:1200000000,scope:"FULL_RETAINED_HORIZON"}});
assert.equal(full.scope,"FULL_RETAINED_HORIZON");assert.equal(full.value_k,300.05);
for(const patch of [{scope:"UNAVAILABLE"},{discarded_rows:1},{end_time_us:NaN},
 {start_time_us:2000000},{scope:"FULL_RETAINED_HORIZON"},{retained_samples:0}]) {
 const unavailable=m.peakBoundDisplay({...metrics,peak_bound_coverage:{...coverage,...patch}});
 assert.equal(unavailable.value_k,null);assert.equal(unavailable.scope,"UNAVAILABLE");
 assert.match(unavailable.detail,/excludes numerical integration error/);
}
assert.equal(m.peakBoundDisplay({...metrics,global_peak_upper_bound_k:null}).value_k,null);
assert.equal(m.peakBoundDisplay({global_peak_upper_bound_k:300.05}).scope,"UNAVAILABLE");
console.log("Independent scope/window/discarded-row literals passed");
'''
        result=subprocess.run([shutil.which("node"),"-e",script,str(ROOT/"web/replay-model.js")],capture_output=True,text=True,timeout=15)
        self.assertEqual(0,result.returncode,result.stdout+result.stderr)


if __name__=="__main__":unittest.main()
