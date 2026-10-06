# M3 bounded read-only core and transport review

Reviewer baseline_review accepted the isolated M3 implementation on2026-10-06.
No production edits. Reviewed core/codec/host/driver against the frozen protocol.

Executed six named Python tests for CRC split literals, independent channel ages,
Q-loss versus ACK-loss lease equality, unread stdin, partial stdout, and missing
reliable reply:6 passed in1.310 s, exit0. A separate actual-host raw probe rejected
old, half-range and profile-changing handshakes; new epoch returned DISARMED and
required ARM. States were[RUNNING,RUNNING,DISARMED,RUNNING], with independent
PI outputs345560,345620,0,345560 ppm. An old temperature sample delivered at
400000 us retained age400000 us and tripped stale-input shutdown.

Core receives observations rather than Plant/fault labels. Bad quality retains
last-good age. Reliable STEP still advances when all experimental observations
drop. Independent CRC literals, tank/thermal PI expectations and saturation/
unwind checks supplement production round trips. Lost ACK cannot extend a lease;
missing R is a run failure with reaped child. The root coordinator subsequently
executed the integrated95-test and seven-C-case checks retained in evidence/M3.

This document is a reviewer execution summary, not a verbatim terminal capture.
The child-transport guarantee excludes arbitrary caller Python callback execution.
MCU acquisition/device clocks and integrated thermal containment remain M4/M5.
Physical validation is NOT_STARTED and board execution is NOT_EXECUTED.
