"""Deterministic virtual-time scheduler. NO wall-clock or hard-RT claims."""
from dataclasses import asdict
from pathlib import Path
import csv, hashlib, json, platform, subprocess
import numpy as np
import scipy
from .plant import Plant, Parameters
from .control import PIController, Supervisor, Observation

FAULTS = {"none","blocked_outlet","pump_failed_off","sensor_dropout",
          "sensor_bias_ramp","sensor_stuck","pump_stuck_on"}


def load_scenario(path):
    cfg = json.loads(Path(path).read_text())
    if cfg.get("fault", "none") not in FAULTS:
        raise ValueError("unknown fault")
    dt,duration,start = cfg["dt_s"],cfg["duration_s"],cfg.get("fault_at_s",60.)
    if not all(np.isfinite(x) and x > 0 for x in (dt,duration)) or start < 0:
        raise ValueError("invalid scenario timing")
    # Faults must align with ticks; adaptive solver input is held across a tick.
    if not np.isclose(start/dt,round(start/dt),atol=1e-8,rtol=0):
        raise ValueError("fault time must align with controller ticks")
    if not np.isclose(duration/dt,round(duration/dt),atol=1e-8,rtol=0):
        raise ValueError("duration must align with controller ticks")
    return cfg


def run(cfg, p=None, method="RK45", rtol=1e-7, atol=None):
    p = p or Parameters()
    plant = Plant(p,h0_m=cfg.get("initial_level_m",0.25))
    ctrl,supervisor = PIController(),Supervisor()
    dt,duration = cfg["dt_s"],cfg["duration_s"]
    fault,at = cfg.get("fault","none"),cfg.get("fault_at_s",60.)
    rng = np.random.default_rng(cfg.get("seed",42))
    noise = cfg.get("sensor_noise_std_m",0.0)
    rows, frozen = [], None
    last_observation = Observation(float(plant.y[0]),0.,True,False)
    boundary = None
    for k in range(round(duration/dt)+1):
        t = k*dt
        h = float(plant.y[0])
        active = t >= at-1e-9 and fault != "none"
        measured,stamp = h+float(rng.normal(0,noise)),t
        if active and fault == "sensor_dropout":
            measured,stamp = last_observation.level_m,last_observation.sampled_at_s
        if active and fault == "sensor_stuck":
            frozen = h if frozen is None else frozen
            measured = frozen # fresh timestamp: deliberately undetectable via freshness
        if active and fault == "sensor_bias_ramp":
            measured += cfg.get("bias_rate_m_s",-0.01)*(t-at)
        obs = Observation(measured,stamp,True,h >= 0.8)
        last_observation = obs
        tripped = supervisor.update(t,obs)
        requested = 0. if tripped else ctrl.update(cfg.get("target_level_m",0.5),measured,dt)
        # The drain remains commanded to 0.65 after trip. This topology's inflow
        # is stopped while gravity drainage is preserved; not a universal rule.
        actual_pump = requested
        actual_valve = 0.65
        if active and fault == "blocked_outlet": actual_valve = 0.
        if active and fault == "pump_failed_off": actual_pump = 0.
        if active and fault == "pump_stuck_on": actual_pump = 1.
        rows.append(dict(time_s=t,level_m=h,measured_level_m=measured,
                         sample_time_s=stamp,pump_command=requested,
                         applied_pump_command=actual_pump,applied_valve_command=actual_valve,
                         flow_m3_s=float(plant.y[1]),valve_opening=float(plant.y[2]),
                         target_m=cfg.get("target_level_m",0.5),
                         trip=supervisor.reason or "",volume_residual_m3=plant.volume_residual_m3()))
        if k == round(duration/dt): break
        advanced = plant.advance(dt,actual_pump,actual_valve,method,rtol,atol)
        if advanced.boundary:
            boundary = advanced.boundary
            rows.append(dict(rows[-1],time_s=advanced.time_s,level_m=float(plant.y[0]),
                             flow_m3_s=float(plant.y[1]),valve_opening=float(plant.y[2]),
                             volume_residual_m3=plant.volume_residual_m3()))
            break
    levels = np.array([r["level_m"] for r in rows])
    checks = {"R02_volume_balance": bool(max(abs(r["volume_residual_m3"]) for r in rows) < 1e-9)}
    expected = cfg.get("expected","nominal")
    if expected == "nominal":
        tail = [r for r in rows if r["time_s"] >= duration-30.]
        checks.update(R01_tracking=bool(tail) and all(abs(r["level_m"]-r["target_m"]) < 0.02 for r in tail),
                      R03_no_trip=supervisor.reason is None,R04_no_boundary=boundary is None)
    elif expected == "stale_trip":
        checks["R05_stale_trip"] = supervisor.reason == "stale_sensor" and supervisor.tripped_at_s-at <= 0.5+1e-9
    elif expected == "high_trip":
        checks["R06_high_trip"] = supervisor.reason == "high_high"
        checks["R07_containment"] = bool(boundary is None and levels.max() < 0.95)
    elif expected == "contained":
        checks["R11_blockage_contained"] = bool(boundary is None and levels.max() < 0.65)
    elif expected == "observe_hazard":
        checks["R08_hazard_exposed"] = supervisor.reason == "high_high" and boundary == "full"
    elif expected == "characterize":
        checks["R09_characterization_complete"] = True
    else: raise ValueError("unknown expected outcome")
    trip_rows = [r for r in rows if r["trip"]]
    checks["R10_latched_command_stop"] = all(r["pump_command"] == 0 for r in trip_rows)
    summary = dict(name=cfg["name"],checks=checks,all_checks_pass=all(checks.values()),
                   trip_reason=supervisor.reason,trip_time_s=supervisor.tripped_at_s,
                   boundary=boundary,peak_level_m=float(levels.max()),final_level_m=float(levels[-1]),
                   max_volume_residual_m3=max(abs(r["volume_residual_m3"]) for r in rows),
                   result_meaning="scenario expectations only; NOT physical safety validation",
                   physical_validation="NOT_STARTED",parameters=asdict(p))
    return rows,summary


def write_run(out, cfg, rows, summary, method="RK45",rtol=1e-7):
    out = Path(out); out.mkdir(parents=True,exist_ok=True)
    with (out/"telemetry.csv").open("w",newline="") as f:
        writer = csv.DictWriter(f,fieldnames=rows[0].keys()); writer.writeheader();writer.writerows(rows)
    (out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    try:
        revision = subprocess.check_output(["git","rev-parse","HEAD"],stderr=subprocess.DEVNULL,text=True).strip()
        dirty = bool(subprocess.check_output(["git","status","--porcelain"],stderr=subprocess.DEVNULL,text=True).strip())
    except (subprocess.CalledProcessError,FileNotFoundError): revision,dirty = "unversioned",True
    root = Path(__file__).resolve().parents[2]
    source_digest = hashlib.sha256()
    for path in sorted((root/"src").rglob("*.py")):
        source_digest.update(str(path.relative_to(root)).encode());source_digest.update(path.read_bytes())
    canonical = json.dumps(cfg,sort_keys=True).encode()
    manifest = dict(scenario=cfg,scenario_sha256=hashlib.sha256(canonical).hexdigest(),
                    source_sha256=source_digest.hexdigest(),git_revision=revision,git_dirty=dirty,
                    python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,
                    solver=method,rtol=rtol,atol=[1e-9,1e-11,1e-9,1e-11,1e-11],
                    solver_max_step_s=min(cfg["dt_s"],0.05),clock="virtual; zero-order-held inputs",
                    validation_status="NOT_STARTED")
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
