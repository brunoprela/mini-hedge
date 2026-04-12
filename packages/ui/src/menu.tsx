"use client";

/**
 * Dropdown menu primitives — thin re-export of Headless UI Menu with tokenized class presets.
 *
 * Bedrock source: tailwind-templates/application-ui-v4/react/elements/dropdowns/01-simple.jsx
 *
 * Consumers can compose with these presets or use the Headless UI primitives directly.
 */

import { Menu, MenuButton, MenuItem, MenuItems } from "@headlessui/react";

export { Menu, MenuButton, MenuItem, MenuItems };

/** MenuItems className preset matching the template's panel look, tokenized. */
export const menuItemsClassName =
  "absolute right-0 z-10 mt-2 w-56 origin-top-right rounded-md border border-[var(--border)] bg-[var(--card)] shadow-lg transition data-closed:scale-95 data-closed:transform data-closed:opacity-0 data-enter:duration-100 data-enter:ease-out data-leave:duration-75 data-leave:ease-in";

/** MenuItem anchor/button className preset matching the template row look, tokenized. */
export const menuItemClassName =
  "block px-4 py-2 text-sm text-[var(--foreground)] data-focus:bg-[var(--muted)] data-focus:text-[var(--foreground-bright)] data-focus:outline-hidden";
