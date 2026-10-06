"""SI-only, constant-density open tank with an ideal metered-flow pump.

This is NOT a centrifugal pump head/flow model. See docs/MODEL.md.
"""
from dataclasses import dataclass, asdict
import math
import numpy as np
from scipy.integrate import solve_ivp


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
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{key} must be finite and positive")
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


class Plant:
    def __init__(self, p=None, h0_m=0.25, q0_m3_s=0.0, valve0=0.65):
        self.p = p or Parameters()
        if not 0 < h0_m < self.p.tank_height_m:
            raise ValueError("starter requires an interior initial level")
        if not 0 <= q0_m3_s <= self.p.pump_max_m3_s or not 0 <= valve0 <= 1:
            raise ValueError("invalid initial actuator state")
        self.initial_h = h0_m
        self.y = np.array([h0_m, q0_m3_s, valve0, 0., 0.])
        self.t = 0.

    def advance(self, dt_s, pump_command, valve_command, method="RK45",
                rtol=1e-7, atol=None):
        if not math.isfinite(dt_s) or dt_s <= 0:
            raise ValueError("dt_s must be finite and positive")
        if not 0 <= pump_command <= 1 or not 0 <= valve_command <= 1:
            raise ValueError("commands must be in [0,1]")
        def empty(t, y):
            return y[0]
        def full(t, y):
            return y[0]-self.p.tank_height_m
        empty.terminal = full.terminal = True
        empty.direction, full.direction = -1, 1
        sol = solve_ivp(
            lambda t,y: rhs(t,y,pump_command,valve_command,self.p),
            (self.t,self.t+dt_s),self.y,method=method,rtol=rtol,
            atol=atol if atol is not None else [1e-9,1e-11,1e-9,1e-11,1e-11],
            max_step=min(dt_s,0.05),events=(empty,full))
        if not sol.success:
            raise RuntimeError(sol.message)
        self.y, self.t = sol.y[:,-1], float(sol.t[-1])
        boundary = "empty" if sol.t_events[0].size else "full" if sol.t_events[1].size else None
        return Advance(self.t,self.y.copy(),boundary)

    def volume_residual_m3(self):
        h,_,_,vin,vout = self.y
        return self.p.area_m2*(h-self.initial_h)-(vin-vout)
