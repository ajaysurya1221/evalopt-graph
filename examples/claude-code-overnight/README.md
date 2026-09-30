# Claude Code overnight-run hooks (example)

Example [Claude Code hooks](https://docs.claude.com/en/docs/claude-code/hooks) and helper scripts
for letting a coding agent run unattended overnight under the deterministic permission classifier
in `evalopt_graph.permissions`.

**This directory is not part of the `evalopt-graph` package.** Nothing here ships in the wheel or
the sdist, and the kernel's stable API does not depend on it. The hooks were written for an external
Claude Code skill (`eval-opt`) that lives outside this repository; that skill is not included, and
the files here stand on their own as a worked example.

## What is here

| File | Hook event | Purpose |
| --- | --- | --- |
| `hooks/pretool_evalopt_safety.py` | `PreToolUse` | Classifies each tool call with `permissions.decide_overnight`: repo-local verification is allowed; destructive, global, remote-mutating, credentialed, or out-of-repo actions are denied. Fails closed if the package cannot be imported. |
| `hooks/permission_request_evalopt_overnight.py` | `PermissionRequest` | Answers permission dialogs the same way, so an unattended run never waits on a prompt. |
| `hooks/elicitation_evalopt_overnight.py` | `Elicitation`, `ElicitationResult` | Declines MCP elicitation requests during an overnight run and logs them for the morning report. |
| `hooks/stop_central_claim_check.py` | `Stop` | Refuses to finish while the claim ledger still holds an unverified central claim. |
| `elicitation-overnight.block.json` | settings fragment | The `hooks` block to merge into `~/.claude/settings.json` for the elicitation hook. |
| `apply_overnight_permissions.py` | script | Merges a permission/hook block into `~/.claude/settings.json`: dry-run by default, timestamped backup on `--apply`, unrelated settings preserved. |
| `check_overnight_readiness.py` | script | Read-only pre-flight check; reports `READY`, `READY_WITH_WARNINGS`, or `NOT_READY` through `permissions.assess_readiness`. |

Every hook is a no-op unless an overnight run is active (`EVALOPT_OVERNIGHT=1` in the environment
or `<repo>/.evalopt/overnight/ACTIVE` exists), so installing them does not change interactive
sessions. Deny rules in Claude Code settings always take precedence over these hooks.

## How this relates to the kernel

The kernel (`evalopt_graph.kernel`) decides whether a finished observation satisfies a policy. These
hooks sit one layer out: they decide which *actions* an agent may take while producing that
observation, using the same deterministic rules as the unattended governor in
`evalopt_graph.unattended`. Nothing here feeds or alters a kernel decision.

## Trying them

1. Copy the hook scripts to a stable location such as `~/.claude/hooks/`, and adjust the command
   paths in `elicitation-overnight.block.json` if you choose a different one.
2. Preview the settings merge, then apply it:

   ```bash
   python examples/claude-code-overnight/apply_overnight_permissions.py \
     --block examples/claude-code-overnight/elicitation-overnight.block.json
   python examples/claude-code-overnight/apply_overnight_permissions.py \
     --block examples/claude-code-overnight/elicitation-overnight.block.json --apply
   ```

3. Check readiness before starting a run:

   ```bash
   python examples/claude-code-overnight/check_overnight_readiness.py --repo .
   ```

The hooks and scripts import `evalopt_graph` from this repository's `src/` when the package is not
installed, so run them from a checkout or with `evalopt-graph` installed.
