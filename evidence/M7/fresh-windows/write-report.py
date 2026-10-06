"""Summarize already executed checks; no simulation or audit is rerun."""
import hashlib
import json
from pathlib import Path
import re

root = Path(__file__).resolve().parents[3]
release = root / "artifacts/release"
checks = release / "checks"
read = lambda path: json.loads(path.read_text(encoding="utf-8-sig"))
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
gate_names = ("01-uv-sync", "02-host-build-ctest", "03-device-configure", "04-device-build", "05-device-ctest",
              "06-full-unit", "07-python-tank-suite", "08-thermal-benchmarks", "09-full-campaign",
              "10-full-refinement", "11-independent-export-audit", "12-pico-cross-build")
commands = [read(checks/f"{name}.json") for name in gate_names]
campaign = read(release / "campaign/campaign.json")
refinement = read(release / "refinement/refinement.json")
nominal = read(release / "campaign/nominal_heat_step/manifest.json")
execution = nominal["execution"]
pico = read(release / "pico/build-evidence.json")
audit = read(checks / "11-independent-export-audit.stdout.txt")
units = (checks / "06-full-unit.stderr.txt").read_text(encoding="utf-8")
unit_match = re.search(r"Ran (\d+) tests in ([0-9.]+)s", units)
manifest_hashes = {
    path.relative_to(release).as_posix(): digest(path)
    for name in ("campaign", "refinement", "thermal", "tank")
    for path in sorted((release / name).rglob("manifest.json"))
}
report = dict(
    schema_version=1,
    scope="clean native Windows reproduction; actual freshly built portable C host; assumed parameters",
    git_revision=execution["git_revision"], git_dirty=execution["git_dirty"],
    source_sha256=execution["source_sha256"], source_files_sha256=execution["source_files_sha256"],
    source_inclusion=execution["source_inclusion"], source_exclusion=execution["source_exclusion"],
    lock_sha256=execution["lock_sha256"],
    controller_sha256=execution["controller_sha256"],
    compiler_build_metadata=execution["compiler_build_metadata"],
    python=execution["python"], numpy=execution["numpy"], scipy=execution["scipy"],
    commands=commands,
    all_gates_exit_zero=all(command["exit_code"] == 0 for command in commands),
    failures=[command for command in commands if command["exit_code"] != 0],
    diagnostic_report_write_failure=read(checks/"13-report-write.json"),
    units=dict(count=int(unit_match[1]), test_elapsed_s=float(unit_match[2]), status="PASS" if units.rstrip().endswith("OK") else "FAIL"),
    campaign=dict(full_release_campaign=campaign["full_release_campaign"],
                  expectation_pass=campaign["expectation_pass"], thermal_cases=len(campaign["cases"]),
                  c_tank_cases=len(campaign["tank_cases"]), seeded_repeat=campaign["seeded_repeat"],
                  wall_elapsed_s=campaign["wall_elapsed_s"],
                  expected_failed_containment=[name for name, value in campaign["cases"].items() if value["containment_status"] == "FAILED"]),
    refinement=dict(status=refinement["status"], full_refinement_gate=refinement["full_refinement_gate"],
                    solver_cases={name:value["status"] for name,value in refinement["solver"].items()},
                    thermal_tick_cases={name:value["status"] for name,value in refinement["thermal_tick"].items()},
                    tank_tick_cases={name:value["status"] for name,value in refinement["tank_tick"].items()},
                    thresholds=refinement["thresholds"]),
    independent_audit=audit,
    pico=dict(source_revision=pico["source_revision"], source_dirty=pico["source_dirty"],
              sdk_revision=pico["sdk_revision"], tinyusb_revision=pico["tinyusb_revision"],
              compiler=pico["compiler"], cmake=pico["cmake"], ninja=pico["ninja"], outputs=pico["outputs"]),
    artifact_manifest_sha256=manifest_hashes,
    report_inputs_sha256={name:digest(release/name) for name in (
        "campaign/campaign.json", "refinement/refinement.json", "thermal/verification.json", "pico/build-evidence.json")},
    performance="NOT_EXECUTED_BY_THIS_TASK", board_execution="NOT_EXECUTED", physical_validation="NOT_STARTED",
)
(checks / "reproduction.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8", newline="\n")
print(json.dumps(dict(status="PASS" if report["all_gates_exit_zero"] else "FAIL", checks=len(commands),
                     unit_tests=report["units"]["count"], source_sha256=report["source_sha256"],
                     controller_sha256=report["controller_sha256"], manifest_hashes=len(manifest_hashes),
                     report=str(checks/"reproduction.json")), indent=2))
