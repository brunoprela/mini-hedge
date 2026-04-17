import type { Meta, StoryObj } from "@storybook/react";
import { KpiCard } from "./kpi-card";

const meta: Meta<typeof KpiCard> = {
  title: "Primitives/KpiCard",
  component: KpiCard,
  args: { label: "Net AUM", value: "$12.4M" },
  argTypes: {
    trend: { control: "inline-radio", options: [undefined, "up", "down", "flat"] },
    flat: { control: "boolean" },
  },
};
export default meta;
type Story = StoryObj<typeof KpiCard>;

export const Default: Story = {};

export const TrendUp: Story = {
  args: { sublabel: "+2.3% today", trend: "up" },
};

export const TrendDown: Story = {
  args: { label: "Realized PnL", value: "-$145.2K", sublabel: "-0.8% today", trend: "down" },
};

export const Grid: Story = {
  render: () => (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-3xl">
      <KpiCard label="Net AUM" value="$12.4M" sublabel="+2.3% today" trend="up" />
      <KpiCard label="Realized PnL" value="-$145.2K" sublabel="-0.8% today" trend="down" />
      <KpiCard label="Open positions" value="23" sublabel="no change" trend="flat" />
    </div>
  ),
};
