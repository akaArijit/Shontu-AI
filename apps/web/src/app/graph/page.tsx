import type { Metadata } from "next";
import BenchmarkGraphClient from "@/components/BenchmarkGraphClient";

export const metadata: Metadata = {
  title: "Benchmark Cluster Graph | MFD Portfolio Dashboard",
  description:
    "Zoomable local benchmark cluster graph for mapped folios and benchmark comparisons.",
};

export default function GraphPage() {
  return <BenchmarkGraphClient />;
}
