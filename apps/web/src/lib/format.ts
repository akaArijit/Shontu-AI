export function formatCurrency(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "Not available";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatPercent(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "Not available";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function formatDays(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "Not available";
  return `${value.toLocaleString("en-IN")} days`;
}

export function formatDate(value: string | null): string {
  if (!value) return "Not available";
  return new Date(`${value.slice(0, 10)}T00:00:00`).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function performanceLabel(status: string): string {
  if (status === "ahead") return "Ahead of benchmark";
  if (status === "behind") return "Behind benchmark";
  if (status === "in_line") return "In line with benchmark";
  if (status === "needs_review") return "Needs review";
  return "Not available";
}
