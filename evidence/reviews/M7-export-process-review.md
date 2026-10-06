# Final export and process-evidence review

Read-only bounded review by release_discovery on2026-10-06. ACCEPT after repairs.
No simulations, full dataset audit, installations or file writes were performed.

Inspected audit_exports.py, benchmark_campaign.py, c_controller.py, replay
exporter/UI, schemas and relevant tests. Executed44 lightweight Python3.12
probes:25 audit/gzip guards,17 PID guards and2 Windows path-collision guards.
All passed.

The reviewer initially found JSON exponent overflow (`1e309`) could bypass the
JSON token guard; omitted manifest hashes could bypass original-byte checks;
gzip output paths could alias by case on Windows. Repairs reject nonfinite
parsed floats, require six core files and complete wire captures, and reject
case-insensitive output/run aliases before writes. Criteria are unchanged.

Actual parent/child identity now requires launcher, scientific Python owner and
each C child in OS peaks. Missing or malformed proof is UNASSESSABLE. Gzip
round-trips original bytes, retains every row, separates packaged/original hashes
and uses deterministic headers. Fresh reproduction/performance remain separate.

Reviewed SHA256:
- auditor f64c4883d191118f23f9b7869b9b6a98bbcf02a59a55583933ed979500997a7d
- benchmark 2de4ead293b3bc2321de3de64a811eea5b88075be6c13afa0b537917d0d25308
- replay exporter ea06c1e5a935a6b1196bb870d9af90385a6d84d86a455e340c01e873d1d02f37
