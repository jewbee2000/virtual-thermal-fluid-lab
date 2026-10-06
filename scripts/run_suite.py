from pathlib import Path
import json
from fluidlab.runner import load_scenario,run,write_run

results=[]
for path in sorted(Path("scenarios").glob("*.json")):
    cfg=load_scenario(path)
    rows,summary=run(cfg)
    write_run(Path("artifacts")/cfg["name"],cfg,rows,summary)
    results.append(summary)
    print(cfg["name"], "PASS" if summary["all_checks_pass"] else "FAIL",summary["trip_reason"],summary["boundary"])
Path("artifacts/suite.json").write_text(json.dumps(results,indent=2)+"\n")
raise SystemExit(0 if all(r["all_checks_pass"] for r in results) else 1)
