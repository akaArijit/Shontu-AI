import type { ReactNode } from "react";

type Tone = "green" | "red" | "amber" | "slate" | "blue";

const tones: Record<Tone, string> = {
  green: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/25",
  red: "bg-rose-400/10 text-rose-300 ring-rose-400/25",
  amber: "bg-amber-400/10 text-amber-300 ring-amber-400/25",
  slate: "bg-parchment-50/[0.06] text-parchment-300 ring-warm-100/15",
  blue: "bg-copper-400/10 text-copper-300 ring-copper-400/25",
};

export default function Badge({
  children,
  tone = "slate",
  className = "",
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex shrink-0 items-center whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}
