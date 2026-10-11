# Development round 0: stopped before the fourth agent dispatch

**48 rows remain accounted for: 3 finalized, 1 unfinalized setup failure, and 44 unstarted.**
The original frozen report has 45 unknown outcomes and does not pass development
admission. It supports no workflow comparison or improvement claim.

| Evidence | What it establishes | Limit |
|---|---|---|
| [Original frozen report](report.json) | Three finalized outcomes, four retained attempts, all 48 scheduled rows | The three completed runs concern one blocker task; there is no complete four-arm block. |
| [Sanitized inputs and attempt ledger](inputs.json) | Original outcomes, unknown rows, measured counters and raw artifact hashes | Projections do not authenticate controller observations or reproduce model behavior. |
| [Preservation and replay receipt](receipt.json) | All 990 original campaign files/modes were preserved; frozen replay passed | Full native histories remain private; their bytes are not published. |

The fourth attempt completed its initial visible check with the expected
unavailable-evidence exit code, then failed during Harbor's Compose network
startup. It has no agent identity, workflow exposure, native execution, grade or
final record. The controller correctly stopped instead of dispatching a later
row. It must not be counted as an agent timeout, failed solution or completed run.

Docker recorded a network-create request immediately before the failure. A
separate offline control subsequently returned `all predefined address pools have
been fully subnetted` without creating a network. This confirms current automatic
pool exhaustion and strongly supports the startup diagnosis; the original
exception message was not retained, so its exact cause cannot be reconstructed
from that message. Historical containers and networks remain intact.

No grades, capture, skills, task contracts or original registration were repaired.
The approved single development revision will use a separately reviewed network
controller and a new registration for all 48 rows. This consumes the sole revision
allowance; it is not a retry of the unfinalized attempt. Round 0 stays stopped and
will remain separate from the revised stage. Held-out admission still requires
all revised outcomes resolved and the original difficulty gate to pass.

## Reproduce the public projection

From the repository root:

```sh
python3 -I -B results/skill-workflows-v2/development-round-zero-stopped-2026-10-11/reproduce.py
```

The standard-library check verifies artifact and analysis-source hashes, the
schedule partition, resource arithmetic, original gate and complete report. It
runs no candidate code, Docker commands or models. Private controller replay also
verified finalized artifact seals, retained grading, native records and boundary
observations; public arithmetic replay is a narrower check.

Three finalized attempts have complete token/call accounting. The unfinished
attempt has unavailable accounting, which remains null. Controller time covers
setup, execution, capture and verification; it is not agent-only time. No dollar
cost or efficiency claim is made. Every attempt is identified by registration,
trial and attempt number so a later development revision cannot double-count or
replace it.
