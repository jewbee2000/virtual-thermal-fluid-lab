# Five-minute evidence walkthrough

Open the exported replay `index.html` in a browser. The static bundle needs no
Python, server or account. Read the assumed-parameter and execution labels first.

1. Inspect **nominal heat step**. At20s heat demand becomes5000W. Compare wall,
   hot and cooled temperatures, and convert9L/min to1.5e-4m3/s. The240s cold-start
   trajectory is a transient; the independent equilibrium benchmark uses1200s.
2. Select **frozen temperature**, compare nominal, and scrub past60s. The observed
   hot/wall values remain plausible and fresh while truth rises. Inspect the
   separate switch and343.9s latched trip. Requested and leased heat become zero;
   full circulation/opening follow. The bound remains below the chosen86C gate.
3. Select **stuck heat lost sink**. At346.6s the C controller trips and requests
   heat-off. Applied heat remains5000W. Press End: the actual fractional root is
   466.299590s, wall95C. ExpectationPASS, containmentFAILED and completionFAIL
   answer different questions. The retained-prefix label does not claim1200s.
4. Select **flow dropout** or a near-tick case. Read source time, receipt time,
   last-good time and age. Stale equality remains running; the first strictly
   overdue tick trips. Use event/sample buttons to expose same-time before/after
   records. Compare with **planned restart**: new epoch60s, explicit ARM62s.
5. Download CSV, summary and manifest. Check a SHA256, inspect the C core and
   Pico build evidence, then open the hardware packet. Board execution is
   NOT_EXECUTED and physical validation NOT_STARTED. Explain the next physical
   measurement that could disprove the assumed model.

To regenerate one demonstration after building the C host:

```powershell
uv run python scripts/run_campaign.py --exe artifacts/host-build/Release/fluid_controller_host.exe --out artifacts/my-demo --case nominal_heat_step --case frozen_temperature --case stuck_heat_lost_sink --skip-tank
uv run python scripts/build_replay.py --run artifacts/my-demo/nominal_heat_step --run artifacts/my-demo/frozen_temperature --run artifacts/my-demo/stuck_heat_lost_sink --out artifacts/my-replay
```

This selected demo does not close the full release campaign gate. Full campaign
and refinement commands are in evidence/M5 and docs/CAMPAIGN.md. Existing output
directories are rejected so an ordinary demo does not overwrite released evidence.
