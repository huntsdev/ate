class DomainError(ValueError):
    """A recoverable domain failure; messages contain no evidence or credentials."""


class NotFound(DomainError):
    pass


class Conflict(DomainError):
    pass


class VersionConflict(Conflict):
    pass


class InvalidTransition(DomainError):
    pass


class InvalidDisposition(DomainError):
    pass


class ActorNotAllowed(DomainError):
    pass
