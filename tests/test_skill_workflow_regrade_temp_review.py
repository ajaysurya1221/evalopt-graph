"""Independent controls for controller-owned temporary roots and evidence aliases."""

from __future__ import annotations

import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"
sys.path.insert(0, str(BENCH))
import pilot_regrade as subject  # noqa: E402


def aliased_temporary_root(tmp_path, monkeypatch):
    parent = tmp_path / "canonical-parent"
    root = parent / "controller-created"
    root.mkdir(parents=True)
    alias = tmp_path / "platform-temp-alias"
    alias.symlink_to(parent, target_is_directory=True)

    @contextmanager
    def temporary(*, prefix):
        assert prefix == "evalopt-regrade-baseline-"
        yield str(alias / root.name)

    monkeypatch.setattr(subject.tempfile, "TemporaryDirectory", temporary)
    return root, alias / root.name


def test_review_controller_temp_alias_is_canonical_before_bridge_and_result_read(tmp_path, monkeypatch):
    root, alias = aliased_temporary_root(tmp_path, monkeypatch)
    expected = {"tracked.py": "file:420:controlled"}
    request = {"task_id": "fixture", "frozen_source": str(alias / "untrusted-source")}
    before = request.copy()
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        data = json.loads(kwargs["input"])
        assert Path(data["destination"]) == root / "materialized"
        assert Path(data["result"]) == root / "result.json"
        assert data["frozen_source"] == request["frozen_source"]
        assert "pycache_prefix=" + str(root / "empty-cache") in argv
        assert argv[1:3] == ["-I", "-B"]
        (root / "result.json").write_text(json.dumps({"initial_manifest": expected}))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subject.subprocess, "run", run)
    assert subject._native_baseline(request) == expected
    assert len(calls) == 1 and request == before
    # Normalizing this one owned root must not normalize unrelated inputs.
    with pytest.raises(ValueError, match="symlinks"):
        subject._safe(alias / "untrusted-source")


@pytest.mark.parametrize("alias_kind", ["file", "parent"])
def test_review_untrusted_evidence_aliases_still_fail_before_json_read(tmp_path, alias_kind):
    canonical = tmp_path / "evidence"
    canonical.mkdir()
    target = canonical / "record.json"
    target.write_text('{"evidence":"controlled"}')
    if alias_kind == "file":
        alias = tmp_path / "record-alias.json"
        alias.symlink_to(target)
    else:
        parent = tmp_path / "evidence-alias"
        parent.symlink_to(canonical, target_is_directory=True)
        alias = parent / target.name
    assert subject._json(target) == {"evidence": "controlled"}
    with pytest.raises(ValueError, match="symlinks"):
        subject._json(alias)


def test_review_symlink_result_inside_canonical_temp_root_is_rejected(tmp_path, monkeypatch):
    root, _ = aliased_temporary_root(tmp_path, monkeypatch)
    foreign = tmp_path / "foreign.json"
    foreign.write_text('{"initial_manifest":{"untrusted":"value"}}')

    def run(argv, **kwargs):
        data = json.loads(kwargs["input"])
        assert Path(data["result"]) == root / "result.json"
        Path(data["result"]).symlink_to(foreign)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subject.subprocess, "run", run)
    with pytest.raises(ValueError, match="symlinks"):
        subject._native_baseline({"task_id": "fixture"})


def test_review_actual_isolated_bridge_rejects_aliased_frozen_source_before_import(tmp_path):
    canonical = tmp_path / "source"
    canonical.mkdir()
    alias = tmp_path / "source-alias"
    alias.symlink_to(canonical, target_is_directory=True)
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(BENCH / "runtime/regrade_bridge.py")],
        input=json.dumps({"frozen_source": str(alias), "frozen_source_sha256": "f" * 64}),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0
    assert "trusted frozen source must not traverse symlinks" in result.stderr
