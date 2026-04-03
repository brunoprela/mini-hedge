"""Verify ROLE_PERMISSIONS (API key fallback) matches FGA model computed relations.

If these drift apart, API key users and Keycloak users would get different
permissions for the same role — a silent authorization bug.
"""

import json
from pathlib import Path

import pytest

from app.shared.auth import FGA_PERMISSION_MAP, ROLE_PERMISSIONS, Role

FGA_MODEL_PATH = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "modules"
    / "platform"
    / "fga_model.json"
)

# Roles that exist in the FGA model's fund type (user-assignable only, not operator)
_USER_ROLES = {r.value for r in Role}


def _parse_fga_model() -> dict[str, set[str]]:
    """Parse fga_model.json and return {can_* relation: set of role names in its union}.

    Only considers ``computed_userset`` children (role-granted permissions),
    ignoring ``{ "this": {} }`` (direct grants).
    """
    model = json.loads(FGA_MODEL_PATH.read_text())
    fund_type = next(td for td in model["type_definitions"] if td["type"] == "fund")
    relations = fund_type["relations"]

    result: dict[str, set[str]] = {}
    for rel_name, rel_def in relations.items():
        if not rel_name.startswith("can_"):
            continue
        if rel_name in ("can_read", "can_admin"):
            # Internal bookkeeping relations, not mapped to Permission enum
            continue
        if rel_name not in FGA_PERMISSION_MAP:
            continue

        children = rel_def.get("union", {}).get("child", [])
        roles_in_union: set[str] = set()
        for child in children:
            cu = child.get("computed_userset", {})
            role = cu.get("relation")
            if role and role in _USER_ROLES:
                roles_in_union.add(role)
        result[rel_name] = roles_in_union

    return result


def _build_role_to_fga_permissions() -> dict[str, set[str]]:
    """Invert FGA model: for each user role, which can_* relations include it."""
    fga_relations = _parse_fga_model()
    role_perms: dict[str, set[str]] = {r: set() for r in _USER_ROLES}
    for fga_rel, roles in fga_relations.items():
        perm = FGA_PERMISSION_MAP[fga_rel]
        for role in roles:
            if role in role_perms:
                role_perms[role].add(perm)
    return role_perms


class TestFGADrift:
    """Ensure ROLE_PERMISSIONS dict stays in sync with fga_model.json."""

    def test_fga_model_exists(self) -> None:
        assert FGA_MODEL_PATH.exists(), f"FGA model not found at {FGA_MODEL_PATH}"

    def test_all_fga_permissions_mapped(self) -> None:
        """Every can_* relation on fund (except internal ones) must be in FGA_PERMISSION_MAP."""
        model = json.loads(FGA_MODEL_PATH.read_text())
        fund_type = next(
            td for td in model["type_definitions"] if td["type"] == "fund"
        )
        internal = ("can_read", "can_admin")
        can_relations = {
            r
            for r in fund_type["relations"]
            if r.startswith("can_") and r not in internal
        }
        mapped = set(FGA_PERMISSION_MAP.keys())
        unmapped = can_relations - mapped
        assert not unmapped, (
            f"FGA can_* relations not in FGA_PERMISSION_MAP: {sorted(unmapped)}"
        )

    @pytest.mark.parametrize("role", list(Role))
    def test_role_permissions_match_fga(self, role: Role) -> None:
        """For each role, ROLE_PERMISSIONS must grant exactly the permissions
        that the FGA model computes via can_* unions."""
        fga_perms = _build_role_to_fga_permissions()
        fga_set = fga_perms.get(role.value, set())
        fga_values = set(FGA_PERMISSION_MAP.values())
        py_set = {
            p.value
            for p in ROLE_PERMISSIONS.get(role, frozenset())
            if p.value in fga_values
        }

        # Filter py_set to only fund-level permissions (exclude platform:* permissions)
        fund_fga_values = set(FGA_PERMISSION_MAP.values())
        py_fund_perms = py_set & fund_fga_values

        missing_in_py = fga_set - py_fund_perms
        extra_in_py = py_fund_perms - fga_set

        errors = []
        if missing_in_py:
            errors.append(f"FGA grants but ROLE_PERMISSIONS missing: {sorted(missing_in_py)}")
        if extra_in_py:
            errors.append(f"ROLE_PERMISSIONS grants but FGA missing: {sorted(extra_in_py)}")
        assert not errors, f"Role '{role.value}' drift:\n" + "\n".join(errors)
