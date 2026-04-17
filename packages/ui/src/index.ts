/**
 * @mini-hedge/ui — shared component primitives for all mini-hedge UIs.
 *
 * Every file in this package is built on the Tailwind UI v4 license at
 * `mono/tailwind-templates/application-ui-v4/react/`. Components are copied
 * from templates verbatim and diverge only at the theme-token layer — they
 * reference CSS variables (`--card`, `--foreground`, `--primary`, etc.)
 * whose canonical values live in `./tokens.css`.
 *
 * Consuming UIs pull in the shared tokens at the top of their globals.css:
 *
 *     @import "@mini-hedge/ui/src/tokens.css";
 *
 * Any per-UI overrides (branding, sidebar width, light vs. dark baseline)
 * follow the import and win via the cascade.
 *
 * See `design/systems/hedge-fund-desk/02-modules/ui/internal/overview.md` for
 * the bedrock workflow.
 */

// Overlays
export * from "./dialog";
export * from "./drawer";
export * from "./menu";
export * from "./combobox";
export * from "./command-palette";
export * from "./tooltip";

// Primitives
export * from "./button";
export * from "./icon-button";
export * from "./card";
export * from "./kpi-card";
export * from "./status-badge";
export * from "./empty-state";
export * from "./error-state";
export * from "./loading-skeleton";
export * from "./pagination";
export * from "./table";
export * from "./section-panel";
export * from "./select";
export * from "./form-field";
export * from "./tabs";
export * from "./spinner";
export * from "./toast";

// Navigation shell
export * from "./sidebar";
export * from "./breadcrumbs";
