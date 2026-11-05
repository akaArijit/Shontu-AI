import Link from "next/link";

export default function AppNav({
  active,
}: {
  active: "upload" | "review" | "graph" | "benchmarks";
}) {
  const base =
    "rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors ring-1 ring-inset";
  const activeClass = "bg-copper-400/10 text-copper-300 ring-copper-400/25";
  const idleClass =
    "bg-parchment-50/[0.045] text-parchment-400 ring-warm-100/15 hover:bg-parchment-50/[0.08] hover:text-parchment-200";
  return (
    <nav
      aria-label="Main navigation"
      className="glass-nav inline-flex flex-wrap gap-1 p-1"
    >
      <Link
        className={`${base} ${active === "upload" ? activeClass : idleClass}`}
        href="/"
      >
        Upload
      </Link>
      <Link
        className={`${base} ${active === "benchmarks" ? activeClass : idleClass}`}
        href="/benchmarks"
      >
        Benchmark Data
      </Link>
      <Link
        className={`${base} ${active === "graph" ? activeClass : idleClass}`}
        href="/graph"
      >
        Graph
      </Link>
    </nav>
  );
}
