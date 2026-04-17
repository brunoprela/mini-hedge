import type { Meta, StoryObj } from "@storybook/react";
import { useMemo, useState } from "react";
import { TBody, TD, TH, THead, TR, Table } from "./table";

const meta: Meta = {
  title: "Primitives/Table",
};
export default meta;
type Story = StoryObj;

type Row = { symbol: string; qty: number; price: number };
const ROWS: Row[] = [
  { symbol: "AAPL", qty: 1000, price: 192.34 },
  { symbol: "MSFT", qty: 500, price: 418.11 },
  { symbol: "NVDA", qty: 250, price: 915.22 },
];

export const Basic: Story = {
  render: () => (
    <Table>
      <THead>
        <TR>
          <TH>Symbol</TH>
          <TH>Quantity</TH>
          <TH>Price</TH>
        </TR>
      </THead>
      <TBody>
        {ROWS.map((r) => (
          <TR key={r.symbol}>
            <TD>{r.symbol}</TD>
            <TD>{r.qty.toLocaleString()}</TD>
            <TD>${r.price.toFixed(2)}</TD>
          </TR>
        ))}
      </TBody>
    </Table>
  ),
};

export const SortableColumns: Story = {
  render: () => {
    const [sort, setSort] = useState<keyof Row>("symbol");
    const sorted = useMemo(
      () => [...ROWS].sort((a, b) => (a[sort] > b[sort] ? 1 : -1)),
      [sort],
    );
    const HeaderCell = ({ col, label }: { col: keyof Row; label: string }) => (
      <TH>
        <button
          type="button"
          onClick={() => setSort(col)}
          className="uppercase tracking-wider hover:text-[var(--foreground)]"
        >
          {label}
          {sort === col ? " ↑" : ""}
        </button>
      </TH>
    );
    return (
      <Table>
        <THead>
          <TR>
            <HeaderCell col="symbol" label="Symbol" />
            <HeaderCell col="qty" label="Quantity" />
            <HeaderCell col="price" label="Price" />
          </TR>
        </THead>
        <TBody>
          {sorted.map((r) => (
            <TR key={r.symbol}>
              <TD>{r.symbol}</TD>
              <TD>{r.qty.toLocaleString()}</TD>
              <TD>${r.price.toFixed(2)}</TD>
            </TR>
          ))}
        </TBody>
      </Table>
    );
  },
};
