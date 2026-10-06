from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Observation:
    level_m: float
    sampled_at_s: float
    valid: bool
    high_high: bool


class Supervisor:
    """Latched shutdown using exposed I/O, never a Plant instance."""
    def __init__(self, stale_after_s=0.3):
        self.reason = None
        self.stale_after_s = stale_after_s
        self.tripped_at_s = None

    def update(self, now_s, obs: Observation):
        reason = None
        if obs.high_high:
            reason = "high_high"
        elif not obs.valid or not math.isfinite(obs.level_m):
            reason = "invalid_sensor"
        elif not math.isfinite(obs.sampled_at_s) or obs.sampled_at_s > now_s+1e-9:
            reason = "invalid_timestamp"
        elif now_s-obs.sampled_at_s > self.stale_after_s+1e-9:
            reason = "stale_sensor"
        elif not 0 <= obs.level_m <= 1.0:
            reason = "sensor_range"
        if self.reason is None and reason:
            self.reason, self.tripped_at_s = reason, now_s
        return self.reason is not None


class PIController:
    """Conditional integration anti-windup; gains are demo assumptions."""
    def __init__(self, kp=3.0, ki=0.06, bias=0.3155):
        self.kp,self.ki,self.bias = kp,ki,bias
        self.integral = 0.

    def update(self, target_m, measured_m, dt_s):
        e = target_m-measured_m
        raw = self.bias+self.kp*e+self.integral
        if 0 <= raw <= 1 or (raw > 1 and e < 0) or (raw < 0 and e > 0):
            self.integral += self.ki*e*dt_s
        return min(1.,max(0.,self.bias+self.kp*e+self.integral))
