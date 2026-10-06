# M1 bounded read-only review

Two inspections, one repair cycle, 2026-10-06. No source changed by reviewer.
First inspection found corrupt observed/receipt/command/state fields and Boolean
identities falsely passing. Truncated stale-trip and missing/inconsistent hazard
endpoints also falsely passed. Coordinator retained requirements and authorized
repair rather than relaxing criteria. Source writer added independent raw fixtures.

Final recommendation:ACCEPT for reviewed M1 behavior. Exact corruption probes
using .venv\Scripts\python.exe -B - returned evidence_validFalse/allpassFalse
without exceptions. Truncated post-trip evidence cannot pass. Five named tests
for persistent empty/full stop, partial failure, fixed-byte hash, wrong-CWD Git
and actual solver/export provenance passed0.592s/exit0 from tests/ using
..\.venv\Scripts\python.exe -B -m unittest. Inactive no-fault dt=.07,horizon.7
normalizes idempotently and completes11ticks; an active unaligned fault rejects.

This acceptance does not cover future thermal physics, firmware/MCU, hardware
execution or physical validation. Those gates retain actual unfinished status.
