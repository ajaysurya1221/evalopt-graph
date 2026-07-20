"""Filesystem and retrieving adapters kept outside the pure kernel import graph."""

from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .attestation import (
    BLOCKED,
    FAILED,
    UNSUPPORTED,
    AdapterPolicy,
    EvidenceAttestation,
    EvidenceRequest,
    RetrievedArtifact,
    SupportAssessment,
    _issue_failure,
    _issue_material,
    _revalidate_material,
)
from .epistemic import T0_DETERMINISTIC, T1_PRIMARY


@dataclass(frozen=True)
class EvidenceResult:
    attestation: EvidenceAttestation
    support_assessment: SupportAssessment


@dataclass(frozen=True)
class AttestationValidation:
    valid: bool
    status: str
    reason: str


class EvidenceAdapter(Protocol):
    @property
    def policy(self) -> AdapterPolicy: ...

    def retrieve(self, locator: str) -> RetrievedArtifact: ...


class _BlockedRetrieval(Exception):
    pass


class _UnsupportedRetrieval(Exception):
    pass


class RecordedEvidenceAdapter:
    def __init__(self, policy: AdapterPolicy, artifacts: Mapping[str, RetrievedArtifact]) -> None:
        self._policy, self._artifacts = policy, dict(artifacts)

    @property
    def policy(self) -> AdapterPolicy:
        return self._policy

    def retrieve(self, locator: str) -> RetrievedArtifact:
        try:
            return self._artifacts[locator]
        except KeyError as exc:
            raise _UnsupportedRetrieval(f"locator is not present in recorded adapter: {locator}") from exc


class DeterministicToolAdapter(RecordedEvidenceAdapter):
    def __init__(self, artifacts: Mapping[str, RetrievedArtifact]) -> None:
        super().__init__(
            AdapterPolicy(
                "deterministic_tool",
                "1",
                "test_output",
                T0_DETERMINISTIC,
                "recorded_deterministic_tool_observation",
                "text/plain@1",
                True,
            ),
            artifacts,
        )


class LocalFileAdapter:
    """Bounded regular-file reads relative to an already-open root directory."""

    def __init__(self, root: str | os.PathLike[str], *, max_bytes: int = 2_000_000) -> None:
        self._root = Path(root).resolve(strict=True)
        if not self._root.is_dir():
            raise ValueError("local evidence root must be a directory")
        if os.open not in os.supports_dir_fd or not all(
            hasattr(os, name) for name in ("O_DIRECTORY", "O_NOFOLLOW")
        ):
            raise RuntimeError("local evidence requires openat-style no-follow support")
        self._policy = AdapterPolicy(
            "local_file",
            "1",
            "local_file",
            T1_PRIMARY,
            "bounded_local_file_read",
            "text/plain@1",
            True,
            max_bytes,
        )

    @property
    def policy(self) -> AdapterPolicy:
        return self._policy

    def retrieve(self, locator: str) -> RetrievedArtifact:
        path = Path(locator)
        parts = path.parts
        if path.is_absolute() or not locator or any(part in {"", ".", ".."} for part in parts):
            raise _BlockedRetrieval("absolute, empty, or traversal local-file locator is blocked")
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        opened: list[int] = []
        try:
            current = os.open(self._root, flags | os.O_DIRECTORY)
            opened.append(current)
            for part in parts[:-1]:
                current = os.open(part, flags | os.O_DIRECTORY, dir_fd=current)
                opened.append(current)
            leaf = os.open(parts[-1], flags, dir_fd=current)
            opened.append(leaf)
            before = os.fstat(leaf)
            if not stat.S_ISREG(before.st_mode):
                raise _BlockedRetrieval("local evidence locator is not a regular file")
            chunks, remaining = [], self._policy.max_bytes + 1
            while remaining:
                chunk = os.read(leaf, min(65_536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            content = b"".join(chunks)
            after = os.fstat(leaf)

            def identity(item: os.stat_result) -> tuple[int, int, int, int]:
                return item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns

            if len(content) > self._policy.max_bytes:
                raise _BlockedRetrieval("local evidence file exceeds the configured byte limit")
            if identity(before) != identity(after):
                raise _BlockedRetrieval("local evidence file changed while it was read")
        except FileNotFoundError as exc:
            raise _UnsupportedRetrieval(f"local evidence file is missing: {locator}") from exc
        except _BlockedRetrieval:
            raise
        except OSError as exc:
            raise _BlockedRetrieval(f"local evidence path is blocked: {exc}") from exc
        finally:
            for descriptor in reversed(opened):
                os.close(descriptor)
        return RetrievedArtifact(content, self._root.joinpath(*parts).as_uri(), "", "text/plain")


class EvidenceAuthority:
    """Deprecated retrieving facade; stable kernel callers supply material explicitly."""

    def __init__(self, adapters: list[EvidenceAdapter] | tuple[EvidenceAdapter, ...], *, now=None) -> None:
        self._adapters: dict[str, EvidenceAdapter] = {}
        self._policies: dict[str, AdapterPolicy] = {}
        self._frozen = False
        self._now = now or (lambda: datetime.now(timezone.utc).isoformat())
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: EvidenceAdapter) -> None:
        adapter_id = adapter.policy.adapter_id
        if adapter_id in self._adapters:
            raise ValueError(f"duplicate evidence adapter id: {adapter_id}")
        self._adapters[adapter_id] = adapter
        self._policies[adapter_id] = adapter.policy

    def has_adapter(self, adapter_id: str) -> bool:
        return adapter_id in self._adapters

    def snapshot(self) -> EvidenceAuthority:
        snapshot = EvidenceAuthority([], now=self._now)
        snapshot._adapters = dict(self._adapters)
        snapshot._policies = dict(self._policies)
        snapshot._frozen = True
        return snapshot

    def attest(
        self,
        request: EvidenceRequest,
        *,
        claim_text: str,
        claim_type: str = "",
        claim_subject: str = "",
        claim_stance: str = "",
    ) -> EvidenceResult:
        adapter = self._adapters.get(request.adapter_id)
        policy = (
            self._policies.get(request.adapter_id) if self._frozen else adapter.policy if adapter else None
        )
        if adapter is None or policy is None:
            pair = _issue_failure(
                request,
                claim_text=claim_text,
                claim_type=claim_type,
                claim_subject=claim_subject,
                claim_stance=claim_stance,
                status=UNSUPPORTED,
                reason=f"evidence adapter is not registered: {request.adapter_id or '(missing)'}",
            )
        else:
            try:
                material = adapter.retrieve(request.locator)
            except _BlockedRetrieval as exc:
                status, reason = BLOCKED, str(exc)
            except _UnsupportedRetrieval as exc:
                status, reason = UNSUPPORTED, str(exc)
            except Exception as exc:
                status, reason = FAILED, f"evidence adapter retrieval failed: {type(exc).__name__}"
            else:
                pair = _issue_material(
                    policy,
                    request,
                    material,
                    observed_at=self._now(),
                    claim_text=claim_text,
                    claim_type=claim_type,
                    claim_subject=claim_subject,
                    claim_stance=claim_stance,
                )
                return EvidenceResult(*pair)
            pair = _issue_failure(
                request,
                claim_text=claim_text,
                claim_type=claim_type,
                claim_subject=claim_subject,
                claim_stance=claim_stance,
                status=status,
                reason=reason,
            )
        return EvidenceResult(*pair)

    def revalidate(self, evidence: EvidenceAttestation) -> AttestationValidation:
        adapter = self._adapters.get(evidence.adapter_id)
        policy = (
            self._policies.get(evidence.adapter_id) if self._frozen else adapter.policy if adapter else None
        )
        if adapter is None or policy is None:
            return AttestationValidation(False, UNSUPPORTED, "attestation adapter is not registered")
        try:
            material = adapter.retrieve(evidence.requested_locator)
        except _BlockedRetrieval as exc:
            return AttestationValidation(False, BLOCKED, str(exc))
        except _UnsupportedRetrieval as exc:
            return AttestationValidation(False, UNSUPPORTED, str(exc))
        except Exception as exc:
            return AttestationValidation(False, FAILED, f"adapter retrieval failed: {exc}")
        return AttestationValidation(*_revalidate_material(policy, evidence, material))


__all__ = [
    "AttestationValidation",
    "DeterministicToolAdapter",
    "EvidenceAdapter",
    "EvidenceAuthority",
    "EvidenceResult",
    "LocalFileAdapter",
    "RecordedEvidenceAdapter",
]
