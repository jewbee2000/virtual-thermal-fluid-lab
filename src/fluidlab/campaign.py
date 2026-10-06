"""Exact virtual-time C SIL campaign, with raw transport evidence and no fallback."""
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
import binascii
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import time
import numpy as np
from .contracts import integer, number, strict_fields
from .c_controller import CController, ControllerProcessFailure
from .plant import IntegrationFailure
from .protocol import Configuration, Frame, PPM, UINT32_MAX, UINT64_MAX, decode, quantize, sequence_newer
from .provenance import PROJECT_ROOT, canonical_json, execution_provenance, file_sha256
from .thermal import (STATE_NAMES, ThermalInputs, ThermalParameters, ThermalPlant,
                      ThermalSolverConfig, hydraulic_operating_point)


CASE_IDS = ("nominal_heat_step", "restriction", "reduced_rejection", "flow_dropout",
            "frozen_temperature", "biased_temperature", "delayed_flow", "reordered_flow",
            "corrupt_flow", "truncated_flow", "dropped_command", "delayed_command", "dropped_ack",
            "planned_restart", "stuck_heat_lost_sink", "near_tick_before", "near_tick_after")
CHANNELS = {2: "flow", 3: "hot", 4: "cold", 5: "wall", 6: "separate"}
COEFFICIENTS = ("hot_conductance_w_k", "sink_conductance_w_k",
                "pipe_resistance_pa_s2_m6", "valve_resistance_pa_s2_m6")
INITIAL_FIELDS = ("wall_temperature_k", "hot_temperature_k", "cold_temperature_k", "pump_speed", "valve_opening")
INPUT_FIELDS = ("schema_version", "topology", "name", "case_id", "duration_us", "tick_us", "seed",
                "initial", "model", "controller", "sensor_adapter", "initial_heat_demand", "events", "solver")
CHANNEL_FIELDS = ("value_i", "quality", "sequence", "source_time_us", "receipt_time_us", "last_good_source_time_us", "age_us")
TELEMETRY_FIELDS = (
    "schema_version", "run_name", "topology", "sample_id", "record_type", "time_us", "time_s",
    "epoch", "session_origin_us", "wire_time_us", "controller_tick_id", "reply_time_us",
    "controller_state", "trip_reason", "operation", "operation_result", "valid_mask", "stale_mask",
    "max_age_us", "observation_cache_source", "cache_matches_reply", "event_ids", "event_phase",
    *STATE_NAMES, "flow_m3_s", "pump_pressure_pa", "energy_residual_j", "observed_flow_m3_s",
    "observed_hot_temperature_k", "observed_cold_temperature_k", "observed_wall_temperature_k", "observed_separate_trip",
    *(f"{prefix}_{field}" for prefix in CHANNELS.values() for field in CHANNEL_FIELDS),
    "requested_heat_command", "requested_pump_command", "requested_valve_command",
    "lease_heat_command", "lease_pump_command", "lease_valve_command",
    "fault_heat_command", "fault_pump_command", "fault_valve_command",
    "command_sequence", "command_expires_us", "command_expired", "heat_demand_command", "applied_heat_w",
    *(f"effective_{name}" for name in COEFFICIENTS), "terminal_boundary", "solver_diagnostic_id")
SUMMARY_FIELDS = ("schema_version", "name", "topology", "case_id", "requested_duration_us", "last_time_us",
                  "completed_horizon", "terminal_boundary", "run_failure", "solver", "model", "controller",
                  "scenario", "metrics", "evaluation", "solver_diagnostics", "wire_evidence", "execution")
MANIFEST_FIELDS = ("schema_version", "scenario", "model", "solver", "controller", "execution", "clocks", "quantization", "artifacts")
STATE_NAMES_MAP = {0: "DISARMED", 1: "RUNNING", 2: "TRIPPED"}
REASONS = {0: "", 1: "separate_trip", 2: "wall_hot", 3: "liquid_hot", 4: "invalid_input", 5: "range_input", 6: "stale_input"}


@dataclass(frozen=True)
class CampaignEvent:
    event_id: str
    type: str
    time_us: int
    payload_json: str

    def to_dict(self):
        return dict(event_id=self.event_id, type=self.type, time_us=self.time_us, **json.loads(self.payload_json))


@dataclass(frozen=True)
class CampaignConfig:
    schema_version: int
    topology: str
    name: str
    case_id: str
    duration_us: int
    tick_us: int
    seed: int
    initial_values: tuple
    model: ThermalParameters
    controller: Configuration
    separate_wall_trip_k: float
    initial_heat_demand: float
    events: tuple
    solver: ThermalSolverConfig

    @property
    def initial(self):
        return dict(zip(INITIAL_FIELDS, self.initial_values))

    def to_dict(self):
        return dict(schema_version=1, topology=self.topology, name=self.name, case_id=self.case_id,
                    duration_us=self.duration_us, tick_us=self.tick_us, seed=self.seed, initial=self.initial,
                    model=asdict(self.model), controller=asdict(self.controller),
                    sensor_adapter=dict(separate_wall_trip_k=self.separate_wall_trip_k),
                    initial_heat_demand=self.initial_heat_demand, events=[e.to_dict() for e in self.events],
                    solver={**asdict(self.solver), "atol": list(self.solver.atol)})


def _object(value, cls, label):
    strict_fields(value, {f.name for f in fields(cls)}, label)
    return cls(**value)


def _event(value, duration_us, tick_us):
    if not isinstance(value, Mapping):
        raise ValueError("event must be an object")
    typ = value.get("type")
    options = {
        "heat_demand": {"command"}, "model_coefficients": set(COEFFICIENTS),
        "observation_link": {"channel", "mode", "end_us", "delay_us"},
        "observation_override": {"channels", "mode", "end_us", "value_i", "bias_k"},
        "command_link": {"mode", "end_us", "delay_us"},
        "actuator_override": {"heat_command", "pump_command", "valve_command", "end_us"},
        "restart": {"epoch"}, "operation": {"operation"}}
    if typ not in options:
        raise ValueError("unknown event type")
    strict_fields(value, {"event_id", "type", "time_us"} | options[typ], "event")
    event_id = value.get("event_id")
    if not isinstance(event_id, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,63}", event_id) is None:
        raise ValueError("event_id must be a short identifier")
    at = integer(value.get("time_us"), "event time_us", 0, duration_us-1)
    payload = {k: v for k, v in value.items() if k not in ("event_id", "type", "time_us")}
    if "end_us" in payload:
        integer(payload["end_us"], "event end_us", at+1, duration_us)
    if typ == "heat_demand":
        payload["command"] = number(payload.get("command"), "heat demand", minimum=0, maximum=1)
    elif typ == "model_coefficients":
        if not payload:
            raise ValueError("coefficient event needs at least one coefficient")
        payload = {k: number(v, k, minimum=0) for k, v in payload.items()}
    elif typ == "observation_link":
        if payload.get("channel") != 2 or type(payload.get("channel")) is not int:
            raise ValueError("campaign observation link is explicitly flow channel2")
        mode = payload.get("mode")
        if mode not in ("drop", "delay", "reorder", "corrupt", "truncate"):
            raise ValueError("unknown observation link mode")
        if mode in ("drop", "delay") and "end_us" not in payload:
            raise ValueError("drop/delay requires an explicit end_us")
        if mode == "delay":
            integer(payload.get("delay_us"), "delay_us", 1, 10_000_000)
        elif "delay_us" in payload:
            raise ValueError("delay_us requires delay mode")
        if mode in ("reorder", "corrupt", "truncate") and ("end_us" in payload or at % tick_us):
            raise ValueError("one-record observation faults must tick-align and omit end_us")
    elif typ == "observation_override":
        if payload.get("channels") != [3, 5] or any(type(ch) is not int for ch in payload["channels"]):
            raise ValueError("temperature override channels must be [3,5]")
        mode = payload.get("mode")
        if mode == "freeze":
            values = payload.get("value_i")
            if not isinstance(values, list) or len(values) != 2 or "bias_k" in payload:
                raise ValueError("freeze needs two explicit wire value_i temperatures")
            for v in values:
                integer(v, "frozen mK", 273_150, 368_150)
        elif mode == "bias":
            payload["bias_k"] = number(payload.get("bias_k"), "bias_k")
            if "value_i" in payload:
                raise ValueError("bias cannot also set frozen values")
        else:
            raise ValueError("unknown observation override mode")
    elif typ == "command_link":
        if payload.get("mode") not in ("drop", "delay", "drop_ack") or "end_us" not in payload:
            raise ValueError("command link needs a mode and explicit span")
        if at % tick_us or payload["end_us"] % tick_us:
            raise ValueError("command link spans must tick-align")
        if payload["mode"] == "delay":
            integer(payload.get("delay_us"), "delay_us", 1, 10_000_000)
        elif "delay_us" in payload:
            raise ValueError("delay_us requires delay mode")
    elif typ == "actuator_override":
        commands = set(payload)-{"end_us"}
        if not commands:
            raise ValueError("actuator override needs a command")
        for k in commands:
            payload[k] = number(payload[k], k, minimum=0, maximum=1)
    elif typ == "restart":
        integer(payload.get("epoch"), "restart epoch", 1, UINT32_MAX)
        if at % tick_us:
            raise ValueError("restart must tick-align")
    elif typ == "operation":
        if payload.get("operation") not in ("ARM", "RESET") or at % tick_us:
            raise ValueError("explicit operation must be ARM/RESET on a tick")
    return CampaignEvent(event_id, typ, at, canonical_json(payload).decode("utf-8"))


def normalize_campaign(value):
    if isinstance(value, CampaignConfig):
        value = value.to_dict()
    strict_fields(value, INPUT_FIELDS, "campaign")
    integer(value.get("schema_version", 1), "schema_version", 1, 1)
    if value.get("topology", "thermal_loop") != "thermal_loop":
        raise ValueError("campaign topology must be thermal_loop")
    case_id = value.get("case_id", value.get("name"))
    if case_id not in CASE_IDS:
        raise ValueError("unknown frozen campaign case_id")
    name = value.get("name", case_id)
    if not isinstance(name, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,95}", name) is None:
        raise ValueError("name must be a short identifier")
    duration = integer(value.get("duration_us", 240_000_000), "duration_us", 1, 1_200_000_000)
    tick = integer(value.get("tick_us", 100_000), "tick_us", 1, 1_000_000)
    if duration % tick or duration // tick > 1_000_000:
        raise ValueError("duration must tick-align with at most1000000 ticks")
    seed = integer(value.get("seed", 1), "seed", 0, UINT32_MAX)
    model = _object(value.get("model", {}), ThermalParameters, "model")
    cfg = Configuration.thermal(tick_us=tick)
    controller = _object(value.get("controller", asdict(cfg)), Configuration, "controller")
    if controller.profile != 2 or controller.tick_us != tick:
        raise ValueError("thermal profile/tick must match campaign")
    initial = value.get("initial", {})
    strict_fields(initial, INITIAL_FIELDS, "initial")
    initial = {**dict(zip(INITIAL_FIELDS, (293.15, 293.15, 293.15, 0., .65))), **initial}
    # Independent public plant initializer enforces strict thermal/actuator domain.
    plant = ThermalPlant(model, **initial)
    initial_values = tuple(float(v) for v in plant.y[:5])
    adapter = value.get("sensor_adapter", {})
    strict_fields(adapter, {"separate_wall_trip_k"}, "sensor_adapter")
    trip = number(adapter.get("separate_wall_trip_k", 358.15), "separate wall trip", minimum=273.15, maximum=368.15)
    demand = number(value.get("initial_heat_demand", 0), "initial heat demand", minimum=0, maximum=1)
    solver = _object(value.get("solver", {}), ThermalSolverConfig, "solver")
    raw_events = value.get("events", [])
    if not isinstance(raw_events, list) or len(raw_events) > 64:
        raise ValueError("events must be an array of at most64 events")
    events = tuple(_event(e, duration, tick) for e in raw_events)
    if len({e.event_id for e in events}) != len(events):
        raise ValueError("duplicate event_id")
    if list(events) != sorted(events, key=lambda e: (e.time_us, e.event_id)):
        raise ValueError("events must sort by time_us then event_id")
    occupied = {}
    previous_epoch = 1
    for event in events:
        d = event.to_dict()
        if event.type == "restart":
            if not sequence_newer(d["epoch"], previous_epoch):
                raise ValueError("restart epoch must be half-range newer")
            previous_epoch = d["epoch"]
        if event.type == "model_coefficients":
            ThermalInputs(**{k:d[k] for k in COEFFICIENTS if k in d}).effective(model)
        if event.type in ("observation_link", "observation_override", "command_link", "actuator_override"):
            key = event.type
            end = d.get("end_us", duration) if event.type not in ("observation_link",) or d["mode"] in ("drop", "delay") else event.time_us+tick
            if event.time_us < occupied.get(key, -1):
                raise ValueError(f"overlapping {key} events require a separate explicit experiment")
            occupied[key] = end
    return CampaignConfig(1, "thermal_loop", name, case_id, duration, tick, seed, initial_values,
                          model, controller, trip, demand, events, solver)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_campaign(path):
    return normalize_campaign(json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_pairs,
                                        parse_constant=lambda v: (_ for _ in ()).throw(ValueError(f"nonfinite {v}"))))


def case_config(case_id):
    if case_id not in CASE_IDS:
        raise ValueError("unknown case")
    cold = case_id in ("nominal_heat_step", "stuck_heat_lost_sink")
    horizon = 600 if case_id in ("reduced_rejection", "frozen_temperature", "biased_temperature") else 1200 if case_id == "stuck_heat_lost_sink" else 90 if case_id in ("reordered_flow", "corrupt_flow", "truncated_flow") else 240 if case_id in ("nominal_heat_step", "restriction") else 120
    initial = dict(zip(INITIAL_FIELDS, (293.15, 293.15, 293.15, 0., .65) if cold else (317.7911483254, 301.1244816587, 293.15, .5274982823, .65)))
    events = [dict(event_id="arm_initial", type="operation", time_us=0, operation="ARM")]
    def add(event_id, typ, at=60_000_000, **payload):
        events.append(dict(event_id=event_id, type=typ, time_us=at, **payload))
    if cold:
        add("heat_step", "heat_demand", 20_000_000, command=1.)
    if case_id == "restriction":
        add("pipe_restriction", "model_coefficients", pipe_resistance_pa_s2_m6=2.4e12)
    elif case_id == "reduced_rejection":
        add("reduced_sink", "model_coefficients", sink_conductance_w_k=125.)
    elif case_id in ("frozen_temperature", "biased_temperature", "stuck_heat_lost_sink"):
        add("lost_sink", "model_coefficients", sink_conductance_w_k=0.)
        if case_id == "frozen_temperature":
            add("frozen_primary", "observation_override", channels=[3,5], mode="freeze", value_i=[301124,317791])
        elif case_id == "biased_temperature":
            add("biased_primary", "observation_override", channels=[3,5], mode="bias", bias_k=-20.)
        else:
            add("stuck_heat", "actuator_override", heat_command=1.)
    elif case_id in ("flow_dropout", "near_tick_before", "near_tick_after", "delayed_flow"):
        at = 60_099_000 if case_id == "near_tick_before" else 60_101_000 if case_id == "near_tick_after" else 60_000_000
        delay = case_id == "delayed_flow"
        add("flow_link_fault", "observation_link", at, channel=2, mode="delay" if delay else "drop",
            end_us=at+(1_000_000 if delay else 5_000_000), **({"delay_us":400_000} if delay else {}))
    elif case_id in ("reordered_flow", "corrupt_flow", "truncated_flow"):
        add("flow_record_fault", "observation_link", channel=2,
            mode={"reordered_flow":"reorder", "corrupt_flow":"corrupt", "truncated_flow":"truncate"}[case_id])
    elif case_id in ("dropped_command", "delayed_command", "dropped_ack"):
        delay = case_id == "delayed_command"
        add("command_link_fault", "command_link", mode={"dropped_command":"drop", "delayed_command":"delay", "dropped_ack":"drop_ack"}[case_id],
            end_us=61_000_000, **({"delay_us":400_000} if delay else {}))
    elif case_id == "planned_restart":
        add("restart", "restart", epoch=2)
        add("arm_restart", "operation", 62_000_000, operation="ARM")
    return normalize_campaign(dict(name=case_id, case_id=case_id, duration_us=horizon*1_000_000,
                                   initial=initial, initial_heat_demand=0. if cold else 1.,
                                   events=sorted(events, key=lambda e:(e["time_us"],e["event_id"]))))


class ObservationCache:
    """Adapter diagnostics reconstructed from encoded observations; never plant access."""
    def __init__(self, origin_us=0, epoch=1):
        self.origin_us, self.epoch = origin_us, epoch
        self.channels = {}

    def observe(self, frame, receipt_us):
        channel, quality, value = frame.payload
        old = self.channels.get(channel)
        sample = self.origin_us+frame.time_us
        if frame.epoch != self.epoch or frame.clock != "V" or sample > receipt_us:
            return False
        if old and (not sequence_newer(frame.sequence, old["sequence"]) or sample < old["source_time_us"]):
            return False
        self.channels[channel] = dict(value_i=value, quality=quality, sequence=frame.sequence,
                                      source_time_us=sample, receipt_time_us=receipt_us,
                                      last_good_source_time_us=sample if quality == 1 else old.get("last_good_source_time_us") if old else None)
        return True

    def masks(self, now_us, stale_us):
        valid, stale, required_ages = 0, 0, []
        for channel in range(1,7):
            d = self.channels.get(channel, {})
            good = d.get("last_good_source_time_us")
            age = UINT64_MAX if good is None else now_us-good
            if d.get("quality") == 1:
                valid |= 1 << (channel-1)
            if age > stale_us:
                stale |= 1 << (channel-1)
            if channel in CHANNELS:
                required_ages.append(age)
        return valid, stale, max(required_ages)


def _active(events, typ, now):
    return [e.to_dict() for e in events if e.type == typ and e.time_us <= now < e.to_dict().get("end_us", UINT64_MAX)]


def _held(cfg, controller, now):
    lease = controller.lease.current(now)
    kwargs = dict(heat_command=lease.heat_command, pump_command=lease.pump_command, valve_command=lease.valve_command)
    for event in _active(cfg.events, "model_coefficients", now):
        kwargs.update({key:event[key] for key in COEFFICIENTS if key in event})
    for event in _active(cfg.events, "actuator_override", now):
        kwargs.update({key:event[key] for key in ("heat_command", "pump_command", "valve_command") if key in event})
    return lease, ThermalInputs(**kwargs)


def _wire_observations(cfg, plant, now, sequence, epoch, origin):
    point = hydraulic_operating_point(plant.y[3], plant.y[4], cfg.model, plant.last_held_inputs)
    values = {2:quantize(point.flow_m3_s,1e9,"flow"),3:quantize(float(plant.y[1]),1000,"hot"),
              4:quantize(float(plant.y[2]),1000,"cold"),5:quantize(float(plant.y[0]),1000,"wall"),
              6:int(plant.y[0]>=cfg.separate_wall_trip_k)}
    for event in _active(cfg.events, "observation_override", now):
        for index, channel in enumerate(event["channels"]):
            values[channel] = event["value_i"][index] if event["mode"] == "freeze" else values[channel]+quantize(event["bias_k"],1000,"bias")
    return [Frame("O",epoch,sequence & UINT32_MAX,"V",now-origin,(channel,1,value)) for channel,value in values.items()]


def _json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+"\n", encoding="utf-8", newline="\n")


def _execution(executable):
    result = execution_provenance()
    sources = {str(p.relative_to(PROJECT_ROOT).as_posix()):file_sha256(p) for p in (PROJECT_ROOT/"firmware/core").glob("*.[ch]")}
    result.update(controller_implementation="portable_c11_host", controller_execution="HOST_SIL",
                  controller_sha256=file_sha256(executable), executable_path=str(Path(executable).resolve()),
                  firmware_core_sha256=sources, physical_validation="NOT_STARTED", board_execution="NOT_EXECUTED",
                  firmware_execution="NOT_EXECUTED", parameter_pedigree="assumed",
                  compiler_build_metadata=_build_metadata(Path(executable)),
                  units=dict(zip(STATE_NAMES,("K","K","K","1","1","J","J")),time_s="s",time_us="us",
                             flow_m3_s="m3/s",pump_pressure_pa="Pa",energy_residual_j="J"))
    return result


def _build_metadata(executable):
    roots = (executable.parent, executable.parent.parent)
    root = next((p for p in roots if (p/"CMakeCache.txt").is_file()),None)
    if root is None:
        return dict(status="UNAVAILABLE",reason="no adjacent CMakeCache; binary identity still retained")
    selected = {}
    for path in [root/"CMakeCache.txt", *root.glob("CMakeFiles/*/CMakeCCompiler.cmake")]:
        text = path.read_text(encoding="utf-8",errors="replace")
        selected[path.relative_to(root).as_posix()] = dict(sha256=file_sha256(path),
            identity_lines=[line for line in text.splitlines() if any(k in line for k in
                ("CMAKE_C_COMPILER_ID", "CMAKE_C_COMPILER_VERSION", "CMAKE_GENERATOR:", "CMAKE_C_COMPILER:", "CMAKE_BUILD_TYPE:"))])
    return dict(status="RECORDED",files=selected)


def run_campaign(cfg, executable, trace_dir, *, solver=None):
    """Execute integer-us schedule; trace_dir is new and retained even on failure."""
    from .campaign_evaluator import audit_wire, campaign_metrics, evaluate_campaign
    cfg = normalize_campaign(cfg)
    solver = cfg.solver if solver is None else solver
    if not isinstance(solver, ThermalSolverConfig):
        raise ValueError("solver must be immutable ThermalSolverConfig")
    executable = Path(executable).resolve()
    if not executable.is_file():
        raise ValueError("real compiled C executable is required; no Python fallback")
    trace_dir = Path(trace_dir)
    trace_dir.mkdir(parents=True, exist_ok=False)
    execution = _execution(executable)
    execution["configuration_sha256"] = cfg.controller.sha256
    execution["scenario_sha256"] = hashlib.sha256(canonical_json(cfg.to_dict())).hexdigest()
    frozen = cfg.to_dict()==case_config(cfg.case_id).to_dict() and solver==cfg.solver
    execution.update(frozen_default_case_match=frozen,configuration_scope="FROZEN_DEFAULT" if frozen else "VARIANT")
    plant = ThermalPlant(cfg.model, **cfg.initial)
    cache, controller, reply = ObservationCache(), None, None
    rows, diagnostics, sessions, pending_flow, pending_commands, held_flow = [], [], [], [], [], None
    origin, epoch, now = 0, 1, 0
    boundary, failure, demand = None, None, cfg.initial_heat_demand
    started = time.perf_counter()
    latency = []
    events_by_time = {}
    for event in cfg.events:
        events_by_time.setdefault(event.time_us, []).append(event)
        end = event.to_dict().get("end_us")
        if end is not None:
            events_by_time.setdefault(end, []).append(event)
    event_times = sorted(events_by_time)
    current_operation = 0
    diagnostic_id = None

    def open_session():
        path = trace_dir/f"epoch-{epoch}"
        descriptor=dict(path=str(path),epoch=epoch,session_origin_us=origin,process_pid=None)
        sessions.append(descriptor)
        process=CController(executable,cfg.controller,epoch=epoch,session_origin_us=origin,trace_dir=path)
        descriptor["process_pid"]=process.process.pid
        return process

    def snapshot(kind, at, *, event_phase=None, event_ids="", boundary_name=None):
        lease, inputs = _held(cfg,controller,int(at))
        plant.last_held_inputs = inputs
        point = hydraulic_operating_point(float(plant.y[3]),float(plant.y[4]),cfg.model,inputs)
        q = reply.raw_command if reply else None
        r = reply.status if reply else None
        row = dict(schema_version=1,run_name=cfg.name,topology=cfg.topology,sample_id=len(rows),record_type=kind,
                   time_us=at,time_s=plant.t,epoch=epoch,session_origin_us=origin,wire_time_us=at-origin,
                   controller_tick_id=at//cfg.tick_us if kind == "controller_tick" else None,
                   reply_time_us=origin+r.time_us if r else None,
                   controller_state=STATE_NAMES_MAP[r.payload[1]] if r else "DISARMED",
                   trip_reason=REASONS[r.payload[2]] if r else "",operation=current_operation if kind=="controller_tick" else 0,
                   operation_result=r.payload[6] if r else 0, valid_mask=r.payload[3] if r else 0,
                   stale_mask=r.payload[4] if r else 63,max_age_us=r.payload[5] if r else UINT64_MAX,
                   observation_cache_source="reconstructed_from_retained_wire",
                   cache_matches_reply=bool(r and cache.masks(origin+r.time_us,cfg.controller.stale_us)==r.payload[3:6]),
                   event_ids=event_ids,event_phase=event_phase,
                   **dict(zip(STATE_NAMES,map(float,plant.y))),flow_m3_s=point.flow_m3_s,pump_pressure_pa=point.pump_pressure_pa,
                   energy_residual_j=plant.energy_residual_j(),
                   requested_heat_command=q.payload[1]/PPM if q else 0.,
                   requested_pump_command=q.payload[2]/PPM if q else 0.,
                   requested_valve_command=q.payload[3]/PPM if q else 1.,
                   lease_heat_command=lease.heat_command,lease_pump_command=lease.pump_command,lease_valve_command=lease.valve_command,
                   fault_heat_command=inputs.heat_command,fault_pump_command=inputs.pump_command,fault_valve_command=inputs.valve_command,
                   command_sequence=lease.sequence,command_expires_us=lease.expires_us,command_expired=lease.expired,
                   heat_demand_command=demand,applied_heat_w=inputs.heat_command*cfg.model.max_heat_w,
                   **{f"effective_{k}":v for k,v in inputs.effective(cfg.model).items()},
                   terminal_boundary=boundary_name,solver_diagnostic_id=diagnostic_id)
        for channel,prefix in CHANNELS.items():
            d = cache.channels.get(channel,{})
            for field in CHANNEL_FIELDS:
                row[f"{prefix}_{field}"] = at-d["last_good_source_time_us"] if field=="age_us" and d.get("last_good_source_time_us") is not None else d.get(field)
        for channel,key,scale in ((2,"observed_flow_m3_s",1e9),(3,"observed_hot_temperature_k",1000),
                                  (4,"observed_cold_temperature_k",1000),(5,"observed_wall_temperature_k",1000),(6,"observed_separate_trip",1)):
            d = cache.channels.get(channel)
            row[key] = d["value_i"]/scale if d else None
        rows.append({key:row[key] for key in TELEMETRY_FIELDS})

    try:
        controller = open_session()
        while True:
            current_events = events_by_time.get(now,[])
            if current_events and rows:
                # Before event, the plant's already executed last interval is
                # retained; snapshot must use its prior coefficient/input set.
                old_held = plant.last_held_inputs
                snapshot("event_boundary",now,event_phase="before",event_ids=";".join(e.event_id for e in current_events))
                # Fix the before row from the independently retained old hold.
                before = rows[-1]
                before.update({f"effective_{k}":v for k,v in old_held.effective(cfg.model).items()})
                old_point = hydraulic_operating_point(plant.y[3],plant.y[4],cfg.model,old_held)
                before.update(flow_m3_s=old_point.flow_m3_s,pump_pressure_pa=old_point.pump_pressure_pa,
                              fault_heat_command=old_held.heat_command,fault_pump_command=old_held.pump_command,
                              fault_valve_command=old_held.valve_command,applied_heat_w=old_held.heat_command*cfg.model.max_heat_w)
            for event in current_events:
                d = event.to_dict()
                if event.time_us != now:
                    continue  # span ending; _active removes its held effect
                if event.type == "heat_demand":
                    demand = d["command"]
                elif event.type == "restart":
                    controller.close()
                    epoch,origin = d["epoch"],now
                    controller = open_session()
                    cache,reply = ObservationCache(origin,epoch),None
                    pending_flow.clear()
                    # Retain queued old Q arrivals: new epoch rejects them.
            # Delayed command arrivals can occur between ticks and cannot renew
            # a lease at equality or after their original expiry.
            due = [item for item in pending_commands if item[0]<=now]
            pending_commands[:] = [item for item in pending_commands if item[0]>now]
            for _,command in due:
                controller.deliver_command(command,now)
                snapshot("command_arrival",now)
            if current_events:
                snapshot("event_boundary",now,event_phase="after",event_ids=";".join(e.event_id for e in current_events))
            if now % cfg.tick_us == 0:
                current_operation = next((1 if e.to_dict()["operation"]=="ARM" else 2 for e in current_events
                                          if e.type=="operation" and e.time_us==now),0)
                observations = _wire_observations(cfg,plant,now,now//cfg.tick_us,epoch,origin)
                raw = []
                flow = observations.pop(0)
                delayed = [f for due_at,f in pending_flow if due_at<=now]
                pending_flow[:] = [(due_at,f) for due_at,f in pending_flow if due_at>now]
                observations = delayed+observations
                links = _active(cfg.events,"observation_link",now)
                link = next((d for d in links if d["mode"] in ("drop","delay") or d["time_us"]==now),None)
                if link and link["mode"]=="drop":
                    pass
                elif link and link["mode"]=="delay":
                    pending_flow.append((now+link["delay_us"],flow))
                elif link and link["mode"]=="reorder":
                    held_flow = flow
                elif link and link["mode"] in ("corrupt","truncate"):
                    encoded = flow.encode()
                    if link["mode"]=="corrupt":
                        index = encoded.index(b"*")-1
                        encoded = encoded[:index]+(b"1" if encoded[index:index+1]!=b"1" else b"2")+encoded[index+1:]
                    else:
                        encoded = encoded[:encoded.index(b"*")-2]+b"\n"
                    raw.append(encoded)
                else:
                    observations.append(flow)
                    if held_flow is not None:
                        observations.append(held_flow)
                        held_flow = None
                command_link = next(iter(_active(cfg.events,"command_link",now)),None)
                def command_filter(command):
                    if command_link and command_link["mode"] in ("drop","delay"):
                        if command_link["mode"]=="delay":
                            pending_commands.append((now+command_link["delay_us"],command))
                        return None
                    return command
                transaction_start = time.perf_counter()
                reply = controller.step(now,observations,operation=current_operation,heat_demand_ppm=quantize(demand,PPM,"heat demand"),
                                        command_filter=command_filter,acknowledge=not(command_link and command_link["mode"]=="drop_ack"),
                                        raw_observations=raw)
                latency.append(time.perf_counter()-transaction_start)
                # Only encoded data enter the diagnostic cache; a raw injection
                # is decoded independently and cannot gain validity by label.
                for frame in observations:
                    cache.observe(frame,now)
                for encoded in raw:
                    try:
                        cache.observe(decode(encoded),now)
                    except ValueError:
                        pass
                snapshot("controller_tick",now)
            elif controller.lease.expires_us==now:
                snapshot("command_expiry",now)
            if now == cfg.duration_us:
                break
            future_events = [at for at in event_times if at>now]
            next_tick = (now//cfg.tick_us+1)*cfg.tick_us
            expiry = controller.lease.expires_us
            candidates = [next_tick,cfg.duration_us]+future_events[:1]+[due_at for due_at,_ in pending_commands if due_at>now]
            if expiry is not None and expiry>now:
                candidates.append(expiry)
            next_time = min(candidates)
            _,inputs = _held(cfg,controller,now)
            result = plant.advance((next_time-now)/1e6,inputs,solver)
            diagnostic_id = len(diagnostics)
            diagnostics.append(result.diagnostics)
            if result.boundary:
                boundary = result.boundary
                snapshot("terminal_boundary",plant.t*1e6,boundary_name=boundary)
                break
            now = next_time
            # The scheduler is authoritative for successful endpoint time;
            # raw solver accepted time remains retained in diagnostics.
            plant.t = now/1e6
    except ControllerProcessFailure as exc:
        failure = dict(kind="controller_process_failure",message=str(exc),time_us=now,trace_dir=str(exc.trace_dir),returncode=exc.returncode)
        if controller is not None:
            snapshot("solver_failure",plant.t*1e6)
    except OSError as exc:
        # OS-level startup/pipe errors retain the capture directory as it exists;
        # malformed programming values are not converted into successful runs.
        failure = dict(kind="controller_io_failure",message=str(exc),time_us=now,
                       trace_dir=sessions[-1]["path"] if sessions else str(trace_dir))
    except IntegrationFailure as exc:
        failure = dict(kind="solver_failure",message=str(exc),time_us=plant.t*1e6)
        if plant.last_advance:
            diagnostic_id = len(diagnostics)
            diagnostics.append(plant.last_advance.diagnostics)
        snapshot("solver_failure",plant.t*1e6)
    finally:
        if controller is not None:
            controller.close()
    wire = audit_wire(sessions,cfg.controller)
    metrics = campaign_metrics(cfg,rows)
    metrics["wall_elapsed_s"] = time.perf_counter()-started
    metrics["protocol_latency_s"] = dict(count=len(latency),minimum=min(latency) if latency else None,
        median=float(np.median(latency)) if latency else None,p95=float(np.percentile(latency,95)) if latency else None,
        maximum=max(latency) if latency else None)
    summary = dict(schema_version=1,name=cfg.name,topology=cfg.topology,case_id=cfg.case_id,
                   requested_duration_us=cfg.duration_us,last_time_us=rows[-1]["time_us"] if rows else None,
                   completed_horizon=bool(rows and rows[-1]["time_us"]==cfg.duration_us and not boundary and not failure),
                   terminal_boundary=boundary,run_failure=failure,solver=solver.executed(cfg.tick_us/1e6),
                   model=asdict(cfg.model),controller=asdict(cfg.controller),scenario=cfg.to_dict(),metrics=metrics,
                   evaluation=None,solver_diagnostics=diagnostics,wire_evidence=wire,execution=execution)
    summary["evaluation"] = evaluate_campaign(cfg,rows,wire,run_failure=failure)
    return rows,summary


def write_campaign(out,cfg,rows,summary,executable):
    """Export executed metadata, never relabel a solver or binary after a run."""
    cfg = normalize_campaign(cfg)
    out = Path(out)
    for session in summary["wire_evidence"]["sessions"]:
        expected=(out/"wire"/f"epoch-{session['epoch']}").resolve()
        actual=Path(session["trace_dir"]).resolve()
        if actual!=expected or not actual.is_dir() or (summary["run_failure"] is None and not all((actual/name).is_file() for name in ("stdin.bin","stdout.bin","stderr.bin","events.jsonl"))):
            raise ValueError("export requires retained captures at out/wire/epoch-{epoch}; external/missing traces cannot be omitted")
    out.mkdir(parents=True,exist_ok=True)
    if summary["scenario"] != cfg.to_dict() or file_sha256(executable)!=summary["execution"]["controller_sha256"]:
        raise ValueError("export scenario/binary does not match executed campaign")
    with (out/"telemetry.csv").open("w",encoding="utf-8",newline="") as stream:
        writer = csv.DictWriter(stream,fieldnames=TELEMETRY_FIELDS,lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    for filename,value in (("scenario.json",cfg.to_dict()),("model.json",summary["model"]),("solver.json",summary["solver"]),
                           ("controller.json",summary["controller"]),("summary.json",summary)):
        _json(out/filename,value)
    artifacts = {path.relative_to(out).as_posix():file_sha256(path) for path in out.rglob("*")
                 if path.is_file() and path.name!="manifest.json"}
    manifest = dict(schema_version=1,scenario=cfg.to_dict(),model=summary["model"],solver=summary["solver"],
                    controller=summary["controller"],execution=summary["execution"],
                    clocks=dict(absolute="virtual simulation microseconds",wire="V: absolute minus session_origin_us",
                                source="original V acquisition",receipt="delivery STEP absolute V",
                                host="monotonic wall seconds; never subtracted from V",device="NOT_EXECUTED"),
                    quantization=dict(command_ppm=1_000_000,temperature_mk=1000,flow_ul_s=1_000_000_000,
                                      command_rounding_max_ppm=.5,temperature_rounding_max_mk=.5,flow_rounding_max_ul_s=.5),
                    artifacts=artifacts)
    _json(out/"manifest.json",manifest)
    return manifest
