# M0 review and pre-implementation contract evidence

2026-10-06. Read-only physics, test and evidence roles; coordinator alone owns
contracts. These are agent-assisted reviews, not measured validation or independent
human certification. M0 accepted with the document repairs integrated in M1.

Executed native baseline:20 tests/8.073s and seven expectations (evidence/M0).
Independent evidence audit checked original traces under artifacts/M0-starter:
monotonic time, matching sampled peaks, all post-trip pump requests0. Stuck pump
trip117.9s, full boundary161.180709s. Expected hazard passed; containment failed.

Actual inherited Linux CI succeeded for378de6c:
https://github.com/jewbee2000/virtual-thermal-fluid-lab/actions/runs/37429238149.
Command: explicit C:\Program Files\GitHub CLI\gh.exe run view37429238149 with
repository and JSON conclusion/headSha/jobs/url. Windows matrix was not executed
at M0; M1 must supply its own actual results. Lock hash independently matched.

Test review demonstrated defects before repair: zero-duration direct run bypassed
validation and falsely passed; unknown fields/Boolean numerics invalid limits
accepted; NaN supervisor stale interval failed to trip; path hashing changed
between Windows and POSIX separators. Initial validation probe used an import-only
SciPy stub and ran no solver; later real .venv Python probe confirmed empty stop
11.5148374266s could resume to12.5148374266s/.0028962728m. Each standalone
Python stdin probe exited0. File-free probes used -B; no source edited.

Physics reviewer separately derived tank drain7.572105L/min/command.315504380,
empty time182.097079s. Separate thermal equations and scipy.linalg.expm reproduced
target speed.527498282, dp18825.443787Pa, Tc/Th/Tw20/27.974482/44.641148C,
slowest99.749539s time constant,240s/1200s errors1.650654/.000109133K.
Independent energy argument predicts lost-sink/stuck5kW upper boundary by585.3s.
Recorded derivation, sources and reviewed limits:docs/THERMAL_MODEL.md. Physics
contract accepted after lower-domain/pressure/zero-coefficient/pump-work repairs.

Instruction/evidence corrections: old research is historical, current M0–M7 and
REQUIREMENTS govern; claims point to actual M0 logs instead of inherited examples;
optional standalone role loading not separately tested. Physical validation
NOT_STARTED; MCU board NOT_EXECUTED. Detailed current employer-role text in the
supplied revised plan lacks a retained rendered first-party capture in this
checkout. Refresh before public employer-specific assertions; authored project
requirements do not depend on claiming that employer's actual tool inventory.

Website workflow reconnaissance matched local/immutable/live AbyssBench bytes and
actual deployment (docs/DEPLOYMENT.md). No lab article built or published.
