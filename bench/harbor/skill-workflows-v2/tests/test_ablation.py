"""Offline portable-skill and single-mechanism ablation controls; no agent calls."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve()
SKILL = HERE.parents[4] / "skills" / "eval-opt-v2"
SPEC = importlib.util.spec_from_file_location("v2_ablation", HERE.parents[1] / "evalopt_v2" / "ablation.py")
ablation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ablation)


class AblationControls(unittest.TestCase):
    def setUp(self):
        self.full = ablation.bundle_files(SKILL)
        self.derived = ablation.derive_files(self.full)

    def test_actual_pair_has_only_the_named_difference(self):
        receipt = ablation.validate_files(self.full, self.derived)
        self.assertEqual(receipt["removed_files"], [ablation.PROCEDURE])
        self.assertEqual(receipt["changed_files"], ["SKILL.md"])
        self.assertEqual(len(receipt["identical_files"]), 6)
        self.assertEqual(receipt["skill_name"], "eval-opt-v2")
        self.assertEqual(receipt["skill_version"], "2.0.0")
        self.assertFalse(receipt["invocation_changed"])
        self.assertFalse(receipt["common_observation_schema_changed"])
        self.assertNotEqual(receipt["C"]["sha256"], receipt["D"]["sha256"])

    def test_derive_is_deterministic_and_does_not_mutate_full(self):
        before = copy.deepcopy(self.full)
        self.assertEqual(ablation.derive_files(self.full), self.derived)
        self.assertEqual(self.full, before)
        self.assertEqual(
            ablation.validate_files(self.full, self.derived), ablation.validate_files(before, self.derived)
        )

    def test_identity_recomputes_from_full_roster_and_bytes(self):
        receipt = ablation.validate_files(self.full, self.derived)
        for arm, files in (("C", self.full), ("D", self.derived)):
            nodes = receipt[arm]["files"]
            self.assertEqual(set(nodes), set(files))
            self.assertEqual(ablation._sha(ablation._canonical(nodes)), receipt[arm]["sha256"])
            for name, value in files.items():
                self.assertEqual(nodes[name], {"sha256": ablation._sha(value), "size": len(value)})

    def test_clean_environment_materialization_and_pair_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "same-invocation-bundle"
            receipt = ablation.derive_ablation(SKILL, target)
            self.assertEqual(ablation.bundle_files(target), self.derived)
            self.assertEqual(receipt, ablation.validate_pair(SKILL, target))
            self.assertEqual(set(ablation.bundle_files(target)), ablation.COMMON)
            # The receipt is external; no extra file reveals a condition label.
            self.assertFalse((target / "ablation.json").exists())

    def test_existing_destination_never_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "D"
            target.mkdir()
            (target / "retain.txt").write_bytes(b"original")
            with self.assertRaises(ValueError):
                ablation.derive_ablation(SKILL, target)
            self.assertEqual((target / "retain.txt").read_bytes(), b"original")

    def test_missing_parent_rejected_without_creating_ancestors(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "absent" / "D"
            with self.assertRaises(FileNotFoundError):
                ablation.derive_ablation(SKILL, target)
            self.assertFalse(target.parent.exists())

    def test_cannot_derive_inside_source(self):
        with self.assertRaises(ValueError):
            ablation.derive_ablation(SKILL, SKILL / "D")
        self.assertFalse((SKILL / "D").exists())

    def test_invocation_and_ui_metadata_cannot_drift(self):
        for name in ("SKILL.md", "agents/openai.yaml"):
            changed = dict(self.derived)
            changed[name] = changed[name].replace(b"eval-opt-v2", b"other-skill")
            with self.subTest(name=name), self.assertRaises(ValueError):
                ablation.validate_files(self.full, changed)

    def test_common_schema_and_any_other_common_bytes_cannot_drift(self):
        for name in ablation.COMMON:
            changed = dict(self.derived)
            changed[name] += b"\nAdditional instruction.\n"
            with self.subTest(name=name), self.assertRaises(ValueError):
                ablation.validate_files(self.full, changed)

    def test_extra_and_missing_files_rejected(self):
        for files, full in ((self.full, True), (self.derived, False)):
            for operation in ("missing", "extra"):
                changed = dict(files)
                if operation == "missing":
                    changed.pop("LICENSE")
                else:
                    changed["scripts/hook.py"] = b"print('not allowed')\n"
                with self.subTest(full=full, operation=operation), self.assertRaises(ValueError):
                    ablation._validate(changed, full=full)

    def test_route_missing_duplicated_reversed_or_broadened_rejected(self):
        for route in (
            b"",
            ablation.ROUTE + ablation.ROUTE,
            ablation.END + ablation.START,
            ablation.ROUTE.replace(ablation.END, b"Erase common constraints.\n" + ablation.END),
        ):
            changed = dict(self.full)
            changed["SKILL.md"] = changed["SKILL.md"].replace(ablation.ROUTE, route)
            with self.subTest(route=route), self.assertRaises(ValueError):
                ablation.derive_files(changed)

    def test_reference_outside_procedure_route_rejected(self):
        changed = dict(self.full)
        changed["SKILL.md"] += ("\nRead " + ablation.PROCEDURE + " always.\n").encode()
        with self.assertRaises(ValueError):
            ablation.derive_files(changed)

    def test_procedure_link_from_common_reference_rejected(self):
        changed = dict(self.full)
        changed["references/debugging.md"] += b"\nRead [extra](evidence-dispute.md).\n"
        with self.assertRaisesRegex(ValueError, "missing local"):
            ablation.derive_files(changed)

    def test_missing_or_unsafe_references_rejected(self):
        for target in ("absent.md", "../../../outside", "/external", "file:external"):
            changed = dict(self.full)
            changed["SKILL.md"] += f"\nRead [reference]({target}).\n".encode()
            with self.subTest(target=target), self.assertRaises(ValueError):
                ablation.derive_files(changed)

    def test_unrouted_common_reference_rejected(self):
        changed = dict(self.full)
        changed["SKILL.md"] = changed["SKILL.md"].replace(
            b"[debugging](references/debugging.md)", b"debugging"
        )
        with self.assertRaisesRegex(ValueError, "unrouted"):
            ablation.derive_files(changed)

    def test_invalid_metadata_and_utf8_rejected(self):
        for original, replacement in (
            (b"name: eval-opt-v2", b"name: wrong"),
            (b'"2.0.0"', b'"2.1.0"'),
            (b"description:", b"other:"),
        ):
            changed = dict(self.full)
            changed["SKILL.md"] = changed["SKILL.md"].replace(original, replacement)
            with self.subTest(original=original), self.assertRaises(ValueError):
                ablation.derive_files(changed)
        changed = dict(self.full)
        changed["LICENSE"] = b"\xff"
        with self.assertRaises(UnicodeDecodeError):
            ablation.derive_files(changed)

    def test_personal_paths_rejected(self):
        for prefix in (
            "/" + "Users/person/",
            "/" + "home/person/",
            "~" + "/.codex/",
            "C:" + "\\Users\\person\\",
        ):
            changed = dict(self.full)
            changed["references/debugging.md"] += ("\n" + prefix).encode()
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                ablation.derive_files(changed)

    def test_skill_root_and_child_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "alias").symlink_to(SKILL, target_is_directory=True)
            with self.assertRaises(ValueError):
                ablation.bundle_files(root / "alias")
            (root / "child").symlink_to(SKILL / "SKILL.md")
            with self.assertRaises(ValueError):
                ablation.bundle_files(root)

    def test_dangling_destination_link_not_followed(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "D"
            target.symlink_to(Path(temporary) / "missing")
            with self.assertRaises(ValueError):
                ablation.derive_ablation(SKILL, target)
            self.assertTrue(target.is_symlink())

    def test_special_node_and_empty_extra_directory_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.mkfifo(root / "pipe")
            with self.assertRaises(ValueError):
                ablation.bundle_files(root)
            (root / "pipe").unlink()
            (root / "hidden").mkdir()
            with self.assertRaises(ValueError):
                ablation.bundle_files(root)

    def test_failed_write_never_returns_a_valid_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "D"
            real = Path.open

            def failing_open(path, mode="r", *args, **kwargs):
                if mode == "xb" and path.name == "SKILL.md":
                    raise OSError("synthetic disk failure")
                return real(path, mode, *args, **kwargs)

            with patch.object(Path, "open", failing_open), self.assertRaises(OSError):
                ablation.derive_ablation(SKILL, target)
            with self.assertRaises(ValueError):
                ablation.validate_pair(SKILL, target)
            with self.assertRaises(ValueError):
                ablation.derive_ablation(SKILL, target)

    def test_platform_parent_alias_is_canonicalized_only_for_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "real").mkdir()
            (root / "alias").symlink_to(root / "real", target_is_directory=True)
            receipt = ablation.derive_ablation(SKILL, root / "alias" / "D")
            self.assertEqual(receipt, ablation.validate_pair(SKILL, root / "real" / "D"))

    def test_manifest_is_json_serializable_without_machine_paths(self):
        value = json.dumps(ablation.validate_files(self.full, self.derived), sort_keys=True)
        self.assertNotIn(str(SKILL), value)
        self.assertNotIn("source_root", value)


if __name__ == "__main__":
    unittest.main()
