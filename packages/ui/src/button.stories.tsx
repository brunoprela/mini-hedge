import type { Meta, StoryObj } from "@storybook/react";
import { Button } from "./button";

const meta: Meta<typeof Button> = {
  title: "Primitives/Button",
  component: Button,
  args: { children: "Execute trade" },
  argTypes: {
    variant: { control: "inline-radio", options: ["primary", "secondary", "ghost", "danger"] },
    size: { control: "inline-radio", options: ["sm", "md", "lg"] },
    loading: { control: "boolean" },
    disabled: { control: "boolean" },
  },
};
export default meta;
type Story = StoryObj<typeof Button>;

export const Primary: Story = { args: { variant: "primary", size: "md" } };
export const Secondary: Story = { args: { variant: "secondary", size: "md" } };
export const Ghost: Story = { args: { variant: "ghost", size: "md" } };
export const Danger: Story = { args: { variant: "danger", size: "md", children: "Cancel order" } };

export const AllVariantsAndSizes: Story = {
  render: () => (
    <div className="flex flex-col gap-3">
      {(["primary", "secondary", "ghost", "danger"] as const).map((variant) => (
        <div key={variant} className="flex items-center gap-2">
          <Button variant={variant} size="sm">{variant} sm</Button>
          <Button variant={variant} size="md">{variant} md</Button>
          <Button variant={variant} size="lg">{variant} lg</Button>
        </div>
      ))}
    </div>
  ),
};

export const Loading: Story = { args: { loading: true, children: "Submitting" } };
