"""Independent wire literals, supervisor decisions and real child-failure probes."""
from dataclasses import replace
from pathlib import Path
import binascii
import os
import subprocess
import sys
import tempfile
import time
import unittest
from fluidlab.protocol import (Configuration, Frame, FrameAssembler, decode, sequence_newer,
                               quantize, UINT32_MAX, UINT64_MAX)
from fluidlab.c_controller import CController, CommandLease, ControllerProcessFailure
from fluidlab.contracts import ControllerConfig

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOST = ROOT / "artifacts/host-build/Release/fluid_controller_host.exe"
if os.name != "nt":
    DEFAULT_HOST = ROOT / "artifacts/host-build/fluid_controller_host"
HOST = Path(os.environ.get("FL_CONTROLLER_HOST", DEFAULT_HOST))
GOLDENS = (b"F|1|H|1|0|V|0|1*7A87\n", b"F|1|O|1|0|V|0|1|1|250000*6EF2\n",
           b"F|1|O|1|0|V|0|6|1|0*0FE2\n", b"F|1|S|1|0|V|0|1|0*AFD1\n",
           b"F|1|A|1|0|V|0|0|0*0493\n")


def raw(body):
    """Independent standard-library CRC for malformed canonical-field probes."""
    body = body.encode("ascii")
    return body + f"*{binascii.crc_hqx(body,0):04X}\n".encode("ascii")


class ProtocolTests(unittest.TestCase):
    def test_device_extension_literals_and_source_clock_separation(self):
        literals=(b"F|1|U|1|4294967295|V|900000000000|1|0*EE1A\n",
                  b"F|1|X|1|3|D|1000000|1|1|0|900000000000|999999|1*3752\n",
                  b"F|1|N|1|3|D|1000000|1|3|2|4|5|1|0*DC53\n")
        for literal in literals:
            self.assertEqual(decode(literal).encode(),literal)
            for split in range(len(literal)+1):
                assembly=FrameAssembler()
                a,ea=assembly.feed(literal[:split],0.)
                b,eb=assembly.feed(literal[split:],.1)
                self.assertEqual(a+b,[decode(literal)])
                self.assertFalse(ea+eb)
        x=decode(literals[1])
        self.assertEqual((x.clock,x.time_us,x.payload[2:5]),("D",1_000_000,(0,900_000_000_000,999_999)))
        self.assertEqual(decode(Frame("X",1,0,"D",0,(1,1,1,UINT64_MAX,UINT64_MAX,2)).encode()).payload[3],UINT64_MAX)

    def test_device_extension_type_and_enum_bounds(self):
        bad=("F|1|U|1|0|V|0|3|0","F|1|U|1|0|V|0|1|1000001",
             "F|1|X|1|0|V|0|1|1|0|0|0|1","F|1|X|1|0|D|0|0|1|0|0|0|1",
             "F|1|X|1|0|D|0|7|1|0|0|0|1","F|1|X|1|0|D|0|1|0|0|0|0|1",
             "F|1|X|1|0|D|0|1|4|0|0|0|1","F|1|X|1|0|D|0|1|1|2|0|0|1",
             "F|1|X|1|0|D|0|1|1|0|0|0|3","F|1|X|1|0|D|0|1|1|0|18446744073709551616|0|1",
             "F|1|N|1|0|V|0|1|0|0|0|0|0|1","F|1|N|1|0|D|0|0|0|0|0|0|0|1",
             "F|1|N|1|0|D|0|3|0|0|0|0|0|1","F|1|N|1|0|D|0|1|0|0|0|0|2|1",
             "F|1|N|1|0|D|0|1|0|0|0|0|0|2","F|1|N|1|0|D|0|1|4294967296|0|0|0|0|1",
             "F|1|Q|1|0|D|0|1|0|0|0|2|8","F|1|R|1|0|D|0|0|2|8|0|0|0|0")
        for body in bad:
            with self.subTest(body=body),self.assertRaises(ValueError):
                decode(raw(body))
        self.assertEqual(Frame("Q",1,0,"D",0,(1,0,0,0,2,7)).payload[-1],7)
        self.assertEqual(Frame("R",1,0,"D",0,(0,2,7,0,0,0,0)).payload[2],7)

    def test_literal_crc_and_all_split_points(self):
        self.assertEqual(binascii.crc_hqx(b"123456789", 0), 0x31C3)
        for literal in GOLDENS:
            self.assertEqual(decode(literal).encode(), literal)
            for split in range(len(literal)+1):
                assembler = FrameAssembler()
                a, ea = assembler.feed(literal[:split], 0.)
                b, eb = assembler.feed(literal[split:], .1)
                self.assertEqual(a+b, [decode(literal)])
                self.assertFalse(ea+eb)
            assembler = FrameAssembler()
            frames = []
            for byte in literal:
                result, errors = assembler.feed(bytes([byte]), .1)
                frames += result
                self.assertFalse(errors)
            self.assertEqual(frames, [decode(literal)])

    def test_strict_fields_crc_overflows_and_signed_placement(self):
        bodies = ("F|1|H|01|0|V|0|1", "F|1|H|1|+0|V|0|1", "F|1|H|1|0|V|-0|1",
                  "F|1|H|1|0|V|18446744073709551616|1", "F|1|H|4294967296|0|V|0|1",
                  "F|1|H|1|0|V|0|1|0", "F|1|O|1|0|V|0|1|1|-2147483649",
                  "F|1|O|1|0|V|0|1|3|0", "F|1|O|1|0|V|0|6|1|2",
                  "F|1|O|1|0|V|0|1|2|250000", "F|1|Z|1|0|V|0|1")
        for body in bodies:
            with self.subTest(body=body), self.assertRaises(ValueError):
                decode(raw(body))
        for invalid in (GOLDENS[0].replace(b"\n",b"\r\n"), GOLDENS[0].replace(b"7A87",b"7a87"),
                        GOLDENS[0].replace(b"|1*",b"|2*"), b"\xff\n"):
            with self.assertRaises(ValueError):
                decode(invalid)
        self.assertEqual(decode(raw("F|1|O|1|0|V|0|1|1|-2147483648")).payload[2], -2**31)

    def test_assembly_limits_timeout_and_recovery(self):
        assembler = FrameAssembler()
        _, errors = assembler.feed(b"x"*255+b"\n", 0.)
        self.assertEqual(len(errors), 1)  #256-byte framing limit, invalid semantic body
        _, errors = assembler.feed(b"x"*256, 0.)
        self.assertEqual(errors, ["oversize_frame"])
        frames, errors = assembler.feed(b"x\n"+GOLDENS[0], .1)
        self.assertEqual(frames, [decode(GOLDENS[0])])
        self.assertFalse(errors)
        assembler.feed(b"F|1", 1.)
        self.assertFalse(assembler.expire(1.499))
        self.assertTrue(assembler.expire(1.5))
        self.assertTrue(assembler.eof())
        frames, _ = assembler.feed(GOLDENS[0]+GOLDENS[0], 1.6)
        self.assertEqual(frames, [decode(GOLDENS[0])])

    def test_config_overrides_relationships_and_units(self):
        cfg = Configuration.tank(ControllerConfig(kp_per_m=4., ki_per_m_s=.03, bias=.4,
                                                  drain_command=.6, stale_after_s=.2, sensor_max_m=.9),
                                 target_level_m=.45, tick_us=50_000)
        self.assertEqual((cfg.kp_scaled, cfg.ki_scaled, cfg.ff_ppm, cfg.normal_valve_ppm,
                          cfg.target_i, cfg.stale_us, cfg.tick_us), (4_000_000, 30_000, 400_000, 600_000, 450_000, 200_000, 50_000))
        self.assertEqual(Configuration.thermal().target_i/1e9, .00015)
        for invalid in (dict(tick_us=0), dict(stale_us=10_000_001), dict(kp_scaled=10**12+1),
                        dict(min_control_i=1_000_000), dict(target_i=1_000_001), dict(min_temp_mK=1)):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                Configuration(**invalid)
        with self.assertRaises(ValueError):
            Configuration.thermal(hot_trip_mK=273_150)
        self.assertEqual(quantize(.5e-6, 1e6, "command"), 1)
        self.assertEqual(quantize(-.5e-6, 1e6, "sensor"), -1)

    def test_sequence_wrap_duplicate_half_range(self):
        self.assertTrue(sequence_newer(0, UINT32_MAX))
        self.assertFalse(sequence_newer(1, 1))
        self.assertFalse(sequence_newer(0, 1))
        self.assertFalse(sequence_newer(2**31, 0))

    def test_lease_equality_and_lost_ack_do_not_extend(self):
        lease = CommandLease(Configuration.thermal(), 1)
        q = Frame("Q", 1, UINT32_MAX, "V", 0, (300_000, 1_000_000, 527_498, 650_000, 1, 0))
        self.assertTrue(lease.accept(q, 0))
        self.assertFalse(lease.current(299_999).expired)
        self.assertEqual(lease.current(300_000).pump_command, 1.)
        self.assertTrue(lease.current(300_000).expired)
        self.assertFalse(lease.accept(q, 300_000))
        self.assertFalse(lease.accept(replace(q, epoch=2), 1))
        self.assertFalse(lease.accept(replace(q, sequence=0, time_us=10), 9))
        self.assertTrue(lease.accept(replace(q, sequence=0, time_us=10), 10))
        self.assertFalse(lease.accept(replace(q, sequence=2**31, time_us=20), 20))
        self.assertFalse(lease.accept(replace(q, sequence=1, time_us=UINT64_MAX), UINT64_MAX))


class ChildFailureTests(unittest.TestCase):
    def fake(self, code, directory, **kw):
        return CController([sys.executable, "-u", "-c", code], Configuration(), trace_dir=Path(directory)/"wire", **kw)

    def test_startup_hang_reaped_with_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            start = time.monotonic()
            with self.assertRaises(ControllerProcessFailure) as raised:
                self.fake("import time; time.sleep(20)", directory, startup_timeout_s=.15)
            self.assertLess(time.monotonic()-start, 2.)
            self.assertIsNotNone(raised.exception.returncode)
            self.assertIn("process_reaped", (raised.exception.trace_dir/"events.jsonl").read_text())

    def test_eof_and_unfinished_eof(self):
        for output in (b"", b"F|1|B"):
            with tempfile.TemporaryDirectory() as directory, self.subTest(output=output):
                code = f"import os; os.write(1,{output!r})"
                with self.assertRaises(ControllerProcessFailure) as raised:
                    self.fake(code, directory, startup_timeout_s=.3)
                self.assertIsNotNone(raised.exception.returncode)
                self.assertEqual((raised.exception.trace_dir/"stdout.bin").read_bytes(), output)

    def test_partial_alive_child_assembly_and_step_timeout(self):
        boot = Frame("B", 0, 0, "V", 0, (100, 0)).encode()
        code = f"import os,time; os.write(1,{boot!r}); time.sleep(.05); os.write(1,b'F|1|Q|'); time.sleep(20)"
        with tempfile.TemporaryDirectory() as directory:
            controller = self.fake(code, directory, step_timeout_s=.25, assembly_timeout_s=.1)
            start = time.monotonic()
            with self.assertRaises(ControllerProcessFailure) as raised:
                controller.step(0, [(1,0,0,1,250000), (6,0,0,1,0)], operation=1)
            self.assertLess(time.monotonic()-start, 2.)
            self.assertIsNotNone(controller.process.poll())
            self.assertIn("frame_assembly_timeout", (raised.exception.trace_dir/"events.jsonl").read_text())
            self.assertIn(b"F|1|Q|", (raised.exception.trace_dir/"stdout.bin").read_bytes())
            self.assertIsNone(raised.exception.last_reply)

    def test_alive_replying_child_unread_stdin_is_bounded_and_retains_last_reply(self):
        #Deliberately false child replies without consuming stdin. Repeated legal
        #32-observation transactions fill the Windows pipe; writer must time out.
        records = [Frame("B",0,0,"V",0,(100,0)).encode()]
        for tick in range(20):
            records.append(Frame("Q",1,tick,"V",tick*100000,(300000,0,315500,650000,1,0)).encode()
                           +Frame("R",1,tick,"V",tick*100000,(tick,1,0,33,0,0,0)).encode())
        #Linux pipe capacity can exceed this fixture's payload. Set only this
        #fake child's pipe to4KiB so the same bounded-writer oracle is portable.
        code = ("import os,time\nif os.name=='posix':\n import fcntl\n"
                " if hasattr(fcntl,'F_SETPIPE_SZ'): fcntl.fcntl(0,fcntl.F_SETPIPE_SZ,4096)\n"
                f"records={records!r}\nos.write(1,records[0])\nfor r in records[1:]:\n time.sleep(.03); os.write(1,r)\ntime.sleep(20)")
        with tempfile.TemporaryDirectory() as directory:
            controller = self.fake(code,directory,step_timeout_s=.2)
            start = time.monotonic()
            with self.assertRaises(ControllerProcessFailure) as raised:
                for tick in range(20):
                    now=tick*100000
                    observations=[(1,tick*32+i,now,1,250000) for i in range(32)]
                    controller.step(now,observations,operation=1 if tick==0 else 0)
            self.assertLess(time.monotonic()-start,3.)
            self.assertIn("stdin wall timeout",str(raised.exception))
            self.assertIsNotNone(raised.exception.last_reply)
            self.assertIsNotNone(controller.process.poll())
            events=(raised.exception.trace_dir/"events.jsonl").read_text()
            self.assertIn("process_reaped",events)
            self.assertIn("accepted_step",events)

    def test_q_without_reliable_r_fails_and_reaps(self):
        boot=Frame("B",0,0,"V",0,(100,0)).encode()
        command=Frame("Q",1,0,"V",0,(300000,0,315500,650000,1,0)).encode()
        code=f"import os,time; os.write(1,{boot!r}); time.sleep(.04); os.write(1,{command!r}); time.sleep(20)"
        with tempfile.TemporaryDirectory() as directory:
            controller=self.fake(code,directory,step_timeout_s=.15)
            with self.assertRaises(ControllerProcessFailure) as raised:
                controller.step(0,[(1,0,0,1,250000),(6,0,0,1,0)],operation=1)
            self.assertIn("reply wall timeout",str(raised.exception))
            self.assertIsNone(controller.last_reply)
            self.assertIsNone(controller.lease.accepted) #Q only is insufficient reliable liveness
            self.assertIsNotNone(controller.process.poll())


@unittest.skipUnless(HOST.is_file(), "build C host first or set FL_CONTROLLER_HOST")
class HostIntegrationTests(unittest.TestCase):
    def test_device_intent_cannot_advance_or_arm_host_virtual_schedule(self):
        frames=[Frame("H",1,0,"V",0,(1,)),Frame("C",1,0,"V",0,Configuration().payload),
                Frame("O",1,0,"V",0,(1,1,490000)),Frame("O",1,0,"V",0,(6,1,0)),
                Frame("U",1,0,"D",123456789,(1,0)),Frame("S",1,0,"V",0,(0,0)),
                Frame("S",1,1,"V",100001,(1,0)),Frame("S",1,1,"V",100000,(1,0))]
        result=subprocess.run([str(HOST)],input=b"".join(f.encode() for f in frames),capture_output=True,timeout=2)
        replies=[decode(line+b"\n") for line in result.stdout.splitlines()]
        replies=[f for f in replies if f.type=="R"]
        self.assertEqual(result.returncode,0)
        self.assertEqual([(f.sequence,f.time_us,f.payload[1]) for f in replies],[(0,0,0),(1,100000,1)])
        self.assertIn(b"rejected",result.stderr)

    def controller(self, directory, configuration=None, **kw):
        return CController(HOST, configuration or Configuration(), trace_dir=Path(directory)/"wire", **kw)

    def test_actual_pi_override_and_latch_reset_arm(self):
        with tempfile.TemporaryDirectory() as directory, self.controller(directory) as c:
            r = c.step(0, [(1,0,0,1,490000), (6,0,0,1,0)], operation=1)
            self.assertEqual(r.raw_command.payload[2], 345560)  #.3155+3*.01+.06*.01*.1
            r = c.step(100000, [(1,1,100000,0,0), (6,1,100000,1,0)])
            self.assertEqual(r.status.payload[1:3], (2,4))
            self.assertEqual(r.status.payload[5], 100000)  #invalid did not refresh last-good age
            r = c.step(200000, [(1,2,200000,1,500000), (6,2,200000,1,0)], operation=1)
            self.assertEqual(r.status.payload[6], 2)
            self.assertEqual(r.raw_command.payload[2], 0)
            r = c.step(300000, [(1,3,300000,1,500000), (6,3,300000,1,0)], operation=2)
            self.assertEqual(r.status.payload[1:3], (0,0))
            self.assertEqual(r.raw_command.payload[2], 0)
            r = c.step(400000, [(1,4,400000,1,500000), (6,4,400000,1,0)], operation=1)
            self.assertEqual(r.raw_command.payload[2], 315500)
        with tempfile.TemporaryDirectory() as directory, self.controller(directory, replace(Configuration(), kp_scaled=4_000_000, ki_scaled=0, ff_ppm=400000, normal_valve_ppm=600000)) as c:
            r = c.step(0, [(1,0,0,1,490000), (6,0,0,1,0)], operation=1)
            self.assertEqual(r.raw_command.payload[2:4], (440000,600000))

    def test_per_channel_freshness_and_old_future_duplicate_rejection(self):
        cfg = Configuration.thermal()
        with tempfile.TemporaryDirectory() as directory, self.controller(directory,cfg) as c:
            obs = [(2,0,0,1,150000), (3,0,0,1,293150), (4,0,0,1,293150), (5,0,0,1,293150), (6,0,0,1,0)]
            self.assertEqual(c.step(0, obs, operation=1).status.payload[1], 1)
            for tick in range(1,4):
                now = tick*100000
                r = c.step(now, [(2,tick,now,1,150000),(6,tick,now,1,0)])
            self.assertEqual(r.status.payload[1],1)
            self.assertEqual(r.status.payload[5],300000)
            #Future, duplicate and old arrival cannot refresh hot temperature.
            r = c.step(400000, [(2,4,400000,1,150000), (6,4,400000,1,0),
                                (3,1,500000,1,293150), (4,0,400000,1,293150)])
            self.assertEqual(r.status.payload[1:3],(2,6))
            self.assertEqual(r.status.payload[4] & 28, 28)
            self.assertEqual(r.raw_command.payload[1:4],(0,1000000,1000000))

    def test_threshold_equality_priority_invalid_missing_and_disarmed(self):
        for channel, reason, value in ((6,1,1),(5,2,358150),(3,3,338150)):
            with tempfile.TemporaryDirectory() as directory, self.controller(directory,Configuration.thermal()) as c:
                obs=[(2,0,0,1,150000),(3,0,0,1,293150),(4,0,0,1,293150),(5,0,0,1,293150),(6,0,0,1,0)]
                c.step(0,obs,operation=1,heat_demand_ppm=1000000)
                fresh=[(a,1,100000,q,value if a==channel else v) for a,s,t,q,v in obs]
                r=c.step(100000,fresh,heat_demand_ppm=1000000)
                self.assertEqual(r.status.payload[2],reason)
        for quality in (0,2):
            with tempfile.TemporaryDirectory() as directory, self.controller(directory) as c:
                c.step(0,[(1,0,0,1,250000),(6,0,0,1,0)],operation=1)
                r=c.step(100000,[(1,1,100000,quality,0),(6,1,100000,1,0)])
                self.assertEqual(r.status.payload[2],4)
        with tempfile.TemporaryDirectory() as directory, self.controller(directory) as c:
            r=c.step(0,[(1,0,0,1,250000),(6,0,0,1,1)],operation=1)
            self.assertEqual(r.status.payload[1:3],(0,0))
            self.assertEqual(r.status.payload[6],2)

    def test_q_drop_vs_ack_drop_reliable_liveness_and_lease_equality(self):
        with tempfile.TemporaryDirectory() as directory, self.controller(directory,Configuration.thermal()) as c:
            for tick in range(4):
                now=tick*100000
                obs=[(2,tick,now,1,150000),(3,tick,now,1,293150),(4,tick,now,1,293150),(5,tick,now,1,293150),(6,tick,now,1,0)]
                r=c.step(now,obs,operation=1 if tick==0 else 0,heat_demand_ppm=1000000,
                         command_filter=None if tick==0 else lambda q:None, acknowledge=False)
                self.assertEqual(r.status.payload[1],1)
                self.assertEqual(r.applied.expired,tick==3)
            self.assertEqual(r.applied.heat_command,0.)
            self.assertEqual(r.applied.pump_command,1.)
            self.assertEqual(r.applied.valve_command,1.)
            self.assertEqual(r.raw_command.payload[1],1000000) #R/Q still running; application lease independently expired

    def test_restart_origin_reacquisition_epoch_and_sequence_wrap(self):
        with tempfile.TemporaryDirectory() as directory, self.controller(directory,epoch=2,session_origin_us=60000000) as c:
            with self.assertRaises(ValueError):
                c.step(60000000,[(1,0,59999999,1,250000)])
            r=c.step(60000000,[(1,UINT32_MAX,60000000,1,250000),(6,UINT32_MAX,60000000,1,0)])
            self.assertEqual(r.status.payload[1],0)
            r=c.step(60100000,[(1,0,60100000,1,250000),(6,0,60100000,1,0)],operation=1)
            self.assertEqual(r.status.payload[1],1)
            #An old epoch and half-range sequence must not replace current good data.
            r=c.step(60200000,[Frame("O",1,1,"V",200000,(1,1,900000)),
                               Frame("O",2,2**31,"V",200000,(1,1,900000)),(6,1,60200000,1,0)])
            self.assertEqual(r.status.payload[1:3],(1,0))
            self.assertEqual(r.status.payload[5],100000)
            self.assertEqual(r.raw_command.payload[2],1000000)

    def test_host_staging_overflow_and_bad_frames_do_not_refresh(self):
        frames=[Frame("H",1,0,"V",0,(1,)),Frame("C",1,0,"V",0,Configuration().payload)]
        frames += [Frame("O",1,i,"V",0,(1,1,250000)) for i in range(32)]
        #33rd separate trip sample is rejected, so ARM has no valid trip channel.
        frames += [Frame("O",1,0,"V",0,(6,1,0)),Frame("S",1,0,"V",0,(1,0))]
        completed=subprocess.run([str(HOST)],input=b"".join(f.encode() for f in frames),capture_output=True,timeout=2)
        output=[decode(line+b"\n") for line in completed.stdout.splitlines()]
        self.assertEqual(completed.returncode,0)
        self.assertIn(b"staging overflow",completed.stderr)
        self.assertEqual(output[-1].payload[1],0)
        self.assertEqual(output[-1].payload[6],2)


if __name__ == "__main__":
    unittest.main()
