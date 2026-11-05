"use client";

import { useEffect, useState } from "react";

function stageFor(kind: "preview" | "confirm" | "demo", seconds: number) {
  if (kind === "preview") {
    if (seconds < 2) return "Uploading files to local temporary storage";
    if (seconds < 6) return "Reading rows and checking headers, dates and amounts";
    if (seconds < 12) {
      return "Matching clients, folios, transactions and benchmark mappings";
    }
    return "Finishing the preview. Large files can take a little longer.";
  }
  if (kind === "confirm") {
    if (seconds < 3) return "Saving normalized rows and preserving reviewed mappings";
    if (seconds < 8) return "Reconciling folios, clients and transactions";
    return "Rebuilding graph and dashboard indexes";
  }
  return "Generating and loading the local demo snapshot";
}

export default function ImportProgress({
  kind,
}: {
  kind: "preview" | "confirm" | "demo";
}) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(() => {
      setSeconds(Math.floor((Date.now() - started) / 1000));
    }, 500);
    return () => window.clearInterval(timer);
  }, []);

  const stage = stageFor(kind, seconds);
  return (
    <section
      aria-live="polite"
      className="panel border-copper-400/30 bg-copper-400/[0.04] p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-copper-300">
            {kind === "confirm"
              ? "Saving snapshot"
              : kind === "demo"
                ? "Loading demo"
                : "Preparing preview"}
          </p>
          <h2 className="mt-1 text-base font-semibold text-parchment-100">
            {stage}
          </h2>
          <p className="mt-1 max-w-3xl text-sm text-parchment-400">
            The page stays responsive while the server processes the files. Raw
            uploads are held only in temporary local storage and are deleted
            when this operation finishes.
          </p>
        </div>
        <span className="rounded-full border border-warm-100/15 px-3 py-1 text-xs text-parchment-300">
          {seconds}s
        </span>
      </div>
      <div
        className="mt-4 h-2 overflow-hidden rounded-full bg-parchment-50/[0.07]"
        role="progressbar"
        aria-label={stage}
      >
        <div className="h-full w-2/3 animate-pulse rounded-full bg-copper-400/80" />
      </div>
      <p className="mt-3 text-xs text-parchment-500">
        Preview does not change the current snapshot. Nothing is confirmed until
        you review the summary and choose Confirm import.
      </p>
    </section>
  );
}
