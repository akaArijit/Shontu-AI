import type { Metadata } from "next";
import BenchmarkClient from "@/components/BenchmarkClient";

export const metadata: Metadata = {
  title: "Benchmark Mapping & Data | MFD Portfolio Dashboard",
  description:
    "Local benchmark mapping review and closing-level import for the MFD dashboard.",
};

export default function BenchmarksPage() {
  return <BenchmarkClient />;
}
