import copy
import importlib.util
import json
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2.freeze import (
    prepare,
    reviewed_inputs,
    tree_manifest,
    validate_admission,
    verify_frozen,
    verify_harness_source_only,
)
from evalopt_v2.records import canonical, digest
from evalopt_v2.registration import development_gate, schedule
from test_study import tasks


class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.harness = self.root / "harness"
        package = self.harness / "evalopt_v2"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text('"""Nonexecuted unit fixture."""\n')
        for name in (
            "case_runner",
            "grading",
            "verifier",
            "verifier_container",
            "framing",
            "accounting",
            "lifecycle",
            "store",
            "campaign",
            "analysis",
            "descriptive",
            "registration",
            "harbor_bridge",
            "observe",
            "snapshot",
            "preflight",
        ):
            (package / f"{name}.py").write_text('"""Nonexecuted unit fixture."""\n')
        repository = Path(__file__).resolve().parents[4]
        self.skill = repository / "skills/eval-opt-v2"
        self.kernel = self.root / "src/evalopt_graph"
        shutil.copytree(
            repository / "src/evalopt_graph",
            self.kernel,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        self.tasks = self.root / "tasks"
        self.tasks.mkdir()
        (self.tasks / "catalog.json").write_bytes(canonical(tasks("development")))
        self.upstream = self.root / "upstream"
        self.upstream.mkdir()
        for args in (
            ["init", "-q"],
            ["config", "user.name", "Fixture"],
            ["config", "user.email", "fixture@example.invalid"],
        ):
            subprocess.run(["git", *args], cwd=self.upstream, check=True, capture_output=True)
        (self.upstream / "README").write_text("Nonexecuted upstream fixture.\n")
        (self.upstream / "AGENTS.md").symlink_to("README")
        (self.upstream / "LICENSE").write_text("Nonexecuted fixture license.\n")
        (self.upstream / "skills/fixture/references").mkdir(parents=True)
        (self.upstream / "skills/fixture/SKILL.md").write_text("Nonexecuted fixture skill.\n")
        (self.upstream / "skills/fixture/references/detail.md").write_text("Complete dependency.\n")
        (self.upstream / ".claude-plugin").mkdir()
        (self.upstream / ".claude-plugin/plugin.json").write_text('{"skills":["./skills/fixture"]}\n')
        for args in (["add", "."], ["commit", "-qm", "fixture"]):
            subprocess.run(["git", *args], cwd=self.upstream, check=True, capture_output=True)
        self.commit = (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.upstream).decode().strip()
        )
        self.inputs = reviewed_inputs(self.harness, self.skill, self.tasks)
        self.admission = {
            "schema_version": "evalopt-workflows-v2/1",
            "development_round": {"revision": 0, "previous": None},
            "inputs": self.inputs,
            "controls": {
                name: {"status": "PASS", "skipped": 0, "evidence_sha256": "a" * 64}
                for name in (
                    "audited_regressions",
                    "semantic",
                    "framing_accounting",
                    "lifecycle",
                    "compatibility_reproduction",
                )
            },
            "reviews": {
                name: {"verdict": "ACCEPT", "evidence_sha256": "b" * 64}
                for name in ("skill", "tasks", "grading_capture", "integration_analysis")
            },
        }
        for target, replacement in (
            ("UPSTREAM_COMMIT", self.commit),
            ("skill_sources", lambda *args: {}),
            ("image_identity", lambda value: value),
            ("verify_preservation", lambda _: {"status": "PASS"}),
        ):
            patcher = patch("evalopt_v2.freeze." + target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def prepare(self):
        root = self.root / "campaign"
        receipt = prepare(
            root,
            harness=self.harness,
            skill_c=self.skill,
            task_root=self.tasks,
            upstream=self.upstream,
            agent_image="sha256:" + "c" * 64,
            verifier_image="sha256:" + "d" * 64,
            admission=self.admission,
            kernel=self.kernel,
        )
        return root, receipt

    def test_copy_freezes_all_inputs_and_replays_without_candidate_execution(self):
        root, receipt = self.prepare()
        store = verify_frozen(root, expected_sha256=receipt["registration_sha256"])
        self.assertEqual(len(store.registration["schedule"]), 48)
        self.assertNotEqual(tree_manifest(root / "frozen/skill-c"), tree_manifest(root / "frozen/skill-d"))
        (self.harness / "evalopt_v2/grading.py").write_text("changed live working tree")
        verify_frozen(root, expected_sha256=receipt["registration_sha256"])

    def test_frozen_source_mutation_blocks_admission(self):
        root, receipt = self.prepare()
        (root / "frozen/harness/evalopt_v2/grading.py").write_text("changed frozen grader")
        with self.assertRaises(ValueError):
            verify_frozen(root, expected_sha256=receipt["registration_sha256"])

    def test_sparse_upstream_retains_complete_bundle_license_and_pinned_commit(self):
        root, _ = self.prepare()
        upstream = root / "frozen/upstream"
        self.assertEqual(
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=upstream).decode().strip(),
            self.commit,
        )
        self.assertEqual(
            set(tree_manifest(upstream)),
            {
                ".claude-plugin/plugin.json",
                "LICENSE",
                "skills/fixture/SKILL.md",
                "skills/fixture/references/detail.md",
            },
        )
        self.assertFalse((upstream / "AGENTS.md").exists())
        self.assertFalse((upstream / "AGENTS.md").is_symlink())

    def test_working_cache_is_excluded_but_frozen_cache_is_rejected(self):
        cache = self.harness / "evalopt_v2/__pycache__"
        cache.mkdir()
        (cache / "ignored.pyc").write_bytes(b"working cache")
        root, receipt = self.prepare()
        harness = root / "frozen/harness"
        self.assertFalse((harness / "evalopt_v2/__pycache__").exists())
        verify_harness_source_only(harness)
        for name in ("__pycache__", "stray.pyc", "stray.pyo"):
            path = harness / "evalopt_v2" / name
            if name == "__pycache__":
                path.mkdir()
            else:
                path.write_bytes(b"unregistered executable cache")
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "bytecode cache"):
                verify_frozen(root, expected_sha256=receipt["registration_sha256"])
            path.rmdir() if path.is_dir() else path.unlink()

    def test_unchecked_hash_cache_cannot_bypass_unchanged_manifest(self):
        root, receipt = self.prepare()
        harness = root / "frozen/harness"
        source = harness / "evalopt_v2/grading.py"
        marker = self.root / "cache-executed"
        malicious = self.root / "other-grading.py"
        malicious.write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n")
        cache = Path(importlib.util.cache_from_source(str(source)))
        cache.parent.mkdir()
        before = tree_manifest(root / "frozen")
        py_compile.compile(
            str(malicious),
            cfile=str(cache),
            dfile=str(source),
            doraise=True,
            invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
        )
        self.assertEqual(before, tree_manifest(root / "frozen"))
        with self.assertRaisesRegex(ValueError, "bytecode cache"):
            verify_frozen(root, expected_sha256=receipt["registration_sha256"])
        self.assertFalse(marker.exists())
        # Establish that -I -B alone would execute these unhashed cache bytes.
        executed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                f"import sys;sys.path.insert(0,{str(harness)!r});import evalopt_v2.grading",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)
        self.assertTrue(marker.exists())

    def test_review_or_control_failure_cannot_freeze(self):
        for field, key, attribute, value in (
            ("reviews", "integration_analysis", "verdict", "REJECT"),
            ("controls", "lifecycle", "skipped", 1),
        ):
            changed = copy.deepcopy(self.admission)
            changed[field][key][attribute] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_admission(changed, self.inputs)

    def test_review_of_old_bytes_is_insufficient(self):
        (self.harness / "evalopt_v2/grading.py").write_text("unreviewed mutation")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse((self.root / "campaign").exists())

    def test_input_symlinks_are_not_frozen(self):
        (self.harness / "alias").symlink_to(self.harness / "evalopt_v2/grading.py")
        with self.assertRaises(ValueError):
            tree_manifest(self.harness)

    def previous_development(self, *, ready=False):
        task_list = tasks("development")
        rows = [
            {**row, "valid_completion": row["task_id"].endswith("-0") if ready else False}
            for row in schedule(task_list, "development")
        ]
        return {
            "tasks": task_list,
            "rows": rows,
            "controls_passed": True,
            "revision": 0,
            "result": development_gate(task_list, rows, controls_passed=True, revision=0),
            "registration_sha256": "f" * 64,
        }

    def test_one_source_bound_revision_requires_complete_nonready_prior_round(self):
        self.admission["development_round"] = {"revision": 1, "previous": self.previous_development()}
        root, receipt = self.prepare()
        verify_frozen(root, expected_sha256=receipt["registration_sha256"])
        retained = json.loads((root / "admission.json").read_text())
        self.assertEqual(retained["development_round"]["revision"], 1)

    def test_invalid_development_rounds_are_rejected(self):
        complete = self.previous_development()
        malformed = [
            {"revision": 0, "previous": {}},
            {"revision": True, "previous": None},
            {"revision": 2, "previous": complete},
            {"revision": 1, "previous": None},
            {"revision": 1, "previous": self.previous_development(ready=True)},
            {"revision": 1, "previous": {**complete, "registration_sha256": "wrong"}},
            {"revision": 1, "previous": {**complete, "revision": 1}},
            {"revision": 1, "previous": {**complete, "revision": False}},
            {"revision": 1, "previous": {**complete, "rows": complete["rows"][:-1]}},
            {
                "revision": 1,
                "previous": {**complete, "result": {**complete["result"], "next": "freeze_heldout"}},
            },
        ]
        for round_ in malformed:
            admission = {**self.admission, "development_round": round_}
            with self.subTest(round_=round_["revision"]), self.assertRaises(ValueError):
                validate_admission(admission, self.inputs)

    def test_heldout_development_round_must_match_retained_gate(self):
        from evalopt_v2.freeze import _validate_stage_round

        passed = self.previous_development(ready=True)
        _validate_stage_round(self.admission, "heldout", passed)
        with self.assertRaisesRegex(ValueError, "different development round"):
            _validate_stage_round(self.admission, "heldout", {**passed, "revision": 1})

    def rewrite_local_receipts(self, root, receipt):
        # Simulate a coherent local rewrite while preserving the external pin.
        manifest = tree_manifest(root / "frozen")
        admission = json.loads((root / "admission.json").read_text())
        admission["inputs"] = reviewed_inputs(
            root / "frozen/harness", root / "frozen/skill-c", root / "frozen/tasks"
        )
        (root / "source-manifest.json").write_bytes(canonical(manifest))
        (root / "admission.json").write_bytes(canonical(admission))
        (root / "freeze.json").write_bytes(
            canonical(
                {
                    "registration_sha256": receipt["registration_sha256"],
                    "source_manifest_sha256": digest(manifest),
                    "admission_sha256": digest(admission),
                }
            )
        )

    def test_coherent_grader_manifest_admission_rewrite_cannot_keep_external_pin(self):
        root, receipt = self.prepare()
        (root / "frozen/harness/evalopt_v2/grading.py").write_text("unreviewed malicious grader\n")
        self.rewrite_local_receipts(root, receipt)
        with self.assertRaisesRegex(ValueError, "externally pinned"):
            verify_frozen(root, expected_sha256=receipt["registration_sha256"])

    def test_coherent_admission_only_rewrite_is_bound_to_source_identity(self):
        root, receipt = self.prepare()
        admission = json.loads((root / "admission.json").read_text())
        admission["reviews"]["tasks"]["evidence_sha256"] = "f" * 64
        (root / "admission.json").write_bytes(canonical(admission))
        self.rewrite_local_receipts(root, receipt)
        with self.assertRaisesRegex(ValueError, "externally pinned"):
            verify_frozen(root, expected_sha256=receipt["registration_sha256"])

    def test_coherent_kernel_rewrite_is_bound_to_external_registration(self):
        root, receipt = self.prepare()
        (root / "frozen/kernel/evalopt_graph/kernel.py").write_text("changed frozen kernel\n")
        self.rewrite_local_receipts(root, receipt)
        with self.assertRaisesRegex(ValueError, "externally pinned"):
            verify_frozen(root, expected_sha256=receipt["registration_sha256"])

    def test_each_registered_identity_is_rederived_from_retained_inputs(self):
        root, receipt = self.prepare()
        original_registration = json.loads((root / "registration.json").read_text())
        original_freeze = json.loads((root / "freeze.json").read_text())
        for field in original_registration["identities"]:
            changed = copy.deepcopy(original_registration)
            changed["identities"][field] = "e" * 64
            changed.pop("registration_sha256")
            changed["registration_sha256"] = digest(changed)
            changed_freeze = {**original_freeze, "registration_sha256": changed["registration_sha256"]}
            (root / "registration.json").write_bytes(canonical(changed))
            (root / "freeze.json").write_bytes(canonical(changed_freeze))
            with self.subTest(identity=field), self.assertRaisesRegex(ValueError, "externally pinned"):
                verify_frozen(root, expected_sha256=changed["registration_sha256"])
        (root / "registration.json").write_bytes(canonical(original_registration))
        (root / "freeze.json").write_bytes(canonical(original_freeze))
        store = verify_frozen(root, expected_sha256=receipt["registration_sha256"])
        manifest = json.loads((root / "source-manifest.json").read_text())
        admission = json.loads((root / "admission.json").read_text())
        self.assertEqual(
            store.registration["identities"]["source"], digest({"manifest": manifest, "admission": admission})
        )
        self.assertIn("kernel/evalopt_graph/kernel.py", manifest)

    def test_kernel_source_requires_actual_preservation_pass(self):
        with patch("evalopt_v2.freeze.verify_preservation", lambda _: {"status": "FAIL"}):
            with self.assertRaisesRegex(ValueError, "preservation"):
                self.prepare()
        self.assertFalse((self.root / "campaign").exists())

    def kernel_subprocess(self, root, code):
        harness = str(Path(__file__).resolve().parents[1])
        bootstrap = (
            "import sys;from pathlib import Path;sys.path.insert(0,"
            + repr(harness)
            + ");from evalopt_v2.freeze import verify_kernel_import;root=Path("
            + repr(str(root))
            + ");"
            + code
        )
        return subprocess.run(
            [sys.executable, "-I", "-B", "-c", bootstrap], capture_output=True, text=True, timeout=10
        )

    def test_frozen_kernel_import_ignores_changed_installed_package(self):
        root, receipt = self.prepare()
        installed = self.root / "installed/evalopt_graph"
        installed.mkdir(parents=True)
        (installed / "__init__.py").write_text("raise RuntimeError('installed package must not run')\n")
        before = (installed / "__init__.py").read_bytes()
        result = self.kernel_subprocess(
            root,
            "sys.path.insert(0,"
            + repr(str(installed.parent))
            + ");sys.path.insert(0,str(root/'frozen/kernel'));print(verify_kernel_import(root)['status'])",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "PASS")
        self.assertEqual((installed / "__init__.py").read_bytes(), before)
        (self.kernel / "kernel.py").write_text("changed original installed/source tree\n")
        verify_frozen(root, expected_sha256=receipt["registration_sha256"])

    def test_preloaded_offpath_kernel_is_rejected_without_silent_replacement(self):
        root, _ = self.prepare()
        installed = self.root / "installed/evalopt_graph"
        installed.mkdir(parents=True)
        (installed / "__init__.py").write_text("loaded_from_wrong_package=True\n")
        result = self.kernel_subprocess(
            root,
            "sys.path.insert(0,"
            + repr(str(installed.parent))
            + ");import evalopt_graph;sys.path.insert(0,str(root/'frozen/kernel'));verify_kernel_import(root)",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside frozen kernel", result.stderr)

    def test_offpath_unimported_kernel_rejected_before_execution(self):
        root, _ = self.prepare()
        installed = self.root / "installed/evalopt_graph"
        installed.mkdir(parents=True)
        marker = self.root / "executed"
        (installed / "__init__.py").write_text(
            "from pathlib import Path;Path(" + repr(str(marker)) + ").write_text('bad')\n"
        )
        result = self.kernel_subprocess(
            root, "sys.path.insert(0," + repr(str(installed.parent)) + ");verify_kernel_import(root)"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not resolve", result.stderr)
        self.assertFalse(marker.exists())

    def test_unhashed_kernel_bytecode_is_not_an_import_input(self):
        root, _ = self.prepare()
        cache = root / "frozen/kernel/evalopt_graph/__pycache__"
        cache.mkdir()
        (cache / "__init__.cpython-313.pyc").write_bytes(b"forged cache")
        result = self.kernel_subprocess(
            root, "sys.path.insert(0,str(root/'frozen/kernel'));verify_kernel_import(root)"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bytecode cache", result.stderr)


if __name__ == "__main__":
    unittest.main()
