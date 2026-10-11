"""Patch application controls; writes fresh synthetic copies only."""

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
# This test's source-repository argument is explicit, never inferred from a
# future publication location. Only pinned Git objects and tracked .py are read.
REPO = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location("apply_verify", HERE / "apply_verify.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def manifest_copy(bundle, mutate):
    value = json.loads((bundle / "manifest.json").read_bytes())
    mutate(value)
    (bundle / "manifest.json").write_text(json.dumps(value) + "\n")


class ApplyControls(unittest.TestCase):
    def test_exact_fresh_copy_and_original_working_source_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp).resolve() / "output"
            manifest, before = helper.apply_to_fresh(REPO, output, HERE)
            for name, change in manifest["changes"].items():
                self.assertEqual(
                    helper.sha((output / "patched" / Path(name).relative_to(helper.PREFIX)).read_bytes()),
                    change["after_sha256"],
                )
            self.assertEqual({name: helper.sha((REPO / name).read_bytes()) for name in before}, before)

    def test_existing_output_is_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp).resolve()
            (output / "sentinel").write_bytes(b"preserve")
            with self.assertRaises(ValueError):
                helper.apply_to_fresh(REPO, output, HERE)
            self.assertEqual([p.name for p in output.iterdir()], ["sentinel"])

    def test_payload_patch_base_and_roster_tamper_reject_before_output(self):
        changes = [
            lambda bundle: (bundle / "payload/materialize.py").write_bytes(b"changed"),
            lambda bundle: (bundle / "response-contract.patch").write_bytes(b"changed"),
            lambda bundle: manifest_copy(bundle, lambda value: value.update(base_commit="0" * 40)),
            lambda bundle: manifest_copy(
                bundle, lambda value: value["base_source_sha256"].pop(next(iter(value["base_source_sha256"])))
            ),
            lambda bundle: manifest_copy(
                bundle,
                lambda value: value["changes"][helper.PREFIX + "evalopt_v3/materialize.py"].update(
                    before_sha256="0" * 64
                ),
            ),
            lambda bundle: manifest_copy(
                bundle,
                lambda value: value["changes"][helper.PREFIX + "evalopt_v3/materialize.py"].update(
                    payload="../escape"
                ),
            ),
        ]
        for mutate in changes:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                bundle = root / "bundle"
                shutil.copytree(HERE, bundle)
                mutate(bundle)
                with self.assertRaises(ValueError):
                    helper.apply_to_fresh(REPO, root / "output", bundle)
                self.assertFalse((root / "output").exists())

    def test_bundle_and_working_source_overlap_rejected(self):
        for output in (HERE / "new-output", REPO / helper.PREFIX / "new-output"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                helper.apply_to_fresh(REPO, output, HERE)
            self.assertFalse(output.exists())

    def test_symlink_payload_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            bundle = root / "bundle"
            shutil.copytree(HERE, bundle)
            original = bundle / "payload/materialize.py"
            target = root / "unchanged.py"
            shutil.copy2(original, target)
            original.unlink()
            original.symlink_to(target)
            with self.assertRaises(ValueError):
                helper.apply_to_fresh(REPO, root / "output", bundle)
            self.assertFalse((root / "output").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
