from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from evalopt_graph.harbor_adapter import evaluate_payload, main

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "bench" / "harbor" / "conformance"


def _payload() -> dict:
    payload = json.loads((FIXTURE / "tests" / "observation.json").read_text())
    payload["run_identity"] = {
        "schema_version": "evalopt.run-identity.v1",
        "candidate_commit": "a" * 40,
        "wheel_sha256": "b" * 64,
        "policy_source_sha256": "c" * 64,
    }
    return payload


def test_governed_arm_maps_visible_observation_to_decision_artifact() -> None:
    payload = _payload()
    result = evaluate_payload(payload)
    payload["acceptance_input"]["gate_results"] = [["tests", "FAIL"]]

    assert result["schema_version"] == "evalopt.harbor-decision.v1"
    assert result["policy_acceptance"] == 1
    assert result["decision"]["status"] == "ACCEPTED"
    assert result["observation"] == _payload()
    assert result["policy_sha256"] == result["decision"]["policy_sha256"]
    assert result["input_sha256"] == result["decision"]["input_sha256"]
    assert result["observation"]["acceptance_input"]["gate_results"] == [["tests", "PASS"]]


def test_governed_arm_rejects_failed_visible_gate() -> None:
    payload = _payload()
    payload["acceptance_input"]["gate_results"] = [["tests", "FAIL"]]

    result = evaluate_payload(payload)

    assert result["policy_acceptance"] == 0
    assert result["decision"]["status"] == "FAILED"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.pop("policy"),
        lambda payload: payload["policy"].pop("schema_version"),
        lambda payload: payload["acceptance_input"].pop("schema_version"),
        lambda payload: payload["acceptance_input"].pop("gate_results"),
        lambda payload: payload.pop("run_identity"),
        lambda payload: payload["run_identity"].update(wheel_sha256="forged"),
        lambda payload: payload.update(post_grade_result={"task_success": 1}),
        lambda payload: payload["policy"].update(unexpected=True),
        lambda payload: payload["acceptance_input"].update(unexpected=True),
    ],
)
def test_governed_arm_rejects_incomplete_observation_schema(mutation) -> None:
    payload = _payload()
    mutation(payload)

    with pytest.raises(ValueError):
        evaluate_payload(payload)


def test_adapter_cli_writes_versioned_artifact(tmp_path) -> None:
    source = tmp_path / "observation.json"
    output = tmp_path / "decision.json"
    source.write_text(json.dumps(_payload()))

    assert main(["--input", str(source), "--output", str(output)]) == 0
    artifact = json.loads(output.read_text())
    assert artifact["decision"]["status"] == "ACCEPTED"
    assert artifact["observation_file_sha256"]
    assert artifact["observation"] == _payload()


def test_controller_builder_hashes_literal_inputs_and_drives_cli(tmp_path) -> None:
    visible = tmp_path / "done.txt"
    visible.write_text("kernel adapter ready\n")
    wheel = tmp_path / "candidate.whl"
    wheel.write_bytes(b"wheel bytes")
    built = tmp_path / "built-observation.json"
    builder = FIXTURE / "tests" / "build_observation.py"
    template = FIXTURE / "tests" / "observation.json"
    subprocess.run(
        [
            sys.executable,
            str(builder),
            "--template",
            str(template),
            "--output",
            str(built),
            "--visible-artifact",
            str(visible),
            "--wheel",
            str(wheel),
            "--policy-source",
            str(template),
            "--candidate-commit",
            "d" * 40,
        ],
        check=True,
    )
    payload = json.loads(built.read_text())
    assert payload["acceptance_input"]["gate_results"] == [["tests", "PASS"]]
    assert payload["run_identity"]["wheel_sha256"] == hashlib.sha256(b"wheel bytes").hexdigest()
    assert (
        payload["run_identity"]["policy_source_sha256"] == hashlib.sha256(template.read_bytes()).hexdigest()
    )

    output = tmp_path / "decision.json"
    assert main(["--input", str(built), "--output", str(output)]) == 0
    artifact = json.loads(output.read_text())
    assert artifact["decision"]["status"] == "ACCEPTED"
    assert artifact["observation_file_sha256"] == hashlib.sha256(built.read_bytes()).hexdigest()


def test_minimal_arm_is_independent_and_reviewable(tmp_path) -> None:
    source = tmp_path / "observation.json"
    output = tmp_path / "decision.json"
    source.write_text(json.dumps(_payload()))
    script = FIXTURE / "tests" / "minimal_policy.py"

    completed = subprocess.run(
        [sys.executable, str(script), str(source), str(output)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(output.read_text())["policy_acceptance"] == 1
    tree = ast.parse(script.read_text())
    imports = [
        name.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for name in node.names
    ]
    assert not any(name.startswith("evalopt") for name in imports)

    malformed = _payload()
    malformed.pop("policy")
    source.write_text(json.dumps(malformed))
    subprocess.run([sys.executable, str(script), str(source), str(output)], check=True)
    assert json.loads(output.read_text())["policy_acceptance"] == 0

    duplicate = _payload()
    duplicate["acceptance_input"]["gate_results"] = [["tests", "FAIL"], ["tests", "PASS"]]
    source.write_text(json.dumps(duplicate))
    subprocess.run([sys.executable, str(script), str(source), str(output)], check=True)
    assert json.loads(output.read_text())["policy_acceptance"] == 0

    weakened = _payload()
    weakened["acceptance_input"]["tests_weakened"] = True
    source.write_text(json.dumps(weakened))
    subprocess.run([sys.executable, str(script), str(source), str(output)], check=True)
    assert json.loads(output.read_text())["policy_acceptance"] == 0


@pytest.mark.parametrize("task_success", [0, 1])
def test_policy_shell_and_separate_grader_never_share_hidden_result(tmp_path, task_success) -> None:
    tests_root = tmp_path / "tests"
    logs_root = tmp_path / "logs"
    artifacts = logs_root / "artifacts"
    tests_root.mkdir()
    artifacts.mkdir(parents=True)
    for name in ("build_observation.py", "minimal_policy.py", "ungoverned_policy.py", "observation.json"):
        shutil.copy2(FIXTURE / "tests" / name, tests_root / name)
    (tests_root / "evalopt_graph-fixture.whl").write_bytes(b"fixture wheel")
    if task_success:
        (artifacts / "done.txt").write_text("kernel adapter ready\n")
    base_env = {
        **os.environ,
        "EVALOPT_ARM": "ALL",
        "EVALOPT_CANDIDATE_COMMIT": "e" * 40,
        "EVALOPT_TESTS_ROOT": str(tests_root),
        "EVALOPT_LOGS_ROOT": str(logs_root),
        "EVALOPT_PYTHON": sys.executable,
    }
    signatures = []
    for order in ("U,M,G", "U,G,M", "M,U,G", "M,G,U", "G,U,M", "G,M,U"):
        env = {**base_env, "EVALOPT_VERIFIER_ORDER": order}
        subprocess.run(["bash", str(FIXTURE / "tests" / "test.sh")], env=env, check=True)
        artifact = json.loads((logs_root / "verifier" / "evalopt-decision.json").read_text())
        reward = json.loads((logs_root / "verifier" / "reward.json").read_text())
        assert artifact["verifier_order"] == order.split(",")
        assert artifact["invariant_error"] is None
        assert "task_success" not in reward
        assert all("task_success" not in value["observation"] for value in artifact["decisions"].values())
        assert reward["U_policy_acceptance"] == 1
        assert reward["M_policy_acceptance"] == task_success
        assert reward["G_policy_acceptance"] == task_success
        assert not any(reward[f"{arm}_policy_error"] for arm in "UMG")
        identities = {arm: artifact["decisions"][arm]["run_identity"] for arm in "UMG"}
        assert {item["candidate_commit"] for item in identities.values()} == {"e" * 40}
        assert len({item["wheel_sha256"] for item in identities.values()}) == 1
        assert len({item["policy_source_sha256"] for item in identities.values()}) == 3
        assert identities["G"]["policy_source_sha256"] == identities["G"]["wheel_sha256"]
        signatures.append(
            tuple(
                (arm, artifact["decisions"][arm]["policy_acceptance"], artifact["decisions"][arm]["decision"])
                for arm in "UMG"
            )
        )
    assert len({json.dumps(item, sort_keys=True) for item in signatures}) == 1

    grade_path = tmp_path / "oracle-grade.json"
    subprocess.run(
        [
            sys.executable,
            str(FIXTURE / "grader" / "grade.py"),
            "--artifact",
            str(artifacts / "done.txt"),
            "--output",
            str(grade_path),
        ],
        check=True,
    )
    grade = json.loads(grade_path.read_text())
    assert grade["task_success"] == task_success
    assert not any((FIXTURE / "tests").glob("*grader*"))


@pytest.mark.parametrize(
    "mutation",
    [
        "payload['run_identity']['candidate_commit']='0'*40",
        "payload['producer_note']='changed'",
        "payload['acceptance_input']['gate_results']=[['tests','FAIL']];"
        "source.write_text(json.dumps(payload));raw=source.read_bytes()",
    ],
)
def test_policy_shell_marks_changed_observation_as_an_explicit_error(tmp_path, mutation) -> None:
    tests_root = tmp_path / "tests"
    logs_root = tmp_path / "logs"
    artifacts = logs_root / "artifacts"
    tests_root.mkdir()
    artifacts.mkdir(parents=True)
    for name in ("build_observation.py", "ungoverned_policy.py", "observation.json"):
        shutil.copy2(FIXTURE / "tests" / name, tests_root / name)
    (tests_root / "minimal_policy.py").write_text(
        "import hashlib,json,pathlib,sys\n"
        "source=pathlib.Path(sys.argv[1]); raw=source.read_bytes(); payload=json.loads(raw)\n"
        f"{mutation}\n"
        "canonical=json.dumps(payload,sort_keys=True,separators=(',',':')).encode()\n"
        "result={'schema_version':'evalopt.harbor-decision.v1','policy_acceptance':1,"
        "'run_identity':payload['run_identity'],'observation':payload,"
        "'observation_sha256':hashlib.sha256(canonical).hexdigest(),"
        "'observation_file_sha256':hashlib.sha256(raw).hexdigest(),"
        "'decision':{'status':'ACCEPTED','reasons':['tampered']}}\n"
        "pathlib.Path(sys.argv[2]).write_text(json.dumps(result))\n"
    )
    (tests_root / "evalopt_graph-fixture.whl").write_bytes(b"fixture wheel")
    (artifacts / "done.txt").write_text("kernel adapter ready\n")
    env = {
        **os.environ,
        "EVALOPT_ARM": "ALL",
        "EVALOPT_VERIFIER_ORDER": "M,U,G",
        "EVALOPT_CANDIDATE_COMMIT": "f" * 40,
        "EVALOPT_TESTS_ROOT": str(tests_root),
        "EVALOPT_LOGS_ROOT": str(logs_root),
        "EVALOPT_PYTHON": sys.executable,
    }
    subprocess.run(["bash", str(FIXTURE / "tests" / "test.sh")], env=env, check=True)
    artifact = json.loads((logs_root / "verifier" / "evalopt-decision.json").read_text())
    reward = json.loads((logs_root / "verifier" / "reward.json").read_text())
    assert artifact["invariant_error"] == "missing_policy_observation"
    assert artifact["decisions"]["M"]["policy_acceptance"] == -1
    assert artifact["decisions"]["U"]["policy_acceptance"] == 1
    assert artifact["decisions"]["G"]["policy_acceptance"] == 1
    assert reward["M_policy_error"] == 1
    assert reward["U_policy_error"] == reward["G_policy_error"] == 0


def test_harbor_fixture_uses_separate_offline_verifier() -> None:
    task = (FIXTURE / "task.toml").read_text()
    verifier = (FIXTURE / "tests" / "test.sh").read_text()

    assert 'environment_mode = "separate"' in task
    assert 'network_mode = "no-network"' in task
    assert "logs_root=${EVALOPT_LOGS_ROOT:-/logs}" in verifier
    assert 'path.parent / "reward.json"' in verifier
    assert set("UMG") <= set(verifier)
    assert "EVALOPT_CANDIDATE_COMMIT" in verifier
    assert "build_observation.py" in verifier
    assert "contains no hidden grader" in verifier
