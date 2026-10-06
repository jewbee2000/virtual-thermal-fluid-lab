(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const M = window.ReplayModel;
  const dataset = window.FLUIDLAB_REPLAY;
  if (!dataset?.runs?.length || !M || typeof uPlot === "undefined") {
    $("load-message").textContent = "No exported evidence is loaded. Run scripts/build_replay.py with retained run directories, then open its index.html. No simulation runs in this page.";
    document.querySelectorAll(".controls button,.controls select,.controls input").forEach(el => el.disabled = true);
    return;
  }
  const runs = dataset.runs.map(M.unpack);
  const byName = new Map(runs.map(run => [run.name, run]));
  let current = runs.find(r => r.name === "nominal_heat_step") || runs[0];
  let comparison = runs.find(r => r.name === "reduced_rejection") || null;
  let plots = [], time = 0, maxTime = 0, playing = false, lastFrame = 0, syncing = false, explicitIndex = null;
  const fmt = (value, digits=3) => M.finite(value) ? value.toFixed(digits) : "—";
  const celsius = v => M.finite(v) ? v - 273.15 : null;
  const lpm = v => M.finite(v) ? v * 60000 : null;
  const text = (tag, content, className) => {
    const el = document.createElement(tag); el.textContent = content;
    if (className) el.className = className;
    return el;
  };
  const state = row => ({0:"DISARMED", 1:"RUNNING", 2:"TRIPPED"})[row?.controller_state] || row?.controller_state || (row?.trip ? "TRIPPED" : "RUNNING");
  const reason = row => row?.trip_reason || row?.trip || "";
  const controller = run => typeof run.summary.controller === "object" && run.summary.controller !== null ? run.summary.controller : run.manifest.controller_configuration || run.manifest.controller || {};
  const staleUs = run => controller(run).stale_us ?? ((controller(run).stale_after_s ?? .3) * 1e6);
  const rowsAt = (run, t) => {
    if (!run?.rows.length || t > run.lastTime + 1e-9) return null;
    const i = run === current && explicitIndex !== null ? explicitIndex : M.indexAt(run.rows, t);
    return run.rows[i] || null;
  };
  function option(run) { const el = text("option", run.name.replaceAll("_", " ")); el.value = run.name; return el; }
  runs.forEach(run => { $("scenario").append(option(run)); $("compare").append(option(run)); });
  $("scenario").value = current.name;
  $("compare").value = comparison?.name || "";

  function chartSeries(run, kind) {
    const thermal = run.topology === "thermal_loop";
    const specs = [];
    const add = (label, color, get, dash=[], stepped=false) => specs.push({label, color, get, dash, stepped});
    const truth = $("truth").checked, observed = $("observed").checked, limits = $("limits").checked;
    if (kind === "temperature") {
      if (thermal) {
        for (const [prefix, color] of [["wall","#ad3c19"],["hot","#946000"],["cold","#1266a2"]]) {
          if (truth) add(prefix+" truth", color, row => celsius(row[prefix+"_temperature_k"]));
          if (observed) add(prefix+" observed", color, row => celsius(M.observedValue(row, "observed_"+prefix+"_temperature_k", prefix, staleUs(run))), [5,4], true);
        }
        if (limits) {
          for (const [key,label] of [["hot_trip_mK","hot trip"],["wall_trip_mK","wall trip"]])
            if (M.finite(controller(run)[key])) add(label,"#687b84",() => controller(run)[key]/1000-273.15,[2,4]);
        }
      } else {
        if (truth) add("level truth", "#1266a2", row => row.level_m);
        if (observed) add("level observed", "#a54816", row => M.tankObservedValue(row, staleUs(run)/1e6), [5,4], true);
        if (limits) {
          add("target", "#526872", row => row.target_m ?? run.manifest.scenario?.target_level_m, [2,4]);
          const high = controller(run).high_switch_m;
          if (M.finite(high)) add("high switch", "#a12836", () => high, [2,4]);
        }
      }
    } else if (kind === "flow") {
      if (truth) add(thermal ? "circulation truth" : "pump inflow truth", "#1266a2", row => lpm(row.flow_m3_s));
      if (thermal && observed) add("flow observed", "#a54816", row => lpm(M.observedValue(row,"observed_flow_m3_s","flow",staleUs(run))),[5,4],true);
      if (thermal && limits) add("flow target", "#526872", () => (controller(run).target_i ?? 150000)/1e9*60000,[2,4]);
    } else {
      const part = kind;
      add(part+" requested", "#183340", row => thermal ? row["requested_"+part+"_command"] : row[part === "pump" ? "pump_command" : "requested_valve_command"],[],true);
      const leaseField = "lease_"+part+"_command";
      if (run.fields.includes(leaseField)) add(part+" live lease", "#176298", row => row[leaseField],[6,3],true);
      add(part+" fault-applied", "#a54816", row => thermal ? row["fault_"+part+"_command"] : row["applied_"+part+"_command"],[2,3],true);
      if (part !== "heat") add(part === "pump" ? (thermal ? "pump actual speed" : "actual inflow / Qmax") : "valve actual opening", "#126d5c", row => part === "valve" ? row.valve_opening : thermal ? row.pump_speed : row.flow_m3_s / (run.summary.parameters?.pump_max_m3_s ?? run.manifest.parameters?.pump_max_m3_s ?? .0004));
    }
    return specs;
  }

  function createChart(run, kind, host) {
    const thermal = run.topology === "thermal_loop";
    const title = kind === "temperature" ? (thermal ? "Temperature · °C (raw: K)" : "Tank level · m") : kind === "flow" ? "Flow · L/min (raw: m³/s)" : kind+" · normalized 0–1";
    const card = text("div", "", "chart-card"); card.append(text("h3",title));
    const plotHost = text("div","","plot"); card.append(plotHost); host.append(card);
    const specs = chartSeries(run,kind);
    const series = [{label:"absolute simulation s"}, ...specs.map(spec => ({label:spec.label, stroke:spec.color,width:1.7,dash:spec.dash,spanGaps:false,points:{show:false}, paths:spec.stepped ? uPlot.paths.stepped({align:1}) : undefined}))];
    const chartData = [run.rows.map(row => row.time_s), ...specs.map(spec => run.rows.map(row => { const v=spec.get(row); return M.finite(v) ? v : null; }))];
    const width = Math.max(230, plotHost.clientWidth);
    const cfg = {
      width, height:205, pxAlign:1, series,
      scales:{x:{time:false,range:() => [0,maxTime || 1]}, y:kind === "temperature" || kind === "flow" ? {range:(u,min,max) => { if (!M.finite(min)||!M.finite(max)) return [0,1]; const pad=Math.max((max-min)*.08,kind==="temperature" ? .5 : .1); return [min-pad,max+pad]; }} : {range:() => [-.04,1.04]}},
      axes:[{stroke:"#506671",grid:{stroke:"#e4ebee",width:1},size:35,values:(u,values) => values.map(v => fmt(v,v%1 ? 1 : 0)),label:"absolute s",labelSize:20}, {stroke:"#506671",grid:{stroke:"#e4ebee",width:1},size:47}],
      legend:{show:true,live:false}, cursor:{drag:{x:false,y:false},y:false,points:{show:false},sync:{key:"fluidlab-absolute-time"}},
      hooks:{setCursor:[u => { if (!syncing && M.finite(u.cursor.left) && u.cursor.left >= 0) setTime(u.posToVal(u.cursor.left,"x")); }]}
    };
    const plot = new uPlot(cfg,chartData,plotHost); plots.push({plot,host:plotHost});
  }
  function rebuildCharts() {
    plots.forEach(({plot})=>plot.destroy()); plots=[]; $("charts").replaceChildren();
    $("charts").classList.toggle("comparing",Boolean(comparison));
    for (const run of [current,comparison].filter(Boolean)) {
      const column = text("div","","chart-run");
      column.append(text("h3",run.name.replaceAll("_"," ")+" · "+run.evidence_level));
      const outcome=run.summary.evaluation || {};
      const detail=text("p",`Expectation: ${(outcome.expectation_pass ?? run.summary.all_checks_pass)===true?"PASS":(outcome.expectation_pass ?? run.summary.all_checks_pass)===false?"FAIL":"UNASSESSABLE"} · containment: ${outcome.containment_status ?? run.summary.containment ?? "UNAVAILABLE"}`,"caption");
      detail.style.marginBottom="8px";column.append(detail);
      $("charts").append(column);
      for (const kind of run.topology === "thermal_loop" ? ["temperature","flow","heat","pump","valve"] : ["temperature","flow","pump","valve"]) createChart(run,kind,column);
    }
    syncPlots();
  }
  function syncPlots() {
    syncing=true;
    for (const {plot} of plots) plot.setCursor({left:plot.valToPos(time,"x"),top:0});
    syncing=false;
  }
  function metric(label,value,detail="") { const el=text("div","","metric");el.append(text("span",label,"label"),text("strong",value)); if(detail)el.append(text("small",detail)); return el; }
  function setRunInfo() {
    const s=current.summary, evaluation=s.evaluation || {}, metrics=s.metrics || s;
    $("implementation").textContent=s.execution?.controller_implementation || current.manifest.execution?.controller_implementation || current.manifest.provenance?.controller_implementation || "Executed controller: inspect manifest";
    const expectation=evaluation.expectation_pass ?? s.all_checks_pass;
    const containment=evaluation.containment_status ?? s.containment ?? "UNAVAILABLE";
    const peak=metrics.global_sampled_peak_k;
    const bound=metrics.global_peak_upper_bound_k;
    const trip=metrics.first_trip_time_s ?? (M.finite(metrics.first_trip_time_us) ? metrics.first_trip_time_us/1e6 : s.trip_time_s);
    $("metrics").replaceChildren(
      metric("Scenario expectation",expectation===true ? "PASS" : expectation===false ? "FAIL" : "UNASSESSABLE"),
      metric("Containment", typeof containment === "string" ? containment : JSON.stringify(containment)),
      metric("Completion", evaluation.completion_status ?? ((s.completed_horizon ?? s.complete_horizon)===true ? "COMPLETE" : (s.completed_horizon ?? s.complete_horizon)===false ? "PARTIAL" : s.completion_status ?? "UNAVAILABLE")),
      metric(current.topology==="thermal_loop" ? "Global sampled peak" : "Sampled level peak",current.topology==="thermal_loop" ? fmt(celsius(peak),2)+" °C" : fmt(s.peak_level_m,4)+" m", "Sample maximum only"),
      metric("Conservative peak bound",current.topology==="thermal_loop" ? fmt(celsius(bound),2)+" °C" : fmt(s.continuous_peak_bound_m,4)+" m", "Includes max sample gap; numerical qualification in raw report"),
      metric("First trip",fmt(trip,3)+" s", metrics.first_trip_reason || s.trip_reason || "No recorded trip"));
    const scope=s.execution?.configuration_scope;
    $("outcome-explanation").textContent=(current.evidence_level.startsWith("UI_FIXTURE") ? "UI_FIXTURE — NOT_VERIFICATION. " : "") + (scope === "VARIANT" ? "VARIANT CONFIGURATION: this run cannot close the frozen-default release gate. " : scope === "FROZEN_DEFAULT" ? "Frozen default configuration. " : "") + "A passing expected hazard can still have FAILED containment. A stop request does not establish that a faulty actuator stopped. Physical validation remains NOT_STARTED.";
    const rules=evaluation.rules || s.rule_results || evaluation;
    $("rules").replaceChildren();
    const entries=Object.entries(rules).filter(([key,value])=> /^TH\d+|^R\d+/.test(key) && value && typeof value==="object");
    if (!entries.length && s.checks) {
      for (const [key,value] of Object.entries(s.checks)) entries.push([key,typeof value === "boolean" ? {status:value?"PASS":"FAIL",evidence:"Legacy tank result retained; inspect summary.json for the original evaluator."} : value || {status:"UNASSESSABLE",evidence:"No per-rule status recorded in this legacy summary."}]);
    }
    for (const [key,rule] of entries) {
      const el=text("div","","rule"); const left=text("div",key+" ");
      const status=rule.status || "UNASSESSABLE";
      left.append(text("span",status,"badge "+(status==="PASS"?"pass":status==="FAIL"||status==="UNASSESSABLE"?"fail":"warn")));
      el.append(left,text("p",typeof rule.evidence==="string"?rule.evidence:rule.rationale || JSON.stringify(rule.evidence ?? rule))); $("rules").append(el);
    }
    if (!entries.length) $("rules").append(text("p","No per-rule result recorded; inspect the raw summary. The viewer does not invent a pass.","caption"));
    const events=[];
    for (const event of s.scenario?.events || current.manifest.scenario?.events || []) {
      events.push({time:event.time_us/1e6,title:event.event_id,detail:event.type,kind:"fault"});
      if(M.finite(event.end_us)) events.push({time:event.end_us/1e6,title:event.event_id+" ended",detail:"Declared injection span ended",kind:"fault"});
    }
    const tankScenario=current.manifest.scenario;
    if (current.topology!=="thermal_loop" && tankScenario?.fault && tankScenario.fault!=="none") events.push({time:tankScenario.fault_at_s,title:tankScenario.fault,detail:"Declared synthetic injection",kind:"fault"});
    let priorState="";
    for (const row of current.rows) {
      if (state(row)!==priorState) { events.push({time:row.time_s,title:state(row),detail:reason(row)||row.record_type,kind:state(row)==="TRIPPED"?"trip":"state"}); priorState=state(row); }
      if(row.terminal_boundary) events.push({time:row.time_s,title:row.terminal_boundary,detail:"Model domain boundary; integration stopped",kind:"boundary"});
      if(["command_expiry","command_arrival","solver_failure"].includes(row.record_type)) events.push({time:row.time_s,title:row.record_type,detail:row.record_type==="solver_failure"?"Partial evidence; inspect run_failure in raw summary":"Lease / delivery event; inspect separate request and applied tracks",kind:"state"});
    }
    events.sort((a,b)=>a.time-b.time); $("events").replaceChildren();
    for (const event of events) { const el=text("button","",event.kind);el.type="button";el.append(text("strong",event.title.replaceAll("_"," ")),text("span",fmt(event.time,3)+" s · "+event.detail));el.addEventListener("click",()=>{pause();setTime(event.time);});$("events").append(el); }
    $("downloads").replaceChildren();
    const important=["telemetry.csv","summary.json","manifest.json"];
    for (const name of important) if(current.downloads[name]) addDownload(name,current.downloads[name],$("downloads"));
    const other=Object.entries(current.downloads).filter(([name])=>!important.includes(name));
    if(other.length){ const details=text("details","");details.append(text("summary",`${other.length} configuration / raw transport files`)); const box=text("div","","downloads");other.forEach(([name,path])=>addDownload(name,path,box));details.append(box);$("downloads").append(details); }
    $("provenance").textContent=JSON.stringify({evidence_level:current.evidence_level,display_policy:dataset.display_policy,physical_validation:dataset.physical_validation,board_execution:dataset.board_execution,manifest:current.manifest,retained_file_sha256:current.raw_hashes},null,2);
    $("all-metrics").textContent=JSON.stringify(metrics,null,2);
    $("fallback").replaceChildren();
    if(current.screenshot){const a=text("a","Download static figure");a.href=current.screenshot;a.download="";const img=document.createElement("img");img.src=current.screenshot;img.alt=current.name+" retained evidence: truth, observations, flow and actuator requests";img.loading="lazy";$("fallback").append(a,img);}
    else $("fallback").append(text("p","No screenshot fallback was exported for this development bundle."));
  }
  function addDownload(name,path,host){const a=text("a",name);a.href=path;a.download="";host.append(a);}
  function renderQuality(row) {
    $("quality").replaceChildren();
    if (!row) { const tr=document.createElement("tr"),td=text("td","No recorded sample at this absolute time. No values are extended beyond termination.");td.colSpan=7;tr.append(td);$("quality").append(tr);return; }
    const thermal=current.topology==="thermal_loop";
    const prefixes=thermal ? ["flow","hot","cold","wall","separate"] : ["level"];
    for(const prefix of prefixes){
      const tr=document.createElement("tr");let value,quality,source,receipt,good,age;
      if(thermal){ value=prefix==="flow" ? fmt(lpm(row.observed_flow_m3_s),3)+" L/min" : prefix==="separate" ? row.observed_separate_trip===null?"—":String(row.observed_separate_trip) : fmt(celsius(row["observed_"+prefix+"_temperature_k"]),3)+" °C"; quality=M.quality(row,prefix,staleUs(current));source=row[prefix+"_source_time_us"];receipt=row[prefix+"_receipt_time_us"];good=row[prefix+"_last_good_source_time_us"];age=row[prefix+"_age_us"]; }
      else{value=fmt(row.measured_level_m,4)+" m";quality=row.sensor_valid!==true?"invalid":M.finite(row.measurement_age_s)?row.measurement_age_s>staleUs(current)/1e6?"stale":"valid / fresh":"unavailable";source=M.finite(row.sample_time_s)?row.sample_time_s*1e6:null;receipt=M.finite(row.receipt_time_s)?row.receipt_time_s*1e6:null;good=row.sensor_valid===true?source:null;age=M.finite(row.measurement_age_s)?row.measurement_age_s*1e6:null;}
      tr.append(text("td",prefix),text("td",value));const cell=document.createElement("td");cell.append(text("span",quality,"badge "+(quality==="valid / fresh"?"pass":"warn")));tr.append(cell);
      for (const stamp of [source,receipt,good,age]) tr.append(text("td",fmt(M.finite(stamp)?stamp/1e6:null,3)));
      $("quality").append(tr);
    }
  }
  function setTime(next, sampleIndex=null) {
    time=Math.min(maxTime,Math.max(0,next));explicitIndex=sampleIndex;
    $("scrub").value=String(time);$("clock").textContent=fmt(time,3)+" s";
    const row=rowsAt(current,time); const thermal=current.topology==="thermal_loop";
    $("thermal-diagram").hidden=!thermal;$("tank-diagram").hidden=thermal;
    $("live-state").textContent=row?state(row)+(reason(row)?" · "+reason(row):""):"No recorded sample";
    $("live-state").className="badge "+(row?state(row):"warn");
    $("svg-wall").textContent="WALL "+fmt(celsius(row?.wall_temperature_k),2)+" °C";
    $("svg-hot").textContent=fmt(celsius(row?.hot_temperature_k),2)+" °C";$("svg-cold").textContent=fmt(celsius(row?.cold_temperature_k),2)+" °C";
    $("svg-pump").textContent=fmt(row?.pump_speed,3)+" actual speed";$("svg-valve").textContent=fmt(row?.valve_opening,3)+" actual opening";
    $("svg-flow").textContent=fmt(lpm(row?.flow_m3_s),3)+" L/min circulating flow";$("svg-heat").textContent=fmt(row?.applied_heat_w,0)+" W applied";$("svg-level").textContent=fmt(row?.level_m,4)+" m";
    const held=row && Math.abs(row.time_s-time)>1e-9;
    $("instant").textContent=row?`Retained sample at ${fmt(row.time_s,6)} s${held?"; cursor readout holds the preceding sample, no interpolation":""}. ${row.record_type || "controller tick"}${row.event_phase?" · "+row.event_phase:""}${row.event_ids?" · "+row.event_ids:""}.` : "This run has no evidence at the selected time.";
    $("sample-label").textContent=row?`Sample ${row.sample_id ?? "unrecorded"} · epoch ${row.epoch ?? "not recorded"} · ${row.record_type || "tick"}`:"No sample";
    renderQuality(row);syncPlots();
  }
  function pause(){playing=false;$("play").textContent="▶ Play";$("play").setAttribute("aria-label","Play replay");}
  function togglePlay(){if(playing){pause();return;}if(time>=maxTime)setTime(0);playing=true;lastFrame=0;$("play").textContent="Ⅱ Pause";$("play").setAttribute("aria-label","Pause replay");requestAnimationFrame(frame);}
  function frame(now){if(!playing)return;if(lastFrame)setTime(time+(now-lastFrame)/1000*Number($("speed").value));lastFrame=now;if(time>=maxTime)pause();else requestAnimationFrame(frame);}
  function changeRuns(){pause();current=byName.get($("scenario").value);comparison=byName.get($("compare").value)||null;if(comparison===current)comparison=null;maxTime=Math.max(current.lastTime,comparison?.lastTime||0);$("scrub").max=String(maxTime);time=Math.min(time,maxTime);setRunInfo();rebuildCharts();setTime(time);}
  $("play").addEventListener("click",togglePlay);
  $("scenario").addEventListener("change",changeRuns);$("compare").addEventListener("change",changeRuns);
  $("scrub").addEventListener("input",()=>{pause();setTime(Number($("scrub").value));});
  $("scrub").addEventListener("keydown",event=>{if(event.code==="Space"){event.preventDefault();togglePlay();}else if(["ArrowLeft","ArrowRight","Home","End"].includes(event.key)){event.preventDefault();pause();setTime(event.key==="Home"?0:event.key==="End"?maxTime:time+(event.key==="ArrowLeft"?-1:1));}});
  for(const [id,direction] of [["previous",-1],["next",1]])$(id).addEventListener("click",()=>{pause();const start=explicitIndex ?? M.indexAt(current.rows,time);const i=Math.max(0,Math.min(current.rows.length-1,start+direction));if(current.rows[i])setTime(current.rows[i].time_s,i);});
  for(const id of ["truth","observed","limits"])$(id).addEventListener("change",rebuildCharts);
  const observer=new ResizeObserver(()=>{for(const {plot,host} of plots)if(host.clientWidth>0)plot.setSize({width:Math.max(230,host.clientWidth),height:205});syncPlots();});observer.observe($("charts"));
  maxTime=Math.max(current.lastTime,comparison?.lastTime||0);$("scrub").max=String(maxTime);setRunInfo();rebuildCharts();setTime(0);
  const elapsed=performance.now()-window.replayLoadStarted;
  $("load-message").textContent=runs.some(r=>r.evidence_level.startsWith("UI_FIXTURE"))?"Development data includes UI_FIXTURE — NOT_VERIFICATION. Final release figures require actual retained C SIL runs.":"";
  $("load-time").textContent=`Initial local script + plot render: ${fmt(elapsed,1)} ms for ${runs.length} runs / ${runs.reduce((n,r)=>n+r.rows.length,0).toLocaleString()} full rows on this browser. This single observation excludes browser startup; repeated released-dataset measurements belong in the evidence record.`;
  document.documentElement.dataset.replayReady="true";
})();
