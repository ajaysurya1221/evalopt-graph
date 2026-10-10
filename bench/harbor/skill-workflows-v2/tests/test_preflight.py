import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2 import preflight


@pytest.fixture
def pinned_upstream(tmp_path, monkeypatch):
    root = tmp_path / "upstream"
    root.mkdir()
    (root / ".claude-plugin").mkdir()
    skills = [f"./skills/family/skill-{number:02d}" for number in range(27)]
    (root / ".claude-plugin/plugin.json").write_text(json.dumps({"skills": skills}))
    (root / ".gitignore").write_text("ignored-reference.txt\n")
    for name in skills:
        source = root / name
        (source / "references").mkdir(parents=True)
        (source / "SKILL.md").write_text("Pinned skill.\n")
        (source / "references/rules.md").write_text("Pinned dependency.\n")
    for args in (
        ["init", "--quiet"],
        ["add", "."],
        [
            "-c",
            "user.name=Control",
            "-c",
            "user.email=control@example.invalid",
            "commit",
            "--quiet",
            "-m",
            "fixture",
        ],
    ):
        subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True)
    head = (
        subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, check=True)
        .stdout.decode()
        .strip()
    )
    monkeypatch.setattr(preflight, "UPSTREAM_COMMIT", head)
    return root


def test_complete_upstream_tree_loads_all_pinned_dependencies(pinned_upstream):
    sources = preflight.skill_sources("B", pinned_upstream, None, None)
    assert len(sources) == 27
    assert all(
        (path / "references/rules.md").read_text() == "Pinned dependency.\n" for path in sources.values()
    )


@pytest.mark.parametrize(
    "change", ["skill", "plugin", "dependency", "new", "ignored", "empty_directory", "mode", "symlink"]
)
def test_pinned_head_does_not_authorize_mutated_injection(pinned_upstream, change):
    skill = pinned_upstream / "skills/family/skill-00"
    if change == "plugin":
        path = pinned_upstream / ".claude-plugin/plugin.json"
        path.write_text(path.read_text() + " ")
    elif change in {"skill", "dependency"}:
        (skill / ("SKILL.md" if change == "skill" else "references/rules.md")).write_text("Changed.\n")
    elif change in {"new", "ignored"}:
        (skill / ("new-reference.txt" if change == "new" else "ignored-reference.txt")).write_text(
            "Injected.\n"
        )
    elif change == "empty_directory":
        (skill / "added").mkdir()
    elif change == "mode":
        (skill / "SKILL.md").chmod(0o755)
    elif change == "symlink":
        (skill / "references/rules.md").unlink()
        (skill / "references/rules.md").symlink_to(skill / "SKILL.md")
    with pytest.raises(ValueError, match="upstream"):
        preflight.skill_sources("B", pinned_upstream, None, None)


def test_export_uses_pinned_blobs_even_if_working_file_changes_after_validation(
    pinned_upstream, tmp_path, monkeypatch
):
    destination = tmp_path / "export"
    destination.mkdir()
    original = preflight._git
    mutated = False

    def git(root, *args):
        nonlocal mutated
        if args[0] == "cat-file" and not mutated:
            (pinned_upstream / "skills/family/skill-00/SKILL.md").write_text("Too late injection.\n")
            mutated = True
        return original(root, *args)

    monkeypatch.setattr(preflight, "_git", git)
    preflight.export_upstream_skills(pinned_upstream, destination)
    assert mutated
    assert len(list(destination.iterdir())) == 27
    assert all((path / "SKILL.md").read_text() == "Pinned skill.\n" for path in destination.iterdir())


def test_permission_requires_actual_boolean_true():
    for value in (1, "true", None, False, {}, []):
        assert not preflight.permission_from_response({"result": {"ordinaryUsageAllowed": value}})[
            "ordinary_usage_allowed"
        ]
    assert (
        preflight.permission_from_response({"result": {"ordinaryUsageAllowed": True}})["state"] == "allowed"
    )


def test_minimal_environment_excludes_billing_routes(monkeypatch):
    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "CODEX_AUTH_JSON_PATH", "AZURE_OPENAI_API_KEY"):
        monkeypatch.setenv(key, "synthetic-private")
        assert key not in preflight.minimal_environment()


def test_auth_only_chatgpt_and_no_key_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    path = tmp_path / "auth.json"
    data = {"auth_mode": "chatgpt", "tokens": {"access_token": "synthetic", "refresh_token": "synthetic"}}
    path.write_text(json.dumps(data))
    assert preflight.auth_path() == path
    for change in ({"auth_mode": "apikey"}, {"OPENAI_API_KEY": "synthetic"}, {"tokens": {}}):
        path.write_text(json.dumps(data | change))
        with pytest.raises(ValueError):
            preflight.auth_path()


def test_config_pins_all_runtime_settings(tmp_path):
    source = Path(__file__).resolve().parents[1] / "runtime/codex.toml"
    assert preflight.native_config(source)[0]["model_reasoning_effort"] == "ultra"
    changed = tmp_path / "config.toml"
    changed.write_text(source.read_text().replace("max_depth = 1", "max_depth = 2"))
    with pytest.raises(ValueError):
        preflight.native_config(changed)


def test_runtime_checks_every_returned_context():
    rows = [
        {"type": "session_meta", "payload": {"source": "exec", "cli_version": "0.154.0"}},
        {"type": "turn_context", "payload": {"model": "gpt-6-astra", "effort": "ultra"}},
    ]

    def encode(rows):
        return b"\n".join(json.dumps(x).encode() for x in rows) + b"\n"

    assert preflight.runtime_observations({"p": encode(rows)})["verified"]
    bad = copy.deepcopy(rows)
    bad[1]["payload"]["effort"] = "high"
    assert not preflight.runtime_observations({"p": encode(rows), "child": encode(bad)})["verified"]
    with pytest.raises(ValueError):
        preflight.runtime_observations({"p": encode(rows[:1])})


def test_unpinned_image_never_calls_docker(monkeypatch):
    monkeypatch.setattr(
        preflight.subprocess, "run", lambda *a, **k: pytest.fail("must not inspect unpinned image")
    )
    with pytest.raises(ValueError):
        preflight.image_identity("tag:latest")


@pytest.mark.parametrize(
    "failure", [OSError("offline"), __import__("subprocess").TimeoutExpired("docker", 15)]
)
def test_precreation_transport_failure_has_narrow_proof(monkeypatch, failure):
    def failed(*a, **k):
        raise failure

    monkeypatch.setattr(preflight.subprocess, "run", failed)
    with pytest.raises(preflight.PreDispatchInfrastructureError) as caught:
        preflight.image_identity("sha256:" + "a" * 64)
    assert caught.value.proof == {
        "phase": "read_only_image_preflight",
        "containers_created": False,
        "agent_dispatched": False,
    }


def test_missing_image_is_configuration_not_retryable_transport(monkeypatch):
    import subprocess

    def failed(*a, **k):
        raise subprocess.CalledProcessError(1, "docker", stderr=b"No such image")

    monkeypatch.setattr(preflight.subprocess, "run", failed)
    with pytest.raises(ValueError, match="required_local_image"):
        preflight.image_identity("sha256:" + "a" * 64)
