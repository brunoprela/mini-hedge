import { RuleTable } from "@/features/compliance/components/rule-table";

export default function CompliancePage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Compliance Rules</h1>
      <RuleTable />
    </div>
  );
}
