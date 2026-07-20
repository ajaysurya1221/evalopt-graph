# Harbor 0.18 kernel-adapter conformance

This repository-authored task validates artifact mapping and U/M/G verifier wiring. It is integration
conformance, not an external benchmark or holdout.

Harbor owns the agent, environment, separate verifier, trial, reward, logs, and artifacts. A
controller-owned builder derives a visible gate from the stopped output and binds the current source
version, built wheel, policy source, and canonical observation. It never reads hidden grader output.

## Prepare a clean task copy

Start from a clean checkout. Build the wheel and copy the task to temporary directories so no generated
artifact enters the repository:

```bash
test -z "$(git status --porcelain)"
source_version="$(git rev-parse HEAD)"
wheel_dir="$(mktemp -d)"
task_dir="$(mktemp -d)"

uv build --wheel --out-dir "$wheel_dir"
cp -R bench/harbor/. "$task_dir/"
cp "$wheel_dir"/evalopt_graph-*.whl "$task_dir/conformance/tests/"
```

## Validate configuration without Docker

```bash
(
  cd "$task_dir"
  uvx --from harbor==0.18.0 harbor run -c job.yaml --print-config \
    >"$task_dir/resolved-config.json"
)
```

This validates Harbor's resolved job/task shape. It is not a task execution.

## Run the deterministic Docker smoke

With a working Docker daemon, apply all three verifier policies to one stopped Oracle output. Reusing
the stopped output is intentional here: it removes model variance while testing policy wiring.

```bash
harbor_output="$(mktemp -d)"
(
  cd "$task_dir"
  uvx --from harbor==0.18.0 harbor run \
    -p conformance -a oracle -e docker -k 1 -n 1 \
    --ve EVALOPT_ARM=ALL \
    --ve EVALOPT_VERIFIER_ORDER=U,M,G \
    --ve EVALOPT_CANDIDATE_COMMIT="$source_version" \
    --verifier-include-logs evalopt-decision.json \
    --job-name evalopt-conformance-all \
    -o "$harbor_output"
)
```

`EVALOPT_ARM=U`, `M`, or `G` remains available for focused diagnosis. With `ALL`, one verifier artifact
contains the three arm decisions and standard `reward.json` metrics; those are three policy decisions,
not three independent agent trials.

## Grader separation

The policy-verifier image is built only from `conformance/tests/` and contains no grader. The public
deterministic oracle is packaged separately under `conformance/grader/` and is exercised after the
policy output freezes. External campaigns must replace it with an official or independently sealed
grader and follow [`docs/BENCHMARK_PROTOCOL.md`](../../docs/BENCHMARK_PROTOCOL.md).

Passing this smoke demonstrates that the task, observation builder, policies, artifact mapping, and
grader boundary fit together. It does not establish model capability, comparative governance
performance, or an external result.

Delete `wheel_dir`, `task_dir`, and `harbor_output` when finished. Never commit wheels, task output,
transcripts, rewards, resolved configuration, or generated metrics.
