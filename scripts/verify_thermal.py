"""Execute frozen M2 analytic benchmarks and fixed-tick solver refinement.

Run natively: uv run python scripts/verify_thermal.py --out artifacts/M2
No controller, device execution or measured process data are involved.
"""
from dataclasses import asdict, replace
from pathlib import Path
import argparse
import csv
import json
import math
import time
import numpy as np
from scipy.linalg import expm
from fluidlab.contracts import microseconds
from fluidlab.provenance import execution_provenance, file_sha256
from fluidlab.thermal import (ThermalInputs, ThermalParameters, ThermalPlant, ThermalSolverConfig,
                              STATE_NAMES, STATE_UNITS, IntegrationFailure, PlantStopped,
                              TEMPERATURE_MIN_K, TEMPERATURE_MAX_K, hydraulic_operating_point)


SCALES = np.array([1e-4, 1e-4, 1e-4, 1e-7, 1e-7, .01, .01])
TIGHT = ThermalSolverConfig(method="DOP853", rtol=1e-11, atol=(1e-11,)*5+(1e-8,)*2)
THRESHOLDS = dict(analytic_temperature_error_k=1e-5, equilibrium_error_k=.01,
                  weighted_energy_error_j=1e-3, normalized_pressure_residual=1e-8,
                  tightest_solver_normalized_maximum=1)


def snapshot(plant, time_us, record_type="benchmark_sample"):
    return dict(record_type=record_type, time_us=time_us, time_s=plant.t, clock_id="simulation",
                **dict(zip(STATE_NAMES, map(float, plant.y))), flow_m3_s=float(plant.flow_m3_s),
                pump_pressure_pa=plant.pump_pressure_pa, energy_residual_j=plant.energy_residual_j())


def fixed_ticks(plant, inputs, duration_s, tick_s, solver):
    duration_us, tick_us = microseconds(duration_s, "duration_s"), microseconds(tick_s, "tick_s")
    if duration_us <= 0 or tick_us <= 0 or duration_us % tick_us:
        raise ValueError("benchmark duration and tick must be positive aligned microseconds")
    initial = snapshot(plant, 0)
    rows = [initial]
    failure, boundary = None, None
    totals = dict(interval_count=0, nfev=0, njev=0, nlu=0)
    for target_us in range(tick_us, duration_us+1, tick_us):
        try:
            result = plant.advance(target_us/1_000_000-plant.t, inputs, solver)
        except IntegrationFailure as exc:
            result = exc.advance
            failure = dict(message=str(exc), diagnostics=result.diagnostics)
        totals["interval_count"] += 1
        for key in ("nfev", "njev", "nlu"):
            totals[key] += result.diagnostics[key]
        boundary = result.boundary
        rows.append(snapshot(plant, None if boundary or failure else target_us,
                             "solver_failure" if failure else "terminal_boundary" if boundary else "benchmark_sample"))
        if boundary or failure:
            break
    metadata = dict(model=dict(version=1, topology="thermal_circulation", parameter_pedigree="assumed",
                               parameters=asdict(plant.p), domain=dict(temperature_min_k=TEMPERATURE_MIN_K,
                                                                     temperature_max_k=TEMPERATURE_MAX_K)),
                    initial_state=initial, applied_inputs=asdict(inputs), solver=solver.executed(tick_s),
                    duration_s=duration_s, tick_s=tick_s, clock="simulation integer microseconds",
                    flow_mode="coupled_hydraulic" if plant.imposed_flow_m3_s is None else "imposed_flow_benchmark",
                    imposed_flow_m3_s=plant.imposed_flow_m3_s, complete_horizon=not boundary and not failure,
                    boundary=boundary, failure=failure, diagnostics=totals,
                    last_interval=plant.last_advance.diagnostics)
    return rows, metadata


def save_trace(out, name, rows):
    path = out/f"{name}.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Independent thermal benchmark evidence; no controller")
    parser.add_argument("--out", type=Path, default=Path("artifacts/M2"))
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    provenance = execution_provenance()
    provenance.update(controller_implementation="none_model_benchmarks", controller_sha256=None,
                      units=dict(zip(STATE_NAMES, STATE_UNITS), time_s="s", flow_m3_s="m3/s",
                                 pump_pressure_pa="Pa", energy_residual_j="J"))
    report = dict(version=1, contract="docs/THERMAL_MODEL.md", parameter_pedigree="assumed",
                  physical_validation="NOT_STARTED", device_execution="NOT_EXECUTED", provenance=provenance,
                  thresholds=THRESHOLDS, cases={}, checks={},
                  scope="plant equation/numerical verification; no controller, measurements or physical validation")
    traces = {}

    def record(name, plant, inputs, duration, tick=10, solver=TIGHT):
        rows, metadata = fixed_ticks(plant, inputs, duration, tick, solver)
        traces[name] = rows
        report["cases"][name] = metadata
        save_trace(out, name, rows)
        return rows

    def check(name, value, threshold, *, complete=True, inclusive=False):
        passing = math.isfinite(value) and (value <= threshold if inclusive else value < threshold)
        report["checks"][name] = dict(status="PASS" if complete and passing else "FAIL" if complete else "UNASSESSABLE",
                                     actual=value, threshold=threshold, comparison="<=" if inclusive else "<")

    p = ThermalParameters()
    hydro = []
    for speed, opening in ((0, .65), (.5, 0), (1, 1), (.5274982823, .65), (.8, .1), (.1, .01)):
        point = hydraulic_operating_point(speed, opening, p)
        pump_pa = 100000*speed**2 - 4e11*point.flow_m3_s**2
        system_pa = None if opening == 0 else (6e11+1e11/opening**2)*point.flow_m3_s**2
        residual = 0 if opening == 0 else abs(pump_pa-system_pa)/100000
        hydro.append(dict(speed=speed, opening=opening, **asdict(point),
                          independent_system_pressure_pa=system_pa, normalized_residual=residual))
    report["cases"]["hydraulic_substitution"] = hydro
    check("hydraulic_pressure_substitution", max(row["normalized_residual"] for row in hydro), THRESHOLDS["normalized_pressure_residual"])

    isolated = replace(p, hot_conductance_w_k=0, sink_conductance_w_k=0)
    rows = record("constant_heating", ThermalPlant(isolated, valve_opening=0), ThermalInputs(heat_command=1, valve_command=0), 100)
    error = max(abs(row["wall_temperature_k"]-(293.15+5000*row["time_s"]/10000)) for row in rows)
    check("constant_heating_max_sampled_error_k", error, 1e-5, complete=report["cases"]["constant_heating"]["complete_horizon"])

    rows = record("exponential_cooling", ThermalPlant(replace(p, hot_conductance_w_k=0), cold_temperature_k=330, valve_opening=0),
                  ThermalInputs(valve_command=0), 100)
    error = max(abs(row["cold_temperature_k"]-(283.15+(330-283.15)*math.exp(-500*row["time_s"]/12540))) for row in rows)
    check("exponential_cooling_max_sampled_error_k", error, 1e-5, complete=report["cases"]["exponential_cooling"]["complete_horizon"])

    # Independent constant-flow matrix, assembled from raw frozen coefficients.
    a = np.array([[-300/10000, 300/10000, 0], [300/8360, -(300+627)/8360, 627/8360],
                  [0, 627/12540, -(627+500)/12540]])
    steady = np.array([283.15+5000/500+5000/627+5000/300, 283.15+5000/500+5000/627, 283.15+5000/500])
    rows = record("imposed_flow_equilibrium", ThermalPlant(imposed_flow_m3_s=.00015), ThermalInputs(heat_command=1), 1200, 20)
    expected = [steady+expm(a*row["time_s"])@(np.full(3, 293.15)-steady) for row in rows]
    states = np.array([[row[key] for key in STATE_NAMES[:3]] for row in rows])
    matrix_error = float(np.max(np.abs(states-np.array(expected))))
    equilibrium_error = float(np.max(np.abs(states[-1]-steady)))
    complete = report["cases"]["imposed_flow_equilibrium"]["complete_horizon"]
    check("matrix_exponential_max_sampled_error_k", matrix_error, 1e-5, complete=complete)
    check("1200s_equilibrium_error_k", equilibrium_error, .01, complete=complete)
    report["cases"]["imposed_flow_equilibrium"].update(independent_steady_temperatures_k=steady.tolist(),
                                                     independent_matrix=a.tolist(),
                                                     slowest_time_constant_s=float(-1/max(np.linalg.eigvals(a).real)))

    rows = record("internal_mixing", ThermalPlant(replace(p, sink_conductance_w_k=0), wall_temperature_k=340,
                  hot_temperature_k=310, cold_temperature_k=290, imposed_flow_m3_s=.00015), ThermalInputs(), 100)
    energy = [10000*row["wall_temperature_k"]+8360*row["hot_temperature_k"]+12540*row["cold_temperature_k"] for row in rows]
    check("internal_mixing_weighted_energy_error_j", max(abs(value-energy[0]) for value in energy), 1e-3,
          complete=report["cases"]["internal_mixing"]["complete_horizon"])
    rows = record("no_flow_wall_exchange", ThermalPlant(replace(p, sink_conductance_w_k=0), wall_temperature_k=340,
                  hot_temperature_k=290, valve_opening=0), ThermalInputs(valve_command=0), 100)
    energy = [10000*row["wall_temperature_k"]+8360*row["hot_temperature_k"] for row in rows]
    check("no_flow_wall_hot_energy_error_j", max(abs(value-energy[0]) for value in energy), 1e-3,
          complete=report["cases"]["no_flow_wall_exchange"]["complete_horizon"])
    report["cases"]["no_flow_steady_state"] = dict(status="NOT_APPLICABLE", imposed_heat_w=5000, flow_m3_s=0,
                                                   reason="wall/hot subsystem has net positive heat with no flowing removal; no finite steady state")
    rows = record("no_flow_heating", ThermalPlant(valve_opening=0), ThermalInputs(heat_command=1, valve_command=0), 60)
    gain_error = max(abs(10000*(row["wall_temperature_k"]-293.15)+8360*(row["hot_temperature_k"]-293.15)-5000*row["time_s"])
                     for row in rows)
    check("no_flow_heating_wall_hot_energy_error_j", gain_error, 1e-3,
          complete=report["cases"]["no_flow_heating"]["complete_horizon"])

    event_plant = ThermalPlant(isolated, valve_opening=0)
    rows = record("upper_boundary", event_plant, ThermalInputs(heat_command=1, valve_command=0), 200)
    event_error = abs(event_plant.t-(368.15-293.15)*10000/5000)
    # Event error is recorded; the original contract gives temperature/error
    # scales, not a new event-time acceptance threshold.
    report["cases"]["upper_boundary"].update(independent_event_time_s=150, absolute_event_time_error_s=event_error)
    refused_reentry = False
    try:
        event_plant.advance(.1, ThermalInputs())
    except PlantStopped:
        refused_reentry = True
    report["checks"]["upper_boundary_stopped"] = dict(status="PASS" if refused_reentry and event_plant.stop_reason == "wall_upper" else "FAIL",
                                                       meaning="terminal boundary; raw root retained; no continuing run")

    dt, horizon = .1, 240
    speed = math.sqrt((.00015**2)*(4e11+6e11+1e11/.65**2)/100000)
    inputs = ThermalInputs(heat_command=1, pump_command=speed, valve_command=.65)
    reference_solver = ThermalSolverConfig(method="DOP853", rtol=1e-11, atol=(1e-12,)*5+(1e-9,)*2)
    reference = record("solver_reference", ThermalPlant(), inputs, horizon, dt, reference_solver)
    reference_values = np.array([[row[key] for key in STATE_NAMES] for row in reference])
    refinements = []
    for rtol in (1e-5, 1e-7, 1e-9):
        solver = ThermalSolverConfig(rtol=rtol, atol=tuple(value*(rtol/1e-7) for value in ThermalSolverConfig().atol))
        name = f"solver_rtol_{rtol:.0e}"
        rows = record(name, ThermalPlant(), inputs, horizon, dt, solver)
        matching = ([row["time_us"] for row in rows] == [row["time_us"] for row in reference]
                    and report["cases"][name]["complete_horizon"] and report["cases"]["solver_reference"]["complete_horizon"])
        values = np.array([[row[key] for key in STATE_NAMES] for row in rows])
        errors = np.max(np.abs(values-reference_values), axis=0) if matching else np.full(7, np.nan)
        normalized = errors/SCALES
        refinements.append(dict(rtol=rtol, status="ASSESSED" if matching else "UNASSESSABLE",
                                maximum_error_per_state=errors.tolist() if matching else None,
                                normalized_error_per_state=normalized.tolist() if matching else None,
                                normalized_maximum=float(np.max(normalized)) if matching else None))
    tightest = refinements[-1]
    check("tightest_solver_normalized_maximum", tightest["normalized_maximum"] if tightest["normalized_maximum"] is not None else 0,
          1, complete=tightest["status"] == "ASSESSED", inclusive=True)
    report["solver_refinement"] = dict(tick_s=dt, horizon_s=horizon, noise="none", state_order=list(STATE_NAMES),
                                      comparison_scales=SCALES.tolist(), state_units=list(STATE_UNITS), cases=refinements,
                                      convergence_behavior="NON_MONOTONIC" if any(
                                          right["normalized_maximum"] > left["normalized_maximum"]
                                          for left, right in zip(refinements, refinements[1:])
                                          if left["normalized_maximum"] is not None and right["normalized_maximum"] is not None) else "NONINCREASING",
                                      convergence_note="The 0.05 s step cap already resolves this smooth case; tiny errors may not shrink monotonically. No monotonic convergence claim.",
                                      interpretation="integration refinement at fixed held-input tick; controller-tick refinement remains M5")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(9, 7))
    equilibrium = traces["imposed_flow_equilibrium"]
    for index, key in enumerate(STATE_NAMES[:3]):
        axes[0].plot([row["time_s"] for row in equilibrium], [row[key] for row in equilibrium], label=key)
        axes[0].axhline(steady[index], ls="--", alpha=.4)
    axes[0].set(xlabel="Simulation time (s)", ylabel="Temperature (K)", title="Imposed-flow benchmark; assumed coefficients")
    axes[0].legend()
    for row in refinements:
        if row["normalized_error_per_state"] is not None:
            axes[1].plot(range(7), row["normalized_error_per_state"], "o-", label=f"rtol={row['rtol']:.0e}")
    axes[1].set_xticks(range(7), ["Tw", "Th", "Tc", "speed", "opening", "heat in", "heat out"])
    axes[1].set(ylabel="Error / declared per-state scale", title="Fixed 0.1 s tick; DOP853 reference")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(out/"thermal_benchmarks.png", dpi=160)
    plt.close(fig)

    report["all_checks_pass"] = all(value["status"] == "PASS" for value in report["checks"].values())
    report["host_wall_elapsed_s"] = time.perf_counter()-started
    (out/"verification.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8", newline="\n")
    artifact_names = [f"{name}.csv" for name in traces]+["thermal_benchmarks.png", "verification.json"]
    manifest = dict(version=1, provenance=provenance, physical_validation="NOT_STARTED", device_execution="NOT_EXECUTED",
                    artifact_sha256={name: file_sha256(out/name) for name in artifact_names})
    (out/"manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False)+"\n", encoding="utf-8", newline="\n")
    print(json.dumps(dict(all_checks_pass=report["all_checks_pass"], checks=report["checks"],
                          solver_refinement=refinements, host_wall_elapsed_s=report["host_wall_elapsed_s"]), indent=2))
    return 0 if report["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
