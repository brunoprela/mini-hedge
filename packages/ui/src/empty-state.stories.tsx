import type { Meta, StoryObj } from "@storybook/react";
import { Button } from "./button";
import { EmptyState } from "./empty-state";

const meta: Meta<typeof EmptyState> = {
  title: "Primitives/EmptyState",
  component: EmptyState,
  args: {
    title: "No positions",
    description: "You have no open positions for this portfolio.",
  },
};
export default meta;
type Story = StoryObj<typeof EmptyState>;

export const Basic: Story = {};

export const WithDescription: Story = {
  args: {
    title: "No trades today",
    description: "Once you execute a trade it will appear in this list.",
  },
};

export const WithAction: Story = {
  args: {
    title: "No portfolios yet",
    description: "Create your first portfolio to start tracking positions.",
    action: <Button variant="primary">Create portfolio</Button>,
  },
};

export const WithIcon: Story = {
  args: {
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        width={40}
        height={40}
        aria-hidden="true"
      >
        <path d="M3 7h18M3 12h18M3 17h18" strokeLinecap="round" />
      </svg>
    ),
    title: "Inbox empty",
    description: "All caught up.",
  },
};
