"""Independent retained-wire and raw-evidence judgments; no plant/controller calls."""
import binascii
import json
import math
from pathlib import Path
import re
from .protocol import UINT64_MAX


APPLICABILITY = {
    "nominal_heat_step": (1,2,3,7), "restriction": (1,2,3,7,12), "reduced_rejection": (2,3,7,11),
    "flow_dropout": (2,3,4,5,7), "near_tick_before": (2,3,4,5,7), "near_tick_after": (2,3,4,5,7),
    "frozen_temperature": (2,3,4,6,7), "biased_temperature": (2,3,4,6,7),
    "delayed_flow": (2,3,4,5,7,8), "reordered_flow": (2,3,7,8), "corrupt_flow": (2,3,7,8),
    "truncated_flow": (2,3,7,8), "dropped_command": (2,3,7,8), "delayed_command": (2,3,7,8),
    "dropped_ack": (2,3,7,8), "planned_restart": (2,3,7,9), "stuck_heat_lost_sink": (2,4,10)}


def parse_retained_line(raw):
    """Separate standard-library wire reader, independent of production decode."""
    if not isinstance(raw,bytes) or len(raw)>256 or not raw.endswith(b"\n"):
        raise ValueError("retained length/LF")
    match = re.fullmatch(rb"([!-~]+)\*([0-9A-F]{4})\n",raw)
    if not match or binascii.crc_hqx(match[1],0)!=int(match[2],16):
        raise ValueError("retained checksum/ASCII")
    p = match[1].decode("ascii").split("|")
    counts = {"B":2,"H":1,"C":17,"O":3,"S":2,"Q":6,"A":2,"R":7}
    if len(p)<8 or p[:2]!=["F","1"] or p[2] not in counts or len(p)!=7+counts[p[2]] or p[5] not in ("V","D"):
        raise ValueError("retained header/fields")
    tokens = [p[3],p[4],p[6],*p[7:]]
    for i,token in enumerate(tokens):
        signed = i>=3 and (p[2]=="O" and i==5 or p[2]=="C" and i==14)
        if re.fullmatch(r"0|[1-9][0-9]*|-[1-9][0-9]*" if signed else r"0|[1-9][0-9]*",token) is None:
            raise ValueError("retained noncanonical integer")
    epoch,seq,at,*payload = map(int,tokens)
    if epoch>2**32-1 or seq>2**32-1 or at>UINT64_MAX:
        raise ValueError("retained integer overflow")
    if p[2]=="O" and (payload[0] not in range(1,7) or payload[1] not in (0,1,2)
                      or not -2**31<=payload[2]<2**31 or payload[1]==2 and payload[2]!=0
                      or payload[0]==6 and payload[2] not in (0,1)):
        raise ValueError("retained O semantics")
    for i,value in enumerate(payload):
        signed = p[2]=="O" and i==2 or p[2]=="C" and i==11
        maximum = UINT64_MAX if p[2]=="R" and i==5 or p[2]=="C" and i in (6,7) else 2**32-1
        if not (-2**31 if signed else 0)<=value<=(2**31-1 if signed else maximum):
            raise ValueError("retained payload overflow")
    if p[2]=="Q" and (not 1<=payload[0]<=10000000 or any(v>1000000 for v in payload[1:4]) or payload[4]>2 or payload[5]>6):
        raise ValueError("retained Q semantics")
    if p[2]=="R" and (payload[1]>2 or payload[2]>6 or payload[3]>63 or payload[4]>63 or payload[6]>2):
        raise ValueError("retained R semantics")
    if p[2]=="S" and (payload[0]>2 or payload[1]>1000000) or p[2]=="A" and payload[1]>1:
        raise ValueError("retained STEP/ACK semantics")
    return dict(type=p[2],epoch=epoch,sequence=seq,clock=p[5],time_us=at,payload=payload)


def audit_wire(sessions,configuration):
    """Re-read captured bytes after child reap, not injector promises."""
    result = dict(status="PASS",issues=[],sessions=[],observation_dispositions=[],command_dispositions=[],
                  invalid_input_records=[],ticks=[],events=[],ack_records=[],stderr_rejection_count=0)
    retained_commands = set()
    for session in sessions:
        path,origin,epoch = Path(session["path"]),session["session_origin_us"],session["epoch"]
        if not all((path/name).is_file() for name in ("stdin.bin","stdout.bin","stderr.bin","events.jsonl")):
            result["issues"].append("missing retained wire artifact")
            result["sessions"].append(dict(epoch=epoch,session_origin_us=origin,trace_dir=str(path),
                process_pid=session.get("process_pid"),step_count=0,child_reaped=False))
            continue
        raw_in,raw_out = (path/"stdin.bin").read_bytes(),(path/"stdout.bin").read_bytes()
        stderr = (path/"stderr.bin").read_bytes()
        result["stderr_rejection_count"] += stderr.count(b"rejected")
        events = []
        for line in (path/"events.jsonl").read_text(encoding="utf-8",errors="replace").splitlines():
            try:
                event=json.loads(line,parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
                if not isinstance(event,dict) or not isinstance(event.get("event"),str) or not _finite(event.get("host_monotonic_s")):
                    raise ValueError("event identity")
                if event["event"]=="command_disposition":
                    f=event["frame"]
                    if (not isinstance(f,dict) or set(f)!={"type","epoch","sequence","clock","time_us","payload"}
                            or not isinstance(f["payload"],list) or len(f["payload"])!=6 or type(event["absolute_receipt_us"]) is not int
                            or type(event["accepted"]) is not bool):
                        raise ValueError("command disposition fields")
                    # Reconstruct only for independent canonical-byte parser;
                    # original raw Q membership is required later as well.
                    body="|".join(map(str,("F",1,f["type"],f["epoch"],f["sequence"],f["clock"],f["time_us"],*f["payload"]))).encode("ascii")
                    parsed=parse_retained_line(body+f"*{binascii.crc_hqx(body,0):04X}\n".encode("ascii"))
                    if parsed!=f or f["type"]!="Q":
                        raise ValueError("command disposition canonical fields")
                if event["event"]=="ack_dropped" and (not isinstance(event.get("frame"),dict) or set(event["frame"])!={"type","epoch","sequence","clock","time_us","payload"}):
                    raise ValueError("dropped ACK fields")
                if event["event"]=="process_reaped" and type(event.get("returncode")) is not int:
                    raise ValueError("reaped returncode")
                events.append(event)
            except (ValueError,KeyError,TypeError,UnicodeError) as exc:
                result["issues"].append("malformed retained event: "+str(exc))
        result["events"].extend({"epoch":epoch,"session_origin_us":origin,**e} for e in events)
        result["command_dispositions"].extend({"epoch":epoch,"session_origin_us":origin,**e} for e in events if e["event"]=="command_disposition")
        output,ordered_output,boot_seen = {},[],False
        for raw in raw_out.splitlines(keepends=True):
            try:
                f = parse_retained_line(raw)
            except ValueError as exc:
                result["issues"].append(str(exc)+" in stdout")
                continue
            if f["type"] in ("Q","R"):
                if (f["type"],f["epoch"],f["time_us"]) in output:
                    result["issues"].append("duplicate reliable output")
                output[(f["type"],f["epoch"],f["time_us"])] = f
                ordered_output.append(f)
            elif f==dict(type="B",epoch=0,sequence=0,clock="V",time_us=0,payload=[100,0]) and not boot_seen and not ordered_output:
                boot_seen=True
            else:
                result["issues"].append("unexpected output type/boot/order")
            if f["type"]=="Q":
                retained_commands.add((f["epoch"],f["sequence"],f["time_us"],tuple(f["payload"])))
        staged,channels,steps,handshake_seen,config_seen = [],{},0,False,False
        for raw in raw_in.splitlines(keepends=True):
            try:
                frame = parse_retained_line(raw)
            except ValueError as exc:
                result["invalid_input_records"].append(dict(epoch=epoch,raw_hex=raw.hex(),reason=str(exc)))
                continue
            if frame["type"]=="O":
                staged.append(frame)
                if len(staged)>32:
                    result["issues"].append("retained observation staging overflow")
            elif frame["type"]=="H":
                if handshake_seen or frame!=dict(type="H",epoch=epoch,sequence=0,clock="V",time_us=0,payload=[2]):
                    result["issues"].append("retained handshake differs from declared session")
                handshake_seen=True
            elif frame["type"]=="C":
                if not handshake_seen or config_seen or frame!=dict(type="C",epoch=epoch,sequence=0,clock="V",time_us=0,payload=list(configuration.payload)):
                    result["issues"].append("retained configuration differs from executed configuration")
                config_seen=True
            elif frame["type"]=="A":
                result["ack_records"].append(dict(epoch=epoch,time_us=origin+frame["time_us"],frame=frame))
            elif frame["type"]=="S":
                if (not config_seen or frame["epoch"]!=epoch or frame["clock"]!="V" or frame["sequence"]!=(steps & (2**32-1))
                        or frame["time_us"]!=steps*configuration.tick_us):
                    result["issues"].append("retained reliable STEP schedule invalid")
                    staged.clear()
                    continue
                at = origin+frame["time_us"]
                for f in staged:
                    channel,quality,value = f["payload"]
                    old = channels.get(channel)
                    sample = origin+f["time_us"]
                    accepted = f["epoch"]==epoch and f["clock"]=="V" and sample<=at
                    if old:
                        delta = (f["sequence"]-old["sequence"]) & (2**32-1)
                        accepted = accepted and 0<delta<2**31 and sample>=old["source_time_us"]
                    if accepted:
                        channels[channel] = dict(value_i=value,quality=quality,sequence=f["sequence"],source_time_us=sample,
                            receipt_time_us=at,last_good_source_time_us=sample if quality==1 else old.get("last_good_source_time_us") if old else None)
                    result["observation_dispositions"].append(dict(epoch=epoch,receipt_time_us=at,frame=f,accepted=bool(accepted),
                                                                cached_after=dict(channels.get(channel,{}))))
                staged.clear()
                valid,stale,ages = 0,0,[]
                for ch in range(1,7):
                    cached = channels.get(ch,{})
                    good = cached.get("last_good_source_time_us")
                    age = UINT64_MAX if good is None else at-good
                    if cached.get("quality")==1:
                        valid |= 1 << (ch-1)
                    if age>configuration.stale_us:
                        stale |= 1 << (ch-1)
                    if ch>=2:
                        ages.append(age)
                q,r = output.get(("Q",epoch,frame["time_us"])),output.get(("R",epoch,frame["time_us"]))
                matches = bool(q and r and r["sequence"]==frame["sequence"] and r["payload"][:3]==[q["sequence"],*q["payload"][4:6]]
                               and r["payload"][3:6]==[valid,stale,max(ages)] and ordered_output[2*steps:2*steps+2]==[q,r]
                               and q["clock"]==r["clock"]=="V" and q["sequence"]==steps)
                tick = dict(epoch=epoch,session_origin_us=origin,time_us=at,step=frame,command=q,reply=r,
                            cache={str(ch):dict(v) for ch,v in channels.items()},cache_matches_reply=matches)
                result["ticks"].append(tick)
                if not matches:
                    result["issues"].append(f"wire cache/reply mismatch or missing reply at {at}")
                steps += 1
        if not any(e["event"]=="process_reaped" for e in events):
            result["issues"].append("child not demonstrably reaped")
        if not boot_seen or not handshake_seen or not config_seen or len(ordered_output)!=2*steps:
            result["issues"].append("missing/extra boot/config/reliable output")
        if any(e["event"]=="process_failure" for e in events):
            result["issues"].append("retained controller process failure")
        result["sessions"].append(dict(epoch=epoch,session_origin_us=origin,trace_dir=str(path),process_pid=session.get("process_pid"),step_count=steps,
                                       child_reaped=any(e["event"]=="process_reaped" for e in events)))
    accepted_by_epoch = {}
    for d in result["command_dispositions"]:
        f,at = d["frame"],d["absolute_receipt_us"]
        origin,epoch = d["session_origin_us"],d["epoch"]
        previous = accepted_by_epoch.get(epoch)
        expected = (f["type"]=="Q" and f["clock"]=="V" and f["epoch"]==epoch
                    and origin+f["time_us"]<=at and f["time_us"]<=UINT64_MAX-f["payload"][0])
        expiry = origin+f["time_us"]+f["payload"][0]
        expected = expected and expiry<=UINT64_MAX and expiry>at
        if previous:
            expected = expected and 0<((f["sequence"]-previous["frame"]["sequence"]) & (2**32-1))<2**31
        if (f["epoch"],f["sequence"],f["time_us"],tuple(f["payload"])) not in retained_commands:
            result["issues"].append("command disposition lacks retained raw Q")
        if type(d["accepted"]) is not bool or d["accepted"]!=bool(expected):
            result["issues"].append("command acceptance label disagrees with independent lease")
        d["independent_accepted"] = bool(expected)
        d["independent_expires_us"] = expiry
        if expected:
            accepted_by_epoch[epoch] = d
    for event in result["events"]:
        if event["event"]=="ack_dropped" and any(a["frame"]==event["frame"] for a in result["ack_records"]):
            result["issues"].append("ACK declared dropped is present in retained stdin")
    if not sessions or result["issues"]:
        result["status"] = "UNASSESSABLE"
    return result


def dropout_oracle_us(start_us,tick_us,stale_us,origin_us=0):
    """Last acquisition strictly before injection; first tick strictly after age limit."""
    last = origin_us+((start_us-origin_us-1)//tick_us)*tick_us
    return origin_us+((last-origin_us+stale_us)//tick_us+1)*tick_us


def campaign_metrics(cfg,rows):
    from .campaign import TELEMETRY_FIELDS
    valid = [r for r in rows if isinstance(r,dict) and set(r)==set(TELEMETRY_FIELDS)
             and all(_finite(r.get(k)) for k in ("time_us","time_s","wall_temperature_k","hot_temperature_k","cold_temperature_k","energy_residual_j"))
             and not any(isinstance(v,(int,float)) and not isinstance(v,bool) and not math.isfinite(v) for v in r.values())]
    discarded=len(rows)-len(valid)
    ordered=(bool(valid) and all(type(r["sample_id"]) is int for r in valid)
             and all(b["sample_id"]>a["sample_id"] and b["time_us"]>=a["time_us"] and b["time_s"]>=a["time_s"] for a,b in zip(valid,valid[1:])))
    coverage=dict(start_time_us=valid[0]["time_us"] if ordered else None,end_time_us=valid[-1]["time_us"] if ordered else None,
                  requested_end_time_us=cfg.duration_us,retained_samples=len(valid),discarded_rows=discarded,scope="UNAVAILABLE")
    if not valid:
        return dict(global_sampled_peak_k=None,largest_sample_gap_s=None,global_peak_upper_bound_k=None,
                    energy_residual_max_j=None,tracking_true_max_error_m3_s=None,tracking_observed_max_error_m3_s=None,
                    integral_flow_error_m3=None,first_trip_time_us=None,first_trip_reason=None,terminal_time_us=None,
                    trip_expected_time_us=None,prefault_temperatures_k=None,final30_mean_temperatures_k=None,
                    sampled_peaks_k={},peak_bound_meaning="sample max+.5 K/s largest gap; excludes numerical error",peak_bound_coverage=coverage)
    names = ("wall_temperature_k","hot_temperature_k","cold_temperature_k")
    peaks = {k:max(r[k] for r in valid) for k in names}
    gaps = [b["time_s"]-a["time_s"] for a,b in zip(valid,valid[1:])]
    gap = max(gaps,default=0.)
    premise = (not discarded and ordered and cfg.model.max_heat_w<=5000 and cfg.model.wall_capacity_j_k>=10000
               and all(r[k]>=cfg.model.sink_temperature_k-64*math.ulp(368.15) for r in valid for k in names))
    if premise:
        coverage["scope"]="FULL_RETAINED_HORIZON" if valid[0]["time_us"]==0 and valid[-1]["time_us"]==cfg.duration_us else "RETAINED_PREFIX"
    final = [r for r in valid if r["time_us"]>=cfg.duration_us-30_000_000]
    full_window = not discarded and ordered and valid[0]["time_us"]==0 and valid[-1]["time_us"]==cfg.duration_us and cfg.duration_us>=30_000_000
    target = cfg.controller.target_i/1e9
    flow_final = final if full_window else []
    triples = [(r["time_s"],abs(r["flow_m3_s"]-target)) for r in valid if _finite(r.get("flow_m3_s"))]
    integral = sum((b[0]-a[0])*(a[1]+b[1])/2 for a,b in zip(triples,triples[1:]))
    trip = next((r for r in valid if r.get("record_type")=="controller_tick" and r.get("controller_state")=="TRIPPED"),None)
    link = next((e.to_dict() for e in cfg.events if e.type=="observation_link" and e.to_dict()["mode"] in ("drop","delay")),None)
    fault_at = next((e.time_us for e in cfg.events if e.type=="model_coefficients"),60_000_000)
    prefault = next((r for r in valid if r["time_us"]==fault_at and r.get("event_phase")=="before"),None)
    return dict(sampled_peaks_k=peaks,global_sampled_peak_k=max(peaks.values()),largest_sample_gap_s=gap,
                global_peak_upper_bound_k=max(peaks.values())+.5*gap if premise else None,
                peak_bound_coverage=coverage,
                peak_bound_meaning="sample max+.5 K/s largest actual event/terminal gap; excludes numerical error",
                energy_residual_max_j=max(abs(r["energy_residual_j"]) for r in valid if _finite(r.get("energy_residual_j"))),
                tracking_true_max_error_m3_s=max((abs(r["flow_m3_s"]-target) for r in flow_final),default=None),
                tracking_observed_max_error_m3_s=max((abs(r["observed_flow_m3_s"]-target) for r in flow_final if _finite(r.get("observed_flow_m3_s"))),default=None),
                integral_flow_error_m3=integral,first_trip_time_us=trip["time_us"] if trip else None,
                first_trip_reason=trip["trip_reason"] if trip else None,
                terminal_time_us=valid[-1]["time_us"] if valid[-1].get("terminal_boundary") else None,
                trip_expected_time_us=dropout_oracle_us(link["time_us"],cfg.tick_us,cfg.controller.stale_us) if link else None,
                prefault_temperatures_k={k:prefault[k] for k in names} if prefault else None,
                final30_mean_temperatures_k={k:sum(r[k] for r in final)/len(final) for k in names} if full_window and final else None)


def _finite(value):
    return not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value)


def _trace_errors(cfg,rows,wire):
    from .campaign import TELEMETRY_FIELDS,CHANNELS,CHANNEL_FIELDS,STATE_NAMES
    errors = []
    if not isinstance(wire,dict):
        return ["missing/nonmapping retained wire audit"]
    if not isinstance(rows,list) or not rows:
        return ["missing telemetry"]
    previous = -1
    root_tolerance = 64*math.ulp(368.15)
    for index,r in enumerate(rows):
        if not isinstance(r,dict) or set(r)!=set(TELEMETRY_FIELDS):
            errors.append(f"row{index} unknown/missing field or nonmapping")
            continue
        numeric = (*STATE_NAMES,"time_us","time_s","wire_time_us","flow_m3_s","pump_pressure_pa","energy_residual_j",
                   "requested_heat_command","requested_pump_command","requested_valve_command","lease_heat_command","lease_pump_command",
                   "lease_valve_command","fault_heat_command","fault_pump_command","fault_valve_command","heat_demand_command","applied_heat_w",
                   "effective_hot_conductance_w_k","effective_sink_conductance_w_k","effective_pipe_resistance_pa_s2_m6","effective_valve_resistance_pa_s2_m6")
        if any(not _finite(r[k]) for k in numeric):
            errors.append(f"row{index} nonfinite numeric")
            continue
        if any(type(r[k]) is not int for k in ("sample_id","epoch","session_origin_us","operation","operation_result","valid_mask","stale_mask","max_age_us")):
            errors.append(f"row{index} noninteger identity/status")
        if r["sample_id"]!=index or r["time_us"]<previous or abs(r["time_s"]*1e6-r["time_us"])>1e-6 or r["wire_time_us"]!=r["time_us"]-r["session_origin_us"]:
            errors.append(f"row{index} schedule identity")
        previous = r["time_us"]
        legal_types = ("controller_tick","event_boundary","command_expiry","command_arrival","terminal_boundary","solver_failure")
        if r["record_type"] not in legal_types or r["event_phase"] not in (None,"before","after") or not isinstance(r["event_ids"],str):
            errors.append(f"row{index} record/event identity")
        if (r["record_type"]=="event_boundary")!=(r["event_phase"] in ("before","after")):
            errors.append(f"row{index} event phase identity")
        if r["controller_state"] not in ("DISARMED","RUNNING","TRIPPED") or r["trip_reason"] not in ("","separate_trip","wall_hot","liquid_hot","invalid_input","range_input","stale_input"):
            errors.append(f"row{index} invalid state/reason")
        if r["observation_cache_source"]!="reconstructed_from_retained_wire" or type(r["cache_matches_reply"]) is not bool or type(r["command_expired"]) is not bool:
            errors.append(f"row{index} provenance/boolean type")
        if r["record_type"]=="controller_tick":
            if type(r["time_us"]) is not int or r["time_us"]%cfg.tick_us or not r["cache_matches_reply"] or r["controller_tick_id"]!=r["time_us"]//cfg.tick_us or type(r["controller_tick_id"]) is not int:
                errors.append(f"row{index} tick/cache mismatch")
        elif r["controller_tick_id"] is not None:
            errors.append(f"row{index} non-tick controller identity")
        for k in numeric:
            if (k.endswith("_command") or k in ("pump_speed","valve_opening")) and not 0<=r[k]<=1:
                errors.append(f"row{index} command/actuator domain")
        boundary = r["terminal_boundary"]
        for name in ("wall","hot","cold"):
            value = r[f"{name}_temperature_k"]
            if boundary==f"{name}_upper":
                legal = r["record_type"]=="terminal_boundary" and index==len(rows)-1 and abs(value-368.15)<=root_tolerance
            elif boundary==f"{name}_lower":
                legal = r["record_type"]=="terminal_boundary" and index==len(rows)-1 and abs(value-273.15)<=root_tolerance
            else:
                legal = 273.15<value<368.15
            if not legal:
                errors.append(f"row{index} temperature/boundary domain")
        if boundary not in (None,"wall_upper","hot_upper","cold_upper","wall_lower","hot_lower","cold_lower"):
            errors.append(f"row{index} invalid terminal enum")
        if bool(boundary)!=(r["record_type"]=="terminal_boundary"):
            errors.append(f"row{index} terminal identity")
        if r["reply_time_us"] is not None:
            if type(r["reply_time_us"]) is not int or r["reply_time_us"]>r["time_us"]:
                errors.append(f"row{index} reply time")
            for channel,prefix in CHANNELS.items():
                vals = {f:r[f"{prefix}_{f}"] for f in CHANNEL_FIELDS}
                if any(type(vals[k]) is not int for k in ("value_i","quality","sequence","source_time_us","receipt_time_us","last_good_source_time_us")):
                    errors.append(f"row{index} {prefix} missing/noninteger cache")
                    continue
                if not(vals["quality"] in (0,1,2) and 0<=vals["sequence"]<2**32 and vals["source_time_us"]<=vals["receipt_time_us"]<=r["reply_time_us"]
                       and r["session_origin_us"]<=vals["last_good_source_time_us"]<=vals["source_time_us"] and vals["age_us"]==r["time_us"]-vals["last_good_source_time_us"]):
                    errors.append(f"row{index} {prefix} source/receipt/age")
            for key in ("observed_flow_m3_s","observed_hot_temperature_k","observed_cold_temperature_k","observed_wall_temperature_k","observed_separate_trip"):
                if not _finite(r[key]):
                    errors.append(f"row{index} observed nonfinite")
        if r["command_sequence"] is not None and (type(r["command_sequence"]) is not int or not 0<=r["command_sequence"]<2**32):
            errors.append(f"row{index} command sequence")
        if r["command_expires_us"] is not None and type(r["command_expires_us"]) is not int:
            errors.append(f"row{index} command expiry")
    if errors:
        return errors
    declared_events = {}
    for event in cfg.events:
        for at in (event.time_us,event.to_dict().get("end_us")):
            if at is not None:
                declared_events.setdefault(at,set()).add(event.event_id)
    for r in rows:
        if r["record_type"]=="event_boundary" and (set(r["event_ids"].split(";"))!=declared_events.get(r["time_us"],set()) or r["time_us"] not in declared_events):
            errors.append("event snapshot lacks declared exact-time event identity")
        if r["record_type"]=="command_expiry" and (not r["command_expired"] or r["time_us"]!=r["command_expires_us"]):
            errors.append("expiry snapshot is not lease equality")
    if wire.get("status")!="PASS" or not wire.get("ticks"):
        errors.append("retained wire audit incomplete/corrupt")
    ticks = [r for r in rows if isinstance(r,dict) and r.get("record_type")=="controller_tick"]
    wire_by = {(t["epoch"],t["time_us"]):t for t in wire.get("ticks",[])}
    row_keys = [(r.get("epoch"),r.get("time_us")) for r in ticks]
    if len(row_keys)!=len(set(row_keys)) or set(row_keys)!=set(wire_by):
        errors.append("missing/duplicate telemetry tick relative to retained wire")
    endpoint=rows[-1]["time_us"]
    last_expected = (math.ceil(endpoint/cfg.tick_us)-1)*cfg.tick_us if rows[-1]["record_type"] in ("terminal_boundary","solver_failure") else int(endpoint//cfg.tick_us)*cfg.tick_us
    if not ticks or [r["time_us"] for r in ticks]!=list(range(0,last_expected+1,cfg.tick_us)):
        errors.append("incomplete/out-of-order absolute tick schedule")
    for r in rows:
        if r["reply_time_us"] is None:
            if not (r["record_type"]=="event_boundary" and r["event_phase"]=="after" and r["time_us"]==r["session_origin_us"]):
                errors.append("missing retained reply on an executed snapshot")
            continue
        t = wire_by.get((r.get("epoch"),r.get("reply_time_us")))
        if not t or not t.get("reply") or not t.get("command"):
            errors.append("telemetry tick lacks retained Q/R")
            continue
        q,rp = t["command"]["payload"],t["reply"]["payload"]
        states={0:"DISARMED",1:"RUNNING",2:"TRIPPED"}
        reasons={0:"",1:"separate_trip",2:"wall_hot",3:"liquid_hot",4:"invalid_input",5:"range_input",6:"stale_input"}
        if (r.get("controller_state")!=states.get(rp[1]) or r.get("trip_reason")!=reasons.get(rp[2])
                or r.get("operation_result")!=rp[6] or r.get("session_origin_us")!=t["session_origin_us"]):
            errors.append("telemetry relabels retained C transition/reply clock")
        if r["record_type"]=="controller_tick" and (r["operation"]!=t["step"]["payload"][0] or r["heat_demand_command"]!=t["step"]["payload"][1]/1e6 or r["reply_time_us"]!=r["time_us"]):
            errors.append("telemetry relabels retained STEP operation/demand")
        if [r.get("requested_heat_command"),r.get("requested_pump_command"),r.get("requested_valve_command")] != [v/1e6 for v in q[1:4]] or [r.get("valid_mask"),r.get("stale_mask"),r.get("max_age_us")]!=rp[3:6]:
            errors.append("telemetry differs from retained Q/R")
        for channel,prefix in CHANNELS.items():
            observed = t["cache"].get(str(channel),{})
            if any(r.get(f"{prefix}_{key}")!=observed.get(key) for key in CHANNEL_FIELDS if key!="age_us"):
                errors.append("telemetry cache differs from retained O/S")
            key,scale={2:("observed_flow_m3_s",1e9),3:("observed_hot_temperature_k",1000),4:("observed_cold_temperature_k",1000),
                       5:("observed_wall_temperature_k",1000),6:("observed_separate_trip",1)}[channel]
            if r.get(key)!=observed.get("value_i",float("nan"))/scale:
                errors.append("telemetry observed conversion differs from raw cache")
    # Verify held/fallback commands independently, including between-tick rows.
    for r in rows:
        if not isinstance(r,dict) or not all(k in r for k in ("epoch","time_us","reply_time_us","command_sequence","command_expires_us","command_expired","lease_heat_command","lease_pump_command","lease_valve_command")):
            continue
        candidates=[d for d in wire.get("command_dispositions",[]) if d["epoch"]==r["epoch"] and d.get("independent_accepted")
                    and (d["absolute_receipt_us"]<r["time_us"] or d["absolute_receipt_us"]==r["time_us"]
                         and (d["session_origin_us"]+d["frame"]["time_us"]<r["time_us"] or r["reply_time_us"]==r["time_us"]))]
        latest=candidates[-1] if candidates else None
        expiry=latest["independent_expires_us"] if latest else None
        expired=latest is None or r["time_us"]>=expiry
        commands=[0.,1.,1.] if expired else [v/1e6 for v in latest["frame"]["payload"][1:4]]
        if ([r["lease_heat_command"],r["lease_pump_command"],r["lease_valve_command"]]!=commands
                or r["command_sequence"]!=(latest["frame"]["sequence"] if latest else None)
                or r["command_expires_us"]!=expiry or r["command_expired"]!=expired):
            errors.append("telemetry lease differs from independently accepted raw Q")
    return errors


def evaluate_campaign(cfg,rows,wire_evidence,*,run_failure=None):
    """Four statuses; a valid hazardous expectation still has FAILED containment."""
    errors = _trace_errors(cfg,rows,wire_evidence)
    required = APPLICABILITY[cfg.case_id]
    rules = {f"TH{i:02}":dict(status="NOT_APPLICABLE",evidence="case-specific rule") for i in range(1,13)}
    if errors:
        for i in required:
            rules[f"TH{i:02}"] = dict(status="UNASSESSABLE",evidence="; ".join(errors[:8]))
        return dict(rules=rules,expectation_pass=False,completion_status="UNASSESSABLE",containment_status="UNASSESSABLE",evidence_errors=errors)
    metrics = campaign_metrics(cfg,rows)
    ticks = [r for r in rows if r["record_type"]=="controller_tick"]
    completed = rows[0]["time_us"]==0 and rows[-1]["time_us"]==cfg.duration_us and not rows[-1]["terminal_boundary"] and run_failure is None
    terminal = rows[-1]["terminal_boundary"]
    trip = next((r for r in ticks if r["controller_state"]=="TRIPPED"),None)
    no_trip_cases = {"nominal_heat_step","restriction","reduced_rejection","reordered_flow","corrupt_flow","truncated_flow","dropped_command","delayed_command","dropped_ack","planned_restart"}
    def put(i,condition,evidence,assessable=True):
        if i in required:
            rules[f"TH{i:02}"] = dict(status="PASS" if assessable and condition else "FAIL" if assessable else "UNASSESSABLE",evidence=evidence)
    true_error,obs_error = metrics["tracking_true_max_error_m3_s"],metrics["tracking_observed_max_error_m3_s"]
    put(1,true_error is not None and obs_error is not None and max(true_error,obs_error)<=3e-6,
        dict(true_max_error_m3_s=true_error,observed_max_error_m3_s=obs_error,limit_m3_s=3e-6),assessable=completed and cfg.duration_us>=30_000_000)
    # Independently assemble augmented energy balance from exported raw states.
    p = cfg.model
    capacities = (p.wall_capacity_j_k,p.hot_mass_kg*p.specific_heat_j_kg_k,p.cold_mass_kg*p.specific_heat_j_kg_k)
    independent_residual = max(abs(sum(c*(r[k]-cfg.initial[k]) for c,k in zip(capacities,("wall_temperature_k","hot_temperature_k","cold_temperature_k")))-r["heat_in_j"]+r["heat_rejected_j"]) for r in rows)
    put(2,max(independent_residual,metrics["energy_residual_max_j"])<1e-3,dict(independent_residual_max_j=independent_residual,limit_j=1e-3))
    put(3,completed and not(cfg.case_id in no_trip_cases and trip),dict(completed_horizon=completed,no_unexpected_trip=not(cfg.case_id in no_trip_cases and trip)))
    if trip:
        after = [r for r in ticks if r["time_us"]>=trip["time_us"]]
        latched,active,reason,reset_seen,armed_again = True,True,trip["trip_reason"],False,False
        for r in after:
            command=(r["requested_heat_command"],r["requested_pump_command"],r["requested_valve_command"])
            if active and r["operation"]==2 and r["operation_result"]==1 and r["controller_state"]=="DISARMED":
                active,reset_seen=False,True
                latched = latched and command==(0.,0.,1.)
            elif active:
                latched = latched and r["controller_state"]=="TRIPPED" and r["trip_reason"]==reason and command==(0.,1.,1.)
            elif r["controller_state"]=="RUNNING":
                if reset_seen and r["operation"]==1 and r["operation_result"]==1:
                    reset_seen,armed_again=False,True
                latched = latched and armed_again
            elif r["controller_state"]=="TRIPPED":
                active,reason,armed_again=True,r["trip_reason"],False
                latched = latched and command==(0.,1.,1.)
            else:
                latched = latched and command==(0.,0.,1.)
        put(4,latched,dict(first_trip_time_us=trip["time_us"],cooling_requests_latched=latched))
    else:
        put(4,False,"no trip",assessable=False)
        if 4 not in required:
            rules["TH04"] = dict(status="NOT_APPLICABLE",evidence="no trip")
    expected = metrics["trip_expected_time_us"]
    injection = next((e.time_us for e in cfg.events if e.type=="observation_link"),None)
    put(5,bool(trip and trip["trip_reason"]=="stale_input" and trip["time_us"]==expected and injection is not None
               and 0<=trip["time_us"]-injection<=cfg.controller.stale_us+cfg.tick_us),
        dict(actual_trip_time_us=trip["time_us"] if trip else None,independent_expected_us=expected),assessable=expected is not None)
    if 6 in required:
        event = next((e for e in cfg.events if e.type=="observation_override"),None)
        concealed = [r for r in ticks if event and event.time_us<=r["time_us"]< (trip["time_us"] if trip else cfg.duration_us)]
        fresh = bool(concealed) and all(r["hot_age_us"]==0 and r["wall_age_us"]==0 and not r["stale_mask"]&28 for r in concealed)
        put(6,bool(trip and trip["trip_reason"]=="separate_trip" and trip["observed_separate_trip"]==1 and fresh),dict(primary_fresh_before_trip=fresh,separate_trip_reason=trip["trip_reason"] if trip else None),assessable=event is not None)
    peak = metrics["global_peak_upper_bound_k"]
    put(7,peak is not None and peak<359.15 and not terminal and completed,dict(continuous_global_peak_upper_bound_k=peak,limit_k=359.15,numerical_error="not included"),assessable=peak is not None)
    if 8 in required:
        okay,evidence = _link_evidence(cfg,rows,wire_evidence)
        put(8,okay,evidence)
    if 9 in required:
        new = [r for r in ticks if r["epoch"]==2]
        first = new[0] if new else None
        before_arm = [r for r in new if r["time_us"]<62_000_000]
        at_arm = next((r for r in new if r["time_us"]==62_000_000),None)
        okay = bool(first and first["time_us"]==60_000_000 and first["session_origin_us"]==60_000_000 and first["wire_time_us"]==0
                    and first["controller_state"]=="DISARMED" and (first["requested_heat_command"],first["requested_pump_command"],first["requested_valve_command"])==(0,0,1)
                    and all(r["controller_state"]=="DISARMED" for r in before_arm) and at_arm and at_arm["controller_state"]=="RUNNING" and at_arm["operation"]==1
                    and all(r[f"{prefix}_source_time_us"]>=60_000_000 for r in new for prefix in ("flow","hot","cold","wall","separate")))
        put(9,okay,dict(new_epoch_first_time_us=first["time_us"] if first else None,rearm_time_us=at_arm["time_us"] if at_arm else None))
    if 10 in required:
        faulted = [r for r in rows if r["time_us"]>=60_000_000 and r["event_phase"]!="before"]
        okay = bool(trip and terminal in ("wall_upper","hot_upper","cold_upper") and trip["time_us"]<rows[-1]["time_us"]<=585_300_000
                    and faulted and all(r["fault_heat_command"]==1 and r["effective_sink_conductance_w_k"]==0 for r in faulted)
                    and all(r["requested_heat_command"]==0 and r["requested_pump_command"]==1 for r in ticks if r["time_us"]>=trip["time_us"]))
        put(10,okay,dict(terminal_boundary=terminal,terminal_time_us=rows[-1]["time_us"],independent_latest_boundary_us=585_300_000,containment="FAILED"))
    if 11 in required:
        pre,final = metrics["prefault_temperatures_k"],metrics["final30_mean_temperatures_k"]
        rises = {k:final[k]-pre[k] for k in pre} if pre and final else None
        put(11,bool(rises and min(rises.values())>=5 and true_error is not None and true_error<=3e-6 and not trip and not terminal),
            dict(temperature_rises_k=rises,flow_max_error_m3_s=true_error),assessable=completed and rises is not None)
    if 12 in required:
        before = next((r for r in rows if r["time_us"]==60_000_000 and r["event_phase"]=="before"),None)
        after = next((r for r in rows if r["time_us"]==60_000_000 and r["event_phase"]=="after"),None)
        later = [r for r in ticks if r["time_us"]>60_000_000]
        ratio = after["flow_m3_s"]/before["flow_m3_s"] if before and after and before["flow_m3_s"] else None
        expected_ratio = math.sqrt((4e11+6e11+1e11/.65**2)/(4e11+2.4e12+1e11/.65**2))
        okay = bool(before and after and ratio is not None and abs(ratio-expected_ratio)<1e-10
                    and any(r["requested_pump_command"]>before["requested_pump_command"] and r["pump_speed"]>before["pump_speed"] for r in later)
                    and cfg.controller.ff_ppm==527498)
        put(12,okay,dict(actual_immediate_flow_ratio=ratio,independent_ratio=expected_ratio,nominal_feedforward_ppm=cfg.controller.ff_ppm),assessable=before is not None and after is not None)
    compatible_hazard = cfg.case_id=="stuck_heat_lost_sink" and terminal in ("wall_upper","hot_upper","cold_upper") and run_failure is None
    expectation = (completed or compatible_hazard) and all(rules[f"TH{i:02}"]["status"]=="PASS" for i in required)
    return dict(rules=rules,expectation_pass=bool(expectation),completion_status="PASS" if completed else "FAIL",
                containment_status="FAILED" if terminal else "CONTAINED" if completed and peak is not None and peak<359.15 else "UNASSESSABLE",
                evidence_errors=[])


def _link_evidence(cfg,rows,wire):
    case = cfg.case_id
    ticks = [r for r in rows if r["record_type"]=="controller_tick"]
    dispositions = wire["observation_dispositions"]
    cmds = wire["command_dispositions"]
    fault = next((e.to_dict() for e in cfg.events if e.type in ("observation_link","command_link")),None)
    if not fault:
        return False,"missing declared link experiment"
    at,end = fault["time_us"],fault.get("end_us",fault["time_us"]+cfg.tick_us)
    if case=="delayed_flow":
        delayed = [d for d in dispositions if d["frame"]["payload"][0]==2 and at<=d["frame"]["time_us"]<end]
        okay = bool(delayed) and all(d["receipt_time_us"]-d["frame"]["time_us"]>=fault["delay_us"] for d in delayed)
        return okay,dict(delayed_record_count=len(delayed),original_source_times_retained=okay)
    if case=="reordered_flow":
        old = [d for d in dispositions if d["frame"]["payload"][0]==2 and d["frame"]["time_us"]==at]
        okay = bool(old) and all(not d["accepted"] and d["cached_after"]["source_time_us"]==at+cfg.tick_us for d in old)
        return okay,dict(old_record_count=len(old),older_arrival_rejected=okay)
    if case in ("corrupt_flow","truncated_flow"):
        injection = next((r for r in ticks if r["time_us"]==at),None)
        recovery = next((r for r in ticks if r["time_us"]==at+cfg.tick_us),None)
        okay = bool(wire["invalid_input_records"] and wire["stderr_rejection_count"] and injection and recovery
                    and injection["flow_source_time_us"]==at-cfg.tick_us and recovery["flow_source_time_us"]==at+cfg.tick_us
                    and all(r["controller_state"]=="RUNNING" for r in ticks))
        return okay,dict(invalid_retained_records=len(wire["invalid_input_records"]),c_stderr_rejections=wire["stderr_rejection_count"],next_tick_recovered=okay)
    if case in ("dropped_command","delayed_command"):
        expected_expiry = at-cfg.tick_us+cfg.controller.lease_us
        expired = [r for r in rows if expected_expiry<=r["time_us"]<end and r["event_phase"]!="before"]
        okay = bool(expired) and all(r["command_expired"] and (r["lease_heat_command"],r["lease_pump_command"],r["lease_valve_command"])==(0,1,1) for r in expired)
        if case=="delayed_command":
            arrivals = [d for d in cmds if at<=d["frame"]["time_us"]<end]
            okay = okay and bool(arrivals) and all(not d["accepted"] and d["absolute_receipt_us"]>=d["frame"]["time_us"]+cfg.controller.lease_us for d in arrivals)
        return okay,dict(independent_expiry_us=expected_expiry,expiry_samples=len(expired),lease_fallback_verified=okay)
    if case=="dropped_ack":
        dropped = [e for e in wire["events"] if e["event"]=="ack_dropped"]
        interval = [r for r in ticks if at<=r["time_us"]<end]
        actual_acks = [a for a in wire["ack_records"] if at<=a["time_us"]<end]
        okay = bool(dropped and interval) and not actual_acks and all(not r["command_expired"] and r["command_expires_us"]==r["time_us"]+cfg.controller.lease_us for r in interval)
        return okay,dict(dropped_ack_count=len(dropped),command_acceptance_continued=okay)
    return False,"unknown link case"
