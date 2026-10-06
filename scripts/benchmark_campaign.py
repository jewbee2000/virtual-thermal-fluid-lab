"""Isolated real-C process-family measurement; includes monitoring overhead."""
import argparse
import ctypes
from ctypes import wintypes
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time


def windows_processes():
    kernel = ctypes.WinDLL("kernel32",use_last_error=True)
    class Entry(ctypes.Structure):
        _fields_ = [("size",wintypes.DWORD),("usage",wintypes.DWORD),("pid",wintypes.DWORD),("heap",ctypes.c_size_t),
                    ("module",wintypes.DWORD),("threads",wintypes.DWORD),("parent",wintypes.DWORD),("priority",wintypes.LONG),
                    ("flags",wintypes.DWORD),("exe",wintypes.WCHAR*260)]
    kernel.CreateToolhelp32Snapshot.argtypes=(wintypes.DWORD,wintypes.DWORD)
    kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    kernel.Process32FirstW.argtypes=(wintypes.HANDLE,ctypes.POINTER(Entry))
    kernel.Process32NextW.argtypes=(wintypes.HANDLE,ctypes.POINTER(Entry))
    kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
    handle=kernel.CreateToolhelp32Snapshot(2,0)
    if handle in (None,ctypes.c_void_p(-1).value):
        raise OSError("process snapshot unavailable")
    entry=Entry();entry.size=ctypes.sizeof(entry);result={}
    try:
        more=kernel.Process32FirstW(handle,ctypes.byref(entry))
        while more:
            result[int(entry.pid)]=int(entry.parent)
            more=kernel.Process32NextW(handle,ctypes.byref(entry))
    finally:
        kernel.CloseHandle(handle)
    return result


def windows_peak(pid):
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    psapi=ctypes.WinDLL("psapi",use_last_error=True)
    class Memory(ctypes.Structure):
        _fields_=[("cb",wintypes.DWORD),("faults",wintypes.DWORD),*( (k,ctypes.c_size_t) for k in
            ("peak_ws","ws","peak_page","page","peak_nonpage","nonpage","pagefile","peak_pagefile"))]
    kernel.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD);kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=(wintypes.HANDLE,)
    psapi.GetProcessMemoryInfo.argtypes=(wintypes.HANDLE,ctypes.POINTER(Memory),wintypes.DWORD)
    handle=kernel.OpenProcess(0x410,False,pid)
    if not handle:
        return None
    value=Memory();value.cb=ctypes.sizeof(value)
    try:
        return int(value.peak_ws) if psapi.GetProcessMemoryInfo(handle,ctypes.byref(value),value.cb) else None
    finally:
        kernel.CloseHandle(handle)


def process_peaks(root_pid,known):
    if os.name=="nt":
        parents=windows_processes()
    else:
        parents={}
        for p in Path("/proc").glob("[0-9]*/stat"):
            try:
                rest=p.read_text().rsplit(")",1)[1].split()
                parents[int(p.parent.name)]=int(rest[1])
            except (OSError,ValueError,IndexError):
                continue
    family={root_pid}|set(known)
    changed=True
    while changed:
        old=len(family);family.update(pid for pid,parent in parents.items() if parent in family);changed=len(family)!=old
    for pid in family:
        if os.name=="nt":
            peak=windows_peak(pid)
        else:
            try:
                lines=(Path("/proc")/str(pid)/"status").read_text().splitlines()
                peak=next(int(line.split()[1])*1024 for line in lines if line.startswith("VmHWM:"))
            except (OSError,ValueError,StopIteration):
                peak=None
        if peak is not None:
            known[pid]=max(known.get(pid,0),peak)
    return known


def worker(args):
    # Scientific imports live only in the measured fresh process.
    from fluidlab.campaign import case_config,run_campaign,write_campaign
    cfg=case_config("nominal_heat_step")
    args.out.mkdir(parents=True,exist_ok=False)
    rows,summary=run_campaign(cfg,args.exe,args.out/"wire")
    write_campaign(args.out,cfg,rows,summary,args.exe)
    return 0 if summary["evaluation"]["expectation_pass"] else 1


def retained_process_pids(artifact):
    """Read actual spawn diagnostics for every thermal and tank wire session."""
    paths={p.parent for p in artifact.rglob("*") if p.is_file()
           and p.name in ("stdin.bin","stdout.bin","stderr.bin","events.jsonl")
           and "wire" in p.relative_to(artifact).parts[:-1]}
    pids,issues=[],[]
    if not paths:
        issues.append("no retained wire sessions")
    for path in sorted(paths):
        try:
            events=[]
            raw=(path/"events.jsonl").read_text(encoding="utf-8")
            if not raw.endswith("\n"):
                raise ValueError("unfinished event capture")
            for line in raw.splitlines():
                event=json.loads(line,parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
                if (not isinstance(event,dict) or not isinstance(event.get("event"),str)
                        or isinstance(event.get("host_monotonic_s"),bool)
                        or not isinstance(event.get("host_monotonic_s"),(int,float))
                        or not math.isfinite(event["host_monotonic_s"])):
                    raise ValueError("malformed event identity")
                events.append(event)
            starts=[event for event in events if event["event"]=="process_started"]
            sessions=[event for event in events if event["event"]=="session"]
            if len(starts)!=1 or len(sessions)!=1:
                raise ValueError("missing/duplicate actual process startup or session")
            start,session=starts[0],sessions[0]
            if (type(start.get("process_pid")) is not int or start["process_pid"]<=0
                    or type(start.get("epoch")) is not int or not 0<start["epoch"]<=2**32-1
                    or type(start.get("session_origin_us")) is not int or not 0<=start["session_origin_us"]<=2**64-1
                    or not isinstance(start.get("command"),list) or not start["command"]
                    or not all(isinstance(value,str) and value for value in start["command"])
                    or type(session.get("epoch")) is not int or type(session.get("session_origin_us")) is not int
                    or start["epoch"]!=session.get("epoch")
                    or start["session_origin_us"]!=session.get("session_origin_us")):
                raise ValueError("invalid actual process PID/session diagnostic")
            pids.append(start["process_pid"])
        except (OSError,UnicodeError,ValueError,TypeError,KeyError) as exc:
            issues.append(f"{path.relative_to(artifact).as_posix()}: {exc}")
    return pids,issues


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe",type=Path,required=True)
    parser.add_argument("--out",type=Path,default=Path("artifacts/M5-performance"))
    parser.add_argument("--suite",action="store_true",help="measure all differing horizons separately from selected demo gate")
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.worker:
        return worker(args)
    args.out.mkdir(parents=True,exist_ok=False)
    artifact=args.out/"run"
    command=[sys.executable,str(Path(__file__).resolve()),"--worker","--exe",str(args.exe.resolve()),"--out",str(artifact.resolve())]
    if args.suite:
        command=[sys.executable,str(Path(__file__).with_name("run_campaign.py")),"--exe",str(args.exe.resolve()),"--out",str(artifact.resolve()),"--repeat"]
    peaks,errors={},[]
    started=time.perf_counter()
    with (args.out/"stdout.txt").open("wb") as stdout,(args.out/"stderr.txt").open("wb") as stderr:
        child=subprocess.Popen(command,stdout=stdout,stderr=stderr)
        while child.poll() is None:
            try:
                process_peaks(child.pid,peaks)
            except OSError as exc:
                errors.append(str(exc))
            time.sleep(.005)
        returncode=child.wait()
    elapsed=time.perf_counter()-started
    memory=sum(peaks.values()) if peaks else None
    summary=json.loads((artifact/("campaign.json" if args.suite else "summary.json")).read_text()) if (artifact/("campaign.json" if args.suite else "summary.json")).is_file() else None
    complete=bool(summary and (summary.get("full_release_campaign") if args.suite else summary.get("completed_horizon")))
    retained_pids,pid_issues=retained_process_pids(artifact)
    required_pids=[child.pid,*retained_pids]
    required_observed=not pid_issues and all(pid in peaks for pid in required_pids) and len(required_pids)>1
    result=dict(schema_version=1,scope="entire differing-horizon suite" if args.suite else "complete frozen nominal240s C SIL demo",
                command=command,returncode=returncode,complete=complete,wall_elapsed_s=elapsed,
                simulation_to_wall_ratio=240/elapsed if not args.suite else None,
                observed_process_family_peak_sum_bytes=memory,individual_os_peak_working_sets_bytes=peaks,
                required_process_pids=required_pids,required_process_pids_observed=required_observed,
                retained_pid_capture_issues=pid_issues,
                required_pid_scope="worker and every retained actual C startup in all recursive thermal/tank wire sessions",
                memory_method="sum of individual OS lifetime peak working sets/HWM of observed descendants;5ms discovery",
                memory_scope_limitations="sum is conservative for recorded peaks of observed processes; discovery may miss short-lived descendants/final growth; no strict unseen-family upper bound",
                monitor_errors=errors,monitoring_overhead="included in wall time; monitor process itself excluded from selected family",
                platform=platform.platform(),machine=platform.machine(),processor=platform.processor(),
                compiler_build_metadata=summary.get("execution",{}).get("compiler_build_metadata") if summary else None,
                protocol_latency_s=summary.get("metrics",{}).get("protocol_latency_s") if summary else None,
                status="UNASSESSABLE" if not required_observed or memory is None or errors else "RECORDED" if args.suite and complete and returncode==0 else "PASS" if not args.suite and complete and returncode==0 and elapsed<60 and memory<512*1024**2 else "FAIL",
                thresholds=None if args.suite else dict(wall_s=60,memory_bytes=512*1024**2),
                qualification="observed laptop software performance; no hard-real-time or WCET claim")
    (args.out/"performance.json").write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps(result,indent=2))
    return 0 if result["status"] in ("PASS","RECORDED") else 1


if __name__=="__main__":
    raise SystemExit(main())
