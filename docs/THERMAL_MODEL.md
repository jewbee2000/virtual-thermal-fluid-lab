# Thermal circulation contract and independent derivation

Frozen 2026-10-06 before M2 implementation. Authority: revised plan and
REQUIREMENTS.md. Educational single-phase liquid bench; all starting coefficients
are assumed. Physical validation NOT_STARTED. No Endurance dimensions or measured
curves are used. Read-only physics review reproduced the hand calculations below
from separate equations and a matrix exponential, without production functions.

## Domain and omitted physics

Two perfectly mixed liquid inventories exchange equal forward volume flow Q,
so each inventory is constant. Density1000kg/m3 and cp4180J/(kg K) are constant.
The hot wall is one thermal capacitance. Pressure-flow response is quasi-steady;
speed and valve positions have assumed first-order lags. No transport delay,
local boiling, spatial gradients, reservoir inventory changes, cavitation, pump
efficiency, motor heating, backflow or phase-change behavior is predicted.

Temperature domain: 273.15<T<368.15K for each accepted wall/liquid state. Initial
states must be strictly interior. Sink may be exactly273.15K but must be below
368.15K; normal sink283.15K. Reaching either boundary terminates persistently and
is reported, never clipped and resumed. This is an educational cutoff; pressure
differences do not establish absolute pressure or a phase envelope. A physical
bench would need measured absolute pressure, properties and local temperatures.
The assumed liquid remains single phase by contract, not by a modeled phase test.

Actual speed x and opening z lie in[0,1]. Accepted states outside that domain are
failures; do not mask them with clipping. The algebraic Q=0 branch at z=0 is exact,
not a numerical leak. Equality at hot/wall trip limits trips (>=); required channel
staleness uses strict age>configured stale interval. Initial controller state is
DISARMED and explicit arming requires valid configuration and all required inputs.

## Hydraulic equations and oracle

Pump: dp=p0*x^2-Kp*Q^2. System: dp=(Kpipe+Kv/z^2)*Q^2 for z>0.
Equating and rearranging:

```
Qstar = x*z*sqrt(p0 / ((Kp+Kpipe)*z*z + Kv))
dx/dt = (u_pump_applied-x)/tau_x_s
dz/dt = (u_valve_applied-z)/tau_z_s
```

Use p0=100000Pa, Kp=4e11, Kpipe=6e11 and Kv=1e11Pa s2/m6;
tau_x=1s and tau_z=.5s. At closed z, Q=0 and dp=p0*x*x; avoid system division
by zero. Independent pressure substitution must have residual divided by
max(p0,1Pa)<1e-8. Test zero speed, zero opening, nominal and restricted branches.

At Q=.00015m3/s and z=.65, independent solution x=.5274982823;
both curves give dp18825.443787Pa. Scaling all four pressure coefficients by2
leaves Q(x,z) unchanged but doubles pressure: flow-only data cannot identify
absolute pressure scale or separate Kp from Kpipe.

The thermal equations omit pump work. At nominal Q*dp=2.823817W, .0565% of
5000W. Maximum hydraulic work over x,z in[0,1] is19.245009W (.385%). This
supports the reduced high-heat model; the P=0 conserved-energy oracle checks the
reduced equations only, not a lossless real pump. Add pump work only for a test
question/measurement that requires it, with renewed evidence.

## Thermal balances

State order: Tw_K, Th_K, Tc_K, pump_speed, valve_opening, heat_in_J,
heat_rejected_J. Ch=Mh*cp=8360J/K; Cc=Mc*cp=12540J/K; Cw=10000J/K.
Normal conductances UAh=300W/K, UAc=500W/K; normal imposed heat P in[0,5000]W.

```
Cw*dTw/dt = P_applied - UAh*(Tw-Th)
Ch*dTh/dt = UAh*(Tw-Th) + rho*Q*cp*(Tc-Th)
Cc*dTc/dt = rho*Q*cp*(Th-Tc) - UAc*(Tc-Ts)
dheat_in_J/dt = P_applied
dheat_rejected_J/dt = UAc*(Tc-Ts)
```

Every RHS balance term has units W. Sum cancels wall exchange and circulation:
d(Cw*Tw+Ch*Th+Cc*Tc)/dt=P-UAc*(Tc-Ts). The residual using augmented
heat integrals is a consistency check, not an independent physical oracle.
Normal coefficients positive; isolated analytic benchmarks may set heat exchange,
sink conductance or pump speed exactly zero. Lost-sink fault sets UAc=0 exactly.

With constant positive Q and P, set derivatives to zero sequentially:
Tc=Ts+P/UAc; Th=Tc+P/(rho*Q*cp); Tw=Th+P/UAh.
At target Q/full heat: Tc293.15K, Th301.1244816587K, Tw317.7911483254K.
Use a1200s imposed-flow equilibrium benchmark, not the240s cold-start demo.
Independent linear-system calculation gives slowest time constant99.749539s,
max equilibrium error1.650654K after240s and .000109133K after1200s.
No-flow/P>0 has no finite steady hot-wall/liquid temperature.

## Frozen M2 checks

- Constant heat in isolated C: T=T0+Pt/C; exponential sink cooling:
  T=Ts+(T0-Ts)exp(-UA*t/C). Tight benchmark max temperature error<1e-5K.
- Internal mixing with P=0,UAc=0 conserves weighted total energy; no-flow wall
  exchange cancels in combined hot-wall/liquid energy. Residual tolerance1e-3J.
- Positive imposed Q,1200s: all steady temperatures within .01K. Independently
  assemble the3x3 constant-flow linear matrix and compare using scipy.linalg.expm;
  no production RHS/helper may generate the expected matrix.
- Upper/lower events agree with constant-heating/cooling analytic times where
  available; repeated advance preserves stopped state/time; retain diagnostics.
- Fixed-tick noise-free tolerance ladder1e-5/1e-7/1e-9 vs DOP8531e-11.
  Per-state comparison scales:[1e-4K,1e-4K,1e-4K,1e-7,1e-7,.01J,.01J].
  Tightest ladder normalized maximum<=1. Record others and convergence behavior.
  Solver atol default:[1e-8K,1e-8K,1e-8K,1e-10,1e-10,1e-5J,1e-5J];
  max step<=.05s. Isolated benchmarks use tighter values as declared in evidence.

Controller tick refinement and continuous thermal peaks require M5 review. Gains
and wire policy freeze before M3. These checks verify assumed equations/numerics;
no plant measurement or physical predictive accuracy follows.

Read-only reviewer accepted this contract before implementation. With Ts>=lower
and nonnegative heat, the lower maximum principle holds: exact sink/lower equality
is approached asymptotically, so no finite cooling lower-event time is invented.
Test initial rejection, guard semantics and a finite-horizon cooling limit.
x,z endpoints0/1 are legal: a stationary endpoint must not trigger termination.
For tiny z use stable pump pressure p0*x*x-Kp*Q*Q rather than dividing by z*z;
independently substitute the system curve at resolvable openings.

## Long hazard predicted before campaign

After fault at60s, heat is stuck5000W and UAc=0. Total capacity30900J/K gives
weighted mean rise5000/30900=.1618123K/s irrespective of circulation. If all
states are initially at or above the10C sink, at least one95C upper boundary
occurs by absolute585.3s. The required1200s scenario must show a trip then
boundary despite heat-off/full-cooling requests. It can pass its expectation
while prominently reporting failed containment. Acknowledged command is not
proof of heat removal or circulation.

Sources consulted by read-only reviewer: [OpenStax Bernoulli](https://openstax.org/books/university-physics-volume-1/pages/14-6-bernoullis-equation),
[DOE energy balances](https://www.energy.gov/sites/default/files/2026-04/DOE-HDBK-1012-92_VOL1.pdf),
[SciPy1.17 integration](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.integrate.solve_ivp.html).
These support methods; coefficients, cutoff and acceptance targets are authored
project assumptions. No physical dataset exists.
