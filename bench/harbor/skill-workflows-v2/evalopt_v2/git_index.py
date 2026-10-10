"""Bounded Git index semantics without executing a stopped candidate's Git.

Adapted from skill-workflows-v1/tasks/suite.py::_index_identity at approved
2deb53feb2bf20061a754b80ff93fccafeac5af7 (repository MIT license). Filesystem
stat-cache refresh is excluded; staged objects/modes/flags remain protected.
Raw capture still retains and hashes every index byte independently.
"""

import hashlib
import stat
import struct

from .case_runner import snapshot_manifest


def index_record(path):
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 2_000_000:
        raise ValueError("invalid index")
    data = path.read_bytes()
    if len(data) < 32 or data[:4] != b"DIRC" or hashlib.sha1(data[:-20]).digest() != data[-20:]:
        raise ValueError("invalid index checksum")
    version, count = struct.unpack_from(">II", data, 4)
    if version not in {2, 3} or count > 10000:
        raise ValueError("unsupported index")
    cursor, entries = 12, []
    for _ in range(count):
        start = cursor
        if cursor + 62 > len(data) - 20:
            raise ValueError("truncated index entry")
        mode = struct.unpack_from(">I", data, cursor + 24)[0]
        oid = data[cursor + 40 : cursor + 60].hex()
        flags = struct.unpack_from(">H", data, cursor + 60)[0]
        cursor += 62
        extended = 0
        if flags & 0x4000:
            if version != 3 or cursor + 2 > len(data) - 20:
                raise ValueError("invalid extended index")
            extended = struct.unpack_from(">H", data, cursor)[0]
            cursor += 2
        end = data.index(b"\0", cursor, len(data) - 20)
        if flags & 0xFFF != min(end - cursor, 0xFFF):
            raise ValueError("invalid index name length")
        filename = data[cursor:end].hex()
        cursor = start + ((end - start + 8) // 8) * 8
        if cursor > len(data) - 20 or any(data[end:cursor]):
            raise ValueError("invalid index entry")
        entries.append([filename, mode, oid, flags & 0xF000, extended])
    while cursor < len(data) - 20:
        if cursor + 8 > len(data) - 20:
            raise ValueError("truncated index extension")
        name = data[cursor : cursor + 4]
        size = struct.unpack_from(">I", data, cursor + 4)[0]
        if not all(65 <= byte <= 90 for byte in name):
            raise ValueError("unsupported index extension")
        cursor += 8 + size
    if cursor != len(data) - 20:
        raise ValueError("invalid index extensions")
    return {"kind": "git-index", "mode": stat.S_IMODE(metadata.st_mode), "entries": entries}


def workspace_manifest(root):
    result = snapshot_manifest(root)
    index = root / ".git/index"
    raw = result.get(".git/index")
    if raw is not None and raw["kind"] == "file":
        try:
            result[".git/index"] = index_record(index)
        except ValueError:
            # Unsupported or malformed agent-written index bytes are still a
            # captured boundary change. Do not convert them into missing capture
            # evidence, or normalize away bytes whose semantics we cannot parse.
            # I/O errors and unsafe snapshot nodes continue to fail capture.
            result[".git/index"] = {**raw, "kind": "git-index-unparsed"}
    return result
