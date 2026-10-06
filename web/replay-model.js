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
  const api = {finite, unpack, indexAt, quality, observedValue, tankObservedValue};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else scope.ReplayModel = api;
})(typeof window !== "undefined" ? window : globalThis);
