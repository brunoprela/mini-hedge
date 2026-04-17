import type { StorybookConfig } from "@storybook/react-vite";
import tailwindcss from "@tailwindcss/vite";
import { mergeConfig } from "vite";

/**
 * Storybook configuration for @mini-hedge/ui.
 *
 * Scope:
 *   - Stories live next to the primitives in `../src/**\/*.stories.tsx`.
 *   - Tailwind CSS v4 is wired in via `@tailwindcss/vite` so primitives that
 *     use Tailwind utility classes render correctly in isolation.
 *   - Global tokens (`src/tokens.css`) are imported in `preview.css`.
 *
 * This config is intentionally minimal and lives only inside `packages/ui/` so
 * consumer UIs (desk-ui, ops-ui, client-ui) are unaffected.
 */
const config: StorybookConfig = {
  stories: ["../src/**/*.stories.@(ts|tsx|mdx)"],
  framework: {
    name: "@storybook/react-vite",
    options: {},
  },
  typescript: {
    reactDocgen: "react-docgen-typescript",
  },
  viteFinal: async (viteConfig) =>
    mergeConfig(viteConfig, {
      plugins: [tailwindcss()],
    }),
};

export default config;
