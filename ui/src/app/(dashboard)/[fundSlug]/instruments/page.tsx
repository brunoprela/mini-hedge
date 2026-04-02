import { InstrumentList } from "@/features/instruments/components/instrument-list";

export default function InstrumentsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Instruments</h1>
      <InstrumentList />
    </div>
  );
}
