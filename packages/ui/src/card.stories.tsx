import type { Meta, StoryObj } from "@storybook/react";
import { Button } from "./button";
import { Card, CardBody, CardFooter, CardHeader } from "./card";

const meta: Meta<typeof Card> = {
  title: "Primitives/Card",
  component: Card,
};
export default meta;
type Story = StoryObj<typeof Card>;

export const PlainCard: Story = {
  render: () => (
    <Card className="max-w-md">
      <p className="text-sm">A bordered container with default 16px padding.</p>
    </Card>
  ),
};

export const WithHeaderAndBody: Story = {
  render: () => (
    <Card noPadding className="max-w-md">
      <CardHeader>
        <h3 className="text-sm font-semibold">Portfolio summary</h3>
        <span className="text-xs text-[var(--muted-foreground)]">Today</span>
      </CardHeader>
      <CardBody>
        <p className="text-sm text-[var(--muted-foreground)]">
          Net exposure $12.4M across 23 positions.
        </p>
      </CardBody>
    </Card>
  ),
};

export const WithFooter: Story = {
  render: () => (
    <Card noPadding className="max-w-md">
      <CardHeader>
        <h3 className="text-sm font-semibold">Confirm trade</h3>
      </CardHeader>
      <CardBody>
        <p className="text-sm">Buy 1,000 AAPL at market price.</p>
      </CardBody>
      <CardFooter>
        <Button variant="ghost" size="sm">Cancel</Button>
        <Button variant="primary" size="sm">Submit</Button>
      </CardFooter>
    </Card>
  ),
};
