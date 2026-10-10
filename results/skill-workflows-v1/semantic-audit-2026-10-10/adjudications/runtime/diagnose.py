"""Optional NEW isolated diagnostics. Never invoked by audit.py or its replay tests."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import resource
import subprocess
import time
import uuid
from pathlib import Path

IMAGE = "sha256:37412af07bfd6a95db6c891f1d57bc2cff0fd569d1e23fcf5af86f1f32eb1d33"
TASK = "fixed-width-record-reader"
CASES_SHA256 = "11434360319bd4e77183505a8cc56c73a82d5a61567eebce6b012c2610ddb5f3"
SOURCE_PINS = {
    "r1--A": "2f070f40d37c70272c1b96c6fa6b697e5bd41284d74c2f933e1ace8c4526ce86",
    "r1--B": "28a60243cad618d8ef5baf2de6bb1c5153a75bbaade3fac833130a30a1173316",
    "r1--C": "d25d9616af42bae202f060a6433d9782f3803cc72844d24ab175df8e06e7a8fd",
    "r2--A": "761d2a0e5c9496f7a4213c5cd8633fd21250a7309ed2eb6f46cae49916a549aa",
    "r2--B": "dfbd58a36be163b1466e2b448eb87e28ba8dc61cdce00c3c04aa072e80d9a0df",
    "r2--C": "f10d10314edc53256aa4339a9eba8cd7029544fc2087bc796e8b5542af826927",
    "r3--A": "74673ec57681bf23e3b9be842da60feb350de67e3b3e3fbd34f052eaee2caf0a",
    "r3--B": "d8d309b77232c7ff3815c8b267256ea7cd906b55a97326187b765fecf9c2100f",
    "r3--C": "49b4ddec5de6ed21097fcd697cf9af53b95dd23105e397b4c86d2a2d10cbd73f",
}
CHILD = """import json,signal,sys
payload=json.loads(sys.stdin.read())
def expired(signum,frame):
    raise TimeoutError("diagnostic case deadline")
signal.signal(signal.SIGALRM,expired)
signal.alarm(5)
try:
    namespace={"__name__":"diagnostic_candidate"}
    exec(compile(payload["source"],"records.py","exec"),namespace)
    args=payload["request"]["args"]
    result=namespace[payload["request"]["function"]](*args)
    out={"result":result,"args":args}
except Exception as error:
    cls=type(error)
    out={"error":cls.__name__,"error_module":cls.__module__,
         "error_mro":[c.__module__+"."+c.__name__ for c in cls.__mro__],
         "args":payload["request"]["args"]}
finally:
    signal.alarm(0)
print(json.dumps(out,sort_keys=True,allow_nan=False))
"""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cap_capture_files() -> None:
    # Runs only in the new Docker CLI child before exec. Its stdout/stderr are
    # regular files, so RLIMIT_FSIZE really bounds capture rather than a pipe.
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))


def argv(name: str, program: str | None) -> list[str]:
    result = [
        "docker",
        "run",
        "--rm",
        "-i",
        "--pull",
        "never",
        "--network",
        "none",
        "--read-only",
        "--user",
        "65534:65534",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "64",
        "--memory",
        "256m",
        "--cpus",
        "1",
        "--name",
        name,
        "--label",
        "evalopt.semantic-audit=runtime-v1",
        "--entrypoint",
        "/usr/bin/python3",
        IMAGE,
        "-I",
        "-B",
    ]
    return result + (["-c", program] if program is not None else ["-"])


def prepared_cases(bundle: Path) -> list[dict]:
    runtime = json.loads((bundle / "runtime.json").read_text())
    if runtime["verifier_image"] != IMAGE:
        raise ValueError("original verifier image pin differs")
    case_bytes = (bundle / "sealed-tasks" / TASK / "hidden_cases.json").read_bytes()
    if sha(case_bytes) != CASES_SHA256:
        raise ValueError("case content pin differs")
    cases = json.loads(case_bytes)
    if len(cases) != 8:
        raise ValueError("case roster differs")
    rows = []
    for suffix, expected in SOURCE_PINS.items():
        trial = "heldout--" + TASK + "--" + suffix
        path = bundle / "evidence/trials" / trial / "attempt-1/agent/snapshot.json"
        snapshot = json.loads(path.read_text())
        source = base64.b64decode(snapshot["nodes"]["records.py"]["data"], validate=True)
        if sha(source) != expected:
            raise ValueError("retained candidate source differs")
        for index, case in enumerate(cases, 1):
            if (case["module"], case["function"]) != ("records", "parse_records"):
                raise ValueError("unregistered candidate function")
            rows.append(
                {
                    "trial_id": trial,
                    "case_number": index,
                    "source_sha256": expected,
                    "snapshot_sha256": sha(path.read_bytes()),
                    "payload": {
                        "source": source.decode("utf-8"),
                        "request": {key: case[key] for key in ("module", "function", "args")},
                    },
                }
            )
    return rows


def execute(bundle: Path, destination: Path, *, run=subprocess.run, monotonic=time.monotonic) -> dict:
    """Explicit invocation only; fresh destination; stop immediately on ambiguous transport."""
    if destination.exists():
        raise ValueError("diagnostic destination must be fresh")
    rows = prepared_cases(bundle)
    probe = Path(__file__).with_name("probe.py").read_bytes()
    inputs = {
        "runtime": sha((bundle / "runtime.json").read_bytes()),
        "hidden_cases": sha((bundle / "sealed-tasks" / TASK / "hidden_cases.json").read_bytes()),
        "helper": sha(Path(__file__).read_bytes()),
        "probe": sha(probe),
    }
    destination.mkdir()
    started = monotonic()
    records = []
    tasks = [(row, CHILD, json.dumps(row["payload"], allow_nan=False).encode()) for row in rows]
    tasks.append(({"kind": "stdlib_mechanism", "source_sha256": sha(probe)}, None, probe))
    for index, (row, program, data) in enumerate(tasks, 1):
        if monotonic() - started >= 300:
            raise TimeoutError("overall diagnostic budget exhausted; no more dispatch")
        name = "evalopt-semantic-runtime-" + uuid.uuid4().hex
        command = argv(name, program)
        metadata = {key: value for key, value in row.items() if key != "payload"}
        metadata.update({"index": index, "stdin_sha256": sha(data), "argv": command})
        # Record the prospective owned identity before launching, so a failed host
        # transport can be inspected separately. This helper never performs cleanup.
        stem = destination / f"case-{index:03d}"
        stem.with_suffix(".start.json").write_text(json.dumps(metadata, sort_keys=True, indent=2) + "\n")
        try:
            with (
                stem.with_suffix(".stdout").open("xb") as stdout,
                stem.with_suffix(".stderr").open("xb") as stderr,
            ):
                result = run(
                    command,
                    input=data,
                    stdout=stdout,
                    stderr=stderr,
                    preexec_fn=cap_capture_files,
                    timeout=15,
                    check=False,
                )
        except subprocess.TimeoutExpired as error:
            stem.with_suffix(".failure.json").write_text(
                json.dumps(
                    {
                        "status": "transport_timeout",
                        "container_absence": "unverified",
                        "further_dispatch": False,
                        "owned_name": name,
                    },
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            )
            raise RuntimeError("transport timeout; stop and inspect owned diagnostic container") from error
        stdout = stem.with_suffix(".stdout").read_bytes()
        stderr = stem.with_suffix(".stderr").read_bytes()
        record = {
            **metadata,
            "returncode": result.returncode,
            "stdout_sha256": sha(stdout),
            "stderr_sha256": sha(stderr),
        }
        stem.with_suffix(".end.json").write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
        if result.returncode != 0 or stderr:
            raise RuntimeError("diagnostic transport failed; no further dispatch")
        record["output"] = json.loads(stdout)
        records.append(record)
    if prepared_cases(bundle) != rows or inputs["probe"] != sha(
        Path(__file__).with_name("probe.py").read_bytes()
    ):
        raise ValueError("diagnostic source input drift")
    receipt = {
        "schema_version": "evalopt.new-semantic-diagnostics.v1",
        "image": IMAGE,
        "scope": "Posthoc diagnostic executions, not original hidden replies, graders, or model trials.",
        "original_trials_modified": False,
        "model_trials": 0,
        "input_sha256": inputs,
        "case_seconds": 5,
        "host_call_seconds": 15,
        "overall_seconds_limit": 300,
        "each_capture_byte_limit": 1048576,
        "records": records,
    }
    (destination / "results.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    result = execute(args.bundle.resolve(strict=True), args.destination.resolve())
    print(json.dumps({"records": len(result["records"]), "model_trials": 0}))
