"""One local Q007 verification run. Never starts the Render controller.

STARTED is durable and fail-closed after crashes; terminal runs cannot repeat.
This is not an installed server-side dispatcher or a server D acceptance.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

INPUT_SHA = 'ca4874635582acfffd70e3f94959a1af91d8e2fd'

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def durable(p, value):
    temp = p.with_suffix('.tmp')
    with temp.open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush(); os.fsync(f.fileno())
    os.replace(temp, p)
    fd = os.open(p.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def run(root, run_dir):
    root = Path(root).resolve(); run_dir = Path(run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / 'LOCK').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (run_dir / 'STARTED.json').exists() or (run_dir / 'RESULT.json').exists():
            raise RuntimeError('ALREADY_STARTED_OR_STOPPED_NO_REPLAY')
        request = json.loads((run_dir / 'REQUEST.json').read_text())
        if request['task'] != 'Q007' or request['original_number'] != 45 or request['input_sha'] != INPUT_SHA:
            raise RuntimeError('TASK_OR_INPUT_BINDING_MISMATCH')
        source = root / 'intro.html'; test = root / 'scripts/test-q007-explanations.cjs'
        if digest(source) != request['source_sha256'] or digest(test) != request['test_sha256']:
            raise RuntimeError('SOURCE_OR_TEST_BINDING_MISMATCH')
        now = time.time()
        if not 0 < request['deadline'] - now <= 1500:
            raise RuntimeError('DEADLINE_EXPIRED_OR_OVER_25_MINUTES')
        timeout = min(120, request['deadline'] - now)
        durable(run_dir / 'STARTED.json', {**request, 'started_at': now})
        result = {'task': 'Q007', 'original_number': 45, 'input_sha': INPUT_SHA,
                  'source_sha256': digest(source), 'test_sha256': digest(test),
                  'scope': 'LOCAL_NODE_DOM_VERIFICATION_ONLY', 'next_task_created': False,
                  'server_resumed': False, 'server_model_calls': 0,
                  'server_D_recorded': False, 'accepted_total_unchanged': 24}
        proc = None
        try:
            with (run_dir / 'TEST.log').open('xb') as log:
                proc = subprocess.Popen(['node', str(test), str(source)], cwd=root,
                                        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    code = proc.wait(timeout=timeout)
                    result.update(status='PASS_STOPPED' if code == 0 else 'FAIL_STOPPED', exit_code=code)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL); proc.wait()
                    result.update(status='TIMEOUT_STOPPED')
        except BaseException as error:
            if proc is not None and proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL); proc.wait()
            result.update(status='ERROR_STOPPED', error=type(error).__name__)
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                result['interrupted'] = True
        if digest(source) != request['source_sha256'] or digest(test) != request['test_sha256']:
            result.update(status='BINDING_CHANGED_STOPPED')
        result.update(finished_at=time.time(), log_sha256=digest(run_dir / 'TEST.log'))
        durable(run_dir / 'RESULT.json', result)
        return result

if __name__ == '__main__':
    outcome = run(Path(__file__).resolve().parent.parent, sys.argv[1])
    print(json.dumps(outcome, ensure_ascii=False))
    sys.exit(0 if outcome['status'] == 'PASS_STOPPED' else 1)
