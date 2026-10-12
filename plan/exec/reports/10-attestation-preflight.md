# Release attestation verification preflight

Read-only installed-CLI inspection: `gh version 2.97.0 (2026-07-31)`. `gh attestation verify --help` confirms support for `--repo`, `--signer-workflow`, `--source-digest`, `--source-ref`, `--deny-self-hosted-runners`, `--predicate-type` and JSON output. This is a capability observation, not verification of any candidate or published artifact.

Task10 will verify each actual wheel/sdist against the repository, the existing `.github/workflows/release.yml` signer, the exact released main commit and `refs/tags/v0.1.1`, with the default SLSA provenance predicate and hosted-runner requirement. Record the actual command, exit status and verified certificate/source identity. Retain native JSON privately; quote only sanitized identifiers and digests in the receipt. Existing SBOM attestations may be checked separately with their actual predicate type; never relabel one as the other.

The installed help warns that workflow-produced predicate fields can be manipulated by a compromised workflow context. Certificate identity and verified timestamps are distinct authenticated inputs. A successful attestation check therefore authenticates the tested artifact/producer binding under the verifier's trust rules; it establishes neither semantic correctness nor production safety. Published PyPI and GitHub distribution bytes must additionally match the accepted workflow bundle.

No attestation was fetched or verified, no artifact was published, and no setting, protection, credential or source file changed during this preflight. Raw help is retained in ignored logs/10-attestation-verify-help.txt.
