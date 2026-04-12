"use client";

/**
 * Combobox primitives — thin re-export of Headless UI Combobox with tokenized class presets.
 *
 * Bedrock source: tailwind-templates/application-ui-v4/react/forms/comboboxes/01-simple.jsx
 *
 * Consumers can use the Headless UI primitives directly with the className presets below,
 * or import the presets ad hoc.
 */

import {
  Combobox,
  ComboboxButton,
  ComboboxInput,
  ComboboxOption,
  ComboboxOptions,
  Label,
} from "@headlessui/react";

export { Combobox, ComboboxButton, ComboboxInput, ComboboxOption, ComboboxOptions, Label };

/** Input className preset, tokenized. */
export const comboboxInputClassName =
  "block w-full rounded-md bg-[var(--input)] py-1.5 pr-12 pl-3 text-sm text-[var(--foreground)] outline-1 -outline-offset-1 outline-[var(--input-border)] placeholder:text-[var(--muted-foreground)] focus:outline-2 focus:-outline-offset-2 focus:outline-[var(--primary)]";

/** Options panel className preset, tokenized. */
export const comboboxOptionsClassName =
  "absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md border border-[var(--border)] bg-[var(--card)] py-1 text-sm shadow-lg data-leave:transition data-leave:duration-100 data-leave:ease-in data-closed:data-leave:opacity-0";

/** Option row className preset, tokenized. */
export const comboboxOptionClassName =
  "cursor-default px-3 py-2 text-[var(--foreground)] select-none data-focus:bg-[var(--primary)] data-focus:text-[var(--primary-foreground)] data-focus:outline-hidden";
