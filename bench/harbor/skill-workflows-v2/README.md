# Eval-opt v2: experimental workflow measurement

This is a separate, prospective study after the v1 semantic audit. It is not a
measured improvement over upstream. The stable kernel and every original v1 file
remain unchanged. See [PROTOCOL.md](PROTOCOL.md) for treatment, allocation,
continuation and claim rules.

## Run the offline controls

From the repository root, use the pinned controller and locked development tools:

```sh
uv sync --frozen --extra dev --python 3.13.12
uv run --frozen --extra dev python -I -B bench/harbor/skill-workflows-v2/run.py preserve
uv run --frozen --extra dev python -I -B -m pytest -p no:cacheprovider -rs bench/harbor/skill-workflows-v2/tests
uv run --frozen --extra dev python -I -B bench/harbor/skill-workflows-v2/tasks/qa.py
```

The default test process does not call models, load credentials or pull images.
Actual Docker fault controls require an explicitly selected, locally available
verifier image. Its image must contain `/candidate-root` as described by
`runtime/Verifier.Dockerfile`:

```sh
EVALOPT_V2_DOCKER_CONTROL_IMAGE=YOUR_LOCAL_VERIFIER_IMAGE \
  uv run --frozen --extra dev python -I -B -m pytest -p no:cacheprovider -rs \
  bench/harbor/skill-workflows-v2/tests/test_capture.py \
  bench/harbor/skill-workflows-v2/tests/test_verifier_docker.py
```

No default image pull or model/authentication fallback is permitted. Docker tests
create and remove only their own disposable, labeled containers. Missing Docker
controls are reported as skips; a skip is not a readiness pass.

## Experimental interfaces

`evalopt_v2` is a benchmark-local package, not a new stable kernel API. Records
use schema version `evalopt-workflows-v2/1`. Controller observations retain
execution status and evidence availability independently; task outcomes are
three-valued. An agent-reported discrepancy is not the unresolved
measurement-contract defect represented by `contract_dispute`.

The grader compares semantic cases and data-only review witnesses. Candidate
execution belongs in the separate Linux verifier. Local `trusted_fixture=True`
execution exists only for authored conformance fixtures; Python `-I` alone is
not a sandbox. Expected values remain outside the candidate chroot.

The controller owns capture, observation custody, visible-policy freezing,
verification and admission. Digests and producer labels cannot authenticate
agent-written records. Replay establishes consistency with retained observations,
not independent replication or the semantic truth of arbitrary programs.

The external supervisor records an absolute deadline before dispatch. A
confirmed stopped container and durable snapshot permit later admission under
the prospectively registered rule despite incomplete historical child ends or
partial usage. This never upgrades a timeout, infers an acknowledgment, retries
an agent failure or treats missing consumption as zero.

## Provenance and packaging

The runtime Docker recipes, Codex configuration and Harbor dependency lock were
copied from the v1 runtime at
`2deb53feb2bf20061a754b80ff93fccafeac5af7`; image identities still require fresh
preflight and freezing. The bounded Git index parser records its exact source
provenance. Other v2 modules are separate implementations, without imports from
the frozen v1 controller. The repository MIT license applies.

The pure analysis code reproduces task-level paired bootstrap contrasts from
retained records. Repetitions are not independent tasks. All scheduled rows stay
in the denominators; unresolved task-contract defects propagate across all arms.
The first report is offline conformance evidence. Live results require the
separate reviewed development gate and a frozen campaign.

## Freeze, dispatch and reproduce

Install the pinned Harbor controller separately from the project test environment:

```sh
uv venv --python 3.13.12 .venv-harbor
uv pip sync --python .venv-harbor/bin/python bench/harbor/skill-workflows-v2/runtime/requirements.lock
.venv-harbor/bin/python -I -B bench/harbor/skill-workflows-v2/run.py preflight \
  --agent-image sha256:AGENT_IMAGE_ID --verifier-image sha256:VERIFIER_IMAGE_ID
```

Preflight reads subscription permission and exact local versions; it makes no
model request and therefore does not establish returned model availability.
A live attempt must independently return the registered identity. Image aliases
are not accepted; all image arguments require complete local content IDs.

`run.py prepare` accepts a fresh `--destination`, `--task-root`, pinned local
`--upstream` checkout, two image IDs, and a controller-owned `--admission` receipt.
The receipt binds the current harness/skill/tasks to all five passing control
groups and separated accepting reviews. It also identifies development round
zero, or the one permitted revision with the complete preceding failed round.
Receipt labels establish neither reviewer identity nor authenticity; the
operator retains the actual source-bound controls and review artifacts.

Preparation preserves v1, copies the unchanged kernel, derives D, freezes the
complete upstream skill bundle, and writes an externally retainable registration
SHA-256. The source identity binds the complete inventory and admission receipt.
Keep that digest outside the campaign directory; a digest read only from the
same mutable directory is not an external anchor.

```sh
.venv-harbor/bin/python -I -B bench/harbor/skill-workflows-v2/run.py run \
  --campaign CAMPAIGN --registration-sha256 EXTERNALLY_RETAINED_SHA256 --limit 48
.venv-harbor/bin/python -I -B bench/harbor/skill-workflows-v2/run.py replay \
  --campaign CAMPAIGN --registration-sha256 EXTERNALLY_RETAINED_SHA256 --output NEW_REPORT.json
```

Both commands verify the external digest and execute the frozen controller copy.
The launcher rejects frozen bytecode caches before importing campaign modules.
The kernel import must resolve to the preserved frozen copy. Only one operator
can hold the campaign lock. Dispatch checks storage, existing owned containers
and current subscription permission before each attempt. Interrupted unsealed
attempts block automatic redispatch. Timeout outcomes remain failures even when
native runtime telemetry is unavailable; functional results remain separate.

Replay never runs candidate code. It checks artifact seals and visible-policy
replay, recomputes semantic grades from independently retained case records, and
reconciles every scheduled row. Disputes make contract-dependent summaries and
kernel ground-truth labels unknown across the complete matched task. Unsealed
attempts count toward resource completeness with unknown counters. Controller
wall time includes setup, capture and verification and is labeled separately
from agent time; it is not a token-matched or dollar-cost experiment.

A stopped archive containing symlinks, special nodes or owner-unreadable modes
is retained but is not materialized onto the host. Such a missing required
snapshot stops admission; no original artifact is rewritten to make it pass.
Candidate code remains confined to the external execution/verification path.
