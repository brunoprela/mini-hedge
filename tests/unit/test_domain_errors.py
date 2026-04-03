"""Unit tests for domain error types and their properties."""

from app.shared.errors import (
    AuthenticationError,
    AuthorizationError,
    DomainError,
    NotFoundError,
    ValidationError,
)


class TestDomainErrors:
    def test_domain_error_defaults(self) -> None:
        err = DomainError("something broke")
        assert err.message == "something broke"
        assert err.code == "DOMAIN_ERROR"
        assert str(err) == "something broke"

    def test_not_found_error(self) -> None:
        err = NotFoundError("User", "abc-123")
        assert err.message == "User not found: abc-123"
        assert err.code == "NOT_FOUND"
        assert err.entity == "User"
        assert err.identifier == "abc-123"
        assert isinstance(err, DomainError)

    def test_validation_error(self) -> None:
        err = ValidationError("Email already exists")
        assert err.message == "Email already exists"
        assert err.code == "VALIDATION_ERROR"
        assert isinstance(err, DomainError)

    def test_authentication_error_defaults(self) -> None:
        err = AuthenticationError()
        assert err.message == "Authentication required"
        assert err.code == "AUTH_REQUIRED"
        assert isinstance(err, DomainError)

    def test_authentication_error_custom(self) -> None:
        err = AuthenticationError("Invalid token", code="INVALID_TOKEN")
        assert err.message == "Invalid token"
        assert err.code == "INVALID_TOKEN"

    def test_authorization_error_defaults(self) -> None:
        err = AuthorizationError()
        assert err.message == "Access denied"
        assert err.code == "ACCESS_DENIED"
        assert isinstance(err, DomainError)

    def test_authorization_error_custom(self) -> None:
        err = AuthorizationError("No fund access", code="NO_FUND_ACCESS")
        assert err.message == "No fund access"
        assert err.code == "NO_FUND_ACCESS"

    def test_error_hierarchy(self) -> None:
        """All domain errors are Exceptions and DomainErrors."""
        for cls in (NotFoundError, ValidationError, AuthenticationError, AuthorizationError):
            assert issubclass(cls, DomainError)
            assert issubclass(cls, Exception)
