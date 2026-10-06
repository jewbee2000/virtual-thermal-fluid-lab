"""Raw-fixture and independent acceptance/provenance checks for tank M1."""
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import hashlib
import json
import math
import os
import tempfile
import unittest
import numpy as np
from fluidlab.contracts import SolverConfig, normalize_scenario
from fluidlab.control import Observation, Supervisor
from fluidlab.evaluator import TELEMETRY_FIELDS, evaluate_tank
from fluidlab.plant import IntegrationFailure, Parameters, Plant, PlantStopped
from fluidlab.provenance import PROJECT_ROOT, git_metadata, source_hash
from fluidlab.runner import load_scenario, run, write_run


WORK = PROJECT_ROOT / "artifacts/M1-work"
WORK.mkdir(parents=True, exist_ok=True)
FIXTURES = Path(__file__).parent / "fixtures"


def scenario(**changes):
    result = dict(name="contract", duration_s=1.0, dt_s=.1, expected="characterize")
    result.update(changes)
    return result


class InputContractTests(unittest.TestCase):
    def test_file_and_direct_validation_have_identical_negative_boundaries(self):
        cases = [dict(extra=1), dict(name="../escape"), dict(schema_version=True),
                 dict(schema_version=2), dict(duration_s=True), dict(dt_s="0.1"),
                 dict(dt_s=0), dict(dt_s=1.1), dict(dt_s=.0000001),
                 dict(duration_s=float("inf")), dict(duration_s=float("nan")),
                 dict(duration_s=86400.1), dict(duration_s=.15),
                 dict(duration_s=1.0000001), dict(dt_s=.000001, duration_s=1.000001),
                 dict(seed=True), dict(seed=1.0), dict(seed=-1), dict(seed=4294967296),
                 dict(initial_level_m=0), dict(initial_level_m=1), dict(target_level_m=1),
                 dict(sensor_noise_std_m=-1), dict(bias_rate_m_s=True),
                 dict(fault="unknown"), dict(expected="unknown"), dict(fault_at_s=-1),
                 dict(fault="sensor_dropout", fault_at_s=.15), dict(fault_at_s=float("nan")),
                 dict(fault="sensor_dropout", fault_at_s=1),
                 dict(fault="sensor_dropout", fault_at_s=2),
                 dict(fault="pump_stuck_on", fault_at_s=0, expected="nominal"),
                 dict(controller={"surprise": 1}), dict(controller={"bias": True}),
                 dict(controller={"bias": 1.1}), dict(controller={"stale_after_s": float("nan")}),
                 dict(controller={"kp_per_m": -1}), dict(controller={"ki_per_m_s": "0.06"}),
                 dict(controller={"high_switch_m": 1}), dict(controller={"sensor_min_m": .6}),
                 dict(controller={"sensor_max_m": 1.1}), dict(controller={"drain_command": -1})]
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            path = Path(temp) / "scenario.json"
            for case in cases:
                cfg = scenario(**case)
                with self.subTest(case=case):
                    path.write_text(json.dumps(cfg), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        run(cfg)
                    with self.assertRaises(ValueError):
                        load_scenario(path)

    def test_duplicate_and_nonfinite_raw_json_rejected(self):
        for name in ("duplicate-scenario-key.json", "duplicate-controller-key.json", "nonfinite-scenario.json"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                load_scenario(FIXTURES / name)

    def test_normalization_is_immutable_and_file_matches_direct(self):
        cfg = scenario(controller={"drain_command": .4})
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            path = Path(temp) / "scenario.json"
            path.write_text(json.dumps(cfg), encoding="utf-8")
            loaded = load_scenario(path)
            self.assertEqual(loaded, normalize_scenario(cfg, Parameters()))
            with self.assertRaises(FrozenInstanceError):
                loaded.dt_s = .2
            with self.assertRaises(FrozenInstanceError):
                loaded.controller.bias = .5
            detached = loaded["controller"]
            detached["bias"] = .9
            self.assertEqual(loaded.controller.bias, .3155)
            a, sa = run(cfg)
            b, sb = run(loaded)
            self.assertEqual(a, b)
            self.assertEqual(sa["execution_config"], sb["execution_config"])

    def test_custom_topology_limits_and_drain_are_used(self):
        p = replace(Parameters(), tank_height_m=2)
        with self.assertRaises(ValueError):
            run(scenario(), p)
        cfg = scenario(initial_level_m=1.2, target_level_m=1.5,
                       controller=dict(high_switch_m=1.7, sensor_max_m=2,
                                       drain_command=.4, kp_per_m=0, ki_per_m_s=0, bias=.2))
        rows, summary = run(cfg, p)
        self.assertIsNone(summary["trip_reason"])
        self.assertEqual(rows[0]["valve_opening"], .4)
        self.assertTrue(all(r["requested_valve_command"] == .4 and r["pump_command"] == .2 for r in rows))
        supervisor = Supervisor(sensor_max_m=2)
        self.assertFalse(supervisor.update(0, Observation(1.5, 0, True, False)))
        self.assertTrue(supervisor.update(.1, Observation(2.1, .1, True, False)))
        self.assertEqual(supervisor.reason, "sensor_range")

    def test_parameter_and_supervisor_nonboolean_finite_values(self):
        for value in (True, "0.05", float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Parameters(area_m2=value)
        for value in (True, "0.3", 0, float("nan")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                Supervisor(stale_after_s=value)

    def test_integer_microsecond_ticks_do_not_accumulate_float_time(self):
        rows, _ = run(scenario(duration_s=.3))
        self.assertEqual([r["time_us"] for r in rows], [0, 100000, 200000, 300000])
        self.assertEqual([r["time_s"] for r in rows], [0, .1, .2, .3])

    def test_inactive_fault_time_normalization_is_idempotent(self):
        cfg = scenario(dt_s=.07, duration_s=.7)
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            path = Path(temp) / "scenario.json"
            path.write_text(json.dumps(cfg), encoding="utf-8")
            loaded = load_scenario(path)
            a, _ = run(cfg)
            b, _ = run(loaded)
            self.assertEqual(a, b)
            self.assertEqual(loaded.fault_at_s, 60)
        _, summary = run(scenario(fault_at_s=.15))
        self.assertTrue(summary["all_checks_pass"])

    def test_malformed_observation_channels_trip_without_boolean_numeric_coercion(self):
        cases = [(Observation(True, 0, True, False), "invalid_sensor"),
                 (Observation("0.5", 0, True, False), "invalid_sensor"),
                 (Observation(10**1000, 0, True, False), "invalid_sensor"),
                 (Observation(.5, True, True, False), "invalid_timestamp"),
                 (Observation(.5, "0", True, False), "invalid_timestamp"),
                 (Observation(.5, -.1, True, False), "invalid_timestamp"),
                 (Observation(.5, 0, 1, False), "invalid_sensor"),
                 (Observation(.5, 0, True, 1), "invalid_sensor"),
                 (Observation("bad", "bad", False, True), "high_high")]
        for obs, expected in cases:
            with self.subTest(obs=obs):
                supervisor = Supervisor()
                self.assertTrue(supervisor.update(0, obs))
                self.assertEqual(supervisor.reason, expected)

    def test_boolean_model_object_never_substitutes_defaults(self):
        with self.assertRaises(ValueError):
            Plant(p=False)
        with self.assertRaises(ValueError):
            run(scenario(), p=False)

    def test_outcome_fault_compatibility_table(self):
        accepted = {"none": {"nominal", "characterize"}, "sensor_dropout": {"stale_trip", "characterize"},
                    "sensor_bias_ramp": {"high_trip", "characterize"}, "blocked_outlet": {"contained", "characterize"},
                    "pump_stuck_on": {"observe_hazard", "characterize"}, "sensor_stuck": {"characterize"},
                    "pump_failed_off": {"characterize"}}
        outcomes = {"nominal", "characterize", "stale_trip", "high_trip", "contained", "observe_hazard"}
        for fault, compatible in accepted.items():
            for expected in outcomes:
                cfg = scenario(fault=fault, expected=expected, fault_at_s=0)
                with self.subTest(fault=fault, expected=expected):
                    if expected in compatible:
                        normalize_scenario(cfg, Parameters())
                    else:
                        with self.assertRaises(ValueError):
                            normalize_scenario(cfg, Parameters())


class SolverAndDomainTests(unittest.TestCase):
    def test_solver_config_is_immutable_and_rejects_bad_values(self):
        supplied = [1e-10] * 5
        solver = SolverConfig(atol=supplied)
        supplied[0] = 1
        self.assertEqual(solver.atol[0], 1e-10)
        with self.assertRaises(FrozenInstanceError):
            solver.method = "Radau"
        for changes in (dict(method="BDF"), dict(rtol=True), dict(rtol=0), dict(rtol=float("inf")),
                        dict(atol=[1e-10] * 4), dict(atol=[True] * 5), dict(atol=1e-10),
                        dict(atol=[float("nan")] * 5), dict(max_step_s=.051), dict(max_step_s=True)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                SolverConfig(**changes)

    def test_terminal_empty_and_full_cannot_resume(self):
        p = Parameters()
        for initial, flow, valve, command, duration, expected in (
                (.9, p.pump_max_m3_s, 0, 1, 50, "full"), (.25, 0, 1, 0, 1000, "empty")):
            with self.subTest(boundary=expected):
                plant = Plant(p, h0_m=initial, q0_m3_s=flow, valve0=valve)
                advanced = plant.advance(duration, command, valve, rtol=1e-9, atol=[1e-11] * 5)
                self.assertEqual(advanced.boundary, expected)
                state = plant.y.copy()
                self.assertIn("boundary_level_residual_m", advanced.diagnostics)
                self.assertIn("boundary_root_tolerance_m", advanced.diagnostics)
                with self.assertRaises(PlantStopped):
                    plant.advance(.1, 0, 1)
                np.testing.assert_array_equal(state, plant.y)

    @staticmethod
    def partial_failure():
        # Synthetic accepted partial state satisfies the independently known
        # A*(h-h0)=Vin relation; no call to the implementation builds the oracle.
        states = np.array([[.25, .251], [0, 0], [.65, .65], [0, .00005], [0, 0]])
        return SimpleNamespace(success=False, status=-1, message="forced partial failure", nfev=7,
                               njev=0, nlu=0, t=np.array([0, .04]), y=states,
                               t_events=(np.array([]), np.array([])))

    def test_partial_failure_retains_state_diagnostics_and_stops(self):
        plant = Plant()
        with patch("fluidlab.plant.solve_ivp", return_value=self.partial_failure()):
            with self.assertRaises(IntegrationFailure) as failure:
                plant.advance(.1, .5, .65)
        self.assertEqual(plant.t, .04)
        self.assertEqual(plant.y[0], .251)
        self.assertEqual(failure.exception.advance.diagnostics["nfev"], 7)
        self.assertEqual(len(failure.exception.advance.diagnostics["partial_trace"]), 2)
        with self.assertRaises(PlantStopped):
            plant.advance(.1, 0, 1)

    def test_failed_run_export_preserves_partial_trace_and_does_not_pass(self):
        with patch("fluidlab.plant.solve_ivp", return_value=self.partial_failure()):
            rows, summary = run(scenario())
        self.assertFalse(summary["all_checks_pass"])
        self.assertFalse(summary["complete_horizon"])
        self.assertEqual(summary["run_outcome"], "solver_failure")
        self.assertEqual(summary["rule_results"]["R09_characterization_complete"]["status"], "UNASSESSABLE")
        self.assertEqual(rows[-1]["record_type"], "solver_failure")
        self.assertEqual(rows[-1]["measurement_age_s"], .04)
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            write_run(temp, scenario(), rows, summary)
            exported = json.loads((Path(temp) / "summary.json").read_text())
            self.assertEqual(exported["diagnostics"]["failure"]["partial_trace"][-1]["state"][0], .251)

    def test_solver_exception_is_retained_as_failure_at_prior_state(self):
        with patch("fluidlab.plant.solve_ivp", side_effect=RuntimeError("forced exception")):
            rows, summary = run(scenario())
        self.assertEqual(rows[-1]["level_m"], .25)
        self.assertEqual(rows[-1]["time_s"], 0)
        self.assertEqual(summary["diagnostics"]["failure"]["exception_type"], "RuntimeError")
        self.assertFalse(summary["all_checks_pass"])

    def test_invalid_accepted_actuator_state_stops_at_prior_domain_state(self):
        for state_index, value in ((1, -.00001), (1, .00041), (2, -.01), (2, 1.01)):
            with self.subTest(state_index=state_index, value=value):
                result = self.partial_failure()
                result.success, result.status, result.message = True, 0, "synthetic solver success"
                result.y[state_index, -1] = value
                plant = Plant()
                with patch("fluidlab.plant.solve_ivp", return_value=result), self.assertRaises(IntegrationFailure) as error:
                    plant.advance(.1, .5, .65)
                self.assertEqual(plant.t, 0)
                self.assertEqual(plant.y[0], .25)
                self.assertEqual(error.exception.advance.diagnostics["rejected_solver_sample"]["state"][state_index], value)
                with self.assertRaises(PlantStopped):
                    plant.advance(.1, 0, 1)

    def test_boundary_snapshot_retains_measurement_identity_and_command(self):
        rows, summary = run(scenario(duration_s=2, initial_level_m=.999,
                                     fault="pump_stuck_on", fault_at_s=0, expected="observe_hazard"),
                            replace(Parameters(), outlet_area_m2=1e-8))
        self.assertEqual(summary["boundary"], "full")
        self.assertEqual(rows[-1]["record_type"], "terminal_boundary")
        self.assertGreater(rows[-1]["measurement_age_s"], 0)
        for key in ("sample_id", "sample_time_s", "receipt_time_s", "measured_level_m",
                    "controller_tick", "pump_command", "applied_pump_command"):
            self.assertEqual(rows[-1][key], rows[-2][key])
        self.assertIsNone(rows[-1]["time_us"])
        self.assertTrue(summary["all_checks_pass"])
        self.assertEqual(summary["containment"], "FAILED")

    def test_solver_agreement_uses_predeclared_per_state_scales(self):
        # Unit-bearing scales frozen before comparison; do not mix raw state units.
        scales = np.array([1e-7, 1e-9, 1e-7, 1e-9, 1e-9])
        candidate, reference = Plant(), Plant()
        candidate.advance(30, .65, .4, method="RK45")
        reference.advance(30, .65, .4, method="DOP853", rtol=1e-10, atol=[1e-12] * 5)
        self.assertLessEqual(float(np.max(np.abs(candidate.y - reference.y) / scales)), 1)


class EvidenceTests(unittest.TestCase):
    def test_no_trip_latch_rule_is_not_applicable(self):
        _, summary = run(scenario())
        self.assertEqual(summary["rule_results"]["R10_latched_command_stop"]["status"], "NOT_APPLICABLE")
        self.assertIsNone(summary["checks"]["R10_latched_command_stop"])
        self.assertTrue(summary["all_checks_pass"])

    def test_short_nominal_tracking_is_unassessable(self):
        _, summary = run(scenario(expected="nominal"))
        self.assertEqual(summary["rule_results"]["R01_tracking"]["status"], "UNASSESSABLE")
        self.assertFalse(summary["all_checks_pass"])

    def test_truncated_or_corrupt_evidence_never_passes(self):
        cfg = normalize_scenario(scenario(), Parameters())
        rows, _ = run(cfg)
        variants = [[], rows[:-1], [dict(r) for r in rows], rows[::2], [dict(r) for r in rows]]
        variants[2][-1]["volume_residual_m3"] = float("nan")
        variants[4][-1]["measurement_age_s"] = -1
        for trace in variants:
            with self.subTest(trace_length=len(trace)):
                evaluation = evaluate_tank(cfg, Parameters(), trace, trip_reason=None, trip_time_s=None, boundary=None)
                self.assertFalse(evaluation["all_checks_pass"])

    def test_all_observed_applied_quality_identity_and_domain_corruption_is_unassessable(self):
        cfg = normalize_scenario(scenario(), Parameters())
        rows, _ = run(cfg)
        corruptions = [("measured_level_m", float("nan")), ("receipt_time_s", float("inf")),
                       ("pump_command", float("nan")), ("requested_valve_command", -1),
                       ("applied_pump_command", 1.1), ("applied_valve_command", True),
                       ("level_m", 1.1), ("flow_m3_s", -.001), ("valve_opening", 2),
                       ("target_m", .6), ("sample_id", True), ("sample_id", 99),
                       ("controller_tick", True), ("time_us", True), ("sensor_valid", 1),
                       ("independent_high_switch", 1), ("sample_time_s", .1),
                       ("receipt_time_s", .1), ("clock_id", "device")]
        for key, value in corruptions:
            trace = [dict(row) for row in rows]
            trace[0][key] = value
            with self.subTest(key=key, value=value):
                result = evaluate_tank(cfg, Parameters(), trace, trip_reason=None, trip_time_s=None, boundary=None)
                self.assertFalse(result["all_checks_pass"])
                self.assertFalse(result["evidence_valid"])
                self.assertEqual(result["rule_results"]["R09_characterization_complete"]["status"], "UNASSESSABLE")

    def test_unknown_missing_and_nonobject_telemetry_is_unassessable(self):
        cfg = normalize_scenario(scenario(), Parameters())
        rows, _ = run(cfg)
        unknown = [dict(row) for row in rows]
        unknown[0]["invented_field"] = 1
        missing = [dict(row) for row in rows]
        del missing[0]["sample_id"]
        for trace in (unknown, missing, [None], None):
            with self.subTest(trace=trace):
                result = evaluate_tank(cfg, Parameters(), trace, trip_reason=None, trip_time_s=None, boundary=None)
                self.assertFalse(result["all_checks_pass"])
                self.assertFalse(result["evidence_valid"])

    def test_hazard_requires_matching_terminal_snapshot(self):
        p = replace(Parameters(), outlet_area_m2=1e-8)
        cfg = normalize_scenario(scenario(duration_s=2, initial_level_m=.999,
                                          fault="pump_stuck_on", fault_at_s=0, expected="observe_hazard"), p)
        rows, summary = run(cfg, p)
        variants = [(rows[:-1], "full"), ([dict(row) for row in rows], "full"), (rows, "empty"), (rows, "bogus")]
        variants[1][0][-1]["level_m"] = .99
        for trace, boundary in variants:
            with self.subTest(boundary=boundary, trace_length=len(trace)):
                result = evaluate_tank(cfg, p, trace, trip_reason=summary["trip_reason"],
                                       trip_time_s=summary["trip_time_s"], boundary=boundary)
                self.assertFalse(result["all_checks_pass"])
                self.assertFalse(result["evidence_valid"])

    def test_detected_stale_trip_does_not_pass_an_incomplete_horizon(self):
        cfg = normalize_scenario(scenario(duration_s=1, fault="sensor_dropout", fault_at_s=0, expected="stale_trip"), Parameters())
        rows, summary = run(cfg)
        truncated = rows[:-1]
        result = evaluate_tank(cfg, Parameters(), truncated, trip_reason=summary["trip_reason"],
                               trip_time_s=summary["trip_time_s"], boundary=None)
        self.assertEqual(result["rule_results"]["R05_stale_trip"]["status"], "PASS")
        self.assertFalse(result["complete_horizon"])
        self.assertFalse(result["all_checks_pass"])

    def test_first_trip_missing_time_returns_unassessable_without_exception(self):
        cfg = normalize_scenario(scenario(fault="sensor_dropout", fault_at_s=0, expected="stale_trip"), Parameters())
        rows, summary = run(cfg)
        corrupt = [dict(row) for row in rows]
        first_trip = next(row for row in corrupt if row["trip"])
        del first_trip["time_s"]
        result = evaluate_tank(cfg, Parameters(), corrupt, trip_reason=summary["trip_reason"],
                               trip_time_s=summary["trip_time_s"], boundary=None)
        self.assertFalse(result["all_checks_pass"])
        self.assertFalse(result["evidence_valid"])
        self.assertEqual(result["rule_results"]["R05_stale_trip"]["status"], "UNASSESSABLE")

    def test_boundary_characterization_fails_completion(self):
        _, summary = run(scenario(duration_s=2, initial_level_m=.999, fault="pump_stuck_on",
                                   fault_at_s=0, expected="characterize"), replace(Parameters(), outlet_area_m2=1e-8))
        self.assertEqual(summary["rule_results"]["R09_characterization_complete"]["status"], "FAIL")
        self.assertFalse(summary["all_checks_pass"])

    def test_continuous_peak_bound_and_containment_use_independent_rate(self):
        p = Parameters()
        cfg = normalize_scenario(scenario(fault="blocked_outlet", fault_at_s=0, expected="contained"), p)
        rows, _ = run(cfg)
        raw = [dict(row, level_m=.6495) for row in rows]
        result = evaluate_tank(cfg, p, raw, trip_reason=None, trip_time_s=None, boundary=None)
        # Independent inequality: dh/dt <= .0004/.05=.008 m/s; gap=.1 s.
        self.assertAlmostEqual(result["continuous_peak_bound_m"], .6503)
        self.assertEqual(result["rule_results"]["R11_blockage_contained"]["status"], "FAIL")
        self.assertEqual(result["containment"], "FAILED")

    def test_portable_source_hash_fixed_raw_byte_vector(self):
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            root = Path(temp)
            (root / "nested").mkdir()
            (root / "a.py").write_bytes(b"one\n")
            (root / "nested/z.py").write_bytes(b"two\n")
            digest, files = source_hash(root, [root / "nested/z.py", root / "a.py"])
            # SHA256 of a manually framed, fixed hexadecimal byte vector.
            self.assertEqual(digest, "c65d0b4d01938678b292e8f9e1fee0704fa62ad80872b5753833488167747548")
            self.assertEqual(list(files), ["a.py", "nested/z.py"])
            (root / "a.py").write_bytes(b"one\r\n")
            self.assertNotEqual(source_hash(root, [root / "nested/z.py", root / "a.py"])[0], digest)

    def test_git_wrong_top_level_is_not_attributed(self):
        with patch("fluidlab.provenance.subprocess.check_output", return_value=str(PROJECT_ROOT.parent)) as call:
            metadata = git_metadata(PROJECT_ROOT)
        self.assertEqual(metadata["git_revision"], "unversioned")
        self.assertFalse(metadata["git_root_matches"])
        self.assertEqual(call.call_args.kwargs["cwd"], PROJECT_ROOT)

    def test_git_metadata_and_run_ignore_unrelated_current_directory(self):
        before = os.getcwd()
        expected = git_metadata(PROJECT_ROOT)
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            try:
                os.chdir(temp)
                _, summary = run(scenario())
                actual = summary["execution_config"]["provenance"]
            finally:
                os.chdir(before)
        self.assertEqual(actual["git_revision"], expected["git_revision"])
        self.assertEqual(actual["git_root_matches"], expected["git_root_matches"])

    def test_manifest_uses_actual_solver_and_hashes_exported_bytes(self):
        cfg = scenario()
        tolerances = [2e-10, 3e-12, 4e-10, 5e-12, 6e-12]
        rows, summary = run(cfg, method="DOP853", rtol=2e-9, atol=tolerances, max_step_s=.03)
        tolerances[0] = 1
        # Legacy write metadata must never relabel an already executed run.
        cfg["seed"] = 999
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            write_run(temp, cfg, rows, summary, method="Radau", rtol=.1)
            root = Path(temp)
            manifest = json.loads((root / "manifest.json").read_text())
            self.assertEqual(manifest["solver"], "DOP853")
            self.assertEqual(manifest["rtol"], 2e-9)
            self.assertEqual(manifest["atol"], [2e-10, 3e-12, 4e-10, 5e-12, 6e-12])
            self.assertEqual(manifest["solver_max_step_s"], .03)
            self.assertEqual(manifest["seed"], 42)
            self.assertEqual(manifest["lock_sha256"], hashlib.sha256((PROJECT_ROOT / "uv.lock").read_bytes()).hexdigest())
            for name in ("summary.json", "telemetry.csv"):
                self.assertEqual(manifest["artifact_sha256"][name], hashlib.sha256((root / name).read_bytes()).hexdigest())
            self.assertNotIn("manifest.json", manifest["artifact_sha256"])
            canonical = json.dumps(manifest["scenario"], sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                                   allow_nan=False).encode("utf-8")
            self.assertEqual(manifest["scenario_sha256"], hashlib.sha256(canonical).hexdigest())

    def test_tiny_rtol_records_scipy_effective_floor(self):
        _, summary = run(scenario(duration_s=.1), rtol=1e-30)
        solver = summary["execution_config"]["solver"]
        self.assertEqual(solver["requested_rtol"], 1e-30)
        self.assertEqual(solver["rtol"], 100 * np.finfo(float).eps)

    def test_artifact_manifest_excludes_stale_plot_unless_explicitly_exported(self):
        cfg = scenario()
        rows, summary = run(cfg)
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            root = Path(temp)
            (root / "plot.png").write_bytes(b"old unrelated figure")
            write_run(root, cfg, rows, summary)
            manifest = json.loads((root / "manifest.json").read_text())
            self.assertNotIn("plot.png", manifest["artifact_sha256"])
            (root / "plot.png").write_bytes(b"current explicit figure")
            write_run(root, cfg, rows, summary, extra_artifacts=("plot.png",))
            manifest = json.loads((root / "manifest.json").read_text())
            self.assertEqual(manifest["artifact_sha256"]["plot.png"], hashlib.sha256(b"current explicit figure").hexdigest())

    def test_exported_field_sets_and_key_types_match_frozen_schema_documents(self):
        # This checks documented field/type drift, not a new JSON-schema engine.
        def check(document, schema):
            self.assertTrue(set(schema.get("required", ())) <= set(document))
            self.assertFalse(set(document) - set(schema["properties"]))
            for key, value in document.items():
                field = schema["properties"][key]
                types = field.get("type", [])
                types = [types] if isinstance(types, str) else types
                if not types:
                    continue
                actual = ("null" if value is None else "boolean" if isinstance(value, bool) else
                          "integer" if isinstance(value, int) else "number" if isinstance(value, float) else
                          "object" if isinstance(value, dict) else "array" if isinstance(value, list) else
                          "string" if isinstance(value, str) else "unsupported")
                self.assertTrue(actual in types or actual == "integer" and "number" in types, key)
                if actual in ("number", "integer"):
                    self.assertTrue(math.isfinite(value), key)
        schemas = {name: json.loads((PROJECT_ROOT / "schemas" / f"tank-{name}-v1.schema.json").read_text(encoding="utf-8"))
                   for name in ("scenario", "telemetry", "summary", "manifest", "model", "solver")}
        self.assertEqual(TELEMETRY_FIELDS, frozenset(schemas["telemetry"]["required"]))
        self.assertEqual(TELEMETRY_FIELDS, frozenset(schemas["telemetry"]["properties"]))
        cfg = scenario()
        rows, summary = run(cfg)
        for row in rows:
            check(row, schemas["telemetry"])
        check(summary, schemas["summary"])
        check(summary["execution_config"], schemas["summary"]["properties"]["execution_config"])
        check(summary["execution_config"]["scenario"], schemas["scenario"])
        check(summary["execution_config"]["model"], schemas["model"])
        check(summary["execution_config"]["model"]["parameters"], schemas["model"]["properties"]["parameters"])
        check(summary["execution_config"]["solver"], schemas["solver"])
        with tempfile.TemporaryDirectory(dir=WORK) as temp:
            write_run(temp, cfg, rows, summary)
            manifest = json.loads((Path(temp) / "manifest.json").read_text())
            check(manifest, schemas["manifest"])


if __name__ == "__main__":
    unittest.main()
