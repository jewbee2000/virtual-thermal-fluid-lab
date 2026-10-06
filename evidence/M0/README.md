# Executed native Windows baseline, 2026-10-06

Actual commands: uv sync --locked (exit0); uv run python -m unittest discover -s tests -v (exit0, 20 tests/8.073s); uv run python scripts/run_suite.py (exit0, seven expectations). Commands used uv0.12.19 from C:\Users\Walt\.local\bin after adding it to process PATH. Python3.12.2; Windows-11-10.0.26300-SP0; NumPy2.3.5/SciPy1.17.0/Matplotlib3.10.8.

uv.lock SHA256: 76472376ec629c6fb1da220501125f413dc2944f76e75139283ea2cb3ca7bcd0.

unit-tests.txt, scenario-console.txt and suite.json retain actual output. artifacts/M0-starter retains full pre-correction traces locally. The old manifest defects are intentionally not corrected in that snapshot. examples/ remains inherited evidence, not a new run. No Git repository existed at baseline execution, so manifests correctly had no project revision, although their implementation could misattribute a caller revision (M1 repair).

The stuck-on pump expectation passed because high_high occurred and the full boundary was reached. Containment failed. Physical validation NOT_STARTED; board NOT_EXECUTED. Root MIT selected by Walter; starter authored by Walter.
