from dataclasses import dataclass
from .contracts import number


@dataclass(frozen=True)
class Observation:
    level_m: float
    sampled_at_s: float
    valid: bool
    high_high: bool


class Supervisor:
    """Latched shutdown using exposed I/O, never a Plant instance."""
    def __init__(self, stale_after_s=0.3, sensor_min_m=0.0, sensor_max_m=1.0):
        self.reason = None
        self.stale_after_s = number(stale_after_s, "stale_after_s", positive=True)
        self.sensor_min_m = number(sensor_min_m, "sensor_min_m", minimum=0)
        self.sensor_max_m = number(sensor_max_m, "sensor_max_m", positive=True)
        if self.sensor_min_m >= self.sensor_max_m:
            raise ValueError("sensor range must be ordered")
        self.tripped_at_s = None

    def update(self, now_s, obs: Observation):
        reason = None
        now_s = number(now_s, "now_s", minimum=0)
        try:
            number(obs.level_m, "observed level_m")
            level_valid = True
        except ValueError:
            level_valid = False
        try:
            number(obs.sampled_at_s, "observed sampled_at_s", minimum=0)
            stamp_valid = True
        except ValueError:
            stamp_valid = False
        if obs.high_high is True:
            reason = "high_high"
        elif (not isinstance(obs.high_high, bool) or not isinstance(obs.valid, bool) or not obs.valid
              or not level_valid):
            reason = "invalid_sensor"
        elif not stamp_valid or obs.sampled_at_s > now_s+1e-9:
            reason = "invalid_timestamp"
        elif now_s-obs.sampled_at_s > self.stale_after_s+1e-9:
            reason = "stale_sensor"
        elif not self.sensor_min_m <= obs.level_m <= self.sensor_max_m:
            reason = "sensor_range"
        if self.reason is None and reason:
            self.reason, self.tripped_at_s = reason, now_s
        return self.reason is not None


class PIController:
    """Conditional integration anti-windup; gains are demo assumptions."""
    def __init__(self, kp=3.0, ki=0.06, bias=0.3155):
        self.kp = number(kp, "kp_per_m", minimum=0)
        self.ki = number(ki, "ki_per_m_s", minimum=0)
        self.bias = number(bias, "bias", minimum=0, maximum=1)
        self.integral = 0.

    def update(self, target_m, measured_m, dt_s):
        e = target_m-measured_m
        raw = self.bias+self.kp*e+self.integral
        if 0 <= raw <= 1 or (raw > 1 and e < 0) or (raw < 0 and e > 0):
            self.integral += self.ki*e*dt_s
        return min(1.,max(0.,self.bias+self.kp*e+self.integral))
