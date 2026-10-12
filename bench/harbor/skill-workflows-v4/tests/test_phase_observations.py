"""Controller phase transitions and retained-byte replay, without model calls."""

# ruff: noqa: E402 -- isolated tests explicitly choose their controller import root.

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(BENCH.parents[2] / "src"))
from evalopt_v4 import harbor_bridge as bridge
from evalopt_v4 import observe
from evalopt_v4.framing import SCHEMA
from evalopt_v4.git_index import workspace_manifest
from evalopt_v4.lifecycle import write_once
from evalopt_v4.policies import evaluate_visible
from evalopt_v4.records import canonical, digest
from evalopt_v4.reporting import check_claim


def retain_synthetic(directory, *, attempt_id, candidate_id, phase, command, code):
    directory.mkdir()
    artifacts = {}
    for name in ("stdout.bin", "stderr.bin"):
        raw = b"controller fixture\n" if name == "stdout.bin" else b""
        (directory / name).write_bytes(raw)
        artifacts[name] = {
            "bytes": len(raw),
            "observed_bytes": len(raw),
            "truncated": False,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    record = observe.command_record(
        attempt_id=attempt_id,
        candidate_id=candidate_id,
        phase=phase,
        command=command,
        execution_state="ran",
        exit_code=code,
        availability="complete",
        artifact_refs=["stdout.bin", "stderr.bin"],
        artifact_sha256={name: item["sha256"] for name, item in artifacts.items()},
    )
    identity = {
        "container_id": "a" * 64,
        "image_id": "sha256:" + "a" * 64,
        "attempt_label": "visible-" + "c" * 32,
    }
    write_once(
        directory / "start.json",
        {
            "schema_version": SCHEMA,
            "kind": "visible_start",
            "identity": identity,
            "attempt_id": attempt_id,
            "candidate_id": candidate_id,
            "phase": phase,
            "check_id": "required",
            "command": command,
            "seconds": 30,
            "max_output_bytes": 2 * 1024**2,
        },
    )
    write_once(directory / "observation.json", record)
    write_once(
        directory / "end.json",
        {
            "schema_version": SCHEMA,
            "kind": "visible_end",
            "identity": identity,
            "after": {
                "schema_version": SCHEMA,
                "kind": "container_observation",
                "identity": identity,
                "stopped": True,
                "running": False,
                "paused": False,
                "exit_code": code,
            },
            "termination": None,
            "artifacts": artifacts,
            "record": record,
        },
    )
    return record


def seed_initial(root, task=None, *, attempt_id="phase-attempt", code=0):
    task = dict(task or {})
    task.setdefault("task_id", "phase-fixture")
    task.setdefault("task_contract", "implementation")
    task.setdefault("visible_command", ["python3", "-B", "verify.py"])
    task.setdefault("category", "ordinary-bug-repair")
    task.setdefault("instruction", "Repair the authored callable and report supplied evidence.")
    initial = root / "initial"
    initial.mkdir()
    (initial / "code.txt").write_text(str(code))
    (initial / "verify.py").write_text(
        "from pathlib import Path\nraise SystemExit(int(Path('code.txt').read_text()))\n"
    )
    manifest = workspace_manifest(initial)
    candidate_id = digest(manifest)
    record = retain_synthetic(
        root / "initial-visible",
        attempt_id=attempt_id,
        candidate_id=candidate_id,
        phase="initial",
        command=task["visible_command"],
        code=code,
    )
    bridge.seal_prompt(root, task, record, attempt_id=attempt_id, initial_candidate_id=candidate_id)
    return {"task": task, "initial_sha256": candidate_id, "initial_manifest": manifest}


def stopped_fixture(root, before=0, after=1):
    materialized = seed_initial(root, code=before)
    shutil.copytree(root / "initial", root / "stopped")
    (root / "stopped/code.txt").write_text(str(after))
    stopped_id = digest(workspace_manifest(root / "stopped"))
    post = retain_synthetic(
        root / "visible",
        attempt_id="phase-attempt",
        candidate_id=stopped_id,
        phase="post_stop",
        command=materialized["task"]["visible_command"],
        code=after,
    )
    initial, receipt = bridge.verify_prompt(
        root,
        materialized["task"],
        attempt_id="phase-attempt",
        initial_candidate_id=materialized["initial_sha256"],
        verifier_image="sha256:" + "a" * 64,
    )
    write_once(root / "post-stop-observation.json", post)
    response = {"status": "completed", "findings": [], "blockers": [], "checks": [check_claim(initial)]}
    bundle = {
        "schema_version": SCHEMA,
        "kind": "stopped_visible_evidence",
        "attempt_id": "phase-attempt",
        "task_contract": "implementation",
        "initial_snapshot_sha256": materialized["initial_sha256"],
        "snapshot_sha256": stopped_id,
        "snapshot_status": "complete",
        "execution_boundary": "confirmed",
        "boundaries_preserved": True,
        "boundary_violations": [],
        "observations": [initial, post],
        "response": response,
        "supplied_observation_ids": receipt["supplied_observation_ids"],
        "prompt_receipt": receipt,
    }
    return materialized, bundle


@pytest.mark.parametrize("before,after", [(0, 1), (1, 0)])
def test_phase_change_preserves_initial_claim_and_separate_final_check(tmp_path, before, after):
    materialized, bundle = stopped_fixture(tmp_path, before, after)
    original = canonical(bundle)
    bound = bridge.verify_retained_observations(
        tmp_path, bundle, materialized["task"], "phase-attempt", verifier_image="sha256:" + "a" * 64
    )
    assert bound["initial_candidate_id"] != bound["visible_candidate_id"]
    result = evaluate_visible(
        bundle,
        check_roster=[{"check_id": "required", "command": materialized["task"]["visible_command"]}],
        attempt_id="phase-attempt",
        candidate_id=bundle["snapshot_sha256"],
        observed_at="2026-10-11T00:00:00Z",
    )
    assert result["visible_claims_supported"] is True
    assert result["M"]["accepted"] is (after == 0)
    assert canonical(bundle) == original
    assert [o["exit_code"] for o in bundle["observations"]] == [before, after]


@pytest.mark.parametrize(
    "tamper",
    [
        "prompt",
        "receipt",
        "initial_bytes",
        "stopped_bytes",
        "initial_artifact",
        "post_artifact",
        "supplied_ids",
        "ledger_order",
    ],
)
def test_retained_phase_binding_rejects_tamper(tmp_path, tamper):
    materialized, bundle = stopped_fixture(tmp_path)
    target = {
        "prompt": "prompt.txt",
        "initial_bytes": "initial/code.txt",
        "stopped_bytes": "stopped/code.txt",
        "initial_artifact": "initial-visible/stdout.bin",
        "post_artifact": "visible/stderr.bin",
    }.get(tamper)
    if target:
        with (tmp_path / target).open("ab") as stream:
            stream.write(b"changed")
    elif tamper == "receipt":
        receipt = json.loads((tmp_path / "prompt-receipt.json").read_bytes())
        receipt["prompt_bytes"] += 1
        (tmp_path / "prompt-receipt.json").write_bytes(canonical(receipt))
    elif tamper == "supplied_ids":
        bundle["supplied_observation_ids"] = [bundle["observations"][1]["observation_id"]]
    else:
        bundle["observations"].reverse()
    with pytest.raises(ValueError):
        bridge.verify_retained_observations(
            tmp_path, bundle, materialized["task"], "phase-attempt", verifier_image="sha256:" + "a" * 64
        )


@pytest.mark.parametrize(
    "tamper",
    ["missing_identity", "after_identity", "running", "truncation", "negative_observed", "record_kind"],
)
def test_retained_observation_rejects_contradictory_closure(tmp_path, tamper):
    materialized, bundle = stopped_fixture(tmp_path)
    path = tmp_path / "initial-visible/end.json"
    end = json.loads(path.read_bytes())
    if tamper == "missing_identity":
        end.pop("identity")
    elif tamper == "after_identity":
        end["after"]["identity"]["container_id"] = "d" * 64
    elif tamper == "running":
        end["after"]["running"] = True
    elif tamper == "truncation":
        end["artifacts"]["stdout.bin"]["truncated"] = True
    elif tamper == "negative_observed":
        end["artifacts"]["stdout.bin"]["observed_bytes"] = -1
    else:
        end["kind"] = "not_a_visible_end"
    path.write_bytes(canonical(end))
    with pytest.raises(ValueError):
        bridge.verify_retained_observations(
            tmp_path, bundle, materialized["task"], "phase-attempt", verifier_image="sha256:" + "a" * 64
        )


@pytest.mark.parametrize("phase", ["initial-visible", "visible"])
@pytest.mark.parametrize("tamper", ["image", "seconds", "output_limit"])
def test_replay_requires_frozen_visible_image_and_limits(tmp_path, phase, tamper):
    materialized, bundle = stopped_fixture(tmp_path)
    start_path = tmp_path / phase / "start.json"
    end_path = tmp_path / phase / "end.json"
    start, end = json.loads(start_path.read_bytes()), json.loads(end_path.read_bytes())
    if tamper == "image":
        start["identity"]["image_id"] = "sha256:" + "d" * 64
        end["identity"]["image_id"] = start["identity"]["image_id"]
        end["after"]["identity"]["image_id"] = start["identity"]["image_id"]
    elif tamper == "seconds":
        start["seconds"] += 1
    else:
        start["max_output_bytes"] -= 1
    start_path.write_bytes(canonical(start))
    end_path.write_bytes(canonical(end))
    with pytest.raises(ValueError, match="container_observation"):
        bridge.verify_retained_observations(
            tmp_path, bundle, materialized["task"], "phase-attempt", verifier_image="sha256:" + "a" * 64
        )


def test_missing_capture_keeps_initial_and_explicit_unavailable_post_stop(tmp_path):
    materialized = seed_initial(tmp_path)

    async def freeze(bundle):
        assert [o["phase"] for o in bundle["observations"]] == ["initial", "post_stop"]
        return {"receipt": "synthetic"}

    result = asyncio.run(
        bridge.finish_stopped(
            {"trial_id": "phase", "attempt_id": "phase-attempt"},
            tmp_path,
            tmp_path,
            materialized,
            {"execution_boundary": "unconfirmed", "snapshot": "missing", "reason": "deadline"},
            verifier_image="sha256:" + "a" * 64,
            freeze_visible=freeze,
        )
    )
    bound = bridge.verify_retained_observations(
        tmp_path,
        result["visible_bundle"],
        materialized["task"],
        "phase-attempt",
        verifier_image="sha256:" + "a" * 64,
    )
    assert bound["initial_candidate_id"] == materialized["initial_sha256"]
    assert bound["visible_candidate_id"] is None
    assert result["visible_bundle"]["observations"][1]["execution_state"] == "not_run"
    assert result["visible_bundle"]["observations"][1]["artifact_sha256"] == {}
    assert result["verification"] is None


@pytest.mark.parametrize("arm", ["A", "C", "D"])
def test_difficulty_bridge_rejects_other_arms_before_auth(tmp_path, arm, monkeypatch):
    monkeypatch.setattr(bridge, "auth_path", lambda: pytest.fail("must not inspect auth"))
    with pytest.raises(ValueError, match="upstream_B"):
        asyncio.run(
            bridge.execute_one(
                {"arm": arm},
                tmp_path,
                tmp_path / "runtime",
                None,
                None,
                None,
                "x",
                "x",
                freeze_visible=lambda _: {},
            )
        )


@pytest.mark.skipif(
    not os.environ.get("EVALOPT_V4_DOCKER_CONTROL_IMAGE"), reason="explicit local Docker image required"
)
@pytest.mark.parametrize("before,after", [(0, 1), (1, 0)])
def test_actual_docker_phase_transition_and_byte_replay(tmp_path, before, after):
    initial = tmp_path / "initial"
    initial.mkdir()
    (initial / "code.txt").write_text(str(before))
    (initial / "verify.py").write_text(
        "from pathlib import Path\nraise SystemExit(int(Path('code.txt').read_text()))\n"
    )
    task = {
        "task_id": "phase-fixture",
        "task_contract": "implementation",
        "category": "ordinary-bug-repair",
        "instruction": "Report supplied initial observations.",
        "visible_command": ["python3", "-B", "verify.py"],
    }
    image = os.environ["EVALOPT_V4_DOCKER_CONTROL_IMAGE"]
    identities = []
    try:
        first = observe.visible_check(
            initial,
            task,
            attempt_id="phase-attempt",
            candidate_id=digest(workspace_manifest(initial)),
            phase="initial",
            image=image,
            directory=tmp_path / "initial-visible",
        )
        identities.append(json.loads((tmp_path / "initial-visible/end.json").read_bytes())["identity"])
        _, receipt = bridge.seal_prompt(
            tmp_path, task, first, attempt_id="phase-attempt", initial_candidate_id=first["candidate_id"]
        )
        shutil.copytree(initial, tmp_path / "stopped")
        (tmp_path / "stopped/code.txt").write_text(str(after))
        last = observe.visible_check(
            tmp_path / "stopped",
            task,
            attempt_id="phase-attempt",
            candidate_id=digest(workspace_manifest(tmp_path / "stopped")),
            phase="post_stop",
            image=image,
            directory=tmp_path / "visible",
        )
        identities.append(json.loads((tmp_path / "visible/end.json").read_bytes())["identity"])
        write_once(tmp_path / "post-stop-observation.json", last)
        bundle = {
            "attempt_id": "phase-attempt",
            "snapshot_status": "complete",
            "initial_snapshot_sha256": first["candidate_id"],
            "snapshot_sha256": last["candidate_id"],
            "observations": [first, last],
            "supplied_observation_ids": receipt["supplied_observation_ids"],
            "prompt_receipt": receipt,
        }
        assert [o["exit_code"] for o in bundle["observations"]] == [before, after]
        bridge.verify_retained_observations(tmp_path, bundle, task, "phase-attempt", verifier_image=image)
    finally:
        for identity in identities:
            assert observe.DockerController().inspect_owned(identity)["stopped"]
            subprocess.run(
                ["docker", "rm", identity["container_id"]], check=True, capture_output=True, timeout=15
            )
