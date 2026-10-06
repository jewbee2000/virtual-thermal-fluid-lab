"""Compare HTTPS-deployed bytes with the exact reviewed site artifacts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

root = Path(r'C:\Users\Walt\Documents\Codex\fluid-lab-import\virtual-fluid-lab')
site = Path(r'C:\Users\Walt\Documents\Codex\fluid-lab-site-release\docs')
base = 'https://walter.teitelbaum.us/'
prefix = Path('assets/projects/virtual-thermal-fluid-lab')
paths = [p.relative_to(site) for p in (site / prefix).rglob('*') if p.is_file()]
paths += [Path('2026/10/06/virtual-thermal-fluid-lab/index.html')]

def check(path):
    relative = path.as_posix()
    url = base + relative
    request = Request(url, headers={'Accept-Encoding': 'identity', 'User-Agent': 'VirtualThermalFluidLab-ReleaseAudit/0.1.0'})
    with urlopen(request, timeout=30) as response:
        data = response.read()
        headers = dict(response.headers)
        status = response.status
    expected = (site / path).read_bytes()
    return {'path': relative, 'url': url, 'status': status,
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'expected_sha256': hashlib.sha256(expected).hexdigest(),
            'content_type': headers.get('Content-Type'),
            'content_encoding': headers.get('Content-Encoding'),
            'result': 'PASS' if data == expected and status == 200 else 'FAIL'}

with ThreadPoolExecutor(max_workers=8) as pool:
    results = list(pool.map(check, sorted(paths)))
failures = [r for r in results if r['result'] != 'PASS']
report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
          'method': 'HTTPS GET, Accept-Encoding identity; SHA256 and direct-byte comparison to reviewed generated docs',
          'site_source_commit': 'be9e3b25beee8d34147cf2eea3dea39461c1f8f7',
          'site_merge_commit': '3fe8de66f153bf8bfd25325947343f05612509d1',
          'result': 'FAIL' if failures else 'PASS', 'files': len(results),
          'bytes': sum(r['bytes'] for r in results), 'assets': results, 'failures': failures}
(root / 'artifacts/M7-live-site-byte-audit.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps({k: report[k] for k in ('result', 'files', 'bytes', 'failures')}))
raise SystemExit(bool(failures))
