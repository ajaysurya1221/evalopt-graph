"""Create and verify a controller-owned, self-contained campaign input freeze.

The review/control receipt records actual reviewed work; its hashes establish
which bytes were checked, not reviewer identity. It must originate outside the
candidate environment. Public reporting uses relative inventory names only.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from .ablation import derive_ablation, validate_pair
from .framing import strict_json
from .preflight import UPSTREAM_COMMIT, image_identity, skill_sources
from .preservation import verify as verify_preservation
from .records import digest
from .registration import development_gate, registration, validate_tasks
from .store import CampaignStore, exclusive_json, read_json, sync_directory


def tree_manifest(root):
    root = Path(root).absolute()
    if root.resolve() != root or not root.is_dir():
        raise ValueError("input tree must be a real directory")
    result = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in {".git", "__pycache__", ".pytest_cache", ".ruff_cache"} for part in rel.parts):
            continue
        metadata = path.lstat()
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("input tree contains symlink or special node")
        result[rel.as_posix()] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "executable": bool(metadata.st_mode & stat.S_IXUSR),
        }
    if not result:
        raise ValueError("empty frozen input tree")
    return result


def copy_tree(source, destination):
    source, destination = Path(source).absolute(), Path(destination).absolute()
    before = tree_manifest(source)
    destination.mkdir()
    for name in before:
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, path)
    if before != tree_manifest(source) or before != tree_manifest(destination):
        raise ValueError("input changed while freezing")
    return before


def verify_harness_source_only(harness):
    """Reject unregistered executable caches in an already frozen harness.

    -B prevents cache writes, not reads. The launcher must perform its own
    equivalent check before importing any frozen harness module; this helper
    also protects subsequent verification and admission from injected caches.
    Working-source caches may be excluded when constructing the frozen copy.
    """
    harness = Path(harness).absolute()
    if harness.resolve() != harness or not harness.is_dir():
        raise ValueError("frozen harness must be a real directory")
    if any(path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"} for path in harness.rglob("*")):
        raise ValueError("frozen harness bytecode cache is not an admitted input")


def reviewed_inputs(harness, skill, tasks):
    return {
        "harness": digest(tree_manifest(harness)),
        "skill_c": digest(tree_manifest(skill)),
        "tasks": digest(tree_manifest(tasks)),
    }


def validate_admission(receipt, inputs):
    """Validate source-bound review/control data and the single revision limit.

    Retained previous rows are replayed for consistency. Their registration
    digest is an identifier, not authentication of the source report's custody.
    """
    if set(receipt) != {"schema_version", "inputs", "controls", "reviews", "development_round"}:
        raise ValueError("invalid offline admission receipt")
    if receipt["schema_version"] != "evalopt-workflows-v2/1" or receipt["inputs"] != inputs:
        raise ValueError("offline admission covers different bytes")
    controls = receipt["controls"]
    required = {
        "audited_regressions",
        "semantic",
        "framing_accounting",
        "lifecycle",
        "compatibility_reproduction",
    }
    if set(controls) != required:
        raise ValueError("all five control groups required")
    for result in controls.values():
        if (
            result.get("status") != "PASS"
            or result.get("skipped") != 0
            or not _sha(result.get("evidence_sha256"))
        ):
            raise ValueError("control group has not passed completely")
    reviews = receipt["reviews"]
    if set(reviews) != {"skill", "tasks", "grading_capture", "integration_analysis"}:
        raise ValueError("separated review coverage incomplete")
    for review in reviews.values():
        if review.get("verdict") != "ACCEPT" or not _sha(review.get("evidence_sha256")):
            raise ValueError("independent review has not accepted")

    round_ = receipt["development_round"]
    if (
        not isinstance(round_, dict)
        or set(round_) != {"revision", "previous"}
        or type(round_["revision"]) is not int
        or round_["revision"] not in (0, 1)
    ):
        raise ValueError("invalid development round")
    previous = round_["previous"]
    if round_["revision"] == 0:
        if previous is not None:
            raise ValueError("initial development round cannot have previous evidence")
    else:
        if (
            not isinstance(previous, dict)
            or set(previous)
            != {"tasks", "rows", "controls_passed", "revision", "result", "registration_sha256"}
            or type(previous["revision"]) is not int
            or previous["revision"] != 0
            or not _sha(previous["registration_sha256"])
        ):
            raise ValueError("development revision requires the previous registered round")
        gate = development_gate(
            previous["tasks"],
            previous["rows"],
            controls_passed=previous["controls_passed"],
            revision=previous["revision"],
        )
        if gate["ready"] or gate["recorded"] != 48 or gate != previous["result"]:
            raise ValueError("revision requires a complete nonready development round")


def _validate_stage_round(admission, stage, development_admission):
    if stage == "heldout" and (
        not isinstance(development_admission, dict)
        or type(development_admission.get("revision")) is not int
        or development_admission["revision"] != admission["development_round"]["revision"]
    ):
        raise ValueError("held-out admission uses a different development round")


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _preserved_kernel(kernel):
    kernel = Path(kernel).resolve()
    if kernel.name != "evalopt_graph" or kernel.parent.name != "src":
        raise ValueError("kernel must be the preserved repository src/evalopt_graph package")
    report = verify_preservation(kernel.parent.parent)
    if report.get("status") != "PASS":
        raise ValueError("kernel source repository failed v1 preservation")
    return kernel


def derive_identities(frozen, admission, manifest):
    """One definition for freeze creation and external-digest-bound verification."""
    frozen = Path(frozen)
    inputs = reviewed_inputs(frozen / "harness", frozen / "skill-c", frozen / "tasks")
    package = frozen / "harness/evalopt_v2"

    def subset(names):
        return digest({name: hashlib.sha256((package / name).read_bytes()).hexdigest() for name in names})

    environment = read_json(frozen / "environment.json")
    if set(environment) != {"agent_image", "verifier_image"} or any(
        not isinstance(value, str) or not value.startswith("sha256:") for value in environment.values()
    ):
        raise ValueError("invalid frozen image environment")
    images = [environment[key].removeprefix("sha256:") for key in ("agent_image", "verifier_image")]
    if not all(_sha(value) for value in images):
        raise ValueError("frozen image digests required")
    return {
        "tasks": inputs["tasks"],
        "skill_c": inputs["skill_c"],
        "skill_d": digest(tree_manifest(frozen / "skill-d")),
        "upstream": digest(tree_manifest(frozen / "upstream")),
        "agent_image": images[0],
        "verifier_image": images[1],
        "source": digest({"manifest": manifest, "admission": admission}),
        "grader": subset(["case_runner.py", "grading.py", "verifier.py", "verifier_container.py"]),
        "parser": subset(["framing.py", "accounting.py"]),
        "continuation_policy": subset(["lifecycle.py", "store.py", "campaign.py"]),
        "analysis": subset(["analysis.py", "descriptive.py", "registration.py"]),
        "controller": subset(
            ["harbor_bridge.py", "observe.py", "snapshot.py", "preflight.py", "campaign.py"]
        ),
    }


def verify_kernel_import(root):
    """Check kernel import custody after verify_frozen has checked the external pin.

    The launcher must prepend frozen/kernel before calling this function. This
    helper never silently swaps an already imported off-path package. It checks
    source origins and retained bytes, not arbitrary mutation of live Python
    objects by trusted controller code.
    """
    root = Path(root).absolute()
    if root.resolve() != root:
        raise ValueError("kernel campaign path must be real")
    kernel = root / "frozen/kernel/evalopt_graph"
    manifest = read_json(root / "source-manifest.json")
    prefix = "kernel/evalopt_graph/"
    expected = {
        name.removeprefix(prefix): record for name, record in manifest.items() if name.startswith(prefix)
    }
    if not expected or tree_manifest(kernel) != expected:
        raise ValueError("frozen kernel source changed")
    # -B prevents writes but can still read existing pyc files. Reject these
    # before import rather than letting an unhashed cache choose executed code.
    if any(path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"} for path in kernel.rglob("*")):
        raise ValueError("frozen kernel bytecode cache is not an admitted input")

    def check_module(name, module):
        relative = (
            "__init__.py"
            if name == "evalopt_graph"
            else name.removeprefix("evalopt_graph.").replace(".", "/") + ".py"
        )
        origin = kernel / relative
        spec = getattr(module, "__spec__", None)
        if (
            relative not in expected
            or getattr(module, "__file__", None) != str(origin)
            or spec is None
            or spec.name != name
            or spec.origin != str(origin)
            or origin.resolve() != origin
            or hashlib.sha256(origin.read_bytes()).hexdigest() != expected[relative]["sha256"]
        ):
            raise ValueError("loaded evalopt_graph module is outside frozen kernel or changed")
        if name == "evalopt_graph" and list(getattr(module, "__path__", ())) != [str(kernel)]:
            raise ValueError("kernel package search path escapes frozen source")

    for name, module in list(sys.modules.items()):
        if name == "evalopt_graph" or name.startswith("evalopt_graph."):
            check_module(name, module)
    spec = importlib.util.find_spec("evalopt_graph")
    if (
        spec is None
        or spec.origin != str(kernel / "__init__.py")
        or list(spec.submodule_search_locations or ()) != [str(kernel)]
    ):
        raise ValueError("kernel import does not resolve to frozen package")
    before = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        importlib.import_module("evalopt_graph")
    finally:
        sys.dont_write_bytecode = before
    checked = []
    for name, module in list(sys.modules.items()):
        if name == "evalopt_graph" or name.startswith("evalopt_graph."):
            check_module(name, module)
            checked.append(name)
    return {"status": "PASS", "package_sha256": digest(expected), "modules": sorted(checked)}


def prepare(
    destination,
    *,
    harness,
    skill_c,
    task_root,
    upstream,
    agent_image,
    verifier_image,
    admission,
    kernel,
    stage="development",
    development_admission=None,
):
    harness, skill_c, task_root, upstream = map(
        lambda value: Path(value).resolve(), (harness, skill_c, task_root, upstream)
    )
    kernel = _preserved_kernel(kernel)
    inputs = reviewed_inputs(harness, skill_c, task_root)
    validate_admission(admission, inputs)
    _validate_stage_round(admission, stage, development_admission)
    catalog = strict_json((task_root / "catalog.json").read_bytes())
    tasks = catalog["tasks"] if isinstance(catalog, dict) else catalog
    validate_tasks(tasks, stage)
    image_identity(agent_image)
    image_identity(verifier_image)
    # Validate exact upstream bytes before copying any input or creating a store.
    skill_sources("B", upstream, skill_c, skill_c)
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink() or destination.resolve() != destination:
        raise ValueError("fresh campaign destination required")
    with tempfile.TemporaryDirectory(prefix="evalopt-v2-freeze-", dir=destination.parent) as temporary:
        frozen = Path(temporary).resolve() / "frozen"
        frozen.mkdir()
        copy_tree(harness, frozen / "harness")
        verify_harness_source_only(frozen / "harness")
        copy_tree(skill_c, frozen / "skill-c")
        derive_ablation(frozen / "skill-c", frozen / "skill-d")
        copy_tree(task_root, frozen / "tasks")
        (frozen / "kernel").mkdir()
        copy_tree(kernel, frozen / "kernel/evalopt_graph")
        exclusive_json(
            frozen / "environment.json", {"agent_image": agent_image, "verifier_image": verifier_image}
        )
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        git = ["git", "-c", "core.hooksPath=/dev/null", "-c", "init.templateDir="]
        subprocess.run(
            [
                *git,
                "clone",
                "--quiet",
                "--no-hardlinks",
                "--no-checkout",
                str(upstream),
                str(frozen / "upstream"),
            ],
            env=env,
            check=True,
            capture_output=True,
            timeout=60,
        )
        subprocess.run(
            [
                *git,
                "-C",
                str(frozen / "upstream"),
                "sparse-checkout",
                "set",
                "--no-cone",
                "/skills/",
                "/.claude-plugin/",
                "/LICENSE",
            ],
            env=env,
            check=True,
            capture_output=True,
            timeout=30,
        )
        # Freeze the entire plugin bundle and license from the pinned commit.
        # Non-cone patterns exclude unrelated root files (including upstream's
        # AGENTS.md symlink) without weakening any tree-manifest symlink rule.
        subprocess.run(
            [*git, "-C", str(frozen / "upstream"), "checkout", "--quiet", "--detach", UPSTREAM_COMMIT],
            env=env,
            check=True,
            capture_output=True,
            timeout=30,
        )
        skill_sources("B", frozen / "upstream", frozen / "skill-c", frozen / "skill-d")
        validate_pair(frozen / "skill-c", frozen / "skill-d")
        manifest = tree_manifest(frozen)
        if reviewed_inputs(harness, skill_c, task_root) != inputs:
            raise ValueError("reviewed inputs changed during freeze")
        _preserved_kernel(kernel)
        identities = derive_identities(frozen, admission, manifest)
        registered = registration(tasks, stage, identities, development_admission=development_admission)
        store = CampaignStore.create(destination, registered)
        os.rename(frozen, destination / "frozen")
        sync_directory(destination)
        exclusive_json(destination / "source-manifest.json", manifest)
        exclusive_json(destination / "admission.json", admission)
        receipt = {
            "registration_sha256": registered["registration_sha256"],
            "source_manifest_sha256": digest(manifest),
            "admission_sha256": digest(admission),
        }
        exclusive_json(destination / "freeze.json", receipt)
        verify_frozen(store.root, expected_sha256=registered["registration_sha256"])
        return receipt


def verify_frozen(root, *, expected_sha256):
    root = Path(root).absolute()
    verify_harness_source_only(root / "frozen/harness")
    store = CampaignStore(root, expected_sha256=expected_sha256)
    receipt = read_json(root / "freeze.json")
    manifest = read_json(root / "source-manifest.json")
    admission = read_json(root / "admission.json")
    if receipt != {
        "registration_sha256": expected_sha256,
        "source_manifest_sha256": digest(manifest),
        "admission_sha256": digest(admission),
    } or manifest != tree_manifest(root / "frozen"):
        raise ValueError("frozen campaign inputs changed")
    frozen = root / "frozen"
    validate_admission(admission, reviewed_inputs(frozen / "harness", frozen / "skill-c", frozen / "tasks"))
    _validate_stage_round(admission, store.registration["stage"], store.registration["development_admission"])
    validate_pair(frozen / "skill-c", frozen / "skill-d")
    skill_sources("B", frozen / "upstream", frozen / "skill-c", frozen / "skill-d")
    catalog = strict_json((frozen / "tasks/catalog.json").read_bytes())
    tasks = catalog["tasks"] if isinstance(catalog, dict) else catalog
    validate_tasks(tasks, store.registration["stage"])
    if tasks != store.registration["tasks"]:
        raise ValueError("frozen task catalog differs from registration")
    identities = derive_identities(frozen, admission, manifest)
    if identities != store.registration["identities"]:
        raise ValueError("frozen input identities differ from externally pinned registration")
    return store
