"""Assumed single-phase circulation plant; see docs/THERMAL_MODEL.md.

No controller, sensor noise or wall clock enters these balances. An imposed-flow
option is an explicitly labeled analytic benchmark, not the coupled pump model.
"""
from dataclasses import asdict, dataclass
import math
import numpy as np
from scipy.integrate import solve_ivp
from .contracts import number, version
from .plant import IntegrationFailure, PlantStopped


TEMPERATURE_MIN_K = 273.15
TEMPERATURE_MAX_K = 368.15
STATE_NAMES = ("wall_temperature_k", "hot_temperature_k", "cold_temperature_k",
               "pump_speed", "valve_opening", "heat_in_j", "heat_rejected_j")
STATE_UNITS = ("K", "K", "K", "1", "1", "J", "J")


@dataclass(frozen=True)
class ThermalParameters:
    version: int = 1
    density_kg_m3: float = 1000.0
    specific_heat_j_kg_k: float = 4180.0
    hot_mass_kg: float = 2.0
    cold_mass_kg: float = 3.0
    wall_capacity_j_k: float = 10000.0
    max_heat_w: float = 5000.0
    hot_conductance_w_k: float = 300.0
    sink_conductance_w_k: float = 500.0
    sink_temperature_k: float = 283.15
    pump_shutoff_pa: float = 100000.0
    pump_curve_pa_s2_m6: float = 4e11
    pipe_resistance_pa_s2_m6: float = 6e11
    valve_resistance_pa_s2_m6: float = 1e11
    pump_tau_s: float = 1.0
    valve_tau_s: float = 0.5

    def __post_init__(self):
        version(self.version, "thermal.version")
        zeros = {"max_heat_w", "hot_conductance_w_k", "sink_conductance_w_k"}
        for name, value in asdict(self).items():
            if name != "version":
                object.__setattr__(self, name, number(value, name, minimum=0 if name in zeros else None,
                                                    positive=name not in zeros))
        if not TEMPERATURE_MIN_K <= self.sink_temperature_k < TEMPERATURE_MAX_K:
            raise ValueError("sink temperature must be within [273.15,368.15) K")
        for name, value in (("hot capacity", self.hot_mass_kg * self.specific_heat_j_kg_k),
                            ("cold capacity", self.cold_mass_kg * self.specific_heat_j_kg_k),
                            ("pump plus pipe resistance", self.pump_curve_pa_s2_m6 + self.pipe_resistance_pa_s2_m6)):
            number(value, name, positive=True)

    @property
    def capacities_j_k(self):
        return (self.wall_capacity_j_k, self.hot_mass_kg * self.specific_heat_j_kg_k,
                self.cold_mass_kg * self.specific_heat_j_kg_k)


@dataclass(frozen=True)
class ThermalInputs:
    heat_command: float = 0.0
    pump_command: float = 0.0
    valve_command: float = 0.65
    hot_conductance_w_k: float | None = None
    sink_conductance_w_k: float | None = None
    pipe_resistance_pa_s2_m6: float | None = None
    valve_resistance_pa_s2_m6: float | None = None

    def __post_init__(self):
        for name in ("heat_command", "pump_command", "valve_command"):
            object.__setattr__(self, name, number(getattr(self, name), name, minimum=0, maximum=1))
        for name in ("hot_conductance_w_k", "sink_conductance_w_k", "pipe_resistance_pa_s2_m6", "valve_resistance_pa_s2_m6"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, number(value, name, minimum=0))

    def effective(self, p):
        values = {name: getattr(p, name) if getattr(self, name) is None else getattr(self, name)
                  for name in ("hot_conductance_w_k", "sink_conductance_w_k", "pipe_resistance_pa_s2_m6", "valve_resistance_pa_s2_m6")}
        number(p.pump_curve_pa_s2_m6+values["pipe_resistance_pa_s2_m6"], "effective pump plus pipe resistance", positive=True)
        return values


@dataclass(frozen=True)
class ThermalSolverConfig:
    version: int = 1
    method: str = "RK45"
    rtol: float = 1e-7
    atol: tuple = (1e-8, 1e-8, 1e-8, 1e-10, 1e-10, 1e-5, 1e-5)
    max_step_s: float = 0.05

    def __post_init__(self):
        version(self.version, "thermal solver.version")
        if self.method not in ("RK45", "DOP853", "Radau"):
            raise ValueError("thermal method must be RK45, DOP853 or Radau")
        object.__setattr__(self, "rtol", number(self.rtol, "rtol", positive=True))
        try:
            values = tuple(self.atol)
        except TypeError as exc:
            raise ValueError("thermal atol requires seven positive tolerances") from exc
        if len(values) != 7:
            raise ValueError("thermal atol requires seven positive tolerances")
        object.__setattr__(self, "atol", tuple(number(v, f"atol[{i}]", positive=True) for i, v in enumerate(values)))
        object.__setattr__(self, "max_step_s", number(self.max_step_s, "max_step_s", positive=True, maximum=.05))

    @property
    def effective_rtol(self):
        return max(self.rtol, 100 * math.ulp(1.0))

    def executed(self, dt_s):
        return dict(version=self.version, method=self.method, rtol=self.effective_rtol,
                    requested_rtol=self.rtol, atol=list(self.atol), max_step_s=self.max_step_s,
                    effective_max_step_s=min(dt_s, self.max_step_s),
                    state_order=list(STATE_NAMES), state_units=list(STATE_UNITS))


@dataclass(frozen=True)
class HydraulicPoint:
    flow_m3_s: float
    pump_pressure_pa: float
    branch: str


def _flow(speed, opening, p, effective):
    if speed == 0 or opening == 0:
        return 0.0
    if effective["valve_resistance_pa_s2_m6"] == 0:
        return speed * math.copysign(1.0, opening) * math.sqrt(p.pump_shutoff_pa) / math.sqrt(
            p.pump_curve_pa_s2_m6 + effective["pipe_resistance_pa_s2_m6"])
    denominator = math.hypot(math.sqrt(p.pump_curve_pa_s2_m6 + effective["pipe_resistance_pa_s2_m6"]) * opening,
                             math.sqrt(effective["valve_resistance_pa_s2_m6"]))
    # Extended algebraic trial evaluations are never accepted as plant truth.
    return speed * opening * math.sqrt(p.pump_shutoff_pa) / denominator


def hydraulic_operating_point(pump_speed, valve_opening, p=None, inputs=None):
    p = ThermalParameters() if p is None else p
    inputs = ThermalInputs() if inputs is None else inputs
    if not isinstance(p, ThermalParameters) or not isinstance(inputs, ThermalInputs):
        raise ValueError("hydraulic point requires ThermalParameters and ThermalInputs")
    speed = number(pump_speed, "pump_speed", minimum=0, maximum=1)
    opening = number(valve_opening, "valve_opening", minimum=0, maximum=1)
    flow = _flow(speed, opening, p, inputs.effective(p))
    pressure = p.pump_shutoff_pa * speed * speed - p.pump_curve_pa_s2_m6 * flow * flow
    return HydraulicPoint(flow, pressure, "closed" if opening == 0 else "zero_speed" if speed == 0 else "forward")


def thermal_rhs(t, y, inputs, p, imposed_flow_m3_s=None):
    wall, hot, cold, speed, opening, _, _ = y
    effective = inputs.effective(p)
    flow = _flow(speed, opening, p, effective) if imposed_flow_m3_s is None else imposed_flow_m3_s
    heat_w = inputs.heat_command * p.max_heat_w
    exchange_w = effective["hot_conductance_w_k"] * (wall - hot)
    circulation_w = p.density_kg_m3 * flow * p.specific_heat_j_kg_k * (hot - cold)
    rejected_w = effective["sink_conductance_w_k"] * (cold - p.sink_temperature_k)
    wall_capacity, hot_capacity, cold_capacity = p.capacities_j_k
    return [(heat_w-exchange_w)/wall_capacity, (exchange_w-circulation_w)/hot_capacity,
            (circulation_w-rejected_w)/cold_capacity, (inputs.pump_command-speed)/p.pump_tau_s,
            (inputs.valve_command-opening)/p.valve_tau_s, heat_w, rejected_w]


@dataclass
class ThermalAdvance:
    time_s: float
    state: np.ndarray
    boundary: str | None
    diagnostics: dict


class ThermalPlant:
    def __init__(self, p=None, *, wall_temperature_k=293.15, hot_temperature_k=293.15,
                 cold_temperature_k=293.15, pump_speed=0.0, valve_opening=.65, imposed_flow_m3_s=None):
        self.p = ThermalParameters() if p is None else p
        if not isinstance(self.p, ThermalParameters):
            raise ValueError("p must be immutable ThermalParameters")
        temperatures = [number(value, name) for value, name in zip(
            (wall_temperature_k, hot_temperature_k, cold_temperature_k), STATE_NAMES[:3])]
        if not all(TEMPERATURE_MIN_K < value < TEMPERATURE_MAX_K for value in temperatures):
            raise ValueError("initial temperatures must be strictly inside (273.15,368.15) K")
        speed = number(pump_speed, "pump_speed", minimum=0, maximum=1)
        opening = number(valve_opening, "valve_opening", minimum=0, maximum=1)
        self.imposed_flow_m3_s = None if imposed_flow_m3_s is None else number(imposed_flow_m3_s, "imposed_flow_m3_s", minimum=0)
        self.y = np.array([*temperatures, speed, opening, 0.0, 0.0])
        self.initial_temperatures_k = np.array(temperatures)
        self.t, self.stopped, self.stop_reason, self.last_advance = 0.0, False, None, None
        self.last_held_inputs = ThermalInputs(pump_command=speed, valve_command=opening)

    @property
    def flow_m3_s(self):
        return (self.imposed_flow_m3_s if self.imposed_flow_m3_s is not None else
                hydraulic_operating_point(float(self.y[3]), float(self.y[4]), self.p, self.last_held_inputs).flow_m3_s)

    @property
    def pump_pressure_pa(self):
        if self.imposed_flow_m3_s is not None:
            return None  # imposed-flow benchmark does not claim a pump intersection
        return hydraulic_operating_point(float(self.y[3]), float(self.y[4]), self.p, self.last_held_inputs).pump_pressure_pa

    def energy_residual_j(self):
        return float(np.dot(self.p.capacities_j_k, self.y[:3] - self.initial_temperatures_k) - (self.y[5] - self.y[6]))

    def upward_rate_bounds_k_s(self, inputs):
        """Conservative domain-based rates, excluding numerical error (M5 use)."""
        effective = inputs.effective(self.p)
        span = TEMPERATURE_MAX_K - TEMPERATURE_MIN_K
        max_flow = self.imposed_flow_m3_s if self.imposed_flow_m3_s is not None else _flow(1.0, 1.0, self.p, effective)
        transport = self.p.density_kg_m3 * max_flow * self.p.specific_heat_j_kg_k * span
        exchange = effective["hot_conductance_w_k"] * span
        wall_capacity, hot_capacity, cold_capacity = self.p.capacities_j_k
        return ((inputs.heat_command*self.p.max_heat_w+exchange)/wall_capacity,
                (exchange+transport)/hot_capacity,
                (transport+effective["sink_conductance_w_k"]*(self.p.sink_temperature_k-TEMPERATURE_MIN_K))/cold_capacity)

    def advance(self, dt_s, inputs, solver=None):
        if self.stopped:
            raise PlantStopped(f"thermal plant already stopped: {self.stop_reason}")
        dt_s = number(dt_s, "dt_s", positive=True)
        if not isinstance(inputs, ThermalInputs):
            raise ValueError("inputs must be immutable ThermalInputs")
        solver = ThermalSolverConfig() if solver is None else solver
        if not isinstance(solver, ThermalSolverConfig):
            raise ValueError("solver must be immutable ThermalSolverConfig")
        effective = inputs.effective(self.p)
        self.last_held_inputs = inputs
        events, names = [], []
        for index, name in enumerate(("wall", "hot", "cold")):
            for endpoint, direction, suffix in ((TEMPERATURE_MIN_K, -1, "lower"), (TEMPERATURE_MAX_K, 1, "upper")):
                def event(t, y, index=index, endpoint=endpoint):
                    return y[index] - endpoint
                event.terminal, event.direction = True, direction
                events.append(event)
                names.append(f"{name}_{suffix}")
        start = self.t
        diagnostics = dict(start_time_s=start, requested_end_time_s=start+dt_s, solver=solver.executed(dt_s),
                           applied_inputs=asdict(inputs), effective_coefficients=effective,
                           applied_heat_w=inputs.heat_command*self.p.max_heat_w,
                           flow_mode="coupled_hydraulic" if self.imposed_flow_m3_s is None else "imposed_flow_benchmark",
                           imposed_flow_m3_s=self.imposed_flow_m3_s,
                           upward_rate_bounds_k_s=list(self.upward_rate_bounds_k_s(inputs)),
                           rate_bound_meaning="domain conservative upward rates; excludes numerical error")
        try:
            sol = solve_ivp(lambda t, y: thermal_rhs(t, y, inputs, self.p, self.imposed_flow_m3_s),
                            (start, start+dt_s), self.y, method=solver.method, rtol=solver.effective_rtol,
                            atol=solver.atol, max_step=min(dt_s, solver.max_step_s), events=events)
        except Exception as exc:
            diagnostics.update(success=False, message=str(exc), exception_type=type(exc).__name__,
                               accepted_time_s=self.t, nfev=0, njev=0, nlu=0)
            self._fail(diagnostics, f"thermal solver exception: {exc}")
        diagnostics.update(success=bool(sol.success), status=int(sol.status), message=str(sol.message),
                           nfev=int(sol.nfev), njev=int(getattr(sol, "njev", 0)), nlu=int(getattr(sol, "nlu", 0)))
        event_index = next((i for i, times in enumerate(sol.t_events) if len(times)), None)
        boundary = None if event_index is None else names[event_index]
        root_tolerance = 64 * math.ulp(TEMPERATURE_MAX_K)
        accepted = []
        for index, (time_s, state) in enumerate(zip(sol.t, sol.y.T)):
            valid_temperatures = [TEMPERATURE_MIN_K < value < TEMPERATURE_MAX_K for value in state[:3]]
            if boundary and index == len(sol.t)-1:
                for event_number, times in enumerate(sol.t_events):
                    if len(times) and abs(float(times[-1])-float(time_s)) <= 1e-9:
                        state_index = event_number // 2
                        endpoint = TEMPERATURE_MIN_K if event_number % 2 == 0 else TEMPERATURE_MAX_K
                        residual = float(state[state_index] - endpoint)
                        diagnostics.setdefault("boundary_residuals_k", {})[names[event_number]] = residual
                        diagnostics["boundary_root_tolerance_k"] = root_tolerance
                        valid_temperatures[state_index] = abs(residual) <= root_tolerance
            if (np.all(np.isfinite(state)) and start <= time_s <= start+dt_s and all(valid_temperatures)
                    and 0 <= state[3] <= 1 and 0 <= state[4] <= 1):
                accepted.append((float(time_s), np.array(state, dtype=float)))
            else:
                diagnostics["rejected_solver_sample"] = dict(
                    time_s=float(time_s) if math.isfinite(time_s) else str(time_s),
                    state=[float(value) if math.isfinite(value) else str(value) for value in state])
                break
        if accepted:
            self.t, self.y = accepted[-1]
        diagnostics["accepted_time_s"] = self.t
        if not sol.success or len(accepted) != len(sol.t):
            diagnostics["partial_trace"] = [dict(time_s=t, state=y.tolist()) for t, y in accepted]
            self._fail(diagnostics, str(sol.message) if not sol.success else "invalid accepted thermal state")
        if boundary:
            self.stopped, self.stop_reason = True, boundary
        self.last_advance = ThermalAdvance(self.t, self.y.copy(), boundary, diagnostics)
        return self.last_advance

    def _fail(self, diagnostics, message):
        self.stopped, self.stop_reason = True, "solver_failure"
        self.last_advance = ThermalAdvance(self.t, self.y.copy(), None, diagnostics)
        raise IntegrationFailure(message, self.last_advance)
