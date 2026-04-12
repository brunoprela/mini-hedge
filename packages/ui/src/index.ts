/**
 * @mini-hedge/ui — shared component primitives for all mini-hedge UIs.
 *
 * Every file in this package is built on the Tailwind UI v4 license at
 * `mono/tailwind-templates/application-ui-v4/react/`. Components are copied
 * from templates verbatim and diverge only at the theme-token layer — they
 * reference CSS variables (`--card`, `--foreground`, `--primary`, etc.) that
 * each consuming UI defines in its own `globals.css`.
 *
 * See `design/systems/hedge-fund-desk/02-modules/ui/internal/overview.md` for
 * the bedrock workflow.
 */

export * from "./dialog";
export * from "./drawer";
export * from "./menu";
export * from "./combobox";
export * from "./command-palette";
export * from "./tooltip";
