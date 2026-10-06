"""Immutable, strict version-1 tank execution contracts (no new dependencies)."""
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from decimal import Decimal
import math
import re


FAULTS = frozenset({"none", "blocked_outlet", "pump_failed_off", "sensor_dropout",
                    "sensor_bias_ramp", "sensor_stuck", "pump_stuck_on"})
OUTCOMES = {
    "none": {"nominal", "characterize"},
    "blocked_outlet": {"contained", "characterize"},
    "pump_failed_off": {"characterize"},
    "sensor_dropout": {"stale_trip", "characterize"},
    "sensor_bias_ramp": {"high_trip", "characterize"},
    "sensor_stuck": {"characterize"},
    "pump_stuck_on": {"observe_hazard", "characterize"},
}


def number(value, name, *, minimum=None, maximum=None, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a nonboolean number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{name} must be finite")
    value = float(value)
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return value


def integer(value, name, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


def version(value, name):
    return integer(value, name, 1, 1)


def microseconds(value, name):
    scaled = Decimal(str(value)) * 1_000_000
    if scaled != scaled.to_integral_value():
        raise ValueError(f"{name} must align to integer microseconds")
    return int(scaled)


def strict_fields(value, allowed, name):
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    unknown = set(value) - set(allowed)
    if unknown:
        raise ValueError(f"unknown {name} fields: {', '.join(sorted(map(str, unknown)))}")


@dataclass(frozen=True)
class ControllerConfig:
    version: int = 1
    kp_per_m: float = 3.0
    ki_per_m_s: float = 0.06
    bias: float = 0.3155
    drain_command: float = 0.65
    high_switch_m: float = 0.8
    stale_after_s: float = 0.3
    sensor_min_m: float = 0.0
    sensor_max_m: float = 1.0

    def __post_init__(self):
        version(self.version, "controller.version")
        for name in ("kp_per_m", "ki_per_m_s", "sensor_min_m"):
            object.__setattr__(self, name, number(getattr(self, name), f"controller.{name}", minimum=0))
        for name in ("bias", "drain_command"):
            object.__setattr__(self, name, number(getattr(self, name), f"controller.{name}", minimum=0, maximum=1))
        for name in ("high_switch_m", "stale_after_s", "sensor_max_m"):
            object.__setattr__(self, name, number(getattr(self, name), f"controller.{name}", positive=True))
        if self.sensor_min_m >= self.sensor_max_m:
            raise ValueError("controller sensor range must be ordered")


@dataclass(frozen=True)
class ScenarioConfig(Mapping):
    schema_version: int
    name: str
    duration_s: float
    dt_s: float
    initial_level_m: float
    target_level_m: float
    fault: str
    fault_at_s: float
    expected: str
    seed: int
    sensor_noise_std_m: float
    bias_rate_m_s: float
    controller: ControllerConfig

    def __getitem__(self, key):
        if key not in self.__dataclass_fields__:
            raise KeyError(key)
        value = getattr(self, key)
        return asdict(value) if key == "controller" else value

    def __iter__(self):
        return iter(self.__dataclass_fields__)

    def __len__(self):
        return len(self.__dataclass_fields__)

    @property
    def dt_us(self):
        return microseconds(self.dt_s, "dt_s")

    @property
    def duration_us(self):
        return microseconds(self.duration_s, "duration_s")

    @property
    def fault_at_us(self):
        return microseconds(self.fault_at_s, "fault_at_s")


def normalize_scenario(cfg, p):
    """Apply this same boundary to file input and direct Python execution."""
    allowed = {f.name for f in fields(ScenarioConfig)}
    strict_fields(cfg, allowed, "scenario")
    for key in ("name", "dt_s", "duration_s"):
        if key not in cfg:
            raise ValueError(f"missing scenario field: {key}")
    name = cfg["name"]
    if not isinstance(name, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name) is None:
        raise ValueError("name must contain 1–80 ASCII letters, digits, underscores or hyphens")
    duration = number(cfg["duration_s"], "duration_s", positive=True, maximum=86400)
    dt = number(cfg["dt_s"], "dt_s", minimum=0.000001, maximum=1)
    duration_us, dt_us = microseconds(duration, "duration_s"), microseconds(dt, "dt_s")
    if duration_us % dt_us:
        raise ValueError("duration must align with controller ticks")
    if duration_us // dt_us > 1_000_000:
        raise ValueError("scenario must have at most 1,000,000 controller intervals")
    fault = cfg.get("fault", "none")
    if not isinstance(fault, str) or fault not in FAULTS:
        raise ValueError("unknown fault")
    expected = cfg.get("expected", "nominal")
    if not isinstance(expected, str) or expected not in OUTCOMES[fault]:
        raise ValueError(f"expected outcome is incompatible with fault {fault}")
    at = number(cfg.get("fault_at_s", 60.0), "fault_at_s", minimum=0)
    at_us = microseconds(at, "fault_at_s")
    if fault != "none" and at_us % dt_us:
        raise ValueError("fault time must align with controller ticks")
    if fault != "none" and at_us >= duration_us:
        raise ValueError("active fault must start before the horizon")
    supplied_controller = cfg.get("controller", {})
    strict_fields(supplied_controller, {f.name for f in fields(ControllerConfig)}, "controller")
    if p.tank_height_m != 1.0 and not {"high_switch_m", "sensor_max_m"} <= set(supplied_controller):
        raise ValueError("custom tank height requires explicit controller.high_switch_m and sensor_max_m")
    controller = ControllerConfig(**dict(supplied_controller))
    initial = number(cfg.get("initial_level_m", 0.25), "initial_level_m", positive=True)
    target = number(cfg.get("target_level_m", 0.5), "target_level_m", positive=True)
    if not initial < p.tank_height_m or not target < p.tank_height_m:
        raise ValueError("initial and target level must be strictly inside the tank")
    if not controller.high_switch_m < p.tank_height_m:
        raise ValueError("high switch must be strictly inside the tank")
    if controller.sensor_max_m > p.tank_height_m:
        raise ValueError("sensor range must be within the tank")
    if not controller.sensor_min_m <= target <= controller.sensor_max_m:
        raise ValueError("target level must be inside the sensor range")
    if not controller.sensor_min_m <= controller.high_switch_m <= controller.sensor_max_m:
        raise ValueError("high switch must be inside the sensor range")
    return ScenarioConfig(
        version(cfg.get("schema_version", 1), "schema_version"), name, duration, dt,
        initial, target, fault, at, expected,
        integer(cfg.get("seed", 42), "seed", 0, 4294967295),
        number(cfg.get("sensor_noise_std_m", 0.0), "sensor_noise_std_m", minimum=0),
        number(cfg.get("bias_rate_m_s", -0.01), "bias_rate_m_s"), controller)


@dataclass(frozen=True)
class SolverConfig:
    version: int = 1
    method: str = "RK45"
    rtol: float = 1e-7
    atol: tuple = (1e-9, 1e-11, 1e-9, 1e-11, 1e-11)
    max_step_s: float = 0.05

    def __post_init__(self):
        version(self.version, "solver.version")
        if self.method not in ("RK45", "DOP853", "Radau"):
            raise ValueError("solver method must be RK45, DOP853 or Radau")
        object.__setattr__(self, "rtol", number(self.rtol, "solver.rtol", positive=True))
        try:
            values = tuple(self.atol)
        except TypeError as exc:
            raise ValueError("solver.atol must have five positive state tolerances") from exc
        if len(values) != 5:
            raise ValueError("solver.atol must have five positive state tolerances")
        object.__setattr__(self, "atol", tuple(number(v, f"solver.atol[{i}]", positive=True)
                                             for i, v in enumerate(values)))
        object.__setattr__(self, "max_step_s", number(self.max_step_s, "solver.max_step_s", positive=True, maximum=0.05))

    @property
    def effective_rtol(self):
        # SciPy's documented machine precision floor; persist requested and used.
        return max(self.rtol, 100 * math.ulp(1.0))

    def executed(self, dt_s):
        result = asdict(self)
        result["requested_rtol"] = self.rtol
        result["rtol"] = self.effective_rtol
        result["atol"] = list(self.atol)
        result["effective_max_step_s"] = min(dt_s, self.max_step_s)
        return result
