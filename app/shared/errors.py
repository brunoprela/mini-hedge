"""Structured domain errors used across modules."""


class DomainError(Exception):
    """Base for all domain-level errors."""

    def __init__(self, message: str, code: str = "DOMAIN_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(DomainError):
    """Requested entity does not exist."""

    def __init__(self, entity: str, identifier: str) -> None:
        super().__init__(
            message=f"{entity} not found: {identifier}",
            code="NOT_FOUND",
        )
        self.entity = entity
        self.identifier = identifier


class ValidationError(DomainError):
    """Domain-level validation failure (not Pydantic schema validation)."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="VALIDATION_ERROR")


class AuthenticationError(DomainError):
    """Caller could not be identified (invalid/missing credentials)."""

    def __init__(
        self, message: str = "Authentication required", code: str = "AUTH_REQUIRED",
    ) -> None:
        super().__init__(message=message, code=code)


class AuthorizationError(DomainError):
    """Caller is identified but lacks access."""

    def __init__(self, message: str = "Access denied", code: str = "ACCESS_DENIED") -> None:
        super().__init__(message=message, code=code)
