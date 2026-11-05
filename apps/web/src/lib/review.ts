import type { BusinessPerformance } from "@/lib/types";

export const performanceMeta: Record<
  BusinessPerformance,
  { label: string; tone: "green" | "red" | "amber" | "slate" }
> = {
  ahead: { label: "Ahead", tone: "green" },
  behind: { label: "Behind", tone: "red" },
  in_line: { label: "In line", tone: "slate" },
  not_available: { label: "Not available", tone: "slate" },
  needs_review: { label: "Needs review", tone: "amber" },
};

export function performanceLabel(value: BusinessPerformance): string {
  return performanceMeta[value].label;
}
