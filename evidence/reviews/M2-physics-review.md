# M2 read-only physics review

Reviewer: physics_contract, 2026-10-06. Recommendation: ACCEPT with limitations.
No source edits or threshold changes. Reviewed thermal.py, test_thermal.py and
verify_thermal.py against the frozen thermal contract.

Balances, units, the stable pump intersection, legal actuator endpoints and
persistent temperature termination match the contract. Expected heating/cooling
solutions, the raw-coefficient3x3 matrix exponential, weighted energy invariants,
no-flow heating and analytic150 s upper event are independent of the production
RHS. Imposed-flow benchmarks explicitly report hydraulic pressure unavailable.
Finite-horizon lower cooling does not invent an asymptotic crossing time.

The reviewer executed a stdout-only Python probe using the existing .venv
interpreter, exit0:96 domain-corner derivative checks under nominal, lost-sink
and restricted forcing. Maximum derivative-minus-reported-bound was
-3.1086e-15 K/s; reported-versus-independently-computed bound difference was
1.7764e-15 K/s. These values are the reviewer's execution summary; this Markdown
is not presented as a verbatim terminal log. The coordinator did not repeat the
writer's full checks, which are retained in evidence/M2.

Minor limitations retained:

- Zero pipe/valve-resistance overrides can yield subtractive pump-pressure
  roundoff down to-5.82e-11 Pa rather than exact zero (5.82e-16 of p0). No clipping
  or gate relaxation was introduced.
- The benchmark JSON records the independent event-time error but gates only
  persistent boundary behavior. The unit suite's independent150 s event-time
  assertion is therefore required alongside the benchmark report.

Parameters remain assumed; pump work is explicitly omitted from the reduced
balances. This review is scientific/code review assistance. Physical validation
is NOT_STARTED and board execution is NOT_EXECUTED.
