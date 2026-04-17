import type { Meta, StoryObj } from "@storybook/react";
import { FormField } from "./form-field";
import { Select } from "./select";

const meta: Meta<typeof FormField> = {
  title: "Primitives/FormField",
  component: FormField,
};
export default meta;
type Story = StoryObj<typeof FormField>;

const inputClass =
  "h-9 w-full rounded-md border border-[var(--border)] bg-[var(--input,var(--card))] px-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--ring,var(--primary))]";

export const WithInput: Story = {
  render: () => (
    <div className="max-w-sm">
      <FormField label="Ticker symbol" hint="Uppercase, up to 5 characters.">
        <input className={inputClass} placeholder="AAPL" />
      </FormField>
    </div>
  ),
};

export const Required: Story = {
  render: () => (
    <div className="max-w-sm">
      <FormField label="Quantity" required hint="Whole shares only.">
        <input type="number" className={inputClass} placeholder="100" />
      </FormField>
    </div>
  ),
};

export const ErrorState: Story = {
  render: () => (
    <div className="max-w-sm">
      <FormField label="Ticker symbol" error="Symbol not recognised.">
        <input className={inputClass} defaultValue="ZZZZ" />
      </FormField>
    </div>
  ),
};

export const WithSelect: Story = {
  render: () => (
    <div className="max-w-sm">
      <FormField label="Side" hint="Direction of the order.">
        <Select defaultValue="buy">
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
        </Select>
      </FormField>
    </div>
  ),
};
