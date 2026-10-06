"""Executed C tank benchmark; M5 integrates thermal campaign/export separately."""
import argparse
from dataclasses import asdict
import csv
import json
from pathlib import Path
import platform
import time
import numpy as np
from fluidlab.c_controller import CController, ControllerProcessFailure
from fluidlab.contracts import SolverConfig
from fluidlab.evaluator import evaluate_tank
from fluidlab.plant import Plant, Parameters, IntegrationFailure
from fluidlab.protocol import Configuration, quantize
from fluidlab.provenance import execution_provenance, file_sha256
from fluidlab.runner import load_scenario, run


def benchmark(executable, scenario, out):
    cfg, p, solver = load_scenario(scenario), Parameters(), SolverConfig()
    out.mkdir(parents=True, exist_ok=True)
    config = Configuration.tank(cfg.controller, target_level_m=cfg.target_level_m, tick_us=cfg.dt_us)
    plant = Plant(p, h0_m=cfg.initial_level_m, valve0=cfg.controller.drain_command)
    rng = np.random.default_rng(cfg.seed)
    rows, frozen, boundary, failure, trip_reason, trip_time = [], None, None, None, None, None
    measured, sampled_at_us, sample_id = cfg.initial_level_m, 0, -1
    reason_names = {0:"", 1:"high_high", 4:"invalid_sensor", 5:"sensor_range", 6:"stale_sensor"}
    started = time.perf_counter()
    with CController(executable, config, trace_dir=out/"wire") as controller:
        for tick in range(cfg.duration_us//cfg.dt_us+1):
            now_us, t = tick*cfg.dt_us, tick*cfg.dt_us/1e6
            h = float(plant.y[0])
            active = cfg.fault != "none" and now_us >= cfg.fault_at_us
            #Sampling and fault injection belong outside plant RHS and C core.
            fresh_measured = h + float(rng.normal(0,cfg.sensor_noise_std_m))
            observations = [(6,tick,now_us,1,int(h>=cfg.controller.high_switch_m))]
            if not (active and cfg.fault == "sensor_dropout"):
                sample_id += 1
                measured, sampled_at_us = fresh_measured, now_us
                if active and cfg.fault == "sensor_stuck":
                    frozen = h if frozen is None else frozen
                    measured = frozen
                if active and cfg.fault == "sensor_bias_ramp":
                    measured += cfg.bias_rate_m_s*(t-cfg.fault_at_s)
                observations.insert(0,(1,sample_id,now_us,1,quantize(measured,1e6,"observed_level_m")))
            try:
                reply = controller.step(now_us,observations,operation=1 if tick==0 else 0)
            except ControllerProcessFailure as exc:
                failure=dict(kind="controller_process_failure",message=str(exc),time_s=t,trace_dir=str(exc.trace_dir))
                break
            requested, drain = reply.applied.pump_command, reply.applied.valve_command
            reason = reason_names[reply.status.payload[2]]
            if reason and trip_reason is None:
                trip_reason, trip_time = reason, t
            applied_pump, applied_valve = requested, drain
            if active and cfg.fault=="blocked_outlet":
                applied_valve=0.
            if active and cfg.fault=="pump_failed_off":
                applied_pump=0.
            if active and cfg.fault=="pump_stuck_on":
                applied_pump=1.
            row=dict(record_type="controller_tick",controller_tick=tick,time_us=now_us,time_s=t,
                     clock_id="simulation",level_m=h,measured_level_m=measured,sample_id=sample_id,
                     sample_time_s=sampled_at_us/1e6,receipt_time_s=sampled_at_us/1e6,
                     measurement_age_s=(now_us-sampled_at_us)/1e6,sensor_valid=True,
                     independent_high_switch=h>=cfg.controller.high_switch_m,pump_command=requested,
                     requested_valve_command=drain,applied_pump_command=applied_pump,
                     applied_valve_command=applied_valve,flow_m3_s=float(plant.y[1]),
                     valve_opening=float(plant.y[2]),target_m=cfg.target_level_m,trip=reason,
                     volume_residual_m3=plant.volume_residual_m3())
            rows.append(row)
            if now_us==cfg.duration_us:
                break
            try:
                advanced=plant.advance((now_us+cfg.dt_us)/1e6-plant.t,applied_pump,applied_valve,solver=solver)
            except IntegrationFailure as exc:
                advanced=exc.advance
                failure=dict(kind="solver_failure",message=str(exc),time_s=advanced.time_s)
            if advanced.boundary or failure:
                boundary=advanced.boundary
                rows.append(dict(row,record_type="solver_failure" if failure else "terminal_boundary",
                                 time_us=None,time_s=advanced.time_s,level_m=float(plant.y[0]),
                                 measurement_age_s=advanced.time_s-sampled_at_us/1e6,
                                 flow_m3_s=float(plant.y[1]),valve_opening=float(plant.y[2]),
                                 volume_residual_m3=plant.volume_residual_m3()))
                break
    result=evaluate_tank(cfg,p,rows,trip_reason=trip_reason,trip_time_s=trip_time,boundary=boundary,run_failure=failure)
    baseline_rows, baseline = run(cfg,p)
    pairs=zip((r for r in rows if r["record_type"]=="controller_tick"),
              (r for r in baseline_rows if r["record_type"]=="controller_tick"))
    max_level_delta=max((abs(a["level_m"]-b["level_m"]) for a,b in pairs),default=None)
    result.update(name=cfg.name,controller="portable C11 host (actual subprocess)",trip_reason=trip_reason,
                  trip_time_s=trip_time,boundary=boundary,run_failure=failure,
                  wall_time_s=time.perf_counter()-started,physical_validation="NOT_STARTED",board_execution="NOT_EXECUTED",
                  python_baseline_max_matching_tick_level_delta_m=max_level_delta,
                  python_baseline_trip_time_s=baseline["trip_time_s"],python_baseline_boundary=baseline["boundary"],
                  comparison_meaning="separate Python baseline; quantized C commands and observations may differ")
    with (out/"telemetry.csv").open("w",encoding="utf-8",newline="") as stream:
        if rows:
            writer=csv.DictWriter(stream,fieldnames=rows[0].keys(),lineterminator="\n")
            writer.writeheader();writer.writerows(rows)
    (out/"summary.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")
    provenance=execution_provenance()
    root=Path(__file__).resolve().parents[1]
    sources={path.relative_to(root).as_posix():file_sha256(path) for path in sorted((root/"firmware/core").glob("*"))}
    manifest=dict(version=1,scenario=asdict(cfg),parameters=asdict(p),parameter_pedigree="assumed",
                  solver=solver.executed(cfg.dt_s),controller_configuration=asdict(config),
                  controller_configuration_sha256=config.sha256,controller_binary_sha256=file_sha256(executable),
                  controller_sources_sha256=sources,provenance=provenance,platform=platform.platform(),
                  clock="integer virtual microseconds; subprocess deadlines are independent host monotonic seconds",
                  quantization=dict(level_um=.5,command_ppm=.5,gain_scale=1e6),
                  physical_validation="NOT_STARTED",board_execution="NOT_EXECUTED")
    manifest["artifact_sha256"]={path.relative_to(out).as_posix():file_sha256(path)
                                 for path in sorted(out.rglob("*")) if path.is_file() and path.name!="manifest.json"}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--exe",type=Path,required=True)
    parser.add_argument("--out",type=Path,default=Path("artifacts/M3-host"))
    parser.add_argument("--scenario",type=Path,action="append")
    args=parser.parse_args()
    if not args.exe.is_file():
        parser.error("build actual C host first; no Python fallback")
    root=Path(__file__).resolve().parents[1]
    scenarios=args.scenario or sorted((root/"scenarios").glob("*.json"))
    args.out.mkdir(parents=True,exist_ok=True)
    results=[benchmark(args.exe.resolve(),path,args.out/path.stem) for path in scenarios]
    (args.out/"suite.json").write_text(json.dumps(results,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps([{k:r[k] for k in ("name","all_checks_pass","trip_reason","trip_time_s","boundary","containment","wall_time_s","python_baseline_max_matching_tick_level_delta_m")} for r in results],indent=2))
    return 0 if all(r["all_checks_pass"] for r in results) else 1


if __name__=="__main__":
    raise SystemExit(main())
