"""Pure phase-bound reporting checks over controller-owned retained observations.

Only caller-established custody makes a record controller evidence. Neither a
producer label nor a self-consistent digest is authentication. Initial facts are
never compared with later observations, even when command argv is identical.
"""

from __future__ import annotations

from .records import canonical, validate_record
from .response_contract import CHECK_FIELDS, envelope_valid

_UNSET = object()


def check_claim(observation):
    """The common response projection; this does not change observation custody."""
    validate_record(observation)
    if observation["record_type"] != "command":
        raise ValueError("command observation required")
    return {key: observation[key] for key in CHECK_FIELDS}


def validate_ledger(
    observations,
    *,
    attempt_id,
    check_roster,
    supplied_observation_ids,
    initial_candidate_id=_UNSET,
    post_stop_candidate_id=_UNSET,
):
    """Validate exact identities, phases and the supplied initial-record roster.

    Missing observations remain missing. A caller grading an executed task must
    additionally require its post-stop record; policy evaluation may abstain.
    Explicit None candidate identity permits only an unavailable not-run record.
    Omitted candidate arguments leave manifest correspondence to the caller.
    """
    canonical([observations, check_roster, supplied_observation_ids])
    if type(attempt_id) is not str or not attempt_id:
        raise ValueError("attempt identity required")
    if type(check_roster) is not list or not check_roster:
        raise ValueError("frozen visible check roster required")
    roster = {}
    for check in check_roster:
        if (
            type(check) is not dict
            or set(check) != {"check_id", "command"}
            or type(check["check_id"]) is not str
            or not check["check_id"]
            or check["check_id"] in roster
            or type(check["command"]) is not list
            or not check["command"]
            or any(type(arg) is not str or not arg for arg in check["command"])
        ):
            raise ValueError("invalid or duplicate registered visible check")
        roster[check["check_id"]] = check["command"]
    if type(observations) is not list or type(supplied_observation_ids) is not list:
        raise ValueError("observation ledger and supplied IDs must be lists")
    phases = {"initial": {}, "post_stop": {}}
    by_id, initial_ids, seen_post = {}, [], False
    candidates = {"initial": initial_candidate_id, "post_stop": post_stop_candidate_id}
    if any(
        expected is not _UNSET and expected is not None and (type(expected) is not str or not expected)
        for expected in candidates.values()
    ):
        raise ValueError("invalid expected candidate identity")
    observed_candidates = {}
    for observed in observations:
        validate_record(observed)
        if observed["record_type"] != "command":
            raise ValueError("agent claims are not command observations")
        phase, check_id, identity = observed["phase"], observed["check_id"], observed["observation_id"]
        if phase == "post_stop":
            seen_post = True
        elif seen_post:
            raise ValueError("initial evidence follows post-stop evidence")
        if (
            observed["attempt_id"] != attempt_id
            or check_id not in roster
            or canonical(observed["command"]) != canonical(roster[check_id])
            or check_id in phases[phase]
            or identity in by_id
        ):
            raise ValueError("unexpected, foreign or duplicate observation")
        expected = candidates[phase]
        if expected is not _UNSET and observed["candidate_id"] != (expected or "unavailable"):
            raise ValueError("observation phase candidate identity differs")
        if expected is None and observed["execution_state"] != "not_run":
            raise ValueError("unidentified candidate cannot have executed observations")
        if phase in observed_candidates and observed_candidates[phase] != observed["candidate_id"]:
            raise ValueError("observations in a phase refer to different candidates")
        observed_candidates[phase] = observed["candidate_id"]
        phases[phase][check_id] = observed
        by_id[identity] = observed
        if phase == "initial":
            initial_ids.append(identity)
    if canonical(supplied_observation_ids) != canonical(initial_ids):
        raise ValueError("supplied IDs differ from retained initial observations")
    return {**phases, "by_id": by_id, "roster": roster}


def check_claims(response, *, observations, supplied_observation_ids, attempt_id, check_roster):
    """Truth of structured reports about supplied evidence, never future checks.

    Correct reporting of a not-run observation is a supported fact; it is not
    proof of passing validation. Missing source records remain unknown. A known
    false or fabricated report takes precedence over other missing evidence.
    """
    ledger = validate_ledger(
        observations,
        attempt_id=attempt_id,
        check_roster=check_roster,
        supplied_observation_ids=supplied_observation_ids,
    )
    if response is None:
        return None
    if not envelope_valid(response, strict=True):
        return False
    seen = []
    for claim in response["checks"]:
        if type(claim) is not dict or set(claim) != set(CHECK_FIELDS):
            return False
        identity = claim["observation_id"]
        if (
            type(identity) is not str
            or identity not in supplied_observation_ids
            or identity in seen
            or claim["phase"] != "initial"
        ):
            return False
        if canonical(claim) != canonical(check_claim(ledger["by_id"][identity])):
            return False
        seen.append(identity)
    if seen != supplied_observation_ids:
        return False
    if len(ledger["initial"]) != len(ledger["roster"]):
        return None
    return True
