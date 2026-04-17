import type { Meta, StoryObj } from "@storybook/react";
import { LoadingSkeleton } from "./loading-skeleton";

const meta: Meta<typeof LoadingSkeleton> = {
  title: "Primitives/LoadingSkeleton",
  component: LoadingSkeleton,
  argTypes: {
    variant: {
      control: "inline-radio",
      options: ["rectangle", "text", "card", "table-row"],
    },
  },
};
export default meta;
type Story = StoryObj<typeof LoadingSkeleton>;

export const Rectangle: Story = {
  args: { variant: "rectangle", height: "2rem" },
  render: (args) => (
    <div className="max-w-md">
      <LoadingSkeleton {...args} />
    </div>
  ),
};

export const Text: Story = {
  args: { variant: "text", rows: 4 },
  render: (args) => (
    <div className="max-w-md">
      <LoadingSkeleton {...args} />
    </div>
  ),
};

export const TableRow: Story = {
  args: { variant: "table-row", rows: 4, columns: 4 },
  render: (args) => (
    <div className="max-w-3xl">
      <LoadingSkeleton {...args} />
    </div>
  ),
};

export const CardGrid: Story = {
  args: { variant: "card", count: 3 },
  render: (args) => (
    <div className="max-w-3xl">
      <LoadingSkeleton {...args} />
    </div>
  ),
};
