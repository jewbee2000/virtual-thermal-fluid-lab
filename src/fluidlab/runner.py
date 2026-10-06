"""Deterministic integer-microsecond tank scheduler; no wall-clock/RT claims."""
from dataclasses import asdict
from pathlib import Path
import csv
import hashlib
import json
import numpy as np
from .contracts import FAULTS, SolverConfig, normalize_scenario
from .plant import Plant, Parameters, IntegrationFailure
from .control import PIController, Supervisor, Observation
from .evaluator import evaluate_tank
from .provenance import canonical_json, execution_provenance, file_sha256


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_scenario(path, p=None):
    cfg = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
                     parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"nonfinite JSON number: {value}")))
    p = Parameters() if p is None else p
    if not isinstance(p, Parameters):
        raise ValueError("p must be immutable Parameters")
    return normalize_scenario(cfg, p)


def run(cfg, p=None, method="RK45", rtol=1e-7, atol=None, max_step_s=0.05):
    p = Parameters() if p is None else p
    if not isinstance(p, Parameters):
        raise ValueError("p must be immutable Parameters")
    cfg = normalize_scenario(cfg, p)
    solver = SolverConfig(method=method, rtol=rtol,
                          atol=atol if atol is not None else SolverConfig().atol,
                          max_step_s=max_step_s)
    execution_config = dict(version=1, scenario=asdict(cfg),
                            model=dict(version=1, topology="atmospheric_tank", parameters=asdict(p),
                                       parameter_pedigree="assumed", initial_pump_flow_m3_s=0.0,
                                       initial_valve_opening=cfg.controller.drain_command),
                            solver=solver.executed(cfg.dt_s), provenance=execution_provenance())
    plant = Plant(p, h0_m=cfg.initial_level_m, valve0=cfg.controller.drain_command)
    controller_cfg = cfg.controller
    ctrl = PIController(controller_cfg.kp_per_m, controller_cfg.ki_per_m_s, controller_cfg.bias)
    supervisor = Supervisor(controller_cfg.stale_after_s, controller_cfg.sensor_min_m,
                            controller_cfg.sensor_max_m)
    rng = np.random.default_rng(cfg.seed)
    rows, frozen, boundary, failure = [], None, None, None
    diagnostics = dict(interval_count=0, nfev=0, njev=0, nlu=0, last_interval=None, failure=None)
    last_observation = Observation(float(plant.y[0]), 0.0, True, False)
    sample_id = -1
    for tick in range(cfg.duration_us // cfg.dt_us + 1):
        now_us = tick * cfg.dt_us
        t = now_us / 1_000_000
        h = float(plant.y[0])
        active = cfg.fault != "none" and now_us >= cfg.fault_at_us
        measured, stamp = h + float(rng.normal(0, cfg.sensor_noise_std_m)), t
        if active and cfg.fault == "sensor_dropout":
            measured, stamp = last_observation.level_m, last_observation.sampled_at_s
        else:
            sample_id += 1
        if active and cfg.fault == "sensor_stuck":
            frozen = h if frozen is None else frozen
            measured = frozen  # plausible fresh samples; fault knowledge stays out of control
        if active and cfg.fault == "sensor_bias_ramp":
            measured += cfg.bias_rate_m_s * (t - cfg.fault_at_s)
        obs = Observation(measured, stamp, True, h >= controller_cfg.high_switch_m)
        last_observation = obs
        tripped = supervisor.update(t, obs)
        requested = 0.0 if tripped else ctrl.update(cfg.target_level_m, measured, cfg.dt_s)
        actual_pump = requested
        actual_valve = controller_cfg.drain_command
        if active and cfg.fault == "blocked_outlet":
            actual_valve = 0.0
        if active and cfg.fault == "pump_failed_off":
            actual_pump = 0.0
        if active and cfg.fault == "pump_stuck_on":
            actual_pump = 1.0
        row = dict(record_type="controller_tick", controller_tick=tick, time_us=now_us, time_s=t,
                   clock_id="simulation", level_m=h, measured_level_m=measured,
                   sample_id=sample_id, sample_time_s=stamp, receipt_time_s=stamp,
                   measurement_age_s=t-stamp, sensor_valid=True,
                   independent_high_switch=obs.high_high, pump_command=requested,
                   requested_valve_command=controller_cfg.drain_command,
                   applied_pump_command=actual_pump, applied_valve_command=actual_valve,
                   flow_m3_s=float(plant.y[1]), valve_opening=float(plant.y[2]),
                   target_m=cfg.target_level_m, trip=supervisor.reason or "",
                   volume_residual_m3=plant.volume_residual_m3())
        rows.append(row)
        if now_us == cfg.duration_us:
            break
        # Endpoints come from the integer virtual clock; inputs remain held.
        interval_s = (now_us + cfg.dt_us) / 1_000_000 - plant.t
        try:
            advanced = plant.advance(interval_s, actual_pump, actual_valve, solver=solver)
        except IntegrationFailure as exc:
            advanced = exc.advance
            failure = dict(kind="solver_failure", message=str(exc), time_s=advanced.time_s)
        diagnostics["interval_count"] += 1
        diagnostics["last_interval"] = advanced.diagnostics
        for key in ("nfev", "njev", "nlu"):
            diagnostics[key] += advanced.diagnostics.get(key, 0)
        if advanced.boundary or failure:
            boundary = advanced.boundary
            if failure:
                diagnostics["failure"] = advanced.diagnostics
            snapshot = dict(row, record_type="solver_failure" if failure else "terminal_boundary",
                            time_us=None, time_s=advanced.time_s, level_m=float(plant.y[0]),
                            measurement_age_s=advanced.time_s-stamp,
                            flow_m3_s=float(plant.y[1]), valve_opening=float(plant.y[2]),
                            volume_residual_m3=plant.volume_residual_m3())
            rows.append(snapshot)
            break
    evaluation = evaluate_tank(cfg, p, rows, trip_reason=supervisor.reason,
                               trip_time_s=supervisor.tripped_at_s, boundary=boundary,
                               run_failure=failure)
    summary = dict(version=1, name=cfg.name, **evaluation, trip_reason=supervisor.reason,
                   trip_time_s=supervisor.tripped_at_s, boundary=boundary,
                   run_outcome="solver_failure" if failure else "domain_boundary_reached" if boundary else "complete_horizon",
                   run_failure=failure, diagnostics=diagnostics, execution_config=execution_config,
                   peak_bound_meaning="sample max + Qmax/A * largest gap; excludes numerical error",
                   result_meaning="scenario expectations only; NOT physical safety validation",
                   physical_validation="NOT_STARTED", parameters=asdict(p))
    return rows, summary


def write_run(out, cfg, rows, summary, method=None, rtol=None, *, extra_artifacts=()):
    """Export actual run configuration; legacy caller solver labels are ignored."""
    if not rows or "execution_config" not in summary:
        raise ValueError("write_run requires trace and executed configuration from run()")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "telemetry.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    executed = summary["execution_config"]
    scenario = executed["scenario"]
    solver = executed["solver"]
    manifest = dict(version=1, **executed["provenance"],
                    scenario=scenario, scenario_sha256=hashlib.sha256(canonical_json(scenario)).hexdigest(),
                    model=executed["model"], controller=scenario["controller"], solver_config=solver,
                    solver=solver["method"], rtol=solver["rtol"], atol=solver["atol"],
                    solver_max_step_s=solver["effective_max_step_s"],
                    controller_tick_s=scenario["dt_s"], seed=scenario["seed"],
                    clock="simulation integer microseconds; zero-order-held inputs",
                    input_provenance="synthetic tank observations; ideal independent high switch",
                    validation_status="NOT_STARTED",
                    artifact_sha256={name: file_sha256(out / name) for name in ("telemetry.csv", "summary.json")})
    for relative in extra_artifacts:
        path = (out / relative).resolve()
        if not path.is_relative_to(out.resolve()) or not path.is_file():
            raise ValueError("extra artifacts must identify current exported files within out")
        if path == (out / "manifest.json").resolve():
            raise ValueError("manifest cannot hash itself")
        manifest["artifact_sha256"][path.relative_to(out.resolve()).as_posix()] = file_sha256(path)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
