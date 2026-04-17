/**
 * SectionPanel — re-export of the shared `@mini-hedge/ui` primitive.
 *
 * The desk UI originally shipped its own copy of this panel; it was moved to
 * the shared package so all three UIs render the same toolbar ribbon / summary
 * strip shell. This re-export exists so existing imports like
 * `@/shared/components/section-panel` keep working; new code should import
 * directly from `@mini-hedge/ui`.
 */

export { SectionPanel, ToolbarTab } from "@mini-hedge/ui";
