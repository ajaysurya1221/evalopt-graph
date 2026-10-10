import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2.preservation import verify


class PreservationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name).resolve()
        for args in (
            ["init", "-q"],
            ["config", "user.name", "Offline fixture"],
            ["config", "user.email", "fixture@example.invalid"],
        ):
            self.git(*args)
        (self.repo / "v1.txt").write_text("immutable\n")
        self.git("add", "v1.txt")
        self.git("commit", "-qm", "fixture")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True, check=True)

    def test_unchanged_and_permitted_addition(self):
        new = self.repo / "skills/eval-opt-v2/SKILL.md"
        new.parent.mkdir(parents=True)
        new.write_text("new skill")
        self.assertEqual(verify(self.repo, self.base)["status"], "PASS")

    def test_changed_deleted_and_mode_changed_are_detected(self):
        path = self.repo / "v1.txt"
        path.write_text("changed")
        self.assertEqual(verify(self.repo, self.base)["violations"], ["v1.txt"])
        path.write_text("immutable\n")
        path.chmod(0o755)
        self.assertEqual(verify(self.repo, self.base)["violations"], ["v1.txt"])
        path.unlink()
        self.assertEqual(verify(self.repo, self.base)["violations"], ["v1.txt"])

    def test_unscoped_new_file_is_detected(self):
        (self.repo / "unrelated.txt").write_text("unexpected")
        self.assertEqual(verify(self.repo, self.base)["violations"], ["unrelated.txt"])

    def test_staged_change_cannot_be_hidden_by_restored_worktree(self):
        path = self.repo / "v1.txt"
        path.write_text("staged mutation")
        self.git("add", "v1.txt")
        path.write_text("immutable\n")
        self.assertEqual(verify(self.repo, self.base)["violations"], ["v1.txt"])

    def test_staged_deletion_is_not_preservation(self):
        self.git("rm", "--cached", "v1.txt")
        self.assertEqual(verify(self.repo, self.base)["violations"], ["v1.txt"])

    def test_git_owner_execute_semantics(self):
        path = self.repo / "v1.txt"
        path.chmod(0o755)
        self.git("add", "v1.txt")
        self.git("commit", "-qm", "executable fixture")
        base = self.git("rev-parse", "HEAD").stdout.strip()
        path.chmod(0o655)
        self.assertEqual(verify(self.repo, base)["violations"], ["v1.txt"])


if __name__ == "__main__":
    unittest.main()
