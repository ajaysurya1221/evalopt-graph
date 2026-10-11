import hashlib
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2.git_index import index_record, workspace_manifest
from evalopt_v2.materialize import boundary_violations


def fixture(*, cache=0, mode=0o100644, oid=b"a" * 20, flags=0, extension=b""):
    fields = [cache] * 10
    fields[6] = mode
    name = b"code.py"
    entry = struct.pack(">10I", *fields) + oid + struct.pack(">H", len(name) | flags) + name + b"\0"
    entry += b"\0" * (-len(entry) % 8)
    return struct.pack(">4sII", b"DIRC", 2, 1) + entry + extension


class GitIndexTests(unittest.TestCase):
    def read(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index"
            path.write_bytes(data + hashlib.sha1(data).digest())
            return index_record(path)

    def test_filesystem_cache_only_refresh_is_neutral(self):
        self.assertEqual(self.read(fixture(cache=0)), self.read(fixture(cache=123)))

    def test_staged_object_mode_stage_and_flags_remain_frozen(self):
        baseline = self.read(fixture())
        for changed in (
            fixture(oid=b"b" * 20),
            fixture(mode=0o100755),
            fixture(flags=0x1000),
            fixture(flags=0x8000),
        ):
            with self.subTest(changed=changed.hex()):
                self.assertNotEqual(self.read(changed), baseline)

    def test_optional_cache_extension_is_neutral_but_required_is_rejected(self):
        self.assertEqual(
            self.read(fixture(extension=b"TREE" + struct.pack(">I", 2) + b"ab")), self.read(fixture())
        )
        with self.assertRaises(ValueError):
            self.read(fixture(extension=b"link" + struct.pack(">I", 2) + b"ab"))

    def test_bad_lengths_padding_truncation_and_unsupported_version_rejected(self):
        original = fixture()
        bad_length = bytearray(original)
        bad_length[73] = 6
        bad_padding = bytearray(original)
        bad_padding[-1] = 1
        version = bytearray(original)
        struct.pack_into(">I", version, 4, 4)
        for changed in (
            bytes(bad_length),
            bytes(bad_padding),
            bytes(version),
            original[:-4],
            fixture(extension=b"TREE" + struct.pack(">I", 20)),
        ):
            with self.subTest(changed=changed.hex()), self.assertRaises(ValueError):
                self.read(changed)

    def test_checksum_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index"
            path.write_bytes(fixture() + b"x" * 20)
            with self.assertRaises(ValueError):
                index_record(path)

    def test_unparsed_index_retains_raw_bytes_and_mode_as_a_boundary_violation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            path = root / ".git/index"
            data = fixture()
            path.write_bytes(data + hashlib.sha1(data).digest())
            initial = workspace_manifest(root)
            invalid = bytearray(data)
            struct.pack_into(">I", invalid, 4, 4)
            for payload in (bytes(invalid) + hashlib.sha1(invalid).digest(), b"not an index", b""):
                path.write_bytes(payload)
                stopped = workspace_manifest(root)
                record = stopped[".git/index"]
                self.assertEqual(record["kind"], "git-index-unparsed")
                self.assertEqual(record["sha256"], hashlib.sha256(payload).hexdigest())
                self.assertEqual(record["size"], len(payload))
                self.assertEqual(boundary_violations(initial, stopped, []), [".git/index"])
            before = workspace_manifest(root)
            path.chmod(0o600 if path.stat().st_mode & 0o777 != 0o600 else 0o644)
            self.assertEqual(boundary_violations(before, workspace_manifest(root), []), [".git/index"])

    def test_index_type_change_is_a_boundary_but_unsafe_nodes_and_io_still_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            path = root / ".git/index"
            data = fixture()
            path.write_bytes(data + hashlib.sha1(data).digest())
            before = workspace_manifest(root)
            with patch("evalopt_v2.git_index.index_record", side_effect=OSError("unreadable")):
                with self.assertRaises(OSError):
                    workspace_manifest(root)
            path.unlink()
            path.mkdir()
            self.assertEqual(boundary_violations(before, workspace_manifest(root), []), [".git/index"])
            path.rmdir()
            path.symlink_to(root / "missing")
            with self.assertRaises(ValueError):
                workspace_manifest(root)


if __name__ == "__main__":
    unittest.main()
