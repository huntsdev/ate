from sentinelforge.domains.errors import InvalidDisposition, InvalidTransition
from sentinelforge.domains.types import CaseStatus, Disposition

TRANSITIONS: dict[CaseStatus, frozenset[CaseStatus]] = {
    CaseStatus.NEW: frozenset({CaseStatus.TRIAGING, CaseStatus.INVESTIGATING}),
    CaseStatus.TRIAGING: frozenset({CaseStatus.INVESTIGATING, CaseStatus.RESOLVED}),
    CaseStatus.INVESTIGATING: frozenset({CaseStatus.RESOLVED}),
    CaseStatus.RESOLVED: frozenset({CaseStatus.CLOSED, CaseStatus.INVESTIGATING}),
    CaseStatus.CLOSED: frozenset({CaseStatus.INVESTIGATING}),
}


def transition_disposition(
    current: CaseStatus,
    target: CaseStatus,
    previous: Disposition | None,
    requested: Disposition | None,
) -> Disposition | None:
    if target not in TRANSITIONS[current]:
        raise InvalidTransition("Case transition is not allowed")
    if target == CaseStatus.RESOLVED:
        if requested is None:
            raise InvalidDisposition("Resolution requires an analyst disposition")
        return requested
    if target == CaseStatus.CLOSED:
        if previous is None or (requested is not None and requested != previous):
            raise InvalidDisposition("Closure must retain the resolved disposition")
        return previous
    if requested is not None:
        raise InvalidDisposition("An open case cannot have a disposition")
    return None
