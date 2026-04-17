import type { Preview } from "@storybook/react";
import "./preview.css";

/**
 * Preview wiring.
 *
 *   - `preview.css` pulls in Tailwind and the canonical token layer.
 *   - The `html` element gets `data-theme="dark"` by default (matches desk-ui);
 *     a toolbar control lets you flip to the light baseline.
 *   - A decorator paints the canvas with `var(--background)` so stories inherit
 *     the themed surface rather than Storybook's default white.
 */

if (typeof document !== "undefined") {
  document.documentElement.setAttribute("data-theme", "dark");
}

const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/,
      },
    },
    backgrounds: { disable: true },
  },
  globalTypes: {
    theme: {
      description: "Design system theme",
      defaultValue: "dark",
      toolbar: {
        title: "Theme",
        icon: "paintbrush",
        items: [
          { value: "dark", title: "Dark" },
          { value: "light", title: "Light" },
        ],
        dynamicTitle: true,
      },
    },
  },
  decorators: [
    (Story, context) => {
      const theme = (context.globals.theme as string) ?? "dark";
      if (typeof document !== "undefined") {
        document.documentElement.setAttribute("data-theme", theme);
      }
      return Story();
    },
  ],
};

export default preview;
