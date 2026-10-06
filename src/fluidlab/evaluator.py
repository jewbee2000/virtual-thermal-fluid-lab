"""Expectation evaluation is separate from execution and physical containment."""
import math
from collections.abc import Mapping
from .contracts import microseconds


TELEMETRY_FIELDS = frozenset({
    "record_type", "controller_tick", "time_us", "time_s", "clock_id", "level_m",
    "measured_level_m", "sample_id", "sample_time_s", "receipt_time_s", "measurement_age_s",
    "sensor_valid", "independent_high_switch", "pump_command", "requested_valve_command",
    "applied_pump_command", "applied_valve_command", "flow_m3_s", "valve_opening", "target_m",
    "trip", "volume_residual_m3",
})


def evaluate_tank(cfg, p, rows, *, trip_reason, trip_time_s, boundary, run_failure=None):
    results = {}
    def rule(name, status, rationale):
        results[name] = dict(status=status, rationale=rationale)

    required = ["R02_volume_balance"]
    required += {
        "nominal": ["R01_tracking", "R03_no_trip", "R04_no_boundary"],
        "stale_trip": ["R05_stale_trip"],
        "high_trip": ["R06_high_trip", "R07_containment"],
        "contained": ["R11_blockage_contained"],
        "observe_hazard": ["R08_hazard_exposed"],
        "characterize": ["R09_characterization_complete"],
    }[cfg.expected]
    required.append("R10_latched_command_stop")
    if not isinstance(rows, (list, tuple)):
        rows = []
    evidence_valid = bool(rows)
    required_numeric = ("time_s", "level_m", "target_m", "flow_m3_s", "valve_opening",
                        "volume_residual_m3", "pump_command", "sample_time_s", "measurement_age_s",
                        "measured_level_m", "receipt_time_s", "requested_valve_command",
                        "applied_pump_command", "applied_valve_command")
    previous_time = -1.0
    tick_count = 0
    root_tolerance_m = 64 * math.ulp(max(1.0, p.tank_height_m))
    trip_reasons = {"", "high_high", "invalid_sensor", "invalid_timestamp", "stale_sensor", "sensor_range"}
    if boundary not in (None, "empty", "full"):
        evidence_valid = False
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            evidence_valid = False
            continue
        try:
            if set(row) != TELEMETRY_FIELDS:
                evidence_valid = False
            if not all(isinstance(row[key], (int, float)) and not isinstance(row[key], bool)
                       and math.isfinite(row[key]) for key in required_numeric):
                evidence_valid = False
            if row["time_s"] < previous_time:
                evidence_valid = False
            if row["time_s"] == previous_time and row.get("record_type") != "solver_failure":
                evidence_valid = False
            if not 0 <= row["sample_time_s"] <= row["receipt_time_s"] <= row["time_s"] <= cfg.duration_s:
                evidence_valid = False
            if row["measurement_age_s"] < 0:
                evidence_valid = False
            if abs(row["measurement_age_s"] - (row["time_s"] - row["sample_time_s"])) > 1e-9:
                evidence_valid = False
            if (row["clock_id"] != "simulation" or not isinstance(row["sensor_valid"], bool)
                    or not isinstance(row["independent_high_switch"], bool)):
                evidence_valid = False
            for key, minimum in (("controller_tick", 0), ("sample_id", -1)):
                if isinstance(row[key], bool) or not isinstance(row[key], int) or row[key] < minimum:
                    evidence_valid = False
            if row["sample_id"] > row["controller_tick"]:
                evidence_valid = False
            if microseconds(row["sample_time_s"], "sample_time_s") % cfg.dt_us:
                evidence_valid = False
            if row["trip"] not in trip_reasons:
                evidence_valid = False
            if row["target_m"] != cfg.target_level_m:
                evidence_valid = False
            if row["record_type"] == "controller_tick":
                if (isinstance(row["time_us"], bool) or not isinstance(row["time_us"], int)
                        or row["controller_tick"] != tick_count or row["time_us"] != tick_count * cfg.dt_us
                        or row["time_s"] != tick_count * cfg.dt_us / 1_000_000):
                    evidence_valid = False
                if not 0 < row["level_m"] < p.tank_height_m:
                    evidence_valid = False
                if index == 0:
                    if row["sample_id"] not in (-1, 0) or row["sample_time_s"] != 0 or row["receipt_time_s"] != 0:
                        evidence_valid = False
                else:
                    previous = rows[index-1]
                    if row["sample_id"] == previous["sample_id"]:
                        if any(row[key] != previous[key] for key in ("sample_time_s", "receipt_time_s", "measured_level_m")):
                            evidence_valid = False
                    elif (row["sample_id"] != previous["sample_id"] + 1
                          or row["sample_time_s"] != row["time_s"] or row["receipt_time_s"] != row["time_s"]):
                        evidence_valid = False
                tick_count += 1
            elif row["record_type"] in ("terminal_boundary", "solver_failure"):
                if index == 0 or index != len(rows) - 1 or row["time_s"] > tick_count * cfg.dt_us / 1_000_000:
                    evidence_valid = False
                else:
                    for key in ("controller_tick", "sample_id", "sample_time_s", "receipt_time_s",
                                "measured_level_m", "pump_command", "requested_valve_command",
                                "applied_pump_command", "applied_valve_command", "trip",
                                "sensor_valid", "independent_high_switch", "target_m", "clock_id"):
                        if row.get(key) != rows[index-1].get(key):
                            evidence_valid = False
                if (row["record_type"] == "terminal_boundary") != (boundary is not None):
                    evidence_valid = False
                if row["time_us"] is not None:
                    evidence_valid = False
                if row["record_type"] == "terminal_boundary":
                    endpoint_m = 0.0 if boundary == "empty" else p.tank_height_m
                    if abs(row["level_m"] - endpoint_m) > root_tolerance_m:
                        evidence_valid = False
                elif run_failure is None or not 0 < row["level_m"] < p.tank_height_m:
                    evidence_valid = False
            else:
                evidence_valid = False
            for key in ("pump_command", "requested_valve_command", "applied_pump_command", "applied_valve_command"):
                if not 0 <= row[key] <= 1:
                    evidence_valid = False
            if not 0 <= row["valve_opening"] <= 1:
                evidence_valid = False
            if not 0 <= row["flow_m3_s"] <= p.pump_max_m3_s:
                evidence_valid = False
            previous_time = row["time_s"]
        except (KeyError, TypeError, ValueError, OverflowError):
            evidence_valid = False
    if rows and isinstance(rows[-1], Mapping) and ((boundary is not None) != (rows[-1].get("record_type") == "terminal_boundary")
                 or (run_failure is not None) != (rows[-1].get("record_type") == "solver_failure")):
        evidence_valid = False
    trip_rows = [r for r in rows if isinstance(r, Mapping) and r.get("trip")]
    if (trip_reason is not None and trip_reason not in trip_reasons
            or trip_time_s is not None and (isinstance(trip_time_s, bool) or not isinstance(trip_time_s, (int, float))
                                           or not math.isfinite(trip_time_s))
            or (trip_reason is None) != (not trip_rows)
            or (trip_rows and (trip_time_s != trip_rows[0].get("time_s") or trip_reason != trip_rows[0]["trip"]))):
        evidence_valid = False
    complete = bool(evidence_valid and run_failure is None and boundary is None
                    and abs(rows[-1]["time_s"] - cfg.duration_s) <= 1e-9)
    if not evidence_valid:
        for key in required:
            rule(key, "UNASSESSABLE", "missing, nonfinite or inconsistent trace evidence")
        return dict(rule_results=results, checks={k: None for k in results}, all_checks_pass=False,
                    evidence_valid=False, complete_horizon=False, containment="UNASSESSABLE",
                    peak_level_m=None, continuous_peak_bound_m=None, largest_sample_gap_s=None,
                    final_level_m=None, max_volume_residual_m3=None)

    peak = max(row["level_m"] for row in rows)
    gap = max((b["time_s"] - a["time_s"] for a, b in zip(rows, rows[1:])), default=0.0)
    peak_bound = peak + p.pump_max_m3_s / p.area_m2 * gap
    residual = max(abs(row["volume_residual_m3"]) for row in rows)
    rule("R02_volume_balance", "PASS" if residual < 1e-9 else "FAIL",
         "augmented ODE volume consistency residual < 1e-9 m3")
    if cfg.expected == "nominal":
        tail = [r for r in rows if r["time_s"] >= cfg.duration_s - 30]
        if not complete or cfg.duration_s < 30:
            rule("R01_tracking", "UNASSESSABLE", "requires a complete last 30 seconds")
        else:
            rule("R01_tracking", "PASS" if all(abs(r["level_m"] - r["target_m"]) < .02 for r in tail) else "FAIL",
                 "all last-30-second level errors < 0.02 m")
        rule("R03_no_trip", "PASS" if complete and trip_reason is None else "FAIL" if trip_reason else "UNASSESSABLE",
             "nominal horizon must complete with no trip")
        rule("R04_no_boundary", "FAIL" if boundary else "PASS" if complete else "UNASSESSABLE",
             "nominal horizon must complete without domain exit")
    elif cfg.expected == "stale_trip":
        detected = (trip_reason == "stale_sensor" and trip_time_s is not None
                    and 0 <= trip_time_s - cfg.fault_at_s <= .5 + 1e-9)
        rule("R05_stale_trip", "PASS" if detected else "FAIL" if complete or boundary else "UNASSESSABLE",
             "stale-sensor trip within 0.5 s of fault")
    elif cfg.expected == "high_trip":
        rule("R06_high_trip", "PASS" if trip_reason == "high_high" else "FAIL" if complete or boundary else "UNASSESSABLE",
             "independent high switch causes trip")
        rule("R07_containment", "FAIL" if boundary or peak_bound >= .95 else "PASS" if complete else "UNASSESSABLE",
             "complete horizon, no boundary and conservative continuous peak < 0.95 m")
    elif cfg.expected == "contained":
        rule("R11_blockage_contained", "FAIL" if boundary or peak_bound >= .65 else "PASS" if complete else "UNASSESSABLE",
             "complete horizon, no boundary and conservative continuous peak < 0.65 m")
    elif cfg.expected == "observe_hazard":
        hazard = trip_reason == "high_high" and boundary == "full"
        rule("R08_hazard_exposed", "PASS" if hazard else "FAIL" if complete or boundary else "UNASSESSABLE",
             "high-switch trip followed by full-tank terminal event; containment failed")
    elif cfg.expected == "characterize":
        rule("R09_characterization_complete", "PASS" if complete else "FAIL" if boundary else "UNASSESSABLE",
             "characterization requires the complete configured horizon")
    if trip_reason is None and not trip_rows:
        rule("R10_latched_command_stop", "NOT_APPLICABLE", "no observed trip; no latch behavior exercised")
    elif not trip_rows:
        rule("R10_latched_command_stop", "UNASSESSABLE", "trip summary has no trip records")
    else:
        latch_ok = all(r["pump_command"] == 0 and r.get("trip") == trip_reason
                       for r in rows if r["time_s"] >= trip_time_s)
        rule("R10_latched_command_stop", "PASS" if latch_ok else "FAIL",
             "all records at/after trip retain reason and request zero pump")
    # A solver failure cannot earn an overall expectation pass even if detection
    # already happened. Containment and scenario expectation remain distinct.
    containment_limit = .95 if cfg.expected == "high_trip" else .65 if cfg.expected == "contained" else p.tank_height_m
    containment = ("FAILED" if boundary or peak_bound >= containment_limit else
                   "UNASSESSABLE" if not complete else "PASSED")
    checks = {key: True if result["status"] == "PASS" else False if result["status"] == "FAIL" else None
              for key, result in results.items()}
    expected_completion = complete or (cfg.expected == "observe_hazard" and boundary == "full")
    return dict(rule_results=results, checks=checks,
                all_checks_pass=run_failure is None and expected_completion
                and all(r["status"] in ("PASS", "NOT_APPLICABLE") for r in results.values()),
                evidence_valid=True, complete_horizon=complete, containment=containment,
                peak_level_m=peak, continuous_peak_bound_m=peak_bound, largest_sample_gap_s=gap,
                final_level_m=rows[-1]["level_m"], max_volume_residual_m3=residual)
