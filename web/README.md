# Static evidence replay

Build the C SIL campaign first. From the project root, export retained run
directories containing `manifest.json`, `summary.json`, `telemetry.csv` and every
manifest-listed raw artifact:

```powershell
uv run python scripts/build_replay.py --run artifacts/campaign/nominal_heat_step --run artifacts/campaign/reduced_rejection --run artifacts/campaign/frozen_temperature --run artifacts/campaign/stuck_heat_lost_sink --out artifacts/replay
Start-Process artifacts/replay/index.html
```

The paths are examples; use the actual run directories produced by the campaign.
The output must be a new directory. The exporter verifies manifest SHA256s before
writing and copies original bytes into `raw/<run>/`. It embeds a column-oriented
presentation dataset in local `data.js`, so `index.html` also works offline under
`file://` without browser CORS exceptions, Python, a server, network or account.
Hosting the unchanged directory is sufficient for website replay. All bundled
asset hashes and original file hashes are in `replay-manifest.json`.
The exporter retains the project root MIT license byte-for-byte as `LICENSE.txt`
for the authored replay assets; uPlot's separate license is also bundled.

For a separate hosted-site variant, add `--compress-raw`. Only `summary.json`
and files beneath `wire/` are losslessly gzip-compressed; telemetry CSV,
manifests, configuration JSON, licenses and boot-time `data.js` remain plain.
The default plain export remains byte-exact and is the full standalone ZIP's
source. Use a new output directory for the hosted variant; it does not replace
the plain bundle or discard any diagnostics or rows.

Compressed links end in `.gz` and are labeled `(gzip)`. Decompress a download
before comparing its original SHA256 in `raw_hashes` or the source run manifest.
Per-download metadata records encoding, actual filename/path, original SHA256
and actual packaged-file SHA256; the replay manifest hashes each `.gz` file's
bytes. Gzip uses level6, mtime0 and no filename header for deterministic output.
No file is fetched or decompressed at page boot; the embedded display dataset
remains immediately available in plain `data.js`.

The source page contains no evidence by default. Explicit developer fixtures may
be exported only with `--allow-ui-fixture`; their summary must declare
`execution.evidence_level="UI_FIXTURE"`. The page then prominently labels them
`UI_FIXTURE NOT_VERIFICATION`. They cannot supply release numbers or figures.

The viewer does not reassess criteria. It displays original expectation,
containment, completion and per-rule statuses and preserves failures. For tank
outputs, mapping is explicit: `level_m`/`measured_level_m`, `pump_command`,
`applied_pump_command`, `applied_valve_command` and `valve_opening`. Pump actual
inflow divided by the recorded `pump_max_m3_s` is a normalized inflow indicator,
not a modeled pump shaft speed. Missing legacy lease/source fields stay absent.
Tank observation gaps require actual sensor-validity and age evidence.

Embedded summaries omit the bulky solver-interval records and retain only wire
audit status/issues/counts. The complete original summary, raw diagnostics and
transport audit remain unchanged in the downloads. Configurations marked VARIANT
are prominently labeled; their passing results do not close the frozen-default
campaign release gate.

## Rendering and time policy

- Every source row is exported; **no decimation** is currently applied. Extrema,
  event-before/event-after duplicates and fractional terminal roots are retained.
  Raw exports stay at full resolution. If a future dataset exceeds the measured
  load budget, freeze and test an extrema/event-preserving policy before reducing
  display data.
- Charts and scenario comparisons use absolute simulation seconds. Epoch restart
  local time is retained in the raw row; it does not reset the plot origin. No
  fault-relative alignment or clock subtraction is performed.
- Commands and observations use post-aligned step paths. Truth uses straight
  visual connectors between retained samples. No interpolated values are inserted
  into the dataset or used in numeric readouts. Cursor readout holds the previous
  source row and labels that behavior; it does not extend beyond termination.
- Observation lines break when quality is invalid/missing, age is unavailable,
  or age exceeds the configured stale threshold. Age equality remains fresh,
  matching the protocol contract. Source, receipt and last-good timestamps remain
  visible even when observations are stale.
- The sample buttons expose duplicate event rows; scrubbing to a timestamp selects
  its final retained row. Limits come from the executed controller configuration,
  not an invented UI safety rating. K and m³/s remain raw units; display converts
  to °C and L/min.
- The thermal conservative bound displays its recorded coverage scope and retained
  start/end separately from the requested end. A valid terminal hazard is a
  RETAINED_PREFIX through its fractional terminal root, not a bound over the
  unfinished requested horizon. UNAVAILABLE, discarded-row or inconsistent
  coverage metadata suppresses the numeric bound. The object remains unchanged
  in embedded metrics and full raw downloads; no new acceptance judgment is made.

The page records its own initial script/plot render observation using the browser
Performance API. Record repeated load observations with the final dataset,
browser/version/device and cache conditions in milestone evidence. The displayed
one-shot duration excludes browser startup and is not a universal performance
claim. Root integration owns desktop/mobile, keyboard, raw-link and final visual
QA on actual retained C runs. Matplotlib PNG fallbacks are generated from those
same verified raw rows; the first fallback remains linked with JavaScript off.
