# Workflow benchmark integration

**Development implementation; no comparative result yet.** Read [STATUS.md](STATUS.md)
for executed evidence and remaining gates, and [PROTOCOL.md](PROTOCOL.md) for the
registered design. The stable acceptance kernel and deprecated runner are unchanged.

Use a Git checkout for the portable skill and benchmark. The Python distributions
serve the acceptance kernel; the skill is distributed in this repository.

The controller uses **CPython 3.13.12**. Container task interpreters are pinned
separately by their images. Run offline benchmark tests from the repository root:

```sh
.venv/bin/python -m pytest tests/test_skill_workflow_*.py
```

## Isolated runtime setup

Use a separate environment so Harbor does not become a kernel dependency:

```sh
uv venv --python 3.13.12 .venv-harbor
uv pip sync --python .venv-harbor/bin/python bench/harbor/skill-workflows-v1/runtime/requirements.lock
uv pip install --python .venv-harbor/bin/python --no-deps -e .
docker build -t evalopt-workflows-runtime:dev bench/harbor/skill-workflows-v1/runtime
docker build -t evalopt-workflows-verifier:dev --build-arg RUNTIME_IMAGE=evalopt-workflows-runtime:dev -f bench/harbor/skill-workflows-v1/runtime/Verifier.Dockerfile bench/harbor/skill-workflows-v1/runtime
```

Clone the upstream repository into a private working directory and check out
`b0618bc436ad893b3c5e84e55fba86586d34a404`. The integration reads the 27 shipped
skills from that revision's plugin manifest. Experimental and miscellaneous skills
not shipped by the plugin are excluded. Sources are not rewritten for the comparison.

The runtime uses existing ChatGPT authentication. It forwards only the selected
auth file, disables API fallback, and stores raw logs under the ignored `.benchmark/`
directory. Never publish that directory wholesale. Containers have no host workspace,
Docker socket, personal memory, or unrelated skills mounted. Harbor's Codex adapter
runs without an inner CLI sandbox inside the disposable Docker environment.

## Preflight and development pilot

Replace the example upstream path with the pinned checkout. Each output directory
must be new; earlier attempts remain available for audit.

```sh
.venv/bin/python bench/harbor/skill-workflows-v1/runtime/preflight.py --image evalopt-workflows-runtime:dev --output .benchmark/native-preflight --upstream .benchmark/upstream --live
PYTHONPATH=bench/harbor/skill-workflows-v1 .venv/bin/python -m runtime.offline_controls --directory .benchmark/oracle-controls
.venv-harbor/bin/python bench/harbor/skill-workflows-v1/campaign.py prepare-pilot --directory .benchmark/pilot --upstream .benchmark/upstream --preflight .benchmark/native-preflight --controls .benchmark/oracle-controls
.venv-harbor/bin/python bench/harbor/skill-workflows-v1/campaign.py run-pilot --directory .benchmark/pilot --upstream .benchmark/upstream
.venv/bin/python bench/harbor/skill-workflows-v1/campaign.py report --directory .benchmark/pilot
```

The development pilot, paused originally at nine of 36 outcomes, uses the approved
[partial-accounting amendment](ACCOUNTING_AMENDMENT.md). Its external controller
calls the original frozen runtime in a separate isolated Python process. Registration
binds the existing outcomes and pending schedule; it never rewrites an old finish
record or marks partial telemetry complete. The following commands require the
actual preserved campaign and frozen source paths:

```sh
.venv-harbor/bin/python bench/harbor/skill-workflows-v1/amended_pilot.py register --campaign /path/to/preserved-pilot --frozen-source /path/to/frozen/bench/harbor/skill-workflows-v1 --upstream /path/to/pinned-upstream --authorization 'partial accounting'
.venv-harbor/bin/python bench/harbor/skill-workflows-v1/amended_pilot.py verify --campaign /path/to/preserved-pilot --amendment-sha256 RECORDED_AMENDMENT_SHA256
.venv-harbor/bin/python bench/harbor/skill-workflows-v1/amended_pilot.py run --campaign /path/to/preserved-pilot --amendment-sha256 RECORDED_AMENDMENT_SHA256
.venv-harbor/bin/python bench/harbor/skill-workflows-v1/amended_pilot.py report --campaign /path/to/preserved-pilot --amendment-sha256 RECORDED_AMENDMENT_SHA256
```

Use the returned amendment identity verbatim. This incident-specific controller
accepts only pending first attempts. New infrastructure failures, unknown quota
permission, invalid runtime identity or unverifiable delegation still pause it.
It reports complete counters and partial observed lower bounds separately;
incomplete resource evidence cannot support an efficiency advantage claim.

`--live` is a bounded capability probe using subscription allowance; it is reported
separately from the 540 study trials. Preparation verifies native model/effort,
subagent accounting, skill loading and all twelve separate-verifier oracle controls.
Missing readiness evidence prevents pilot dispatch. Each stopped output is captured
before policy evaluation; hidden expected values remain outside candidate processes.
The separate verifier imports candidate code as an unprivileged child in a chroot
containing only runtime libraries and the stopped snapshot. An empty exit-zero
process cannot satisfy a hidden function case.

The development controller currently dispatches sequentially, within the registered
maximum of two concurrent trials. A source change requires a new development campaign
directory. An interrupted finalization is reconciled from its retained transaction;
agent timeouts remain failed outcomes even when usage is incomplete. Infrastructure
failure or incomplete accounting under the original strict policy pauses dispatch for inspection. Every dispatch also
requires fresh backend permission for ordinary included usage, read through the pinned
Codex app-server without a model call. Unknown permission fails closed.

Resume flags are explicit: `--retry-infrastructure`, `--resume-quota`, and
`--recover-interrupted`. None permits a second infrastructure retry or retrying an
agent error. Every invocation retains a scheduling receipt; a process lock prevents
two controllers from dispatching the same campaign.

## Held-out gate

`heldout_campaign.py freeze-heldout` requires a complete, reviewed pilot, the
explicit candidate-manifest hash, and the sealed 48-task source. It verifies that
the skill, upstream loader, agent configuration and images match the reviewed pilot.
A changed shared grader requires an explicit compatibility review bound to both
grader identities. The freeze excludes authoring/QA material and creates 432
scheduled trials. `run-heldout` requires the resulting registration hash explicitly
and checks source and sealed-task identities before every dispatch.

The current pilot does **not** pass this gate while it is incomplete. A legacy
v1 review still requires complete accounting. An explicit v2 review binds the approved
amendment, complete pilot outcome export, resource report and accounting rules;
the held-out registration then freezes those rules and their source identities.
Partial counters cannot satisfy a claim of exact accounting. Runtime identity,
provenance and delegation checks remain mandatory.
The 48-task candidate is private pending registration; its authoring and finite
oracle controls are not live workflow evidence.

Transfer selection is reproducible using `select_transfer.py`. Its runtime keeps
the original upstream verifier and required dependency access. Image resolution,
deadline controls, per-task readiness and immutable registration remain required.
Do not substitute a task after seeing scores. `transfer_campaign.py freeze` binds
the exact held-out registration and its immutable report to the prepared transfer
tasks. Dispatch requires all 432 primary trials accounted for and the same skill,
upstream loader, model configuration and CLI identity. No transfer model trial has
run; image and per-task preflight gates remain pending.

## Evidence and publication boundary

`evidence/` in a campaign directory holds the immutable schedule, every attempt,
stopped node data (bytes, types, modes and directories), visible check observations,
U/M/G decisions, hidden grade and usage record. `report` rechecks manifests and kernel
replay before producing outcomes and analysis. `private-harbor/` retains unsanitized
runtime traces separately. Content hashes bind bytes; controller custody supplies
origin. Neither a hash nor an agent-written success file authenticates a check.

Publish sanitized outcomes and provenance only after review. Do not equate a pilot,
authored conformance, terminal transfer subset or deterministic replay with independent
replication. Subscription consumption is measured in tokens, calls and seconds.

## Local publication candidate and replay

The exporter creates a new local directory; it never uploads or edits evidence.
It checks the retained report, registration and policy decisions, then rejects
sensitive content instead of silently rewriting it. Use the frozen benchmark
source when a development campaign predates the current working tree:

```sh
.venv/bin/python bench/harbor/skill-workflows-v1/publish_bundle.py export --campaign .benchmark/pilot --destination .benchmark/public-pilot-candidate --frozen-source /path/to/frozen/bench/harbor/skill-workflows-v1
.venv/bin/python bench/harbor/skill-workflows-v1/publish_bundle.py verify .benchmark/public-pilot-candidate
```

Offline verification requires the registered analysis library and kernel source,
plus CPython 3.13.12. It reproduces report arithmetic and acceptance decisions from
retained controller evidence. It does not rerun the agents, authenticate evidence
independently of the controller, or turn missing resource telemetry into a total.

An amended pilot uses a separate wrapper around that unchanged outcome bundle:

```sh
.venv-harbor/bin/python bench/harbor/skill-workflows-v1/amended_publish.py export --campaign /path/to/preserved-pilot --destination .benchmark/public-amended-pilot --amendment-sha256 RECORDED_AMENDMENT_SHA256
.venv/bin/python bench/harbor/skill-workflows-v1/amended_publish.py verify .benchmark/public-amended-pilot --amendment-sha256 RECORDED_AMENDMENT_SHA256
```

Export only while the controller is stopped. The wrapper preserves original grades,
binds the amendment and dispatch receipts, checks per-agent sums, and reports exact
counters separately from partial lower bounds. It excludes raw native logs and
private source paths. Public replay verifies arithmetic from sanitized controller
counters; it does not re-derive them from raw logs or recover missing consumption.

Held-out results use `heldout_publish.py`, which also releases the sealed tasks,
reference assets, grader sources and grading inputs. It requires all scheduled
outcomes or explicit, hash-bound unavailable-evidence receipts. Hidden-case replies
support replay of grade calculations; independent candidate execution is a separate
verification step. A narrowly reviewed synthetic-fixture allowance binds exact
source bytes, JSON pointers, values and case provenance. Other sensitive content
still prevents export; original artifacts and score records are never redacted.

Transfer uses `transfer_publish.py`. Its separate schema reproduces original reward
aggregation and validates retained artifact identities, without inventing U/M/G decisions or
claiming independent execution of the upstream verifier. Raw transfer archives
remain private pending separate review.
