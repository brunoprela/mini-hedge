export const Role = {
  ADMIN: "admin",
  PORTFOLIO_MANAGER: "portfolio_manager",
  ANALYST: "analyst",
  RISK_MANAGER: "risk_manager",
  COMPLIANCE: "compliance",
  VIEWER: "viewer",
} as const;

export type Role = (typeof Role)[keyof typeof Role];

export const Permission = {
  INSTRUMENTS_READ: "instruments:read",
  INSTRUMENTS_WRITE: "instruments:write",
  PRICES_READ: "prices:read",
  POSITIONS_READ: "positions:read",
  POSITIONS_WRITE: "positions:write",
  TRADES_EXECUTE: "trades:execute",
  FUNDS_READ: "funds:read",
  FUNDS_MANAGE: "funds:manage",
} as const;

export type Permission = (typeof Permission)[keyof typeof Permission];

const ALL_PERMISSIONS = new Set(Object.values(Permission));

export const ROLE_PERMISSIONS: Record<Role, ReadonlySet<Permission>> = {
  [Role.ADMIN]: ALL_PERMISSIONS,
  [Role.PORTFOLIO_MANAGER]: new Set([
    Permission.INSTRUMENTS_READ,
    Permission.PRICES_READ,
    Permission.POSITIONS_READ,
    Permission.POSITIONS_WRITE,
    Permission.TRADES_EXECUTE,
    Permission.FUNDS_READ,
  ]),
  [Role.ANALYST]: new Set([
    Permission.INSTRUMENTS_READ,
    Permission.PRICES_READ,
    Permission.POSITIONS_READ,
    Permission.FUNDS_READ,
  ]),
  [Role.RISK_MANAGER]: new Set([
    Permission.INSTRUMENTS_READ,
    Permission.PRICES_READ,
    Permission.POSITIONS_READ,
    Permission.FUNDS_READ,
  ]),
  [Role.COMPLIANCE]: new Set([
    Permission.INSTRUMENTS_READ,
    Permission.PRICES_READ,
    Permission.POSITIONS_READ,
    Permission.FUNDS_READ,
  ]),
  [Role.VIEWER]: new Set([
    Permission.INSTRUMENTS_READ,
    Permission.PRICES_READ,
    Permission.POSITIONS_READ,
    Permission.FUNDS_READ,
  ]),
};

export function resolvePermissions(roles: readonly string[]): Set<Permission> {
  const perms = new Set<Permission>();
  for (const role of roles) {
    const rolePerms = ROLE_PERMISSIONS[role as Role];
    if (rolePerms) {
      for (const p of rolePerms) perms.add(p);
    }
  }
  return perms;
}

export function hasPermission(
  userPermissions: ReadonlySet<Permission>,
  required: Permission
): boolean {
  return userPermissions.has(required);
}

export function hasAllPermissions(
  userPermissions: ReadonlySet<Permission>,
  required: readonly Permission[]
): boolean {
  return required.every((p) => userPermissions.has(p));
}
