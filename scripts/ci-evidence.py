"""Collect only artifacts produced by this CI job, with explicit provenance."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMMON = ['phase3/browser-results.json', 'phase3/postgres-results.json',
          'phase3/browser-artifacts/*.png']
EXTRA = ['phase3/staging-browser-results.json', 'phase3/video-browser-results.json',
         'audit/staging9-instant-results.json', 'audit/phase2-content.json',
         'audit/professional96-*.json', 'audit/browser-functional.json']
REQUIRED = {
    'phase3': ['phase3/browser-results.json', 'phase3/postgres-results.json'],
    'integration': ['phase3/browser-results.json', 'phase3/postgres-results.json',
                    'phase3/staging-browser-results.json', 'phase3/video-browser-results.json',
                    'audit/staging9-instant-results.json', 'audit/phase2-content.json',
                    'audit/professional96-content.json', 'audit/browser-functional.json'],
}

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def context():
    return {key: os.environ.get(key) for key in (
        'GITHUB_REPOSITORY', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_JOB', 'GITHUB_SHA')}

def artifacts(kind):
    return sorted({p for pattern in COMMON + (EXTRA if kind == 'integration' else [])
                   for p in ROOT.glob(pattern) if p.is_file()})

def prepare(kind, output):
    output.mkdir(parents=True, exist_ok=False)
    removed = []
    for path in artifacts(kind):
        removed.append(str(path.relative_to(ROOT)))
        path.unlink()
    state = {'schema': 1, 'kind': kind, 'workspace': str(ROOT), 'prepared_at': now(),
             'context': context(), 'checkout_sha': subprocess.check_output(
                 ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
             'removed_prior_artifacts': removed}
    (output / 'prepared.json').write_text(json.dumps(state, indent=2) + '\n')
    print(json.dumps({'prepared': kind, 'removed_prior_artifacts': len(removed)}))

def collect(kind, output, status):
    state = json.loads((output / 'prepared.json').read_text())
    if state['kind'] != kind or state['workspace'] != str(ROOT) or state['context'] != context():
        raise RuntimeError('CI_EVIDENCE_CONTEXT_CHANGED')
    files = []
    report_errors = []
    for path in artifacts(kind):
        if path.is_symlink():
            raise RuntimeError('CI_EVIDENCE_SYMLINK')
        relative = path.relative_to(ROOT)
        target = output / 'files' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        if target.suffix == '.json':
            report = json.loads(target.read_text())
            if isinstance(report, dict) and report.get('errors'):
                report_errors.append(str(relative))
        files.append({'path': str(relative), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                      'bytes': target.stat().st_size})
    present = {item['path'] for item in files}
    missing = [path for path in REQUIRED[kind] if path not in present]
    state.update(collected_at=now(), job_status_before_collection=status,
                 files=files, missing_required=missing,
                 reports_with_errors=report_errors,
                 evidence_complete=status == 'success' and not missing and not report_errors,
                 note='Artifact existence alone is not a test pass; inspect workflow step results.')
    (output / 'manifest.json').write_text(json.dumps(state, indent=2) + '\n')
    print(json.dumps({'status': status, 'files': len(files), 'missing': missing}))
    return 1 if status == 'success' and (missing or report_errors) else 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'collect'])
    parser.add_argument('kind', choices=REQUIRED)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--status', choices=['success', 'failure', 'cancelled'], default='failure')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.kind, args.output)
    else:
        raise SystemExit(collect(args.kind, args.output, args.status))
