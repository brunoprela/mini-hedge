"""Unit tests for admin DTO input validation."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.modules.platform.interface import (
    AccessGrantRequest,
    AccessRevokeRequest,
    CreateFundRequest,
    CreateOperatorRequest,
    CreateUserRequest,
)


class TestAccessGrantRequest:
    def test_valid_user_grant(self) -> None:
        req = AccessGrantRequest(
            user_type="user",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            relation="admin",
        )
        assert req.user_type == "user"

    def test_valid_operator_grant(self) -> None:
        req = AccessGrantRequest(
            user_type="operator",
            user_id="550e8400-e29b-41d4-a716-446655440000",
            relation="ops_full",
        )
        assert req.user_type == "operator"

    def test_invalid_user_type_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            AccessGrantRequest(
                user_type="admin",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                relation="viewer",
            )

    def test_invalid_uuid_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            AccessGrantRequest(
                user_type="user",
                user_id="not-a-uuid",
                relation="viewer",
            )

    def test_invalid_relation_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            AccessGrantRequest(
                user_type="user",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                relation="superadmin",
            )

    def test_revoke_same_validation(self) -> None:
        with pytest.raises(PydanticValidationError):
            AccessRevokeRequest(
                user_type="bad",
                user_id="550e8400-e29b-41d4-a716-446655440000",
                relation="viewer",
            )


class TestCreateFundRequest:
    def test_valid_slug(self) -> None:
        req = CreateFundRequest(slug="alpha-fund", name="Alpha Fund")
        assert req.slug == "alpha-fund"

    def test_slug_too_short(self) -> None:
        with pytest.raises(PydanticValidationError):
            CreateFundRequest(slug="ab", name="Too Short")

    def test_slug_uppercase_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            CreateFundRequest(slug="Alpha-Fund", name="Upper Case")

    def test_slug_special_chars_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            CreateFundRequest(slug="alpha_fund!", name="Special Chars")

    def test_slug_starts_with_number_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            CreateFundRequest(slug="1alpha", name="Starts with number")

    def test_valid_currencies(self) -> None:
        for currency in ("USD", "EUR", "GBP", "JPY", "CHF"):
            req = CreateFundRequest(slug="test-fund", name="Test", base_currency=currency)
            assert req.base_currency == currency

    def test_invalid_currency_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            CreateFundRequest(slug="test-fund", name="Test", base_currency="BTC")


class TestCreateUserRequest:
    def test_valid_user(self) -> None:
        req = CreateUserRequest(email="alice@example.com", name="Alice")
        assert req.email == "alice@example.com"

    def test_invalid_email_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            CreateUserRequest(email="not-an-email", name="Test")

    def test_blank_name_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            CreateUserRequest(email="alice@example.com", name="   ")

    def test_name_trimmed(self) -> None:
        req = CreateUserRequest(email="alice@example.com", name="  Alice  ")
        assert req.name == "Alice"


class TestCreateOperatorRequest:
    def test_valid_operator(self) -> None:
        req = CreateOperatorRequest(
            email="ops@example.com",
            name="Ops Admin",
            platform_role="ops_admin",
        )
        assert req.platform_role == "ops_admin"

    def test_default_role(self) -> None:
        req = CreateOperatorRequest(email="ops@example.com", name="Viewer")
        assert req.platform_role == "ops_viewer"

    def test_invalid_role_rejected(self) -> None:
        with pytest.raises(PydanticValidationError):
            CreateOperatorRequest(
                email="ops@example.com",
                name="Bad",
                platform_role="superadmin",
            )
