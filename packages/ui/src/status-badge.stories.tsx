import type { Meta, StoryObj } from "@storybook/react";
import { StatusBadge, type StatusVariant } from "./status-badge";

const meta: Meta<typeof StatusBadge> = {
  title: "Primitives/StatusBadge",
  component: StatusBadge,
  args: { children: "Filled" },
  argTypes: {
    variant: {
      control: "inline-radio",
      options: ["success", "warning", "danger", "info", "primary", "neutral"],
    },
  },
};
export default meta;
type Story = StoryObj<typeof StatusBadge>;

export const Success: Story = { args: { variant: "success", children: "Filled" } };
export const Warning: Story = { args: { variant: "warning", children: "Partial" } };
export const Danger: Story = { args: { variant: "danger", children: "Rejected" } };
export const Info: Story = { args: { variant: "info", children: "Pending" } };
export const Primary: Story = { args: { variant: "primary", children: "Active" } };
export const Neutral: Story = { args: { variant: "neutral", children: "Draft" } };

const LABELS: Record<StatusVariant, string> = {
  success: "Filled",
  warning: "Partial",
  danger: "Rejected",
  info: "Pending",
  primary: "Active",
  neutral: "Draft",
};

export const AllVariants: Story = {
  render: () => (
    <div className="flex flex-wrap gap-2">
      {(Object.keys(LABELS) as StatusVariant[]).map((v) => (
        <StatusBadge key={v} variant={v}>
          {LABELS[v]}
        </StatusBadge>
      ))}
    </div>
  ),
};
