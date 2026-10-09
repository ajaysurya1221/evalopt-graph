# Development overhead accounting draft

Three complete capability probes account for **223,938 input tokens, 1,017 output
tokens, 17 completed response records, 10 tool calls, and 73.168 summed parent
wall seconds**. The original pilot-v1 attempt has unavailable consumption.
Probe 02 has no retained files establishing dispatch or consumption. Unavailable
is not zero; these figures do not establish total overhead or an efficiency result.

Probe 04 is also referenced by readiness and is counted once. Token and call
counts sum exclusive agent observations; time sums parent intervals without
adding concurrent child durations. Engineering-assistant usage and unmeasured
setup or verification overhead are outside this ledger. The registered pilot-v2
campaign is reported separately. No dollar costs are inferred.

`capability-probes.json` is byte-identical to the committed sanitized source at
the repository path and commit recorded in `overhead-ledger.json`. The original
finish and manifest are unchanged, safe JSON projections; raw native logs and
the other referenced private artifacts are excluded. All 12 private manifest
entries were hash-checked locally. The readiness mirror was checked against its
registered private tree and the committed probe summary. Those local checks are
supplied provenance, not publicly replayable raw-log verification or authentication.

Run this standard-library-only check from this folder. It verifies the draft's
checksums, the retained finish's manifest binding, and recomputes probe arithmetic:

```sh
python3 - <<'PY'
import hashlib, json
from decimal import Decimal
from pathlib import Path
sha = lambda raw: hashlib.sha256(raw).hexdigest()
read = lambda name: json.loads(Path(name).read_bytes())
envelope = read('CHECKSUMS.json')
assert set(envelope['files']) == {p.name for p in Path('.').iterdir() if p.name != 'CHECKSUMS.json'}
for name, expected in envelope['files'].items():
    raw = Path(name).read_bytes()
    assert expected == {'sha256': sha(raw), 'size': len(raw)}
assert envelope['bundle_id'] == sha(json.dumps(envelope['files'], sort_keys=True, separators=(',', ':')).encode())
ledger, probes = read('overhead-ledger.json'), read('capability-probes.json')['probes']
assert sha(Path('capability-probes.json').read_bytes()) == ledger['provenance']['capability_source']['sha256']
keys = ('input_tokens', 'output_tokens', 'model_calls', 'tool_calls')
totals, seconds, complete = dict.fromkeys(keys, 0), Decimal(0), 0
for probe in probes:
    if probe['usage'] is None:
        continue
    events = probe['usage_events']
    parent, = [event for event in events if event['parent_id'] is None]
    assert len({event['agent_id'] for event in events}) == len(events)
    assert set(parent['roster']) == {event['agent_id'] for event in events}
    assert all(event['complete'] and event['scope'] == 'agent_exclusive' for event in events)
    for key in keys:
        measured = sum(event[key] for event in events)
        assert measured == probe['usage'][key]
        totals[key] += measured
    assert parent['wall_seconds'] == probe['usage']['wall_seconds']
    seconds += Decimal(str(parent['wall_seconds']))
    complete += 1
assert ledger['summary']['observed_complete_probe_totals'] == {**totals, 'parent_wall_seconds': str(seconds)}
assert complete == ledger['summary']['complete_capability_probes']
source = ledger['provenance']['original_attempt']
assert sha(Path(source['finish_file']).read_bytes()) == source['finish_sha256']
assert sha(Path(source['manifest_file']).read_bytes()) == source['manifest_sha256']
binding, = [row for row in read(source['manifest_file'])['artifacts'] if row['path'] == 'finish.json']
assert binding['sha256'] == source['finish_sha256']
assert binding['size'] == Path(source['finish_file']).stat().st_size
assert read(source['finish_file'])['usage']['accounting_status'] == 'unavailable'
assert all(row['exact_usage'] is None for row in ledger['records'] if row['accounting_status'] == 'unavailable')
assert ledger['summary']['efficiency_comparison_eligible'] is False
print(json.dumps(ledger['summary'], sort_keys=True))
PY
```

Checksums establish retained content identity. Public reproduction is limited to
the displayed sanitized evidence and arithmetic; it cannot recover missing usage
or independently rerun or authenticate the original agents.
