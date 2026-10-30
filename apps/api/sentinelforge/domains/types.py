from enum import StrEnum


class ActorKind(StrEnum):
    HUMAN = "human"
    SERVICE = "service"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CaseStatus(StrEnum):
    NEW = "new"
    TRIAGING = "triaging"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Disposition(StrEnum):
    TRUE_POSITIVE = "true_positive"
    BENIGN_POSITIVE = "benign_positive"
    FALSE_POSITIVE = "false_positive"
    INCONCLUSIVE = "inconclusive"


class Sensitivity(StrEnum):
    SYNTHETIC = "synthetic"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
