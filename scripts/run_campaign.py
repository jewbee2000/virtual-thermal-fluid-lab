"""Run the frozen real-C thermal campaign and preserved C/Python tank regression."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from fluidlab.campaign import CASE_IDS, case_config, load_campaign, run_campaign, write_campaign
from fluidlab.provenance import canonical_json, file_sha256
from verify_host import benchmark as tank_benchmark


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe",type=Path,required=True)
    parser.add_argument("--out",type=Path,default=Path("artifacts/M5-campaign"))
    parser.add_argument("--case",choices=CASE_IDS,action="append")
    parser.add_argument("--skip-tank",action="store_true",help="selected development runs; full gate requires tanks")
    parser.add_argument("--repeat",action="store_true",help="repeat nominal and require identical same-machine telemetry bytes")
    args = parser.parse_args()
    started = time.perf_counter()
    args.out.mkdir(parents=True,exist_ok=False)
    report = dict(schema_version=1,contract="docs/CAMPAIGN.md",scope="HOST_SIL; assumed parameters; no board or physical validation",
                  executable_sha256=file_sha256(args.exe),cases={},tank_cases={},seeded_repeat=None,
                  exact_frozen_configs=True,full_release_campaign=False)
    selected = args.case or list(CASE_IDS)
    for name in selected:
        cfg = load_campaign(Path("scenarios/thermal")/(name+".json"))
        if cfg.to_dict()!=case_config(name).to_dict():
            raise ValueError(f"{name} is modified exploration; cannot satisfy frozen release campaign")
        out = args.out/name
        out.mkdir()
        rows,summary = run_campaign(cfg,args.exe,out/"wire")
        write_campaign(out,cfg,rows,summary,args.exe)
        report["cases"][name] = dict(expectation_pass=summary["evaluation"]["expectation_pass"],
            containment_status=summary["evaluation"]["containment_status"],completion_status=summary["evaluation"]["completion_status"],
            metrics=summary["metrics"],rules=summary["evaluation"]["rules"],manifest_sha256=file_sha256(out/"manifest.json"))
        print(f"{name}: expectation={summary['evaluation']['expectation_pass']} containment={summary['evaluation']['containment_status']}",flush=True)
    if not args.skip_tank:
        for path in sorted(Path("scenarios").glob("*.json")):
            summary = tank_benchmark(args.exe,path,args.out/"tank"/path.stem)
            report["tank_cases"][path.stem] = dict(expectation_pass=summary["all_checks_pass"],
                                                   containment_status=summary["containment"])
    if args.repeat:
        cfg = case_config("nominal_heat_step")
        out = args.out/"seeded-repeat"
        out.mkdir()
        rows,summary = run_campaign(cfg,args.exe,out/"wire")
        write_campaign(out,cfg,rows,summary,args.exe)
        nominal = args.out/"nominal_heat_step"/"telemetry.csv"
        equal = nominal.is_file() and nominal.read_bytes()==(out/"telemetry.csv").read_bytes()
        report["seeded_repeat"] = dict(status="PASS" if equal else "FAIL",seed=cfg.seed,telemetry_sha256=file_sha256(out/"telemetry.csv"),
                                      comparison="identical raw telemetry bytes on same machine; wall/provenance excluded")
    report["wall_elapsed_s"] = time.perf_counter()-started
    report["expectation_pass"] = all(c["expectation_pass"] for c in report["cases"].values()) and all(c["expectation_pass"] for c in report["tank_cases"].values()) and (not args.repeat or report["seeded_repeat"]["status"]=="PASS")
    report["full_release_campaign"] = set(selected)==set(CASE_IDS) and len(report["tank_cases"])==7 and args.repeat and report["expectation_pass"]
    report["artifacts"] = {p.relative_to(args.out).as_posix():file_sha256(p) for p in args.out.rglob("manifest.json")}
    (args.out/"campaign.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")
    return 0 if report["expectation_pass"] else 1


if __name__=="__main__":
    raise SystemExit(main())
