import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2 import snapshot
from evalopt_v2.snapshot import (
    RESPONSE_MAX_BYTES,
    RESPONSE_MAX_DEPTH,
    RESPONSE_MAX_NODES,
    extract_capture,
    final_response,
    session_files,
)


def archive(tmp_path, rows):
    path = tmp_path / "capture.tar"
    with tarfile.open(path, "w") as tar:
        for name, kind, data in rows:
            member = tarfile.TarInfo(name)
            member.type = kind
            member.mode = 0o755 if kind == tarfile.DIRTYPE else 0o644
            member.size = len(data) if kind == tarfile.REGTYPE else 0
            tar.addfile(member, io.BytesIO(data) if kind == tarfile.REGTYPE else None)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_valid_capture_preserves_exact_data_and_modes(tmp_path):
    path, sha = archive(
        tmp_path, [("workspace", tarfile.DIRTYPE, b""), ("workspace/a.py", tarfile.REGTYPE, b"pass\n")]
    )
    result = extract_capture(path, tmp_path / "out", root_name="workspace", expected_sha256=sha)
    assert result["file_bytes"] == 5
    assert (tmp_path / "out/a.py").read_bytes() == b"pass\n"
    assert (tmp_path / "out/a.py").stat().st_mode & 0o777 == 0o644


@pytest.mark.parametrize(
    "name,kind",
    [
        ("workspace/../escape", tarfile.REGTYPE),
        ("/workspace/x", tarfile.REGTYPE),
        ("workspace/a//b", tarfile.REGTYPE),
        ("workspace/link", tarfile.SYMTYPE),
        ("workspace/fifo", tarfile.FIFOTYPE),
        ("workspace/hard", tarfile.LNKTYPE),
        ("workspace/missing/x", tarfile.REGTYPE),
    ],
)
def test_entire_archive_validated_before_output(tmp_path, name, kind):
    path, sha = archive(
        tmp_path,
        [
            ("workspace", tarfile.DIRTYPE, b""),
            ("workspace/good", tarfile.REGTYPE, b"ok"),
            (name, kind, b"bad"),
        ],
    )
    with pytest.raises(ValueError):
        extract_capture(path, tmp_path / "out", root_name="workspace", expected_sha256=sha)
    assert not (tmp_path / "out").exists()


def test_capture_hash_duplicate_and_size_fail_closed(tmp_path):
    path, sha = archive(
        tmp_path,
        [
            ("workspace", tarfile.DIRTYPE, b""),
            ("workspace/x", tarfile.REGTYPE, b"a"),
            ("workspace/x", tarfile.REGTYPE, b"b"),
        ],
    )
    for kwargs in (
        {"expected_sha256": "0" * 64},
        {"expected_sha256": sha},
        {"expected_sha256": sha, "max_bytes": 1},
    ):
        with pytest.raises(ValueError):
            extract_capture(path, tmp_path / "out", root_name="workspace", **kwargs)


def native(source="exec", text='{"status":"completed"}', phase="final_answer"):
    return (
        b"\n".join(
            json.dumps(x, ensure_ascii=False).encode()
            for x in [
                {"type": "session_meta", "payload": {"source": source}},
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "phase": phase,
                        "content": [{"type": "output_text", "text": text}],
                    },
                },
            ]
        )
        + b"\n"
    )


def test_final_response_parent_only_and_literal_unicode():
    result = final_response(
        {
            "parent": native(text='{"text":"a\u0085b"}'),
            "child": native(source={"subagent": {}}, text='{"wrong":true}'),
        }
    )
    assert result["response"] == {"text": "a\u0085b"}
    assert final_response({"p": native(phase="commentary")})["status"] == "missing"
    assert final_response({"p": native(text="```json\n{}\n```")})["status"] == "malformed"
    assert final_response({"p": native(text='{"a":1,"a":2}')})["status"] == "malformed"
    with pytest.raises(ValueError):
        final_response({"a": native(), "b": native()})


def test_native_roster_rejects_links_and_unexpected_files(tmp_path):
    (tmp_path / "a.jsonl").write_bytes(native())
    assert len(session_files(tmp_path)) == 1
    (tmp_path / "link.jsonl").symlink_to(tmp_path / "a.jsonl")
    with pytest.raises(ValueError):
        session_files(tmp_path)


@pytest.mark.parametrize("directory,mode", [(False, 0), (False, 0o200), (True, 0o400), (True, 0o100)])
def test_unreadable_modes_never_materialize_hidden_host_evidence(tmp_path, directory, mode):
    path = tmp_path / "capture.tar"
    with tarfile.open(path, "w") as tar:
        root = tarfile.TarInfo("workspace")
        root.type, root.mode = tarfile.DIRTYPE, 0o755
        tar.addfile(root)
        item = tarfile.TarInfo("workspace/hidden")
        item.type, item.mode = (tarfile.DIRTYPE if directory else tarfile.REGTYPE), mode
        item.size = 0 if directory else 5
        tar.addfile(item, None if directory else io.BytesIO(b"bytes"))
    original = path.read_bytes()
    with pytest.raises(ValueError, match="unreadable_owner_mode"):
        extract_capture(
            path,
            tmp_path / "out",
            root_name="workspace",
            expected_sha256=hashlib.sha256(original).hexdigest(),
        )
    assert not (tmp_path / "out").exists()
    assert path.read_bytes() == original


def test_overdeep_response_remains_explicit_malformed_evidence():
    text = '{"nested":' + "[" * 800 + "0" + "]" * 800 + "}"
    result = final_response({"parent": native(text=text)})
    assert result["status"] == "malformed"
    assert result["response"] is None and result["parsed_sha256"] is None
    assert result["response_sha256"] == hashlib.sha256(text.encode()).hexdigest()


def bounded_response_text(kind, limit):
    if kind == "depth":
        return '{"padding":' + "[" * (limit - 1) + "null" + "]" * (limit - 1) + "}"
    if kind == "nodes":
        return '{"padding":[' + ",".join("null" for _ in range(limit - 3)) + "]}"
    base = '{"padding":""}'
    return '{"padding":"' + "x" * (limit - len(base.encode())) + '"}'


@pytest.mark.parametrize(
    "kind,limit",
    [("depth", RESPONSE_MAX_DEPTH), ("nodes", RESPONSE_MAX_NODES), ("bytes", RESPONSE_MAX_BYTES)],
)
def test_published_response_transport_boundaries_are_parseable(kind, limit):
    text = bounded_response_text(kind, limit)
    result = final_response({"parent": native(text=text)})
    assert result["status"] == "parsed" and result["malformed_reason"] is None
    assert result["response_sha256"] == hashlib.sha256(text.encode()).hexdigest()


@pytest.mark.parametrize(
    "kind,limit",
    [("depth", RESPONSE_MAX_DEPTH), ("nodes", RESPONSE_MAX_NODES), ("bytes", RESPONSE_MAX_BYTES)],
)
def test_transport_overflow_is_rejected_before_parsed_digest(kind, limit, monkeypatch):
    text = bounded_response_text(kind, limit + 1)
    raw = native(text=text)
    monkeypatch.setattr(snapshot, "digest", lambda _: pytest.fail("oversized response reached parsed digest"))
    result = final_response({"parent": raw})
    assert result["status"] == "malformed"
    assert result["response"] is None and result["parsed_sha256"] is None
    expected = {
        "depth": "response_depth_limit",
        "nodes": "response_node_limit",
        "bytes": "response_byte_limit",
    }
    assert result["malformed_reason"] == expected[kind]
    assert result["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["response_sha256"] == hashlib.sha256(text.encode()).hexdigest()


def test_previous_standalone_depth_limit_does_not_enter_wrapper():
    text = bounded_response_text("depth", 768)
    result = final_response({"parent": native(text=text)})
    assert result["status"] == "malformed" and result["response"] is None
    assert result["malformed_reason"] == "response_depth_limit"


def test_six_hundred_level_response_is_still_supported():
    result = final_response({"parent": native(text=bounded_response_text("depth", 602))})
    assert result["status"] == "parsed"


def test_response_limit_counts_utf8_bytes_instead_of_characters():
    text = json.dumps({"padding": "☃" * (RESPONSE_MAX_BYTES // 2)}, ensure_ascii=False)
    assert len(text) < RESPONSE_MAX_BYTES < len(text.encode())
    result = final_response({"parent": native(text=text)})
    assert result["status"] == "malformed" and result["malformed_reason"] == "response_byte_limit"
    assert result["response_sha256"] == hashlib.sha256(text.encode()).hexdigest()


def test_non_utf8_response_retains_native_source_hash():
    raw = native().replace(b'{\\"status\\":\\"completed\\"}', b"\\ud800")
    result = final_response({"parent": raw})
    assert result["status"] == "malformed" and result["response"] is None
    assert result["malformed_reason"] == "response_not_utf8"
    assert result["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["response_sha256"] is None
