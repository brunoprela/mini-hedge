export const USER_ROLES = [
  "admin",
  "portfolio_manager",
  "analyst",
  "risk_manager",
  "compliance_officer",
  "viewer",
];
export const OPERATOR_RELATIONS = ["ops_full", "ops_read"];

// All individual permissions that can be directly granted
export const FUND_PERMISSIONS = [
  "can_read_instruments",
  "can_write_instruments",
  "can_read_prices",
  "can_read_positions",
  "can_write_positions",
  "can_execute_trades",
  "can_read_fund",
  "can_manage_fund",
  "can_read_orders",
  "can_create_orders",
  "can_cancel_orders",
  "can_read_compliance",
  "can_manage_compliance",
  "can_read_exposure",
];

// Platform-level permissions for operators
export const PLATFORM_PERMISSIONS = [
  "platform:users.read",
  "platform:users.write",
  "platform:funds.read",
  "platform:funds.write",
  "platform:operators.read",
  "platform:operators.write",
  "platform:audit.read",
  "platform:access.read",
  "platform:access.write",
];

// FGA relation name -> human-readable permission label
export const PERMISSION_LABELS: Record<string, string> = {
  can_read_instruments: "Instruments Read",
  can_write_instruments: "Instruments Write",
  can_read_prices: "Prices Read",
  can_read_positions: "Positions Read",
  can_write_positions: "Positions Write",
  can_execute_trades: "Trades Execute",
  can_read_fund: "Fund Read",
  can_manage_fund: "Fund Manage",
  can_read_orders: "Orders Read",
  can_create_orders: "Orders Create",
  can_cancel_orders: "Orders Cancel",
  can_read_compliance: "Compliance Read",
  can_manage_compliance: "Compliance Manage",
  can_read_exposure: "Exposure Read",
  "platform:users.read": "Users Read",
  "platform:users.write": "Users Write",
  "platform:funds.read": "Funds Read",
  "platform:funds.write": "Funds Write",
  "platform:operators.read": "Operators Read",
  "platform:operators.write": "Operators Write",
  "platform:audit.read": "Audit Read",
  "platform:access.read": "Access Read",
  "platform:access.write": "Access Write",
};

// Which roles grant which permissions (mirrors FGA model computed unions)
export const ROLE_PERMISSIONS: Record<string, string[]> = {
  admin: FUND_PERMISSIONS, // all
  portfolio_manager: [
    "can_read_instruments",
    "can_read_prices",
    "can_read_positions",
    "can_write_positions",
    "can_execute_trades",
    "can_read_fund",
    "can_read_orders",
    "can_create_orders",
    "can_cancel_orders",
    "can_read_compliance",
    "can_read_exposure",
  ],
  analyst: [
    "can_read_instruments",
    "can_read_prices",
    "can_read_positions",
    "can_read_fund",
    "can_read_orders",
    "can_read_exposure",
  ],
  risk_manager: [
    "can_read_instruments",
    "can_read_prices",
    "can_read_positions",
    "can_read_fund",
    "can_read_orders",
    "can_read_compliance",
    "can_read_exposure",
  ],
  compliance_officer: [
    "can_read_instruments",
    "can_read_prices",
    "can_read_positions",
    "can_read_fund",
    "can_read_orders",
    "can_read_compliance",
    "can_manage_compliance",
    "can_read_exposure",
  ],
  viewer: [
    "can_read_instruments",
    "can_read_prices",
    "can_read_positions",
    "can_read_fund",
    "can_read_orders",
  ],
  ops_full: PLATFORM_PERMISSIONS, // all platform permissions
  ops_read: [
    "platform:users.read",
    "platform:funds.read",
    "platform:operators.read",
    "platform:audit.read",
    "platform:access.read",
  ],
};

export interface GroupedAccess {
  user_type: string;
  user_id: string;
  display_name: string | null;
  roles: Set<string>;
  directPermissions: Set<string>;
}

export function rolesForType(type: string) {
  return type === "user" ? USER_ROLES : OPERATOR_RELATIONS;
}

export function formatRelation(r: string) {
  return r.replace(/_/g, " ");
}

/** Compute the set of permissions granted by the user's active roles. */
export function roleGrantedPermissions(roles: Set<string>): Set<string> {
  const perms = new Set<string>();
  for (const role of roles) {
    for (const p of ROLE_PERMISSIONS[role] ?? []) {
      perms.add(p);
    }
  }
  return perms;
}

/** Compute the full effective permissions: role-granted + direct grants. */
export function effectivePermissions(roles: Set<string>, directPerms: Set<string>): Set<string> {
  const perms = roleGrantedPermissions(roles);
  for (const p of directPerms) {
    perms.add(p);
  }
  return perms;
}
