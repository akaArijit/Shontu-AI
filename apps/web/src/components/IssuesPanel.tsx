import Badge from "@/components/Badge";
import type { ImportIssue } from "@/lib/types";

function tone(severity: string): "red" | "amber" | "slate" {
  if (severity === "error") return "red";
  if (severity === "warning") return "amber";
  return "slate";
}

function fileLabel(fileType: string): string {
  const labels: Record<string, string> = {
    clients: "Client Details",
    folios: "Folios",
    portfolio: "Portfolio Valuation",
    reconciliation: "Reconciliation",
  };
  return labels[fileType] ?? fileType;
}

export default function IssuesPanel({ issues }: { issues: ImportIssue[] }) {
  const errors = issues.filter((item) => item.severity === "error").length;
  const warnings = issues.filter((item) => item.severity === "warning").length;

  return (
    <section className="panel">
      <div className="flex flex-col gap-1 border-b border-warm-100/15 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-parchment-100">
            Import issues / warnings
          </h2>
          <p className="mt-1 text-xs text-parchment-400">
            Skipped rows, unmatched clients, missing values and reconciliation
            warnings from the latest confirmed import.
          </p>
        </div>
        <div className="flex gap-2">
          <Badge tone={errors > 0 ? "red" : "slate"}>{errors} errors</Badge>
          <Badge tone={warnings > 0 ? "amber" : "slate"}>{warnings} warnings</Badge>
        </div>
      </div>

      {issues.length === 0 ? (
        <p className="px-5 py-5 text-sm text-parchment-400">
          No import issues were recorded for this snapshot.
        </p>
      ) : (
        <div className="max-h-[420px] overflow-auto">
          <table className="w-full min-w-[900px] border-collapse text-left text-sm">
            <thead className="sticky top-0 bg-ink-900/95 text-[11px] uppercase tracking-[0.14em] text-parchment-400 backdrop-blur">
              <tr>
                <th className="px-4 py-3 font-semibold">Severity</th>
                <th className="px-4 py-3 font-semibold">File</th>
                <th className="px-4 py-3 font-semibold">Row</th>
                <th className="px-4 py-3 font-semibold">Field</th>
                <th className="px-4 py-3 font-semibold">Message</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-warm-100/10">
              {issues.slice(0, 250).map((item, index) => (
                <tr key={`${item.id ?? "issue"}-${index}`} className="align-top">
                  <td className="px-4 py-3">
                    <Badge tone={tone(item.severity)}>{item.severity}</Badge>
                  </td>
                  <td className="px-4 py-3 text-xs text-parchment-400">
                    {fileLabel(item.file_type)}
                  </td>
                  <td className="px-4 py-3 text-xs text-parchment-400">
                    {item.row_number ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-xs text-parchment-400">
                    {item.field ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-xs text-parchment-300">{item.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {issues.length > 250 && (
            <p className="px-4 py-3 text-xs text-parchment-400">
              Showing 250 of {issues.length} issues.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
