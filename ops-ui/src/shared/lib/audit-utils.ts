export function eventCategory(eventType: string): "success" | "warning" | "danger" | "neutral" {
  if (eventType.includes("created") || eventType.includes("granted")) return "success";
  if (eventType.includes("revoked") || eventType.includes("deleted")) return "danger";
  if (eventType.includes("updated")) return "warning";
  return "neutral";
}
