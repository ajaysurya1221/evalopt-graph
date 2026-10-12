"""Run-local Fable process accounting. Not a product or a security sandbox."""
import argparse
import fcntl
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from datetime import datetime, timezone

EXPECTED_MODEL = 'claude-fable-5-1'
PLAN_SHA = '697f3fd7fa61b294146fff13868c87d6762d00395f39d8085ba52a111eb22b3c'
ADMISSION_END = '2026-10-13T04:37:18+00:00'
RUN_END = '2026-10-13T05:22:18+00:00'


def classify(exit_code, timed_out, raw, report, scope_errors):
    reasons = []
    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError('JSON result must be an object')
    except (ValueError, TypeError):
        obj = {}
        reasons.append('invalid_json')
    if timed_out:
        reasons.append('timeout')
    if exit_code != 0:
        reasons.append('nonzero_exit')
    if obj.get('subtype') != 'success' or obj.get('is_error') is not False:
        reasons.append('native_failure')
    usage = obj.get('modelUsage', {})
    if not isinstance(usage, dict) or list(usage) != [EXPECTED_MODEL]:
        reasons.append('model_identity')
    elif not isinstance(usage[EXPECTED_MODEL], dict) or usage[EXPECTED_MODEL].get('provider') != 'firstParty':
        reasons.append('provider_identity')
    if not report or not re.search(r'(?:Status\s*:?\s*DONE|Verdict\s*:?\s*ACCEPT)', report.replace('**', '')):
        reasons.append('missing_or_nonaccepted_report')
    if scope_errors:
        reasons.append('out_of_scope')
    return {'state': 'PARTIAL' if reasons else 'DONE', 'reasons': reasons,
            'scope_errors': scope_errors, 'usage': obj.get('usage'),
            'model_usage': usage, 'native_turns': obj.get('num_turns'),
            'effective_effort': 'not exposed in terminal JSON'}


def changed_paths(cwd, base):
    tracked = subprocess.check_output(['git', 'diff', '--name-only', '-z', base], cwd=cwd).split(b'\0')
    untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '-z'], cwd=cwd).split(b'\0')
    return sorted({os.fsdecode(p) for p in tracked + untracked if p})


def scope_errors(paths, allow):
    return [p for p in paths if not any(fnmatch.fnmatchcase(p, pattern) for pattern in allow)]


def execute(command, cwd, output, stderr, timeout):
    started = time.monotonic()
    with output.open('xb') as out, stderr.open('xb') as err:
        child = subprocess.Popen(command, cwd=cwd, stdout=out, stderr=err, start_new_session=True)
        timed_out = False
        try:
            code = child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(child.pid, signal.SIGTERM)
            try:
                code = child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                code = child.wait()
    return {'pid': child.pid, 'exit_code': code, 'timed_out': timed_out,
            'elapsed_seconds': round(time.monotonic() - started, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('config', type=Path)
    args = ap.parse_args()
    cfg = json.loads(args.config.read_text())
    root = Path(cfg['plan_root']).resolve()
    cwd = Path(cfg['cwd']).resolve()
    now = datetime.now(timezone.utc)
    end = datetime.fromisoformat(RUN_END)
    if now >= datetime.fromisoformat(ADMISSION_END) and not cfg.get('wrapup', False):
        raise SystemExit('task admission closed')
    if now >= end:
        raise SystemExit('run deadline exceeded')
    if hashlib.sha256((root / 'exec/PLAN.md').read_bytes()).hexdigest() != PLAN_SHA:
        raise SystemExit('approved plan changed')
    bad_env = [k for k in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL',
                          'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY') if os.environ.get(k)]
    if bad_env:
        raise SystemExit('provider routing variables present: ' + ','.join(bad_env))
    output_dir = root / 'logs' / cfg['id']
    output_dir.mkdir()  # Refuse accidental replay/overwrite of an existing attempt.
    slot = None
    for n in range(2):
        handle = (root / 'logs' / f'fable-slot-{n}.lock').open('a')
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            slot = handle
            break
        except BlockingIOError:
            handle.close()
    if slot is None:
        raise SystemExit('two Fable slots occupied')
    initial = scope_errors(changed_paths(cwd, cfg['base']), cfg['allow'])
    if initial:
        raise SystemExit('preexisting out-of-scope changes: ' + ','.join(initial))
    report = Path(cfg['report'])
    if report.exists():
        raise SystemExit('report already exists; use a new attempt id and path')
    prompt = Path(cfg['prompt']).read_text()
    command = ['claude', '-p', prompt, '--model', 'claude-fable-5-1[1m]', '--effort', cfg['effort'],
               '--permission-mode', 'bypassPermissions', '--max-turns', str(cfg['turns']),
               '--output-format', 'json', '--no-session-persistence', '--safe-mode',
               '--append-system-prompt', (root / 'exec/CONTRACT.md').read_text()]
    record = {'id': cfg['id'], 'started_at': now.isoformat(), 'cwd': str(cwd),
              'base': cfg['base'], 'requested_model': 'claude-fable-5-1[1m]',
              'requested_effort': cfg['effort'], 'turn_cap': cfg['turns'], 'command': command,
              'allow': cfg['allow'], 'report': str(report), 'supervisor_pid': os.getpid()}
    (output_dir / 'start.json').write_text(json.dumps(record, indent=2) + '\n')
    timeout = min(cfg['timeout_seconds'], (end - now).total_seconds())
    result = execute(command, cwd, output_dir/'native.json', output_dir/'stderr.txt', timeout)
    errors = scope_errors(changed_paths(cwd, cfg['base']), cfg['allow'])
    result.update(classify(result['exit_code'], result['timed_out'],
                           (output_dir/'native.json').read_text(),
                           report.read_text() if report.exists() else '', errors))
    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    result['head'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=cwd, text=True).strip()
    (output_dir/'finish.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('state','reasons','head','elapsed_seconds')}), flush=True)
    slot.close()
    raise SystemExit(0 if result['state']=='DONE' else 1)


if __name__ == '__main__':
    main()
