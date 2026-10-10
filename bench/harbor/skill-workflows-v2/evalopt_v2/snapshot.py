"""Bounded extraction of stopped Docker captures and native final responses.

No tar member is executed or imported. Identity hashes detect changes; they do
not authenticate agent-produced content or turn it into controller evidence.
"""

from __future__ import annotations

import hashlib
import stat
import tarfile
from pathlib import Path, PurePosixPath

from .framing import SCHEMA, decode_jsonl, strict_json
from .records import digest

RESPONSE_MAX_DEPTH = 640
RESPONSE_MAX_NODES = 16_384
RESPONSE_MAX_BYTES = 256 * 1024


def response_transport_contract(max_findings):
    """One visible transport contract, shared by every experimental arm."""
    if type(max_findings) is not int or max_findings < 0:
        raise ValueError("invalid_task_finding_limit")
    return (
        f"Final response transport limits: a UTF-8 JSON object of at most {RESPONSE_MAX_BYTES} bytes, "
        f"at most {RESPONSE_MAX_DEPTH} nested containers (the outer object counts as one), "
        f"and at most {RESPONSE_MAX_NODES} JSON nodes (each value and each object key counts once). "
        f"The findings array may contain at most {max_findings} entries. "
    )


def _validate_response_transport(response):
    """Reserve envelope depth/node headroom before hashing or storing a response."""
    if not isinstance(response, dict):
        raise ValueError("response_not_object")
    stack, nodes = [iter((response,))], 0
    while stack:
        try:
            value = next(stack[-1])
        except StopIteration:
            stack.pop()
            continue
        nodes += 1
        if nodes > RESPONSE_MAX_NODES:
            raise ValueError("response_node_limit")
        if type(value) not in (list, dict):
            continue
        if len(stack) > RESPONSE_MAX_DEPTH:
            raise ValueError("response_depth_limit")
        if type(value) is dict:
            nodes += len(value)
            if nodes > RESPONSE_MAX_NODES:
                raise ValueError("response_node_limit")
        stack.append(iter(value.values() if type(value) is dict else value))


def _response_bytes(content):
    """Hash all response text while retaining at most the published byte budget."""
    sha, size, pieces = hashlib.sha256(), 0, []
    for item in content:
        # Chunk the encoding too: one oversized native text item need not create
        # a second unbounded response-sized byte buffer merely to reject it.
        text = item["text"]
        for offset in range(0, len(text), 65536):
            try:
                raw = text[offset : offset + 65536].encode("utf-8")
            except UnicodeError:
                # The native source bytes are still retained and hashed. There
                # is no valid UTF-8 response byte string whose hash to invent.
                return None, None, "response_not_utf8"
            sha.update(raw)
            size += len(raw)
            if size <= RESPONSE_MAX_BYTES:
                pieces.append(raw)
    if size > RESPONSE_MAX_BYTES:
        return None, sha.hexdigest(), "response_byte_limit"
    return b"".join(pieces), sha.hexdigest(), None


def extract_capture(
    archive, destination, *, root_name, expected_sha256, max_bytes=64 * 1024**2, max_members=20000
):
    archive, destination = Path(archive), Path(destination)
    if archive.is_symlink() or not archive.is_file() or destination.exists() or destination.is_symlink():
        raise ValueError("capture_path_not_fresh_regular")
    if destination.parent.resolve() != destination.parent.absolute():
        raise ValueError("capture_destination_alias")
    if not root_name or PurePosixPath(root_name).name != root_name:
        raise ValueError("invalid_capture_root")
    if archive.stat().st_size > max_bytes:
        raise ValueError("capture_bytes_changed_or_oversized")
    with archive.open("rb") as stream:
        raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("capture_bytes_changed_or_oversized")
    import io

    entries, total = {}, 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tar:
        for member in tar:
            if len(entries) >= max_members:
                raise ValueError("capture_member_limit")
            name = member.name
            if name.endswith("/"):
                name = name[:-1]
            parts = name.split("/")
            if (
                not name
                or any(part in {"", ".", ".."} for part in parts)
                or parts[0] != root_name
                or "\\" in name
                or "\x00" in name
            ):
                raise ValueError("capture_unsafe_path")
            relative = "/".join(parts[1:])
            if relative in entries or not (member.isfile() or member.isdir()) or member.issparse():
                raise ValueError("capture_duplicate_or_unsafe_node")
            if member.mode & ~0o777:
                raise ValueError("capture_privileged_mode")
            # Preserve the original archive, but never materialize host nodes
            # that could hide evidence from later traversal or byte verification.
            if not member.mode & stat.S_IRUSR or (member.isdir() and not member.mode & stat.S_IXUSR):
                raise ValueError("capture_unreadable_owner_mode")
            if not relative and not member.isdir():
                raise ValueError("capture_root_not_directory")
            total += member.size
            if total > max_bytes or member.size < 0:
                raise ValueError("capture_unpacked_limit")
            data = tar.extractfile(member).read() if member.isfile() else None
            if data is not None and len(data) != member.size:
                raise ValueError("capture_short_file")
            entries[relative] = (member.isdir(), member.mode, data)
    if "" not in entries:
        raise ValueError("capture_root_missing")
    for name in entries:
        parts = name.split("/")
        for count in range(1, len(parts)):
            parent = "/".join(parts[:count])
            if parent not in entries or not entries[parent][0]:
                raise ValueError("capture_parent_missing_or_file")
    # Validate the entire archive before making any output nodes.
    destination.mkdir(mode=0o700)
    for name, (directory, mode, data) in sorted(
        entries.items(), key=lambda item: (item[0].count("/"), item[0])
    ):
        if not name:
            continue
        path = destination / name
        if directory:
            path.mkdir(mode=0o700)
        else:
            with path.open("xb") as stream:
                stream.write(data)
            path.chmod(mode)
    for name, (directory, mode, _) in sorted(entries.items(), reverse=True):
        if directory:
            (destination / name).chmod(mode)
    return {
        "schema_version": SCHEMA,
        "kind": "extracted_capture",
        "archive_sha256": expected_sha256,
        "members": len(entries),
        "file_bytes": total,
    }


def session_files(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("native_sessions_missing")
    result = {}
    for path in sorted(root.rglob("*")):
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode) or path.suffix != ".jsonl":
            raise ValueError("unexpected_native_session_node")
        result[path.relative_to(root).as_posix()] = path.read_bytes()
    return result


def final_response(files):
    parents = []
    for raw in files.values():
        framed = decode_jsonl(raw)
        rows = [item["value"] for item in framed["records"]]
        if not rows or rows[0].get("type") != "session_meta":
            raise ValueError("native_owner_missing")
        if rows[0].get("payload", {}).get("source") == "exec":
            parents.append((framed, rows))
    if len(parents) != 1:
        raise ValueError("native_parent_not_unique")
    framed, rows = parents[0]
    messages = [
        row["payload"]
        for row in rows
        if row.get("type") == "response_item"
        and isinstance(row.get("payload"), dict)
        and row["payload"].get("type") == "message"
        and row["payload"].get("role") == "assistant"
        and row["payload"].get("phase") == "final_answer"
    ]
    # Codex also uses channel=final on older event envelopes. Never accept
    # commentary or a child's copied/final message as the parent's completion.
    if not messages:
        messages = [
            row["payload"]
            for row in rows
            if row.get("type") == "response_item"
            and isinstance(row.get("payload"), dict)
            and row["payload"].get("type") == "message"
            and row["payload"].get("role") == "assistant"
            and row["payload"].get("channel") == "final"
        ]
    if not messages:
        return {
            "schema_version": SCHEMA,
            "kind": "response_capture",
            "status": "missing",
            "response": None,
            "source_sha256": framed["source_sha256"],
            "response_sha256": None,
        }
    content = messages[-1].get("content")
    if (
        not isinstance(content, list)
        or not content
        or any(
            not isinstance(item, dict)
            or item.get("type") != "output_text"
            or not isinstance(item.get("text"), str)
            for item in content
        )
    ):
        raise ValueError("native_final_content_malformed")
    raw, response_sha, malformed_reason = _response_bytes(content)
    try:
        if malformed_reason is not None:
            raise ValueError(malformed_reason)
        response = strict_json(raw)
        _validate_response_transport(response)
        parsed_sha = digest(response)
    except (ValueError, UnicodeError, RecursionError) as error:
        if malformed_reason is None:
            malformed_reason = (
                str(error)
                if str(error) in {"response_not_object", "response_node_limit", "response_depth_limit"}
                else "response_json_malformed"
            )
        response, parsed_sha = None, None
    return {
        "schema_version": SCHEMA,
        "kind": "response_capture",
        "status": "parsed" if response is not None else "malformed",
        "response": response,
        "source_sha256": framed["source_sha256"],
        "response_sha256": response_sha,
        "parsed_sha256": parsed_sha,
        "malformed_reason": malformed_reason,
    }
