"""Unit tests for interface/DTO validators — Pydantic field_validators and models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.platform.interfaces.access import (
    AccessGrantRequest,
    AccessRevokeRequest,
    FundAccessGrant,
)
from app.modules.platform.interfaces.customer import (
    CreateCustomerRequest,
    CustomerInfo,
    CustomerPage,
    UpdateCustomerRequest,
)
from app.modules.platform.interfaces.fund import (
    CreateFundRequest,
    FundDetail,
    FundInfo,
    FundPage,
    PortfolioInfo,
    UpdateFundRequest,
)
from app.modules.platform.interfaces.operator import (
    CreateOperatorRequest,
    OperatorInfo,
    OperatorPage,
    UpdateOperatorRequest,
)
from app.modules.platform.interfaces.user import (
    CreateUserRequest,
    UpdateUserRequest,
    UserInfo,
    UserPage,
)


class TestCreateCustomerRequest:
    def test_valid_slug(self) -> None:
        req = CreateCustomerRequest(slug="acme-fund", name="Acme Fund")
        assert req.slug == "acme-fund"

    def test_slug_stripped_and_lowered(self) -> None:
        req = CreateCustomerRequest(slug="  ACME  ", name="Acme")
        assert req.slug == "acme"

    def test_empty_slug_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateCustomerRequest(slug="", name="Acme")

    def test_slug_too_long_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateCustomerRequest(slug="x" * 65, name="Acme")

    def test_name_stripped(self) -> None:
        req = CreateCustomerRequest(slug="acme", name="  Acme Fund  ")
        assert req.name == "Acme Fund"

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateCustomerRequest(slug="acme", name="")

    def test_name_too_long_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateCustomerRequest(slug="acme", name="x" * 256)

    def test_valid_customer_types(self) -> None:
        req1 = CreateCustomerRequest(slug="a", name="A", customer_type="direct_fund")
        assert req1.customer_type == "direct_fund"
        req2 = CreateCustomerRequest(slug="b", name="B", customer_type="fund_administrator")
        assert req2.customer_type == "fund_administrator"

    def test_invalid_customer_type_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateCustomerRequest(slug="a", name="A", customer_type="invalid_type")

    def test_default_customer_type(self) -> None:
        req = CreateCustomerRequest(slug="a", name="A")
        assert req.customer_type == "direct_fund"


class TestCustomerPage:
    def test_frozen(self) -> None:
        info = CustomerInfo(id="c1", slug="acme", name="Acme", customer_type="direct_fund", status="active")
        page = CustomerPage(items=[info], total=1, limit=100, offset=0)
        assert page.total == 1
        assert len(page.items) == 1


class TestUpdateCustomerRequest:
    def test_partial_update(self) -> None:
        req = UpdateCustomerRequest(name="New Name")
        assert req.name == "New Name"
        assert req.status is None

    def test_all_none(self) -> None:
        req = UpdateCustomerRequest()
        assert req.name is None
        assert req.status is None


class TestAccessGrantRequest:
    def test_valid_user_grant(self) -> None:
        from uuid import uuid4

        uid = str(uuid4())
        req = AccessGrantRequest(user_type="user", user_id=uid, relation="admin")
        assert req.user_type == "user"
        assert req.relation == "admin"

    def test_invalid_uuid_raises(self) -> None:
        with pytest.raises(ValidationError):
            AccessGrantRequest(user_type="user", user_id="not-a-uuid", relation="admin")

    def test_invalid_relation_raises(self) -> None:
        from uuid import uuid4

        with pytest.raises(ValidationError):
            AccessGrantRequest(user_type="user", user_id=str(uuid4()), relation="superadmin")

    def test_operator_relations(self) -> None:
        from uuid import uuid4

        uid = str(uuid4())
        req = AccessGrantRequest(user_type="operator", user_id=uid, relation="ops_full")
        assert req.relation == "ops_full"

    def test_permission_relations(self) -> None:
        from uuid import uuid4

        uid = str(uuid4())
        req = AccessGrantRequest(user_type="user", user_id=uid, relation="can_read_instruments")
        assert req.relation == "can_read_instruments"


class TestAccessRevokeRequest:
    def test_valid_revoke(self) -> None:
        from uuid import uuid4

        uid = str(uuid4())
        req = AccessRevokeRequest(user_type="operator", user_id=uid, relation="ops_read")
        assert req.relation == "ops_read"


class TestFundAccessGrant:
    def test_default_relation_type(self) -> None:
        grant = FundAccessGrant(user_type="user", user_id="u1", relation="admin")
        assert grant.relation_type == "role"

    def test_permission_relation_type(self) -> None:
        grant = FundAccessGrant(
            user_type="user", user_id="u1", relation="can_read", relation_type="permission"
        )
        assert grant.relation_type == "permission"


class TestCreateFundRequest:
    def test_valid_slug(self) -> None:
        req = CreateFundRequest(slug="alpha-fund", name="Alpha")
        assert req.slug == "alpha-fund"

    def test_invalid_slug_too_short(self) -> None:
        with pytest.raises(ValidationError):
            CreateFundRequest(slug="ab", name="X")

    def test_invalid_slug_starts_with_number(self) -> None:
        with pytest.raises(ValidationError):
            CreateFundRequest(slug="1alpha", name="X")

    def test_invalid_slug_uppercase(self) -> None:
        with pytest.raises(ValidationError):
            CreateFundRequest(slug="Alpha-Fund", name="X")

    def test_valid_currencies(self) -> None:
        for curr in ("USD", "EUR", "GBP", "JPY", "CHF"):
            req = CreateFundRequest(slug="test-fund", name="T", base_currency=curr)
            assert req.base_currency == curr

    def test_invalid_currency(self) -> None:
        with pytest.raises(ValidationError):
            CreateFundRequest(slug="test-fund", name="T", base_currency="BTC")

    def test_default_currency(self) -> None:
        req = CreateFundRequest(slug="test-fund", name="T")
        assert req.base_currency == "USD"


class TestFundDetail:
    def test_frozen(self) -> None:
        detail = FundDetail(id="f1", slug="alpha", name="Alpha", status="active", base_currency="USD")
        assert detail.id == "f1"


class TestFundPage:
    def test_structure(self) -> None:
        page = FundPage(items=[], total=0, limit=100, offset=0)
        assert page.total == 0


class TestPortfolioInfo:
    def test_optional_strategy(self) -> None:
        p = PortfolioInfo(id="p1", slug="main", name="Main", strategy=None, fund_id="f1")
        assert p.strategy is None


class TestCreateOperatorRequest:
    def test_valid(self) -> None:
        req = CreateOperatorRequest(email="ops@example.com", name="Ops User")
        assert req.platform_role == "ops_viewer"  # default

    def test_name_stripped(self) -> None:
        req = CreateOperatorRequest(email="ops@example.com", name="  Ops  ")
        assert req.name == "Ops"

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateOperatorRequest(email="ops@example.com", name="")

    def test_name_too_long_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateOperatorRequest(email="ops@example.com", name="x" * 201)

    def test_admin_role(self) -> None:
        req = CreateOperatorRequest(email="ops@example.com", name="Ops", platform_role="ops_admin")
        assert req.platform_role == "ops_admin"


class TestCreateUserRequest:
    def test_valid(self) -> None:
        req = CreateUserRequest(email="user@example.com", name="User")
        assert req.name == "User"

    def test_name_stripped(self) -> None:
        req = CreateUserRequest(email="user@example.com", name="  Alice  ")
        assert req.name == "Alice"

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateUserRequest(email="user@example.com", name="")

    def test_name_too_long_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateUserRequest(email="user@example.com", name="x" * 201)


class TestUpdateUserRequest:
    def test_partial(self) -> None:
        req = UpdateUserRequest(is_active=False)
        assert req.name is None
        assert req.is_active is False


class TestUserPage:
    def test_structure(self) -> None:
        page = UserPage(items=[], total=0, limit=100, offset=0)
        assert page.total == 0


class TestOperatorPage:
    def test_structure(self) -> None:
        page = OperatorPage(items=[], total=0, limit=100, offset=0)
        assert page.total == 0


class TestFundInfo:
    def test_optional_customer_fields(self) -> None:
        info = FundInfo(fund_slug="alpha", fund_name="Alpha", role="admin")
        assert info.customer_id is None
        assert info.customer_name is None

    def test_with_customer(self) -> None:
        info = FundInfo(
            fund_slug="alpha", fund_name="Alpha", role="admin",
            customer_id="c1", customer_name="Acme",
        )
        assert info.customer_id == "c1"
        assert info.customer_name == "Acme"
