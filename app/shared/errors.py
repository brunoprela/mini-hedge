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
        self,
        message: str = "Authentication required",
        code: str = "AUTH_REQUIRED",
    ) -> None:
        super().__init__(message=message, code=code)


class AuthorizationError(DomainError):
    """Caller is identified but lacks access."""

    def __init__(self, message: str = "Access denied", code: str = "ACCESS_DENIED") -> None:
        super().__init__(message=message, code=code)


# ---------------------------------------------------------------------------
# Tenant context errors
# ---------------------------------------------------------------------------


class CustomerContextMissing(DomainError):
    """No customer context is active for the current request/task."""

    def __init__(self) -> None:
        super().__init__(
            message="Customer context is required but not set",
            code="CUSTOMER_CONTEXT_MISSING",
        )


class FundContextMissing(DomainError):
    """No fund context is active for the current request/task."""

    def __init__(self) -> None:
        super().__init__(
            message="Fund context is required but not set",
            code="FUND_CONTEXT_MISSING",
        )


class UnknownCustomerError(DomainError):
    """The customer ID in context does not match any known customer."""

    def __init__(self, customer_id: str) -> None:
        super().__init__(
            message=f"Unknown customer: {customer_id}",
            code="UNKNOWN_CUSTOMER",
        )
        self.customer_id = customer_id
