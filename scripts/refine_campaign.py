"""Separate fixed-controller solver accuracy and digital-tick sensitivity."""
import argparse
import csv
from dataclasses import asdict
import json
import math
from pathlib import Path
import numpy as np
from fluidlab.campaign import case_config,normalize_campaign,run_campaign,write_campaign
from fluidlab.provenance import execution_provenance,file_sha256
from fluidlab.thermal import STATE_NAMES,ThermalSolverConfig
from verify_host import benchmark as tank_benchmark


SCALES = np.array([1e-4,1e-4,1e-4,1e-7,1e-7,.01,.01])
SOLVER_CASES = ("nominal_heat_step","frozen_temperature","stuck_heat_lost_sink")
TICK_CASES = ("nominal_heat_step","restriction","frozen_temperature","near_tick_before","near_tick_after","stuck_heat_lost_sink")


def trajectory_comparison(rows,reference):
    def samples(records):
        return {(r["time_us"],r["record_type"],r["event_phase"]):r for r in records
                if r["record_type"] not in ("terminal_boundary","solver_failure")}
    actual,ref=samples(rows),samples(reference)
    common=sorted(set(actual)&set(ref),key=lambda k:(k[0],k[1],str(k[2])))
    if not common:
        return dict(status="UNASSESSABLE",matching_samples=0)
    delta=np.array([[abs(actual[k][n]-ref[k][n]) for n in STATE_NAMES] for k in common])
    raw=np.max(delta,axis=0)
    return dict(matching_samples=len(common),per_state_absolute_max=raw.tolist(),per_state_normalized_max=(raw/SCALES).tolist(),
                max_normalized=float(np.max(raw/SCALES)),last_matching_time_us=common[-1][0],
                meaning="matching absolute scheduled/event samples before terminal roots; terminal event times compared separately")


def optional_delta(a,b):
    return abs(a-b) if a is not None and b is not None else None


def common_prefix_peak(rows,reference,*,topology):
    """Compare identical absolute preterminal keys, never fixed cutoff roots."""
    names=("wall_temperature_k","hot_temperature_k","cold_temperature_k") if topology=="thermal" else ("level_m",)
    rate=.5 if topology=="thermal" else .0004/.05
    def samples(records):
        return {(float(r["time_s"]),r["record_type"],r.get("event_phase")):r for r in records
                if r["record_type"] not in ("terminal_boundary","solver_failure")}
    actual,ref=samples(rows),samples(reference)
    common=sorted(set(actual)&set(ref),key=lambda k:(k[0],k[1],str(k[2])))
    distinct=len({k[0] for k in common})
    if distinct<2:
        return dict(status="UNASSESSABLE",matching_samples=len(common),distinct_shared_times=distinct,
                    last_time_s=common[-1][0] if common else None,peak_bound_delta=None)
    gap=max((b[0]-a[0] for a,b in zip(common,common[1:])),default=0.)
    peaks=[{n:max(float(records[k][n]) for k in common) for n in names} for records in (actual,ref)]
    bounds=[max(p.values())+rate*gap for p in peaks]
    return dict(status="ASSESSED",comparison_scope="identical matching absolute preterminal sample keys; roots excluded",
                matching_samples=len(common),distinct_shared_times=distinct,first_time_s=common[0][0],last_time_s=common[-1][0],largest_common_gap_s=gap,
                rate_bound_per_s=rate,per_state_sampled_peaks=peaks,common_prefix_peak_upper_bounds=bounds,
                peak_bound_delta=abs(bounds[0]-bounds[1]),numerical_error="not included in rate bound")


def boundary_comparison(rows,summary,reference,reference_summary,*,topology):
    """Educational .10s event-resolution gate, independent of peak cutoffs."""
    key="terminal_boundary" if topology=="thermal" else "boundary"
    kinds=(summary.get(key),reference_summary.get(key))
    presence=(kinds[0] is not None,kinds[1] is not None)
    times,actual_presence=[],[]
    for records in (rows,reference):
        terminal=next((r for r in reversed(records) if r["record_type"]=="terminal_boundary"),None)
        actual_presence.append(terminal is not None)
        try:
            raw_time=float(terminal["time_s"]) if terminal else None
        except (TypeError,ValueError):
            raw_time=None
        times.append(raw_time if raw_time is not None and math.isfinite(raw_time) else None)
    delta=optional_delta(*times)
    matches=presence[0]==presence[1] and kinds[0]==kinds[1] and list(presence)==actual_presence
    passing=matches and (not any(presence) or delta is not None and delta<=.10)
    return dict(status="NOT_APPLICABLE" if not any(presence) and not any(actual_presence) else "PASS" if passing else "FAIL",
                presence=list(presence),boundary_kinds=list(kinds),boundary_times_s=times,boundary_time_delta_s=delta,
                presence_and_kind_match=matches,limit_s=.10,
                rationale="predeclared educational timer-resolution criterion; not a physical standard or derived from peak limits")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe",type=Path,required=True)
    parser.add_argument("--out",type=Path,default=Path("artifacts/M5-refinement"))
    parser.add_argument("--solver-only",action="store_true")
    parser.add_argument("--tick-only",action="store_true")
    args=parser.parse_args()
    if args.solver_only and args.tick_only:
        parser.error("choose at most one subset")
    args.out.mkdir(parents=True,exist_ok=False)
    report=dict(schema_version=1,contract="docs/CAMPAIGN.md",state_order=list(STATE_NAMES),state_scales=SCALES.tolist(),
                solver={},thermal_tick={},tank_tick={},execution=execution_provenance(),
                baseline="exact frozen case_config; only recorded solver or tick overrides; noise-free",
                thresholds=dict(tightest_max_normalized=1,thermal_peak_delta_k=.1,thermal_trip_delta_s=.1,tank_peak_delta_m=.002,tank_trip_delta_s=.1,
                                terminated_boundary_time_delta_s=.10))
    report["execution"].update(controller_sha256=file_sha256(args.exe),controller_implementation="portable_c11_host",controller_execution="HOST_SIL")
    def record(cfg,folder,solver=None):
        out=args.out/folder;out.mkdir(parents=True)
        rows,summary=run_campaign(cfg,args.exe,out/"wire",solver=solver)
        write_campaign(out,cfg,rows,summary,args.exe)
        return rows,summary
    if not args.tick_only:
        for name in SOLVER_CASES:
            cfg=case_config(name)
            base=ThermalSolverConfig()
            reference_solver=ThermalSolverConfig(method="DOP853",rtol=1e-11,atol=tuple(v*1e-4 for v in base.atol))
            ref,ref_summary=record(cfg,f"solver/{name}/reference",reference_solver)
            comparisons=[]
            for rtol in (1e-5,1e-7,1e-9):
                solver=ThermalSolverConfig(rtol=rtol,atol=tuple(v*(rtol/1e-7) for v in base.atol))
                rows,summary=record(cfg,f"solver/{name}/{rtol:g}",solver)
                comparison=trajectory_comparison(rows,ref)
                comparison.update(rtol=rtol,solver=summary["solver"],expectation_pass=summary["evaluation"]["expectation_pass"],
                    trip_time_delta_us=optional_delta(summary["metrics"]["first_trip_time_us"],ref_summary["metrics"]["first_trip_time_us"]),
                    terminal_time_delta_us=optional_delta(summary["metrics"]["terminal_time_us"],ref_summary["metrics"]["terminal_time_us"]),
                    global_peak_bound_delta_k=optional_delta(summary["metrics"]["global_peak_upper_bound_k"],ref_summary["metrics"]["global_peak_upper_bound_k"]))
                comparisons.append(comparison)
            tight=comparisons[-1]
            passing=ref_summary["evaluation"]["expectation_pass"] and tight.get("max_normalized",float("inf"))<=1 and all(c["expectation_pass"] for c in comparisons)
            report["solver"][name]=dict(status="PASS" if passing else "FAIL",reference_solver=ref_summary["solver"],comparisons=comparisons)
            print(f"solver {name}: {report['solver'][name]['status']}",flush=True)
    if not args.solver_only:
        for name in TICK_CASES:
            runs={}
            for tick in (200000,100000,50000):
                d=case_config(name).to_dict();d["tick_us"]=tick;d["controller"]["tick_us"]=tick
                rows,summary=record(normalize_campaign(d),f"tick/{name}/{tick}")
                runs[tick]=(rows,summary)
            coarse,fine=runs[100000][1],runs[50000][1]
            full_peak=optional_delta(coarse["metrics"]["global_peak_upper_bound_k"],fine["metrics"]["global_peak_upper_bound_k"])
            terminated=coarse["terminal_boundary"] is not None or fine["terminal_boundary"] is not None
            prefix=common_prefix_peak(runs[100000][0],runs[50000][0],topology="thermal") if terminated else None
            peak=prefix["peak_bound_delta"] if terminated else full_peak
            boundary=boundary_comparison(runs[100000][0],coarse,runs[50000][0],fine,topology="thermal")
            trip=optional_delta(coarse["metrics"]["first_trip_time_us"],fine["metrics"]["first_trip_time_us"])
            trip_assessable=(coarse["metrics"]["first_trip_time_us"] is None)==(fine["metrics"]["first_trip_time_us"] is None)
            passing=peak is not None and peak<.1 and trip_assessable and (trip is None or trip<=100000) and boundary["status"] in ("PASS","NOT_APPLICABLE") and all(s["evaluation"]["expectation_pass"] for _,s in runs.values())
            report["thermal_tick"][name]=dict(status="PASS" if passing else "FAIL",peak_bound_delta_100_50_k=peak,trip_delta_100_50_us=trip,
                peak_comparison_scope="COMMON_PRETERMINAL_PREFIX" if terminated else "FULL_RECOVERABLE_RUN",
                common_prefix_peak_comparison=prefix,full_run_peak_bound_delta_k=full_peak,
                full_run_peak_meaning="fixed95C cutoff peaks are hazard evidence only, excluded from terminal peak convergence gate" if terminated else "recoverable continuous bound",
                boundary_comparison=boundary,
                terminal_delta_100_50_us=optional_delta(coarse["metrics"]["terminal_time_us"],fine["metrics"]["terminal_time_us"]),
                trajectories_100_50=trajectory_comparison(runs[100000][0],runs[50000][0]),
                metrics={str(t):s["metrics"] for t,(_,s) in runs.items()},
                expectation_by_tick={str(t):s["evaluation"]["expectation_pass"] for t,(_,s) in runs.items()})
            print(f"tick {name}: {report['thermal_tick'][name]['status']}",flush=True)
        configs=args.out/"tank-configs";configs.mkdir()
        for name in ("nominal","pump_stuck_on"):
            runs={}
            for tick in (.2,.1,.05):
                d=json.loads((Path("scenarios")/(name+".json")).read_text());d["dt_s"]=tick;d["sensor_noise_std_m"]=0.
                scenario=configs/f"{name}-{tick:g}.json";scenario.write_text(json.dumps(d,indent=2)+"\n",encoding="utf-8",newline="\n")
                out=args.out/"tank-tick"/name/f"{tick:g}"
                summary=tank_benchmark(args.exe,scenario,out)
                with (out/"telemetry.csv").open(newline="",encoding="utf-8") as stream:
                    rows=list(csv.DictReader(stream))
                runs[tick]=(rows,summary)
            a,b=runs[.1][1],runs[.05][1]
            full_peak=abs(a["continuous_peak_bound_m"]-b["continuous_peak_bound_m"])
            terminated=a["boundary"] is not None or b["boundary"] is not None
            prefix=common_prefix_peak(runs[.1][0],runs[.05][0],topology="tank") if terminated else None
            peak=prefix["peak_bound_delta"] if terminated else full_peak
            boundary=boundary_comparison(runs[.1][0],a,runs[.05][0],b,topology="tank")
            trip=optional_delta(a["trip_time_s"],b["trip_time_s"])
            trip_assessable=(a["trip_time_s"] is None)==(b["trip_time_s"] is None)
            common_a={float(r["time_s"]):float(r["level_m"]) for r in runs[.1][0] if r["record_type"]=="controller_tick"}
            common_b={float(r["time_s"]):float(r["level_m"]) for r in runs[.05][0] if r["record_type"]=="controller_tick"}
            delta=max(abs(common_a[t]-common_b[t]) for t in common_a.keys()&common_b.keys())
            passing=peak is not None and peak<.002 and trip_assessable and (trip is None or trip<=.1) and boundary["status"] in ("PASS","NOT_APPLICABLE") and all(s["all_checks_pass"] for _,s in runs.values())
            report["tank_tick"][name]=dict(status="PASS" if passing else "FAIL",peak_bound_delta_m=peak,trip_delta_s=trip,
                                          peak_comparison_scope="COMMON_PRETERMINAL_PREFIX" if terminated else "FULL_RECOVERABLE_RUN",
                                          common_prefix_peak_comparison=prefix,full_run_peak_bound_delta_m=full_peak,boundary_comparison=boundary,
                                          max_matching_level_delta_m=delta,metrics={str(t):s for t,(_,s) in runs.items()})
    groups=(report["solver"],report["thermal_tick"],report["tank_tick"])
    report["status"]="PASS" if all(v["status"]=="PASS" for g in groups for v in g.values()) else "FAIL"
    report["full_refinement_gate"]=not args.solver_only and not args.tick_only and report["status"]=="PASS"
    report["artifact_manifest_sha256"]={p.relative_to(args.out).as_posix():file_sha256(p) for p in args.out.rglob("manifest.json")}
    (args.out/"refinement.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")
    return 0 if report["status"]=="PASS" else 1


if __name__=="__main__":
    raise SystemExit(main())
