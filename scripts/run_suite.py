from pathlib import Path
import argparse,json
from fluidlab.runner import load_scenario,run,write_run

parser = argparse.ArgumentParser(description="Run the preserved seven tank scenarios")
parser.add_argument("--out", type=Path, default=Path("artifacts"))
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
results=[]
for path in sorted(Path("scenarios").glob("*.json")):
    cfg=load_scenario(path)
    rows,summary=run(cfg)
    write_run(args.out/cfg["name"],cfg,rows,summary)
    results.append(summary)
    print(cfg["name"], "PASS" if summary["all_checks_pass"] else "FAIL",summary["trip_reason"],summary["boundary"])
(args.out/"suite.json").write_text(json.dumps(results,indent=2,allow_nan=False)+"\n",encoding="utf-8")
raise SystemExit(0 if all(r["all_checks_pass"] for r in results) else 1)
