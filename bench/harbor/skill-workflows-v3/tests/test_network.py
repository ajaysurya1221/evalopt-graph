"""Prospective network controls; no historical resource or model is touched."""

import asyncio
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v3 import network
from evalopt_v3.capture import LABEL, DockerController
from evalopt_v3.lifecycle import close_attempt, read_record

IMAGE = "sha256:" + "a" * 64
CONTAINER = "c" * 64
LABEL_VALUE = "trial-" + "a" * 32


class FakeDocker:
    def __init__(self, directory):
        self.directory = directory
        self.historical = {"1" * 64: {"id": "1" * 64, "ipam": [{"Subnet": "172.17.0.0/16"}]}}
        self.networks = copy.deepcopy(self.historical)
        self.pools = None
        self.calls = []
        self.created = 0
        self.fail_create = self.fail_disconnect = self.fail_remove = None
        self.create_response = None
        self.running = True
        self.endpoint = None
        self.project_collision = None
        self.container_identity = {"container_id": CONTAINER, "image_id": IMAGE, "attempt_label": LABEL_VALUE}

    def inspect_owned(self, identity):
        assert identity == self.container_identity
        return {
            "running": self.running,
            "paused": False,
            "stopped": not self.running,
            "observed_at": "fixture",
        }

    def command(self, argv, *, timeout):
        assert argv[0] == "docker" and timeout == 20
        args = argv[1:]
        self.calls.append(args)
        value = None
        if args[1] == "ls" and "--filter" in args:
            kind = "named_container" if args[-1].startswith("name=") else args[0]
            return SimpleNamespace(
                returncode=0,
                stdout=b"existing-resource\n" if kind == self.project_collision else b"",
                stderr=b"",
            )
        if args[0] == "info":
            value = self.pools
        elif args[:2] == ["network", "ls"]:
            return SimpleNamespace(
                returncode=0, stdout=("\n".join(self.networks) + "\n").encode(), stderr=b""
            )
        elif args[:2] == ["network", "inspect"]:
            if '"ipam":{{json .IPAM.Config}}' in args[3]:
                return SimpleNamespace(
                    returncode=0,
                    stdout=b"\n".join(
                        json.dumps(
                            {
                                "id": nid,
                                "ipam": self.networks[nid]["ipam"]
                                if nid in self.historical
                                else self.networks[nid]["ipam"]["Config"],
                            }
                        ).encode()
                        for nid in args[4:]
                    )
                    + b"\n",
                    stderr=b"",
                )
            value = self.networks[args[-1]]
        elif args[:2] == ["network", "create"]:
            plan = read_record(self.directory / "intent.json")
            assert args[-1] == plan["network_name"]
            assert args[args.index("--subnet") + 1] == plan["subnet"]
            assert args[args.index("--gateway") + 1] == plan["gateway"]
            self.created += 1
            if self.fail_create == "overlap":
                return SimpleNamespace(
                    returncode=1,
                    stdout=b"",
                    stderr=b"invalid pool request: Pool overlaps with other one on this address space",
                )
            nid = f"{self.created + 100:064x}"
            self.networks[nid] = {
                "id": nid,
                "name": plan["network_name"],
                "driver": "bridge",
                "scope": "local",
                "internal": False,
                "attachable": False,
                "ingress": False,
                "ipv6": False,
                "labels": {LABEL: LABEL_VALUE, network.OWNER_LABEL: plan["ownership_nonce"]},
                "ipam": {
                    "Driver": "default",
                    "Options": None,
                    "Config": [{"Subnet": plan["subnet"], "Gateway": plan["gateway"]}],
                },
                "options": {network.MASQUERADE: "true"},
                "containers": {},
            }
            if self.fail_create == "ambiguous":
                raise subprocess.TimeoutExpired(argv, timeout, output=b"partial daemon reply")
            return SimpleNamespace(
                returncode=0, stdout=(self.create_response or nid).encode() + b"\n", stderr=b""
            )
        elif args[:2] == ["container", "inspect"]:
            value = self.endpoint
        elif args[:2] == ["network", "disconnect"]:
            assert args[-1] == CONTAINER
            if self.fail_disconnect:
                return SimpleNamespace(returncode=1, stdout=b"", stderr=b"has active endpoints")
            self.endpoint["networks"] = {}
            self.networks[args[-2]]["containers"] = {}
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        elif args[:2] == ["network", "rm"]:
            assert args[-1] not in self.historical
            if self.fail_remove:
                return SimpleNamespace(returncode=1, stdout=b"", stderr=b"daemon unavailable")
            del self.networks[args[-1]]
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        else:
            pytest.fail(str(args))
        return SimpleNamespace(returncode=0, stdout=json.dumps(value).encode(), stderr=b"")

    def attach(self, owner):
        plan, ident = owner.plan, owner.identity
        ip = str(network.ipaddress.ip_network(plan["subnet"]).network_address + 2)
        self.endpoint = {
            "id": CONTAINER,
            "owner": plan["ownership_nonce"],
            "mode": plan["network_name"],
            "networks": {
                plan["network_name"]: {
                    "NetworkID": ident["network_id"],
                    "Gateway": plan["gateway"],
                    "IPAddress": ip,
                    "EndpointID": "e" * 64,
                }
            },
        }
        self.networks[ident["network_id"]]["containers"] = {
            CONTAINER: {"Name": LABEL_VALUE, "EndpointID": "e" * 64, "IPv4Address": ip + "/28"}
        }


def fixture(tmp_path):
    directory = tmp_path / "network"
    docker = FakeDocker(directory)
    owner = network.TrialNetwork(directory, command=docker.command, controller=docker)
    return owner, docker


def created(tmp_path):
    owner, docker = fixture(tmp_path)
    owner.create(attempt_label=LABEL_VALUE, image_id=IMAGE)
    docker.attach(owner)
    return owner, docker


def closed(tmp_path, monkeypatch):
    owner, docker = created(tmp_path)
    owner.bind(docker.container_identity)
    closure = {
        "identity": docker.container_identity,
        "execution_boundary": "confirmed",
        "snapshot": "complete",
        "failures": [],
    }
    monkeypatch.setattr(network, "recover_closure", lambda path: closure)
    docker.running = False
    return owner, docker, closure


def test_exhausted_default_pools_never_used_and_intent_predates_create(tmp_path):
    owner, docker = fixture(tmp_path)
    # Every built-in pool can be occupied: allocation is explicit and disjoint.
    docker.networks = {
        "1" * 64: {"id": "1" * 64, "ipam": [{"Subnet": "172.16.0.0/12"}, {"Subnet": "192.168.0.0/16"}]}
    }
    owner.create(attempt_label=LABEL_VALUE, image_id=IMAGE)
    assert owner.plan["subnet"] == "10.254.0.0/28"
    assert len([call for call in docker.calls if call[:2] == ["network", "create"]]) == 1
    assert not any(call[:2] in (["network", "prune"], ["system", "prune"]) for call in docker.calls)


def test_collision_inventory_skips_used_subnet_without_create_retry(tmp_path):
    owner, docker = fixture(tmp_path)
    docker.networks["1" * 64]["ipam"].append({"Subnet": "10.254.0.0/28"})
    owner.create(attempt_label=LABEL_VALUE, image_id=IMAGE)
    assert owner.plan["subnet"] == "10.254.0.16/28" and docker.created == 1


@pytest.mark.parametrize("kind", ["container", "named_container", "network", "volume"])
def test_existing_compose_project_or_container_name_never_reaches_harbor_cleanup(tmp_path, kind):
    owner, docker = fixture(tmp_path)
    docker.project_collision = kind
    with pytest.raises(network.NetworkError, match="project_already_exists"):
        owner.create(attempt_label=LABEL_VALUE, image_id=IMAGE)
    assert docker.created == 0 and docker.networks == docker.historical


@pytest.mark.parametrize("case", ["default_pool", "occupied_reservation"])
def test_full_or_overlapping_reservation_fails_before_create(tmp_path, case):
    owner, docker = fixture(tmp_path)
    if case == "default_pool":
        docker.pools = [{"Base": "10.0.0.0/8", "Size": 24}]
    else:
        docker.networks["1" * 64]["ipam"].append({"Subnet": "10.254.0.0/16"})
    with pytest.raises(network.NetworkError, match="reservation"):
        owner.create(attempt_label=LABEL_VALUE, image_id=IMAGE)
    assert docker.created == 0 and not (owner.directory / "intent.json").exists()


@pytest.mark.parametrize("failure", ["overlap", "ambiguous"])
def test_create_collision_or_ambiguous_return_stops_without_retry_or_cleanup(tmp_path, failure):
    owner, docker = fixture(tmp_path)
    docker.fail_create = failure
    with pytest.raises(network.NetworkError) as caught:
        owner.create(attempt_label=LABEL_VALUE, image_id=IMAGE)
    diagnostic = network.record_failure(tmp_path, "network_prepare", caught.value)
    assert diagnostic["docker_cause"] == (
        "docker_subnet_overlap" if failure == "overlap" else "docker_timeout"
    )
    assert docker.created == 1 and (owner.directory / "intent.json").exists()
    assert not (owner.directory / "created.json").exists()
    assert not any(call[:2] in (["network", "rm"], ["network", "disconnect"]) for call in docker.calls)


@pytest.mark.parametrize("returned", ["shortid", "1" * 64])
def test_wrong_create_ids_cannot_authenticate_network(tmp_path, returned):
    owner, docker = fixture(tmp_path)
    docker.create_response = returned
    with pytest.raises(network.NetworkError, match="identity_ambiguous"):
        owner.create(attempt_label=LABEL_VALUE, image_id=IMAGE)
    assert not (owner.directory / "created.json").exists()


@pytest.mark.parametrize(
    "field",
    [
        "labels",
        "id",
        "internal",
        "ipam",
        "options",
        "foreign_endpoint",
        "container_owner",
        "container_network",
        "extra_network",
    ],
)
def test_binding_rejects_wrong_identity_conditions_or_foreign_endpoint(tmp_path, field):
    owner, docker = created(tmp_path)
    actual = docker.networks[owner.identity["network_id"]]
    if field == "labels":
        actual["labels"][network.OWNER_LABEL] = "wrong"
    elif field == "id":
        actual["id"] = "f" * 64
    elif field == "internal":
        actual["internal"] = True
    elif field == "ipam":
        actual["ipam"]["Config"][0]["Subnet"] = "10.255.0.0/28"
    elif field == "options":
        actual["options"][network.MASQUERADE] = "false"
    elif field == "foreign_endpoint":
        actual["containers"]["f" * 64] = {}
    elif field == "container_owner":
        docker.endpoint["owner"] = "wrong"
    elif field == "container_network":
        docker.endpoint["networks"][owner.plan["network_name"]]["NetworkID"] = "f" * 64
    else:
        docker.endpoint["networks"]["extra"] = {}
    with pytest.raises(network.NetworkError):
        owner.bind(docker.container_identity)
    assert not (owner.directory / "binding.json").exists()


@pytest.mark.parametrize(
    "failure",
    [
        "running",
        "incomplete_capture",
        "unconfirmed_stop",
        "wrong_closure",
        "wrong_labels",
        "foreign_endpoint",
        "disconnect",
        "remove",
    ],
)
def test_release_failure_never_deletes_historical_and_preserves_capture(tmp_path, monkeypatch, failure):
    owner, docker, closure = closed(tmp_path, monkeypatch)
    archive = tmp_path / "retained.tar"
    archive.write_bytes(b"stopped evidence")
    expected = archive.read_bytes()
    if failure == "running":
        docker.running = True
    elif failure == "incomplete_capture":
        closure["snapshot"] = "partial"
    elif failure == "unconfirmed_stop":
        closure["execution_boundary"] = "unconfirmed"
    elif failure == "wrong_closure":
        closure["identity"] = dict(docker.container_identity, container_id="f" * 64)
    elif failure == "wrong_labels":
        docker.networks[owner.identity["network_id"]]["labels"][LABEL] = "wrong"
    elif failure == "foreign_endpoint":
        docker.networks[owner.identity["network_id"]]["containers"]["f" * 64] = {}
    elif failure == "disconnect":
        docker.fail_disconnect = True
    else:
        docker.fail_remove = True
    with pytest.raises(network.NetworkError):
        owner.release(docker.container_identity, closure_directory=tmp_path / "closure")
    assert not (owner.directory / "release.json").exists()
    assert archive.read_bytes() == expected
    assert all(docker.networks[nid] == value for nid, value in docker.historical.items())


def test_sequential_prospective_networks_reuse_explicit_subnet(tmp_path, monkeypatch):
    seen = []
    for index in range(5):
        trial = tmp_path / str(index)
        trial.mkdir()
        owner, docker, _ = closed(trial, monkeypatch)
        before = copy.deepcopy(docker.historical)
        owner.release(docker.container_identity, closure_directory=trial / "closure")
        assert docker.networks == before
        seen.append((owner.plan["subnet"], owner.identity["network_id"], owner.plan["ownership_nonce"]))
        with pytest.raises(network.NetworkError, match="already_started"):
            owner.release(docker.container_identity, closure_directory=trial / "closure")
    assert len({row[0] for row in seen}) == 1 and len({row[2] for row in seen}) == 5


def test_startup_diagnostic_classifies_true_pool_cause_without_raw_secret(tmp_path):
    secret = "Bearer SECRET-CREDENTIAL-MUST-NOT-LEAK"
    error = RuntimeError(
        "Docker compose command failed. " + secret + " all predefined address pools have been fully subnetted"
    )
    record = network.record_failure(tmp_path, "harbor_start", error)
    assert record["docker_cause"] == "docker_address_pool_exhausted"
    assert record["phase"] == "harbor_start" and not record["automatic_retry_allowed"]
    assert secret not in (tmp_path / "runtime-failure.json").read_text()
    assert record["diagnostic_sha256"] == hashlib.sha256((str(error) + "\n\n").encode()).hexdigest()


@pytest.mark.parametrize(
    "failed_phase", [None, "constructor", "harbor_start", "container_binding", "network_release"]
)
def test_bridge_network_binding_before_auth_and_failure_custody(tmp_path, monkeypatch, failed_phase):
    from evalopt_v3 import harbor_bridge as bridge

    events = []
    runtime = tmp_path / "runtime"
    identity = {"container_id": CONTAINER, "image_id": IMAGE, "attempt_label": LABEL_VALUE}
    from evalopt_v3.git_index import workspace_manifest
    from evalopt_v3.records import digest
    from test_phase_observations import retain_synthetic

    task = {
        "task_id": "fixture",
        "task_contract": "implementation",
        "category": "ordinary-bug-repair",
        "instruction": "Repair the fixture.",
        "visible_command": ["python3", "-B", "verify.py"],
    }

    def materialized(_source, target, **kwargs):
        target.mkdir()
        (target / "verify.py").write_text("pass\n")
        manifest = workspace_manifest(target)
        return {"task": task, "initial_sha256": digest(manifest), "initial_manifest": manifest}

    def observed(_snapshot, _task, **kwargs):
        return retain_synthetic(
            kwargs["directory"],
            attempt_id=kwargs["attempt_id"],
            candidate_id=kwargs["candidate_id"],
            phase=kwargs["phase"],
            command=task["visible_command"],
            code=0,
        )

    monkeypatch.setattr(bridge, "require_versions", lambda: {})
    monkeypatch.setattr(bridge, "image_identity", lambda _: None)
    monkeypatch.setattr(bridge, "auth_path", lambda: tmp_path / "auth-never-read")
    monkeypatch.setattr(bridge, "native_config", lambda _: ({}, "a" * 64))
    monkeypatch.setattr(bridge, "materialize", materialized)
    monkeypatch.setattr(bridge, "skill_sources", lambda *a: {})
    monkeypatch.setattr(bridge, "stage_skills", lambda *a, **k: {})
    monkeypatch.setattr(bridge, "visible_check", observed)
    monkeypatch.setattr(bridge, "snapshot_manifest", lambda _: {})
    monkeypatch.setattr(bridge, "_inspect_runtime_container", lambda *a: identity)
    monkeypatch.setattr(bridge, "subscription_permission", lambda: {"ordinary_usage_allowed": True})

    class OwnedNetwork:
        plan = {"ownership_nonce": "a" * 32}

        def __init__(self, directory):
            pass

        def create(self, **kwargs):
            events.append("network-create")
            return {"name": "owned-network", "network_id": "n" * 64}

        def bind(self, value):
            events.append("binding")
            if failed_phase == "container_binding":
                raise network.NetworkError("container_network_binding_changed")

        def release(self, value, **kwargs):
            assert (runtime / "result.json").read_bytes() == b"retained stopped result"
            events.append("release")
            if failed_phase == "network_release":
                raise network.NetworkError("network_command_failed")

    class Environment:
        def __init__(self, **kwargs):
            compose = json.loads((kwargs["environment_dir"] / "docker-compose.yaml").read_text())
            assert compose["networks"] == {"trial": {"external": True, "name": "owned-network"}}
            assert compose["services"]["main"]["networks"] == ["trial"]
            if failed_phase == "constructor":
                raise RuntimeError("constructor failed PRIVATE-TEXT")

        async def start(self, **kwargs):
            events.append("start")
            if failed_phase == "harbor_start":
                raise RuntimeError("all predefined address pools have been fully subnetted PRIVATE-TEXT")

        async def upload_dir(self, *args):
            events.append("upload")

        async def exec(self, *, command, **kwargs):
            return SimpleNamespace(
                return_code=0,
                stdout="codex-cli 0.154.0"
                if command == "codex --version"
                else '{"workspace":{},"skills":{},"config":{}}',
            )

    class Paths:
        def __init__(self, *args):
            self.agent_dir = runtime / "agent"

        def mkdir(self):
            pass

    class Agent:
        def __init__(self, **kwargs):
            pass

        async def prepare(self, *args, **kwargs):
            assert "binding" in events
            events.append("auth")

    async def supervised(*args, **kwargs):
        events.append("supervisor")
        return {}, None

    async def finish(*args, **kwargs):
        events.append("stopped-result")
        (runtime / "result.json").write_bytes(b"retained stopped result")
        return {"fixture": "retained"}

    for module, value in {
        "harbor.environments.docker.docker": {"DockerEnvironment": Environment},
        "harbor.models.agent.context": {"AgentContext": lambda: None},
        "harbor.models.task.config": {"EnvironmentConfig": lambda **k: k},
        "harbor.models.trial.paths": {"TrialPaths": Paths},
    }.items():
        monkeypatch.setitem(sys.modules, module, SimpleNamespace(**value))
    monkeypatch.setattr(bridge, "TrialNetwork", OwnedNetwork)
    monkeypatch.setattr(bridge, "retained_codex_class", lambda: Agent)
    monkeypatch.setattr(bridge, "run_supervised", supervised)
    monkeypatch.setattr(bridge, "finish_stopped", finish)
    run = bridge.execute_one(
        {"task_id": "fixture", "trial_id": "fixture", "arm": "B"},
        tmp_path,
        runtime,
        None,
        None,
        None,
        IMAGE,
        IMAGE,
        freeze_visible=lambda _: None,
    )
    if failed_phase is None:
        assert asyncio.run(run) == {"fixture": "retained"}
        assert (
            events.index("binding")
            < events.index("auth")
            < events.index("stopped-result")
            < events.index("release")
        )
        assert not (runtime / "runtime-failure.json").exists()
    else:
        with pytest.raises((RuntimeError, network.NetworkError)):
            asyncio.run(run)
        diagnostic = read_record(runtime / "runtime-failure.json")
        assert diagnostic["phase"] == ("harbor_start" if failed_phase == "constructor" else failed_phase)
        assert "PRIVATE-TEXT" not in (runtime / "runtime-failure.json").read_text()
        if failed_phase == "harbor_start":
            assert diagnostic["docker_cause"] == "docker_address_pool_exhausted"
        if failed_phase == "network_release":
            assert (runtime / "result.json").read_bytes() == b"retained stopped result"
        else:
            assert "auth" not in events


@pytest.mark.skipif(
    not os.environ.get("EVALOPT_V2_DOCKER_CONTROL_IMAGE"), reason="explicit local verifier image required"
)
def test_actual_docker_sequential_owned_networks_capture_and_release(tmp_path):
    """Real explicit networks and stopped copy, no auth, no model, no image pull."""
    image = os.environ["EVALOPT_V2_DOCKER_CONTROL_IMAGE"]
    controller = DockerController()
    before = subprocess.run(
        ["docker", "network", "ls", "--no-trunc", "--quiet"], check=True, capture_output=True, timeout=20
    ).stdout.splitlines()
    subnets = []
    for index in range(2):
        directory = tmp_path / str(index)
        directory.mkdir()
        owner = network.TrialNetwork(directory / "network")
        label = "trial-" + network.uuid.uuid4().hex
        owner.create(attempt_label=label, image_id=image)
        created = subprocess.run(
            [
                "docker",
                "create",
                "--pull",
                "never",
                "--name",
                label,
                "--label",
                LABEL + "=" + label,
                "--label",
                network.OWNER_LABEL + "=" + owner.plan["ownership_nonce"],
                "--network",
                owner.plan["network_name"],
                "--restart",
                "no",
                "--cpus",
                "1",
                "--memory",
                "2g",
                "--entrypoint",
                "/bin/sh",
                image,
                "-c",
                "echo offline-network-control > /candidate-root/control.txt; exec sleep 300",
            ],
            check=True,
            capture_output=True,
            timeout=20,
        )
        identity = {
            "container_id": created.stdout.decode().strip(),
            "image_id": image,
            "attempt_label": label,
        }
        try:
            subprocess.run(
                ["docker", "start", identity["container_id"]], check=True, capture_output=True, timeout=20
            )
            owner.bind(identity)
            closed_record = close_attempt(
                controller,
                identity,
                directory / "closure",
                ["/candidate-root/control.txt"],
                reason="agent_end",
            )
            assert (
                closed_record["execution_boundary"] == "confirmed" and closed_record["snapshot"] == "complete"
            )
            archive = directory / "closure/output-000.tar"
            digest_before = hashlib.sha256(archive.read_bytes()).hexdigest()
            owner.release(identity, closure_directory=directory / "closure")
            assert hashlib.sha256(archive.read_bytes()).hexdigest() == digest_before
            assert controller.inspect_owned(identity)["stopped"]
            assert read_record(owner.directory / "release.json")["status"] == "released"
            subnets.append(owner.plan["subnet"])
        finally:
            # Only the full prospective identity, after exact ownership/stop proof.
            if not controller.inspect_owned(identity)["stopped"]:
                controller.terminate(identity)
            subprocess.run(
                ["docker", "rm", identity["container_id"]], check=True, capture_output=True, timeout=20
            )
    after = subprocess.run(
        ["docker", "network", "ls", "--no-trunc", "--quiet"], check=True, capture_output=True, timeout=20
    ).stdout.splitlines()
    assert set(after) == set(before) and len(set(subnets)) == 1
