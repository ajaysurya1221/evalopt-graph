#!/bin/bash
set -euo pipefail

tests_root=${EVALOPT_TESTS_ROOT:-/tests}
logs_root=${EVALOPT_LOGS_ROOT:-/logs}
python_bin=${EVALOPT_PYTHON:-python}
work_root=$(mktemp -d "${TMPDIR:-/tmp}/evalopt-verifier.XXXXXX")
trap 'rm -rf "$work_root"' EXIT
mkdir -p "$logs_root/verifier"
requested_arm=${EVALOPT_ARM:?set EVALOPT_ARM to U, M, G, or ALL}
candidate=${EVALOPT_CANDIDATE_COMMIT:?set the frozen full candidate commit}
wheel=("$tests_root"/evalopt_graph-*.whl)
[ "${#wheel[@]}" -eq 1 ] && [ -f "${wheel[0]}" ]

run_arm() {
  local arm=$1
  local output=$2
  local observation="$work_root/evalopt-observation-$arm.json"
  rm -f "$output" "$observation"
  local policy_source="${wheel[0]}"
  [ "$arm" != U ] || policy_source="$tests_root/ungoverned_policy.py"
  [ "$arm" != M ] || policy_source="$tests_root/minimal_policy.py"
  "$python_bin" "$tests_root/build_observation.py" \
    --template "$tests_root/observation.json" \
    --output "$observation" \
    --visible-artifact "$logs_root/artifacts/done.txt" \
    --wheel "${wheel[0]}" \
    --policy-source "$policy_source" \
    --candidate-commit "$candidate"
  expected_observation_sha256=$("$python_bin" - "$observation" <<'PY'
import hashlib, sys
from pathlib import Path
print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)
  case "$arm" in
    U) "$python_bin" "$tests_root/ungoverned_policy.py" "$observation" "$output" ;;
    M) "$python_bin" "$tests_root/minimal_policy.py" "$observation" "$output" ;;
    G) "$python_bin" -m evalopt_graph.harbor_adapter --input "$observation" --output "$output" ;;
    *) echo "invalid EVALOPT_ARM" >&2; exit 2 ;;
  esac
}

run_arm_safe() {
  local arm=$1
  local output=$2
  local observation="$work_root/evalopt-observation-$arm.json"
  local expected_observation_sha256=""
  set +e
  run_arm "$arm" "$output"
  local code=$?
  if [ "$code" -eq 0 ] && [ -s "$output" ]; then
    "$python_bin" - "$arm" "$output" "$candidate" "${wheel[0]}" "$tests_root" "$observation" "$expected_observation_sha256" <<'PY'
import hashlib, importlib.metadata, json, sys
from pathlib import Path
arm, output, candidate, wheel, tests_root, observation_file, expected_observation_sha256 = sys.argv[1:]
value = json.loads(Path(output).read_text())
observation = value.get("observation")
source_observation = json.loads(Path(observation_file).read_text())
identity = value.get("run_identity")
source = {"U": "ungoverned_policy.py", "M": "minimal_policy.py"}.get(arm)
source = Path(wheel) if source is None else Path(tests_root, source)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def hex_digest(item, size):
    return isinstance(item, str) and len(item) == size and not set(item) - set("0123456789abcdef")

fields = {
    "U": set("schema_version policy_acceptance kernel run_identity observation observation_sha256 observation_file_sha256 decision".split()),
    "M": set("schema_version policy_acceptance run_identity observation observation_sha256 observation_file_sha256 decision".split()),
    "G": set("schema_version policy_acceptance kernel run_identity observation observation_sha256 observation_file_sha256 policy_sha256 input_sha256 decision".split()),
}
valid = (
    set(value) == fields[arm]
    and value.get("schema_version") == "evalopt.harbor-decision.v1"
    and type(value.get("policy_acceptance")) is int
    and value["policy_acceptance"] in (0, 1)
    and isinstance(observation, dict)
    and isinstance(value.get("decision"), dict)
    and observation == source_observation
    and set(source_observation) == {"schema_version", "run_identity", "policy", "acceptance_input"}
    and source_observation.get("schema_version") == "evalopt.harbor-observation.v1"
    and all(isinstance(source_observation.get(field), dict) for field in ("run_identity", "policy", "acceptance_input"))
    and value["decision"].get("status") in {"ACCEPTED", "BLOCKED", "UNVERIFIED", "UNSUPPORTED", "FAILED"}
    and isinstance(value["decision"].get("reasons"), list)
    and all(isinstance(reason, str) for reason in value["decision"]["reasons"])
    and (value["policy_acceptance"] == 1) == (value["decision"].get("status") == "ACCEPTED")
    and isinstance(identity, dict)
    and identity == observation.get("run_identity")
    and set(identity) == {"schema_version", "candidate_commit", "wheel_sha256", "policy_source_sha256"}
    and identity.get("schema_version") == "evalopt.run-identity.v1"
    and identity.get("candidate_commit") == candidate
    and identity.get("wheel_sha256") == sha(wheel)
    and identity.get("policy_source_sha256") == sha(source)
    and hex_digest(value.get("observation_sha256"), 64)
    and value["observation_sha256"]
    == hashlib.sha256(json.dumps(observation, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    and value.get("observation_file_sha256") == expected_observation_sha256
    and sha(observation_file) == expected_observation_sha256
    and (arm != "U" or value.get("kernel") is None)
    and (
        arm != "G"
        or (
            value.get("kernel") == {
                "distribution": "evalopt-graph",
                "version": importlib.metadata.version("evalopt-graph"),
            }
            and hex_digest(value.get("policy_sha256"), 64)
            and hex_digest(value.get("input_sha256"), 64)
            and value["policy_sha256"] == value["decision"].get("policy_sha256")
            and value["input_sha256"] == value["decision"].get("input_sha256")
        )
    )
)
if not valid:
    raise SystemExit(65)
PY
    code=$?
  fi
  set -e
  if [ "$code" -ne 0 ] || [ ! -s "$output" ]; then
    "$python_bin" - "$arm" "$output" "$code" <<'PY'
import json, sys
from pathlib import Path
arm, output, code = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
output.write_text(json.dumps({
    "schema_version": "evalopt.harbor-decision.v1",
    "policy_acceptance": -1,
    "policy_error": {"arm": arm, "exit_code": code},
    "decision": {"status": "FAILED", "reasons": ["policy_subprocess_failed"]},
}, sort_keys=True) + "\n")
PY
  fi
}

decision="$logs_root/verifier/evalopt-decision.json"
if [ "$requested_arm" = ALL ]; then
  order=${EVALOPT_VERIFIER_ORDER:-U,M,G}
  case "$order" in
    U,M,G|U,G,M|M,U,G|M,G,U|G,U,M|G,M,U) ;;
    *) echo "invalid EVALOPT_VERIFIER_ORDER" >&2; exit 2 ;;
  esac
  IFS=, read -r first second third <<< "$order"
  for arm in "$first" "$second" "$third"; do
    run_arm_safe "$arm" "$work_root/evalopt-decision-$arm.json"
  done
  "$python_bin" - "$decision" "$order" "$work_root"/evalopt-decision-{U,M,G}.json <<'PY'
import json, sys
from pathlib import Path
output, order, *paths = sys.argv[1:]
decisions = {path.rsplit("-", 1)[-1].split(".")[0]: json.loads(Path(path).read_text()) for path in paths}
invariant_error = None
try:
    policies = {json.dumps(value["observation"]["policy"], sort_keys=True) for value in decisions.values()}
    inputs = {
        json.dumps(value["observation"]["acceptance_input"], sort_keys=True)
        for value in decisions.values()
    }
    identities = [value["run_identity"] for value in decisions.values()]
    if len(policies) != 1 or len(inputs) != 1:
        invariant_error = "policy_or_input_mismatch"
    elif (
        len({item["candidate_commit"] for item in identities}) != 1
        or len({item["wheel_sha256"] for item in identities}) != 1
    ):
        invariant_error = "run_identity_mismatch"
except (KeyError, TypeError):
    invariant_error = "missing_policy_observation"
Path(output).write_text(json.dumps({
    "schema_version": "evalopt.harbor-three-arm.v1",
    "verifier_order": order.split(","),
    "invariant_error": invariant_error,
    "decisions": decisions,
}, sort_keys=True) + "\n")
PY
else
  run_arm_safe "$requested_arm" "$decision"
fi

# This policy-verifier image contains no hidden grader. Correctness is graded only after Harbor stops.
"$python_bin" - "$requested_arm" "$decision" <<'PY'
import json, sys
from pathlib import Path
requested_arm, path = sys.argv[1], Path(sys.argv[2])
artifact = json.loads(path.read_text())
arms = artifact["decisions"] if requested_arm == "ALL" else {requested_arm: artifact}
reward = {}
for arm, result in arms.items():
    accepted = result.get("policy_acceptance")
    reward[f"{arm}_policy_acceptance"] = accepted if accepted in (0, 1) else -1
    reward[f"{arm}_policy_error"] = int(accepted not in (0, 1))
Path(path.parent / "reward.json").write_text(json.dumps(reward, sort_keys=True) + "\n")
PY
