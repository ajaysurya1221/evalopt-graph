"""Prospective, exact-owned bridge networks; historical resources are read-only.

One explicit creation is attempted. Ambiguous creation or release stops the
caller; neither a different subnet nor a historical resource is a fallback.
The default Docker bridge/NAT internet behavior is retained for the agent.
"""

from __future__ import annotations

import hashlib
import ipaddress
import re
import subprocess
import uuid
from pathlib import Path

from .capture import HEX, LABEL, DockerController, check_identity, now, run_command
from .framing import SCHEMA, strict_json
from .lifecycle import digest, read_record, recover_closure, write_once

RESERVATION = ipaddress.IPv4Network("10.254.0.0/16")
PREFIX = 28
OWNER_LABEL = "evalopt.v2.prospective-network"
MASQUERADE = "com.docker.network.bridge.enable_ip_masquerade"
# Docker's built-in local bridge pools, used when no custom pools are reported.
DEFAULT_POOLS = (ipaddress.IPv4Network("172.16.0.0/12"), ipaddress.IPv4Network("192.168.0.0/16"))
PHASES = {
    "network_prepare",
    "harbor_start",
    "container_binding",
    "workspace_upload",
    "agent_prepare",
    "exposure",
    "subscription",
    "supervisor",
    "stopped_processing",
    "network_release",
}
CAUSES = {
    "docker_address_pool_exhausted": (
        "all predefined address pools have been fully subnetted",
        "could not find an available, non-overlapping ipv4 address pool",
    ),
    "docker_subnet_overlap": (
        "pool overlaps with other one on this address space",
        "invalid pool request: pool overlaps",
    ),
    "docker_network_name_collision": ("already exists",),
    "docker_active_endpoints": ("has active endpoints", "active endpoints"),
    "docker_daemon_unavailable": (
        "cannot connect to the docker daemon",
        "error during connect",
        "connection refused",
    ),
    "docker_permission_denied": ("permission denied", "access is denied"),
}


class NetworkError(ValueError):
    """Static classification, never interpolated raw Docker output."""

    def __init__(self, reason, *, docker_cause=None):
        super().__init__(reason)
        self.reason, self.docker_cause = reason, docker_cause


def _bytes(value):
    if value is None:
        return b""
    return value if isinstance(value, bytes) else str(value).encode("utf-8", "backslashreplace")


def _cause(raw):
    text = raw.decode("utf-8", "replace").lower()
    for cause, patterns in CAUSES.items():
        if any(pattern in text for pattern in patterns):
            return cause
    return "docker_cause_unclassified"


def record_failure(directory, phase, error):
    """Retain safe cause/provenance without serializing credential-bearing text."""
    if phase not in PHASES:
        raise ValueError("invalid_runtime_failure_phase")
    pieces = [
        _bytes(str(error)),
        _bytes(getattr(error, "stdout", None)),
        _bytes(getattr(error, "stderr", None)),
    ]
    raw = b"\n".join(pieces)
    known = {
        "NetworkError",
        "RuntimeError",
        "ValueError",
        "OSError",
        "PermissionError",
        "FileNotFoundError",
        "TimeoutError",
        "TimeoutExpired",
        "CalledProcessError",
        "CancelledError",
    }
    record = {
        "schema_version": SCHEMA,
        "kind": "runtime_failure_diagnostic",
        "phase": phase,
        "error_type": type(error).__name__ if type(error).__name__ in known else "Exception",
        "classification": error.reason if isinstance(error, NetworkError) else "runtime_phase_failed",
        "docker_cause": getattr(error, "docker_cause", None)
        or (
            "docker_timeout" if isinstance(error, (TimeoutError, subprocess.TimeoutExpired)) else _cause(raw)
        ),
        "diagnostic_bytes": len(raw),
        "diagnostic_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_diagnostic_retained": False,
        "automatic_retry_allowed": False,
        "observed_at": now(),
    }
    write_once(Path(directory) / "runtime-failure.json", record)
    return record


class TrialNetwork:
    """Fresh network intent and safe exact release, outside the agent container."""

    def __init__(self, directory, *, command=run_command, controller=None):
        self.directory = Path(directory).absolute()
        if self.directory.resolve() != self.directory or self.directory.exists():
            raise NetworkError("network_record_directory_not_fresh")
        self.directory.mkdir(mode=0o700)
        self.command = command
        self.controller = controller or DockerController(command=command)
        self.sequence = 0
        self.plan = self.identity = None

    def _call(self, operation, argv):
        self.sequence += 1
        record = {
            "schema_version": SCHEMA,
            "kind": "network_command",
            "operation": operation,
            "observed_at": now(),
        }
        try:
            result = self.command(["docker", *argv], timeout=20)
        except (OSError, subprocess.TimeoutExpired) as error:
            record.update(
                status="unavailable",
                returncode=None,
                cause="docker_timeout"
                if isinstance(error, subprocess.TimeoutExpired)
                else "docker_transport_unavailable",
            )
            for channel in ("stdout", "stderr"):
                raw = _bytes(getattr(error, channel, None))
                record[channel + "_bytes"] = len(raw)
                record[channel + "_sha256"] = hashlib.sha256(raw).hexdigest()
            write_once(self.directory / f"command-{self.sequence:03d}.json", record)
            raise NetworkError("network_command_ambiguous", docker_cause=record["cause"]) from None
        for channel in ("stdout", "stderr"):
            raw = _bytes(getattr(result, channel))
            record[channel + "_bytes"] = len(raw)
            record[channel + "_sha256"] = hashlib.sha256(raw).hexdigest()
        record.update(
            status="returned",
            returncode=result.returncode,
            cause=None
            if result.returncode == 0
            else _cause(_bytes(result.stderr) + b"\n" + _bytes(result.stdout)),
        )
        write_once(self.directory / f"command-{self.sequence:03d}.json", record)
        if result.returncode != 0:
            raise NetworkError("network_command_failed", docker_cause=record["cause"])
        if any(record[channel + "_bytes"] > 1024 * 1024 for channel in ("stdout", "stderr")):
            raise NetworkError("network_command_output_limit")
        return _bytes(result.stdout)

    def _ids(self):
        raw = self._call("network_list", ["network", "ls", "--no-trunc", "--quiet"])
        ids = raw.decode("ascii").splitlines()
        if not ids or len(ids) > 4096 or len(set(ids)) != len(ids) or any(not HEX.fullmatch(x) for x in ids):
            raise NetworkError("network_inventory_invalid")
        return ids

    def _pools(self):
        value = strict_json(
            self._call("default_pool_inspect", ["info", "--format", "{{json .DefaultAddressPools}}"])
        )
        if value is None or value == []:
            return DEFAULT_POOLS
        if type(value) is not list or len(value) > 256:
            raise NetworkError("docker_default_pools_invalid")
        pools = []
        for entry in value:
            if type(entry) is not dict or set(entry) != {"Base", "Size"} or type(entry["Size"]) is not int:
                raise NetworkError("docker_default_pools_invalid")
            network = ipaddress.ip_network(entry["Base"])
            if not network.prefixlen <= entry["Size"] <= network.max_prefixlen:
                raise NetworkError("docker_default_pools_invalid")
            pools.append(network)
        return pools

    def create(self, *, attempt_label, image_id):
        if (
            self.plan is not None
            or not re.fullmatch(r"trial-[0-9a-f]{32}", attempt_label)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id)
        ):
            raise NetworkError("network_creation_identity_invalid")
        # Harbor runs compose-down before compose-up. Establish that this exact
        # random project/name has no old resources before allowing that path.
        project = "label=com.docker.compose.project=" + attempt_label
        for operation, argv in (
            (
                "project_containers",
                ["container", "ls", "--all", "--quiet", "--no-trunc", "--filter", project],
            ),
            (
                "named_container",
                [
                    "container",
                    "ls",
                    "--all",
                    "--quiet",
                    "--no-trunc",
                    "--filter",
                    "name=^/" + attempt_label + "$",
                ],
            ),
            ("project_networks", ["network", "ls", "--quiet", "--no-trunc", "--filter", project]),
            ("project_volumes", ["volume", "ls", "--quiet", "--filter", project]),
        ):
            if self._call(operation, argv).strip():
                raise NetworkError("prospective_project_already_exists")
        pools = self._pools()
        if any(pool.version == 4 and pool.overlaps(RESERVATION) for pool in pools):
            raise NetworkError("network_reservation_overlaps_default_pool")
        ids = self._ids()
        template = '{"id":{{json .Id}},"ipam":{{json .IPAM.Config}}}'
        raw = self._call("network_subnets", ["network", "inspect", "--format", template, *ids])
        rows = [strict_json(line) for line in raw.split(b"\n") if line]
        if len(rows) != len(ids) or {item.get("id") for item in rows} != set(ids):
            raise NetworkError("network_inventory_changed")
        occupied = []
        for row in rows:
            if set(row) != {"id", "ipam"} or row["ipam"] is not None and type(row["ipam"]) is not list:
                raise NetworkError("network_ipam_invalid")
            for cfg in row["ipam"] or []:
                if type(cfg) is not dict or type(cfg.get("Subnet")) is not str:
                    raise NetworkError("network_ipam_invalid")
                occupied.append(ipaddress.ip_network(cfg["Subnet"]))
        subnet = next(
            (
                item
                for item in RESERVATION.subnets(new_prefix=PREFIX)
                if not any(other.version == 4 and item.overlaps(other) for other in occupied)
            ),
            None,
        )
        if subnet is None:
            raise NetworkError("network_reservation_exhausted")
        nonce = uuid.uuid4().hex
        self.plan = {
            "schema_version": SCHEMA,
            "kind": "prospective_network_intent",
            "attempt_label": attempt_label,
            "image_id": image_id,
            "ownership_nonce": nonce,
            "network_name": "evalopt-v2-" + nonce,
            "subnet": str(subnet),
            "gateway": str(subnet.network_address + 1),
            "reservation": str(RESERVATION),
            "driver": "bridge",
            "internal": False,
            "inventory_sha256": hashlib.sha256(raw).hexdigest(),
            "created_at": now(),
        }
        # Durable exact intent predates the one possible Docker create call.
        write_once(self.directory / "intent.json", self.plan)
        raw_id = self._call(
            "network_create",
            [
                "network",
                "create",
                "--driver",
                "bridge",
                "--subnet",
                self.plan["subnet"],
                "--gateway",
                self.plan["gateway"],
                "--label",
                LABEL + "=" + attempt_label,
                "--label",
                OWNER_LABEL + "=" + nonce,
                "--opt",
                MASQUERADE + "=true",
                self.plan["network_name"],
            ],
        )
        network_id = raw_id.decode("ascii").strip()
        if not HEX.fullmatch(network_id) or network_id in ids:
            raise NetworkError("network_creation_identity_ambiguous")
        self.identity = {"network_id": network_id, "intent_sha256": digest(self.plan)}
        write_once(self.directory / "created.json", self.identity)
        if self.inspect()["containers"]:
            raise NetworkError("new_network_has_endpoints")
        return {"name": self.plan["network_name"], "network_id": network_id}

    def inspect(self):
        if (
            self.identity is None
            or self.plan != read_record(self.directory / "intent.json")
            or self.identity != read_record(self.directory / "created.json")
        ):
            raise NetworkError("network_ownership_record_changed")
        template = '{"id":{{json .Id}},"name":{{json .Name}},"driver":{{json .Driver}},"scope":{{json .Scope}},"internal":{{json .Internal}},"attachable":{{json .Attachable}},"ingress":{{json .Ingress}},"ipv6":{{json .EnableIPv6}},"labels":{{json .Labels}},"ipam":{{json .IPAM}},"options":{{json .Options}},"containers":{{json .Containers}}}'
        obj = strict_json(
            self._call(
                "network_inspect", ["network", "inspect", "--format", template, self.identity["network_id"]]
            )
        )
        # Docker 29 injects explicit IPv4/IPv6 options and serializes empty
        # IPAM options as {}; older supported serialization uses null. Only
        # these known default-preserving spellings are accepted.
        options = obj.get("options") if isinstance(obj, dict) else None
        ipam_options = (
            obj.get("ipam", {}).get("Options")
            if isinstance(obj, dict) and isinstance(obj.get("ipam"), dict)
            else "invalid"
        )
        if (
            type(options) is not dict
            or set(options) - {MASQUERADE, "com.docker.network.enable_ipv4", "com.docker.network.enable_ipv6"}
            or options.get(MASQUERADE) != "true"
            or options.get("com.docker.network.enable_ipv4", "true") != "true"
            or options.get("com.docker.network.enable_ipv6", "false") != "false"
            or ipam_options not in (None, {})
        ):
            raise NetworkError("network_identity_or_conditions_changed")
        expected = {
            "id": self.identity["network_id"],
            "name": self.plan["network_name"],
            "driver": "bridge",
            "scope": "local",
            "internal": False,
            "attachable": False,
            "ingress": False,
            "ipv6": False,
            "labels": {LABEL: self.plan["attempt_label"], OWNER_LABEL: self.plan["ownership_nonce"]},
            "ipam": {
                "Driver": "default",
                "Options": ipam_options,
                "Config": [{"Subnet": self.plan["subnet"], "Gateway": self.plan["gateway"]}],
            },
            "options": options,
        }
        if (
            type(obj) is not dict
            or set(obj) != set(expected) | {"containers"}
            or any(obj[key] != value for key, value in expected.items())
            or any(type(obj[key]) is not bool for key in ("internal", "attachable", "ingress", "ipv6"))
            or type(obj["containers"]) is not dict
        ):
            raise NetworkError("network_identity_or_conditions_changed")
        return obj

    def _attachment(self, identity, *, running):
        check_identity(identity)
        if (
            identity["attempt_label"] != self.plan["attempt_label"]
            or identity["image_id"] != self.plan["image_id"]
        ):
            raise NetworkError("network_container_ownership_changed")
        observation = self.controller.inspect_owned(identity)
        if (
            observation["running"] is not running
            or observation.get("paused") is not False
            or (not running and observation["stopped"] is not True)
        ):
            raise NetworkError("network_container_state_unsafe")
        template = (
            '{"id":{{json .Id}},"owner":{{json (index .Config.Labels "'
            + OWNER_LABEL
            + '")}},"mode":{{json .HostConfig.NetworkMode}},"networks":{{json .NetworkSettings.Networks}}}'
        )
        obj = strict_json(
            self._call(
                "container_network_inspect",
                ["container", "inspect", "--format", template, identity["container_id"]],
            )
        )
        if (
            type(obj) is not dict
            or set(obj) != {"id", "owner", "mode", "networks"}
            or obj["id"] != identity["container_id"]
            or obj["owner"] != self.plan["ownership_nonce"]
            or obj["mode"] not in {self.plan["network_name"], self.identity["network_id"]}
            or type(obj["networks"]) is not dict
            or set(obj["networks"]) != {self.plan["network_name"]}
        ):
            raise NetworkError("container_network_binding_changed")
        endpoint = obj["networks"][self.plan["network_name"]]
        if type(endpoint) is not dict or endpoint.get("NetworkID") != self.identity["network_id"]:
            raise NetworkError("container_network_identity_changed")
        if running and (
            endpoint.get("Gateway") != self.plan["gateway"]
            or not isinstance(endpoint.get("IPAddress"), str)
            or ipaddress.ip_address(endpoint["IPAddress"]) not in ipaddress.ip_network(self.plan["subnet"])
        ):
            raise NetworkError("container_network_address_changed")
        network = self.inspect()
        if set(network["containers"]) - {identity["container_id"]}:
            raise NetworkError("network_has_foreign_endpoint")
        if running:
            peer = network["containers"].get(identity["container_id"])
            if (
                type(peer) is not dict
                or peer.get("Name") != self.plan["attempt_label"]
                or peer.get("EndpointID") != endpoint.get("EndpointID")
                or not isinstance(peer.get("EndpointID"), str)
                or not HEX.fullmatch(peer["EndpointID"])
            ):
                raise NetworkError("network_endpoint_identity_changed")
        return observation

    def bind(self, identity):
        observed = self._attachment(identity, running=True)
        record = {
            "schema_version": SCHEMA,
            "kind": "trial_network_binding",
            "container_identity": identity,
            "network_identity": self.identity,
            "observed_at": observed["observed_at"],
            "before_auth_upload": True,
        }
        write_once(self.directory / "binding.json", record)
        return record

    def release(self, identity, *, closure_directory):
        """No historical discovery or recovery. Release only this instance's resource."""
        if (self.directory / "release-intent.json").exists():
            raise NetworkError("network_release_already_started")
        binding = read_record(self.directory / "binding.json")
        if binding["container_identity"] != identity or binding["network_identity"] != self.identity:
            raise NetworkError("network_release_binding_changed")
        closure = recover_closure(closure_directory)
        if (
            closure["identity"] != identity
            or closure["execution_boundary"] != "confirmed"
            or closure["snapshot"] != "complete"
            or closure["failures"]
        ):
            raise NetworkError("network_release_requires_durable_capture")
        self._attachment(identity, running=False)
        write_once(
            self.directory / "release-intent.json",
            {
                "schema_version": SCHEMA,
                "kind": "trial_network_release_intent",
                "container_identity": identity,
                "network_identity": self.identity,
                "closure_sha256": digest(closure),
                "observed_at": now(),
            },
        )
        # Do not force-disconnect: Docker must also agree the precise endpoint is detachable.
        self._call(
            "network_disconnect",
            ["network", "disconnect", self.identity["network_id"], identity["container_id"]],
        )
        if self.controller.inspect_owned(identity)["stopped"] is not True or self.inspect()["containers"]:
            raise NetworkError("network_release_not_quiescent")
        self._call("network_remove", ["network", "rm", self.identity["network_id"]])
        if (
            self.identity["network_id"] in self._ids()
            or self.controller.inspect_owned(identity)["stopped"] is not True
        ):
            raise NetworkError("network_release_unconfirmed")
        record = {
            "schema_version": SCHEMA,
            "kind": "trial_network_release",
            "network_identity": self.identity,
            "container_identity": identity,
            "closure_sha256": digest(closure),
            "status": "released",
            "observed_at": now(),
            "container_removed": False,
        }
        write_once(self.directory / "release.json", record)
        return record
