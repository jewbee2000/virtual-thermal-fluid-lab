"""SI-only, constant-density open tank with an ideal metered-flow pump.

This is NOT a centrifugal pump head/flow model. See docs/MODEL.md.
"""
from dataclasses import dataclass, asdict
import math
import numpy as np
from scipy.integrate import solve_ivp
from .contracts import SolverConfig, number


@dataclass(frozen=True)
class Parameters:
    area_m2: float = 0.05
    tank_height_m: float = 1.0
    outlet_area_m2: float = 1e-4
    discharge_coefficient: float = 0.62
    gravity_m_s2: float = 9.80665
    pump_max_m3_s: float = 4e-4
    pump_tau_s: float = 1.0
    valve_tau_s: float = 0.5

    def __post_init__(self):
        for key, value in asdict(self).items():
            number(value, key, positive=True)
        if self.discharge_coefficient > 1:
            raise ValueError("discharge coefficient must be <= 1 for this model")


def drain_flow(h_m: float, opening: float, p: Parameters) -> float:
    # max(h,0) keeps trial solver evaluations real at a terminal boundary.
    # Accepted negative levels are never silently clamped.
    return p.discharge_coefficient * p.outlet_area_m2 * opening * math.sqrt(
        2 * p.gravity_m_s2 * max(h_m, 0.0)
    )


def rhs(t, y, pump_command, valve_command, p: Parameters):
    h, q, valve, _, _ = y
    out = drain_flow(h, valve, p)
    return [(q-out)/p.area_m2,
            (p.pump_max_m3_s*pump_command-q)/p.pump_tau_s,
            (valve_command-valve)/p.valve_tau_s, q, out]


@dataclass
class Advance:
    time_s: float
    state: np.ndarray
    boundary: str | None
    diagnostics: dict | None = None


class IntegrationFailure(RuntimeError):
    """The plant remains stopped at the last finite, in-domain accepted state."""
    def __init__(self, message, advance):
        super().__init__(message)
        self.advance = advance


class PlantStopped(RuntimeError):
    pass


class Plant:
    def __init__(self, p=None, h0_m=0.25, q0_m3_s=0.0, valve0=0.65):
        self.p = Parameters() if p is None else p
        if not isinstance(self.p, Parameters):
            raise ValueError("p must be immutable Parameters")
        h0_m = number(h0_m, "h0_m", positive=True)
        q0_m3_s = number(q0_m3_s, "q0_m3_s", minimum=0, maximum=self.p.pump_max_m3_s)
        valve0 = number(valve0, "valve0", minimum=0, maximum=1)
        if not 0 < h0_m < self.p.tank_height_m:
            raise ValueError("starter requires an interior initial level")
        if not 0 <= q0_m3_s <= self.p.pump_max_m3_s or not 0 <= valve0 <= 1:
            raise ValueError("invalid initial actuator state")
        self.initial_h = h0_m
        self.y = np.array([h0_m, q0_m3_s, valve0, 0., 0.])
        self.t = 0.
        self.stopped = False
        self.stop_reason = None
        self.last_advance = None

    def advance(self, dt_s, pump_command, valve_command, method="RK45",
                rtol=1e-7, atol=None, max_step_s=0.05, *, solver=None):
        if self.stopped:
            raise PlantStopped(f"plant already stopped: {self.stop_reason}")
        dt_s = number(dt_s, "dt_s", positive=True)
        pump_command = number(pump_command, "pump_command", minimum=0, maximum=1)
        valve_command = number(valve_command, "valve_command", minimum=0, maximum=1)
        solver = solver or SolverConfig(method=method, rtol=rtol,
                                        atol=atol if atol is not None else SolverConfig().atol,
                                        max_step_s=max_step_s)
        if not isinstance(solver, SolverConfig):
            raise ValueError("solver must be an immutable SolverConfig")
        def empty(t, y):
            return y[0]
        def full(t, y):
            return y[0]-self.p.tank_height_m
        empty.terminal = full.terminal = True
        empty.direction, full.direction = -1, 1
        started_at_s = self.t
        diagnostics = dict(start_time_s=self.t, requested_end_time_s=self.t + dt_s,
                           solver=solver.executed(dt_s))
        try:
            sol = solve_ivp(
                lambda t,y: rhs(t,y,pump_command,valve_command,self.p),
                (self.t,self.t+dt_s),self.y,method=solver.method,rtol=solver.effective_rtol,
                atol=solver.atol,max_step=min(dt_s,solver.max_step_s),events=(empty,full))
        except Exception as exc:
            diagnostics.update(success=False, message=str(exc), exception_type=type(exc).__name__,
                               accepted_time_s=self.t, nfev=0, njev=0, nlu=0)
            self._fail(diagnostics, f"solver exception: {exc}")
        diagnostics.update(success=bool(sol.success), status=int(sol.status), message=str(sol.message),
                           nfev=int(sol.nfev), njev=int(getattr(sol, "njev", 0)),
                           nlu=int(getattr(sol, "nlu", 0)))
        boundary = "empty" if sol.t_events[0].size else "full" if sol.t_events[1].size else None
        # Preserve the solver's partial trace, but never install an invalid state.
        accepted = []
        for index, (time_s, state) in enumerate(zip(sol.t, sol.y.T)):
            domain_valid = 0 <= state[0] <= self.p.tank_height_m
            if boundary and index == len(sol.t) - 1:
                event_value = 0.0 if boundary == "empty" else self.p.tank_height_m
                event_residual = float(state[0] - event_value)
                diagnostics["boundary_level_residual_m"] = event_residual
                diagnostics["boundary_root_tolerance_m"] = 64 * math.ulp(max(1.0, self.p.tank_height_m))
                # The stopped terminal root may retain floating-point residue.
                # Keep its raw value: this is neither clipping nor reentry.
                domain_valid = abs(event_residual) <= diagnostics["boundary_root_tolerance_m"]
            if (np.all(np.isfinite(state)) and started_at_s <= time_s <= started_at_s + dt_s
                    and domain_valid and 0 <= state[1] <= self.p.pump_max_m3_s
                    and 0 <= state[2] <= 1):
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
            self._fail(diagnostics, str(sol.message) if not sol.success else "invalid accepted solver state")
        if boundary:
            self.stopped, self.stop_reason = True, boundary
        self.last_advance = Advance(self.t, self.y.copy(), boundary, diagnostics)
        return self.last_advance

    def _fail(self, diagnostics, message):
        self.stopped, self.stop_reason = True, "solver_failure"
        self.last_advance = Advance(self.t, self.y.copy(), None, diagnostics)
        raise IntegrationFailure(message, self.last_advance)

    def volume_residual_m3(self):
        h,_,_,vin,vout = self.y
        return self.p.area_m2*(h-self.initial_h)-(vin-vout)
