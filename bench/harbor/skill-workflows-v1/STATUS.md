# Campaign implementation status

Protocol: `evalopt-skill-workflows-v1`. Status: implementation in progress.

The current development pilot has nine of 36 terminal outcomes. It is paused
because one interrupted child has incomplete native usage telemetry. No held-out
or transfer model trials have run, and no comparative claim is established.
Held-out trials must wait for pilot QA, separate task review and immutable
registration. See [the retained pilot incidents](evidence/PILOT_INCIDENTS.md).

| Work package | State | Acceptance evidence |
| --- | --- | --- |
| Portable skill | Implemented and reviewed | Clean loader/reference validation; read-only forward review fixture preserved |
| Campaign core | Implemented and reviewed | Immutable capture, policy replay, interrupted finalization and paired analysis controls |
| Development tasks | Reviewed | 12 isolated Docker/chroot oracle controls pass; negative and boundary controls pass |
| Runtime | Capability checks pass | Actual model/effort, complete skill reads and two native children verified; Harbor oracle and forced-timeout lifecycle controls pass |
| Held-out tasks | Authored and separately reviewed; not frozen | 48 distinct problems; 126 incorrect/oracle control variants plus targeted review corrections |
| Development pilot | Nine of 36 recorded; paused | Eight complete usage records; ninth outcome retained with unavailable exact usage |
| Held-out integration | Implemented and separately reviewed | Sealed 48-task loader; all 48 Docker/chroot oracle controls and six Harbor lifecycle smoke controls pass |
| Hidden-grade retention | Implemented and separately reviewed | Actual hidden replies retained after policy freeze; all 12 Docker/chroot oracle controls pass |
| Transfer integration | Implemented and separately reviewed | Real Docker deadline controls pass; dispatch requires the same frozen candidate and all 432 primary outcomes accounted for |
| Publication tooling | Implemented and separately reviewed | Separate pilot, held-out and transfer schemas; 43 held-out release controls; nine-attempt pilot candidate reproduces with 27 policy decisions replayed |

The current native capability probe used the requested model and reasoning effort
through existing subscription authentication. Capability probes and offline controls
are not benchmark trials. The final passing native probe recorded 125,624 input tokens,
422 output tokens, eight model calls, five tool calls and 31.309 parent wall seconds
across one parent and two children. Earlier probe failures remain retained privately
and must accompany the eventual resource report.

The runtime has a fresh included-usage permission check before each dispatch. Unknown
permission or subscription exhaustion prevents dispatch; neither credits nor another
billing route are selected. Missing native accounting pauses the campaign.

The partial public evidence candidate remains local. No benchmark result bundle
has been uploaded or published. The original pilot's telemetry-corruption incident and all capability
probe attempts remain retained separately; unavailable usage is not zero usage.

CI has a required offline benchmark lane pinned to CPython 3.13.12. The stable
kernel matrix remains intact; other interpreters explicitly skip only the new
workflow benchmark modules. Hosted CI must be verified on the exact pull-request
head; local checks do not substitute for it.

Final local verification: 765 tests pass. The default suite skips three explicitly
enabled Docker controls; all three pass when run with the cached runtime digest.
Ruff, formatting, workflow action pins, wheel/sdist hygiene, and a clean wheel
installation's stable API/serialization/replay check pass. These checks establish
implementation behavior, not a workflow advantage.

Task review is by a separate agent role under the maintainer's control. It is not
independent human authorship or independent replication. Some held-out requirements
are finite models of ordering, planning or cleanup; they do not demonstrate operating
system durability or general concurrent-system correctness.

The existing `evalopt-governance-external-v1` protocol remains unexecuted.
This maintainer-run study does not meet its independent-human-authorship gate.
