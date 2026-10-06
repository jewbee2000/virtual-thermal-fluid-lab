# Versioned contracts

M1 tank input is tank-scenario-v1.schema.json. Omitted schema_version normalizes
to 1 for preserved starter files and direct Python callers. Reject unknown fields,
duplicate JSON keys, nonfinite/Boolean numeric values, and incompatible outcomes.
Ticks/horizon use integer microseconds; tank duration and active fault align to
ticks. Bound tick count to 1,000,000. M5 adds versioned event splitting rather than
silently retiming faults.

Controller defaults: version1, kp_per_m=3, ki_per_m_s=.06, bias=.3155,
drain_command=.65, high_switch_m=.8, stale_after_s=.3, sensor_min_m=0,
sensor_max_m=tank_height_m. Custom topology requires explicit valid limits;
target/high switch strictly inside tank and sensor range ordered and within tank.
All commands normalized [0,1]. Plant parameters keep existing positive SI fields
and assumed pedigree; reject Boolean numeric values.

Immutable solver config version1: RK45/DOP853/Radau; finite positive rtol;
five finite positive atols; positive max_step_s<=.05. Default rtol1e-7,
atol=[1e-9,1e-11,1e-9,1e-11,1e-11], max_step_s=.05. Persist executed config
and effective per-interval cap min(dt,max_step_s); caller metadata cannot override.

Summary/manifest version1 retain baseline compatibility fields and add per-rule
PASS/FAIL/NOT_APPLICABLE/UNASSESSABLE, complete horizon, run outcome, containment,
configuration/diagnostics and conservative peak bound. No-trip R10 is inapplicable;
characterization requires complete horizon. Required FAIL/UNASSESSABLE prevents
overall pass. Boundary/failure snapshot has record_type and retained sample_time_s,
command and age at snapshot time. Separate expectation from containment.

Canonical source digest: project-relevant paths sorted by POSIX UTF-8 path.
SHA256 stream per file: path UTF-8, NUL, unsigned 8-byte big-endian length, raw
file bytes. Document file inclusion. Hash does not canonicalize bytes; .gitattributes
defines LF storage. Scenario hash: sorted compact UTF-8 JSON allow_nan=False.
Artifact hashes identify exported bytes; manifest does not hash itself. Git cwd
is project root; verify reported top-level equals it. Include lock hash and units.

Tank continuous peak bound: sample max + (pump_max_m3_s/area_m2)*largest_gap_s,
since drain>=0 and modeled inflow<=Qmax. Report numerical error separately;
no claim that this alone bounds floating point error. Dense extrema may replace
this with reviewed checks. Thermal/wire contracts precede corresponding work.
Coordinator alone changes shared schemas and acceptance definitions.
