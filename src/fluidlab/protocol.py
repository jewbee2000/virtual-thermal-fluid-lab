"""Strict protocol-v1 codec. CRC oracle is Python's independent binascii code."""
from dataclasses import asdict, dataclass
import binascii
import hashlib
import json
import math
import re

MAX_FRAME_BYTES = 256
UINT32_MAX = 2**32 - 1
UINT64_MAX = 2**64 - 1
PPM = 1_000_000
COUNTS = dict(B=2, H=1, C=17, O=3, S=2, U=2, Q=6, A=2, R=7, X=6, N=7)


def _integer(value, minimum, maximum, name):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


def quantize(value, scale, name):
    """Nearest integer, half away from zero; retain scale/quantization in manifests."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    scaled = value * scale
    if not math.isfinite(scaled):
        raise ValueError(f"{name} overflows wire scale")
    return math.floor(scaled + .5) if scaled >= 0 else math.ceil(scaled - .5)


@dataclass(frozen=True)
class Configuration:
    profile: int = 1
    version: int = 1
    config_id: int = 1
    tick_us: int = 100_000
    stale_us: int = 300_000
    lease_us: int = 300_000
    kp_scaled: int = 3_000_000
    ki_scaled: int = 60_000
    ff_ppm: int = 315_500
    normal_valve_ppm: int = 650_000
    target_i: int = 500_000
    min_control_i: int = 0
    max_control_i: int = 1_000_000
    min_temp_mK: int = 0
    max_temp_mK: int = 0
    hot_trip_mK: int = 0
    wall_trip_mK: int = 0

    def __post_init__(self):
        limits = dict(profile=(1, 2), version=(1, 1), config_id=(0, UINT32_MAX),
                      tick_us=(1, 1_000_000), stale_us=(1, 10_000_000), lease_us=(1, 10_000_000),
                      kp_scaled=(0, 10**12), ki_scaled=(0, 10**12), ff_ppm=(0, PPM),
                      normal_valve_ppm=(0, PPM), target_i=(0, 2**31-1),
                      min_control_i=(-2**31, 2**31-1), max_control_i=(0, 2**31-1),
                      min_temp_mK=(0, 1_000_000), max_temp_mK=(0, 1_000_000),
                      hot_trip_mK=(0, 1_000_000), wall_trip_mK=(0, 1_000_000))
        for name, (lo, hi) in limits.items():
            _integer(getattr(self, name), lo, hi, name)
        if not self.min_control_i < self.max_control_i or not self.min_control_i <= self.target_i <= self.max_control_i:
            raise ValueError("control range must be ordered and contain the target")
        temps = (self.min_temp_mK, self.max_temp_mK, self.hot_trip_mK, self.wall_trip_mK)
        if self.profile == 1:
            if any(temps):
                raise ValueError("tank thermal configuration fields must be zero")
        elif (self.min_control_i < 0 or not self.min_temp_mK < self.hot_trip_mK <= self.max_temp_mK
              or not self.min_temp_mK < self.wall_trip_mK <= self.max_temp_mK):
            raise ValueError("thermal trips must exceed lower bound and be within temperature range")

    @classmethod
    def thermal(cls, **overrides):
        defaults = dict(profile=2, config_id=2, kp_scaled=2_000_000_000, ki_scaled=200_000_000,
                        ff_ppm=527_498, target_i=150_000, max_control_i=500_000,
                        min_temp_mK=273_150, max_temp_mK=368_150, hot_trip_mK=338_150, wall_trip_mK=358_150)
        defaults.update(overrides)
        return cls(**defaults)

    @classmethod
    def tank(cls, controller, *, target_level_m, tick_us, lease_us=300_000, config_id=1):
        from .contracts import ControllerConfig, microseconds
        if not isinstance(controller, ControllerConfig):
            raise ValueError("tank adapter requires explicit ControllerConfig")
        return cls(config_id=config_id, tick_us=tick_us, lease_us=lease_us,
                   stale_us=microseconds(controller.stale_after_s, "stale_after_s"),
                   kp_scaled=quantize(controller.kp_per_m, 1e6, "kp_per_m"),
                   ki_scaled=quantize(controller.ki_per_m_s, 1e6, "ki_per_m_s"),
                   ff_ppm=quantize(controller.bias, 1e6, "bias"),
                   normal_valve_ppm=quantize(controller.drain_command, 1e6, "drain_command"),
                   target_i=quantize(target_level_m, 1e6, "target_level_m"),
                   min_control_i=quantize(controller.sensor_min_m, 1e6, "sensor_min_m"),
                   max_control_i=quantize(controller.sensor_max_m, 1e6, "sensor_max_m"))

    @property
    def payload(self):
        return tuple(asdict(self).values())

    @property
    def sha256(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Frame:
    type: str
    epoch: int
    sequence: int
    clock: str
    time_us: int
    payload: tuple

    def __post_init__(self):
        if self.type not in COUNTS or self.clock not in ("V", "D"):
            raise ValueError("unknown record type or clock")
        _integer(self.epoch, 0, UINT32_MAX, "epoch")
        _integer(self.sequence, 0, UINT32_MAX, "sequence")
        _integer(self.time_us, 0, UINT64_MAX, "time_us")
        object.__setattr__(self, "payload", tuple(self.payload))
        if len(self.payload) != COUNTS[self.type]:
            raise ValueError("wrong payload field count")
        for i, value in enumerate(self.payload):
            signed = self.type == "O" and i == 2 or self.type == "C" and i == 11
            hi = UINT64_MAX if (self.type == "C" and i in (6, 7) or self.type == "R" and i == 5
                               or self.type == "X" and i in (3,4)) else UINT32_MAX
            if signed or self.type == "C" and i in (10, 12):
                hi = 2**31-1
            _integer(value, -2**31 if signed else 0, hi, f"payload[{i}]")
        p = self.payload
        if self.type == "C":
            Configuration(*p)
        elif self.type == "B" and (self.epoch != 0 or p[0] != 100 or p[1] > 2):
            raise ValueError("invalid boot fields")
        elif self.type == "H" and (self.epoch == 0 or p[0] not in (1, 2)):
            raise ValueError("invalid handshake fields")
        elif self.type == "O" and (not 1 <= p[0] <= 6 or p[1] not in (0, 1, 2)
                                   or p[1] == 2 and p[2] != 0 or p[0] == 6 and p[2] not in (0, 1)):
            raise ValueError("invalid observation fields")
        elif self.type in ("S","U") and (p[0] > 2 or p[1] > PPM):
            raise ValueError("invalid STEP fields")
        elif self.type == "Q" and (not 1 <= p[0] <= 10_000_000 or any(v > PPM for v in p[1:4]) or p[4] > 2 or p[5] > 7):
            raise ValueError("invalid command fields")
        elif self.type == "A" and p[1] > 1:
            raise ValueError("invalid ACK fields")
        elif self.type == "R" and (p[1] > 2 or p[2] > 7 or p[3] > 63 or p[4] > 63 or p[6] > 2):
            raise ValueError("invalid reply fields")
        elif self.type == "X" and (self.clock!="D" or not 1<=p[0]<=6 or not 1<=p[1]<=3 or p[2]>1 or p[5]>2):
            raise ValueError("invalid channel-source diagnostic fields")
        elif self.type == "N" and (self.clock!="D" or p[0] not in (1,2) or p[5]>1 or p[6]>1):
            raise ValueError("invalid device diagnostic fields")

    def encode(self):
        body = "|".join(map(str, ("F", 1, self.type, self.epoch, self.sequence,
                                  self.clock, self.time_us, *self.payload))).encode("ascii")
        frame = body + f"*{binascii.crc_hqx(body, 0):04X}\n".encode("ascii")
        if len(frame) > MAX_FRAME_BYTES:
            raise ValueError("frame exceeds 256 bytes")
        return frame


def decode(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_FRAME_BYTES or not raw.endswith(b"\n"):
        raise ValueError("frame must be <=256 bytes including LF")
    match = re.fullmatch(rb"([!-~]+)\*([0-9A-F]{4})\n", raw)
    if not match or binascii.crc_hqx(match[1], 0) != int(match[2], 16):
        raise ValueError("invalid ASCII/checksum frame")
    fields = match[1].decode("ascii").split("|")
    if len(fields) < 8 or fields[:2] != ["F", "1"]:
        raise ValueError("invalid protocol header")
    numbers = [fields[3], fields[4], fields[6], *fields[7:]]
    for index, token in enumerate(numbers):
        payload_index = index-3
        signed = index >= 3 and (fields[2] == "O" and payload_index == 2 or fields[2] == "C" and payload_index == 11)
        if re.fullmatch(r"0|[1-9][0-9]*|-[1-9][0-9]*" if signed else r"0|[1-9][0-9]*", token) is None:
            raise ValueError("noncanonical decimal field")
    return Frame(fields[2], int(fields[3]), int(fields[4]), fields[5], int(fields[6]), tuple(map(int, fields[7:])))


def sequence_newer(new, old):
    _integer(new, 0, UINT32_MAX, "new sequence")
    _integer(old, 0, UINT32_MAX, "old sequence")
    return 0 < ((new-old) & UINT32_MAX) < 2**31


class FrameAssembler:
    """Bounded bytes; elapsed clock supplied by caller, no blocking reads."""
    def __init__(self, timeout_s=.5):
        self.timeout_s = timeout_s
        self.partial = bytearray()
        self.started_at = None
        self.discard = False

    def expire(self, now):
        if self.started_at is not None and not self.discard and now-self.started_at >= self.timeout_s:
            self.partial.clear()
            self.discard = True
            return True
        return False

    def feed(self, chunk, now):
        frames, errors = [], []
        if self.expire(now):
            errors.append("frame_assembly_timeout")
        for byte in chunk:
            if self.discard:
                if byte == 10:
                    self.discard = False
                    self.started_at = None
                continue
            if self.started_at is None:
                self.started_at = now
            if len(self.partial) >= MAX_FRAME_BYTES-1 and byte != 10:
                self.partial.clear()
                self.discard = True
                errors.append("oversize_frame")
                continue
            self.partial.append(byte)
            if byte == 10:
                try:
                    frames.append(decode(bytes(self.partial)))
                except ValueError as exc:
                    errors.append(str(exc))
                self.partial.clear()
                self.started_at = None
        return frames, errors

    def eof(self):
        return bool(self.partial or self.discard)
