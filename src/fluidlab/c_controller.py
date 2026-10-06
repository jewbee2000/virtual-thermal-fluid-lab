"""Actual subprocess C controller. Host wall deadlines never advance virtual time."""
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
import json
import os
import queue
import subprocess
import threading
import time
import uuid
from .protocol import Configuration, Frame, FrameAssembler, PPM, UINT32_MAX, UINT64_MAX, decode, sequence_newer


class ControllerProcessFailure(RuntimeError):
    def __init__(self, message, controller):
        super().__init__(message)
        self.trace_dir = controller.trace_dir
        self.last_reply = controller.last_reply
        self.returncode = controller.process.poll()


@dataclass(frozen=True)
class Command:
    heat_command: float
    pump_command: float
    valve_command: float
    expired: bool
    sequence: int | None
    expires_us: int | None


class CommandLease:
    """Experimental Q acceptance is distinct from reliable R and optional ACK."""
    def __init__(self, configuration, epoch, *, session_origin_us=0):
        self.configuration, self.epoch, self.origin_us = configuration, epoch, session_origin_us
        self.accepted = None
        self.expires_us = None

    def accept(self, frame, now_us):
        if (frame.type != "Q" or frame.clock != "V" or frame.epoch != self.epoch
                or self.origin_us + frame.time_us > now_us
                or frame.time_us > UINT64_MAX-frame.payload[0]):
            return False
        expiry = self.origin_us + frame.time_us + frame.payload[0]
        if expiry > UINT64_MAX or expiry <= now_us:
            return False
        if self.accepted is not None and not sequence_newer(frame.sequence, self.accepted.sequence):
            return False
        self.accepted, self.expires_us = frame, expiry
        return True

    def current(self, now_us):
        if self.accepted is not None and now_us < self.expires_us:
            p = self.accepted.payload
            return Command(p[1]/PPM, p[2]/PPM, p[3]/PPM, False, self.accepted.sequence, self.expires_us)
        p = self.configuration
        return Command(0., 1. if p.profile == 2 else 0., 1. if p.profile == 2 else p.normal_valve_ppm/PPM,
                       True, self.accepted.sequence if self.accepted else None, self.expires_us)


@dataclass(frozen=True)
class ControllerReply:
    status: Frame
    raw_command: Frame
    applied: Command
    ack: Frame | None


class CController:
    """Fixed protocol host process with bounded reader queue and preserved traces.

    Observations are O Frames or (channel, sequence, absolute_sample_us, quality,
    integer_value) tuples. No plant reference/fault labels cross this interface.
    Session wire time starts at0; trace records retain the absolute origin.
    """
    def __init__(self, executable, configuration, *, epoch=1, session_origin_us=0,
                 trace_dir=None, startup_timeout_s=5., step_timeout_s=1., assembly_timeout_s=.5):
        if not isinstance(configuration, Configuration):
            raise ValueError("explicit Configuration required")
        Frame("H", epoch, 0, "V", 0, (configuration.profile,))
        if type(session_origin_us) is not int or not 0 <= session_origin_us <= UINT64_MAX:
            raise ValueError("session origin must be nonnegative uint64 microseconds")
        for label, value in (("startup", startup_timeout_s), ("step", step_timeout_s), ("assembly", assembly_timeout_s)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 60:
                raise ValueError(f"{label} deadline must be positive and <=60 wall seconds")
        self.configuration, self.epoch, self.origin_us = configuration, epoch, session_origin_us
        self.startup_timeout_s, self.step_timeout_s = startup_timeout_s, step_timeout_s
        self.trace_dir = Path(trace_dir) if trace_dir else Path("artifacts/host-traces") / uuid.uuid4().hex
        self.trace_dir.mkdir(parents=True, exist_ok=False)
        self._capture = {key: (self.trace_dir / f"{key}.bin").open("wb") for key in ("stdin", "stdout", "stderr")}
        self._events = (self.trace_dir / "events.jsonl").open("w", encoding="utf-8", newline="\n")
        self._lock = threading.Lock()
        self._queue = queue.Queue(maxsize=64)
        self._writes = queue.Queue(maxsize=64)
        self._pending = deque()
        self._assembler = FrameAssembler(assembly_timeout_s)
        self._stop = threading.Event()
        self._reader_overflow = threading.Event()
        self.closed = False
        self.failed = False
        self.last_reply = None
        self.sequence = 0
        self.ack_sequence = 0
        self.lease = CommandLease(configuration, epoch, session_origin_us=session_origin_us)
        self._log("session", epoch=epoch, session_origin_us=session_origin_us, configuration=asdict(configuration),
                  configuration_sha256=configuration.sha256, clock="V", source="host C subprocess")
        command = [str(executable)] if isinstance(executable, (str, Path)) else list(executable)
        try:
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        except OSError:
            self._close_captures()
            raise
        self._log("process_started", process_pid=self.process.pid, parent_process_pid=os.getpid(), command=command,
                  epoch=epoch, session_origin_us=session_origin_us)
        self._threads = [threading.Thread(target=self._read, args=(key,), daemon=True) for key in ("stdout", "stderr")]
        self._threads.append(threading.Thread(target=self._writer, daemon=True))
        for thread in self._threads:
            thread.start()
        try:
            deadline = time.monotonic()+self.startup_timeout_s
            boot = self._next_frame(deadline)
            if boot != Frame("B", 0, 0, "V", 0, (100, 0)):
                self._fail("unexpected startup announcement")
            self._write(Frame("H", epoch, 0, "V", 0, (configuration.profile,)), deadline)
            self._write(Frame("C", epoch, 0, "V", 0, configuration.payload), deadline)
        except BaseException:
            self.close()
            raise

    def _log(self, event, **fields):
        with self._lock:
            self._events.write(json.dumps(dict(event=event, host_monotonic_s=time.monotonic(), **fields), allow_nan=False)+"\n")
            self._events.flush()

    def _read(self, key):
        stream = getattr(self.process, key)
        try:
            while not self._stop.is_set():
                chunk = os.read(stream.fileno(), 256)
                if not chunk:
                    if key == "stdout":
                        self._put(("eof", b""))
                    return
                with self._lock:
                    self._capture[key].write(chunk)
                    self._capture[key].flush()
                if key == "stdout":
                    self._put(("bytes", chunk))
        except (OSError, ValueError) as exc:
            if key == "stdout" and not self._stop.is_set():
                self._put(("reader_error", str(exc)))

    def _put(self, item):
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            self._reader_overflow.set()

    def _next_frame(self, deadline):
        while True:
            if self._reader_overflow.is_set():
                self._fail("bounded stdout reader queue overflow")
            if self._pending:
                return self._pending.popleft()
            now = time.monotonic()
            if self._assembler.expire(now):
                self._log("rejected_output", reason="frame_assembly_timeout")
            remaining = deadline-now
            if remaining <= 0:
                self._fail("controller reply wall timeout")
            if self._assembler.started_at is not None and not self._assembler.discard:
                remaining = min(remaining, max(.001, self._assembler.started_at+self._assembler.timeout_s-now))
            try:
                event, payload = self._queue.get(timeout=remaining)
            except queue.Empty:
                continue
            if event == "eof":
                self._fail("unfinished output frame at EOF" if self._assembler.eof() else "controller EOF")
            if event == "reader_error":
                self._fail("stdout reader error: "+payload)
            frames, errors = self._assembler.feed(payload, time.monotonic())
            for error in errors:
                self._log("rejected_output", reason=error)
            for frame in frames:
                self._log("received", frame=asdict(frame), absolute_time_us=self.origin_us+frame.time_us)
            self._pending.extend(frames)

    def _writer(self):
        while not self._stop.is_set():
            try:
                raw, done, errors = self._writes.get(timeout=.1)
            except queue.Empty:
                continue
            try:
                written = self.process.stdin.write(raw)
                self.process.stdin.flush()
                if written != len(raw):
                    raise OSError("partial stdin write")
                with self._lock:
                    self._capture["stdin"].write(raw)
                    self._capture["stdin"].flush()
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
            finally:
                done.set()

    def _write(self, frame, deadline=None):
        deadline = time.monotonic()+self.step_timeout_s if deadline is None else deadline
        raw = frame.encode()
        self._log("send_attempt", frame=asdict(frame), absolute_time_us=self.origin_us+frame.time_us)
        self._write_bytes(raw, deadline)
        self._log("sent", frame=asdict(frame), absolute_time_us=self.origin_us+frame.time_us)

    def _write_bytes(self, raw, deadline):
        # Both encoded and deliberately malformed O records share the whole
        # transaction deadline and the existing bounded pipe writer.
        done, errors = threading.Event(), []
        try:
            self._writes.put_nowait((raw, done, errors))
        except queue.Full:
            self._fail("bounded stdin writer queue overflow")
        remaining = deadline-time.monotonic()
        if remaining <= 0 or not done.wait(timeout=remaining):
            self._fail("controller stdin wall timeout")
        if errors:
            self._fail("controller stdin failed: "+errors[0])

    def _fail(self, message):
        self.failed = True
        self._log("process_failure", message=message, last_reply=asdict(self.last_reply) if self.last_reply else None)
        self.close()
        raise ControllerProcessFailure(message, self)

    def deliver_command(self, frame, now_us):
        accepted = self.lease.accept(frame, now_us)
        self._log("command_disposition", accepted=accepted, frame=asdict(frame), absolute_receipt_us=now_us)
        return accepted

    def step(self, now_us, observations=(), *, operation=0, heat_demand_ppm=0,
             command_filter=None, acknowledge=True, raw_observations=()):
        if self.closed:
            raise RuntimeError("controller already closed; no fallback is available")
        deadline = time.monotonic()+self.step_timeout_s
        if type(now_us) is not int or not 0 <= now_us <= UINT64_MAX:
            raise ValueError("STEP absolute time must be uint64 integer microseconds")
        expected = self.origin_us + self.sequence*self.configuration.tick_us
        if now_us != expected:
            raise ValueError(f"STEP requires absolute time {expected}us")
        wire_now = now_us-self.origin_us
        frames = []
        for observation in observations:
            if isinstance(observation, Frame):
                frame = observation
                if frame.type != "O":
                    raise ValueError("observation must be an O record")
            else:
                channel, sequence, sample_us, quality, value = observation
                if sample_us < self.origin_us:
                    raise ValueError("pre-session samples must be reacquired, never refreshed")
                frame = Frame("O", self.epoch, sequence, "V", sample_us-self.origin_us, (channel, quality, value))
            frames.append(frame)
        raw_observations = tuple(raw_observations)
        if len(frames)+len(raw_observations) > 32:
            raise ValueError("at most32 staged observations per STEP")
        for raw in raw_observations:
            if (not isinstance(raw, bytes) or not raw.startswith(b"F|1|O|")
                    or not 1 <= len(raw) <= 257):
                raise ValueError("raw observation injection requires <=257 O-prefix bytes")
        step = Frame("S", self.epoch, self.sequence & UINT32_MAX, "V", wire_now, (operation, heat_demand_ppm))
        for frame in frames:
            self._write(frame, deadline)
        for raw in raw_observations:
            self._log("raw_observation_attempt", raw_hex=raw.hex(), absolute_time_us=now_us)
            self._write_bytes(raw, deadline)
            self._log("raw_observation_sent", raw_hex=raw.hex(), absolute_time_us=now_us)
        self._write(step, deadline)
        raw_command, status = None, None
        while status is None:
            frame = self._next_frame(deadline)
            if frame.epoch != self.epoch or frame.clock != "V" or frame.time_us != wire_now:
                self._fail("unexpected reply session/time")
            if frame.type == "Q" and raw_command is None:
                raw_command = frame
            elif frame.type == "R" and raw_command is not None and frame.sequence == step.sequence:
                if frame.payload[0] != raw_command.sequence or frame.payload[1:3] != raw_command.payload[4:6]:
                    self._fail("command/reliable status mismatch")
                status = frame
            else:
                self._fail("unexpected reliable reply ordering/type")
        experimental = command_filter(raw_command) if command_filter else raw_command
        ack = None
        if experimental is not None:
            try:
                candidate = decode(experimental) if isinstance(experimental, bytes) else experimental
                if not isinstance(candidate, Frame):
                    raise ValueError("experimental command must be a Frame or encoded bytes")
                accepted = self.deliver_command(candidate, now_us)
                ack = Frame("A", self.epoch, self.ack_sequence, "V", wire_now, (candidate.sequence, 0 if accepted else 1))
                self.ack_sequence = (self.ack_sequence+1) & UINT32_MAX
                if acknowledge:
                    self._write(ack, deadline)
                else:
                    self._log("ack_dropped", frame=asdict(ack))
            except ValueError as exc:
                self._log("rejected_command", reason=str(exc))
        else:
            self._log("command_dropped", command_seq=raw_command.sequence)
        self.sequence += 1
        self.last_reply = ControllerReply(status, raw_command, self.lease.current(now_us), ack)
        self._log("accepted_step", absolute_time_us=now_us, reply=asdict(self.last_reply))
        return self.last_reply

    def _close_captures(self):
        for stream in self._capture.values():
            stream.close()
        self._events.close()

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.failed:
            self.process.terminate()
        else:
            try:
                self.process.stdin.close()
            except OSError:
                pass
        try:
            self.process.wait(timeout=.5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=.5)
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=.5)
        for key in ("stdin", "stdout", "stderr"):
            try:
                getattr(self.process, key).close()
            except OSError:
                pass
        self._log("process_reaped", returncode=self.process.returncode)
        self._close_captures()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
