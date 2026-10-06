/* Pure replay helpers; original evidence is never evaluated or modified here. */
(function (scope) {
  "use strict";
  const finite = value => typeof value === "number" && Number.isFinite(value);
  function unpack(run) {
    const rows = Array.from({length: run.columns[0]?.length || 0}, (_, i) =>
      Object.fromEntries(run.fields.map((field, j) => [field, run.columns[j][i]])));
    return {...run, rows, lastTime: rows.at(-1)?.time_s || 0};
  }
  function indexAt(rows, time) {
    let low = 0, high = rows.length;
    while (low < high) {
      const mid = (low + high) >>> 1;
      if (rows[mid].time_s <= time + 1e-10) low = mid + 1;
      else high = mid;
    }
    return low - 1;
  }
  function quality(row, prefix, staleUs) {
    if (!row) return "unavailable";
    const q = row[prefix + "_quality"], age = row[prefix + "_age_us"];
    if (q === 0) return "invalid";
    if (q === 2) return "missing";
    if (q !== 1 || !finite(age)) return "unavailable";
    return age > staleUs ? "stale" : "valid / fresh";
  }
  function observedValue(row, field, prefix, staleUs) {
    return quality(row, prefix, staleUs) === "valid / fresh" && finite(row[field]) ? row[field] : null;
  }
  function tankObservedValue(row, staleSeconds) {
    return row && row.sensor_valid === true && finite(row.measurement_age_s) &&
      row.measurement_age_s <= staleSeconds && finite(row.measured_level_m) ? row.measured_level_m : null;
  }
  function peakBoundDisplay(metrics) {
    const coverage = metrics?.peak_bound_coverage;
    const fields = ["start_time_us", "end_time_us", "requested_end_time_us", "retained_samples", "discarded_rows", "scope"];
    const closed = coverage && typeof coverage === "object" && !Array.isArray(coverage) &&
      Object.keys(coverage).length === fields.length && fields.every(field => Object.hasOwn(coverage, field));
    const windowValid = closed && finite(coverage.start_time_us) && finite(coverage.end_time_us) &&
      finite(coverage.requested_end_time_us) && coverage.start_time_us >= 0 &&
      coverage.end_time_us >= coverage.start_time_us && coverage.requested_end_time_us >= coverage.end_time_us;
    const countsValid = closed && Number.isInteger(coverage.retained_samples) && coverage.retained_samples > 0 &&
      Number.isInteger(coverage.discarded_rows) && coverage.discarded_rows >= 0;
    const full = windowValid && coverage.scope === "FULL_RETAINED_HORIZON" &&
      coverage.start_time_us === 0 && coverage.end_time_us === coverage.requested_end_time_us;
    const prefix = windowValid && coverage.scope === "RETAINED_PREFIX" &&
      (coverage.start_time_us > 0 || coverage.end_time_us < coverage.requested_end_time_us);
    const available = countsValid && coverage.discarded_rows === 0 && (full || prefix) && finite(metrics.global_peak_upper_bound_k);
    const scope = available ? coverage.scope : "UNAVAILABLE";
    const seconds = value => (value / 1e6).toFixed(9).replace(/(\.\d*?[1-9])0+$|\.0+$/, "$1");
    const windowLabel = windowValid ? `retained ${seconds(coverage.start_time_us)}–${seconds(coverage.end_time_us)} s; requested end ${seconds(coverage.requested_end_time_us)} s` : "no verified coverage window";
    const countsLabel = countsValid ? `; ${coverage.retained_samples} rows, ${coverage.discarded_rows} discarded` : "";
    return {value_k: available ? metrics.global_peak_upper_bound_k : null, scope,
      detail: `${scope} · ${windowLabel}${countsLabel} · excludes numerical integration error`};
  }
  const api = {finite, unpack, indexAt, quality, observedValue, tankObservedValue, peakBoundDisplay};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else scope.ReplayModel = api;
})(typeof window !== "undefined" ? window : globalThis);
