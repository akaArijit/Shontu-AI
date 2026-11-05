import type { Metadata } from "next";
import Link from "next/link";
import AppNav from "@/components/AppNav";

export const metadata: Metadata = {
  title: "Business Review inactive | MFD Portfolio Dashboard",
  description:
    "The Business Review screen is inactive in the simplified local upload and benchmark graph application.",
};

export default function BusinessReviewPage() {
  return (
    <main className="mx-auto w-full max-w-[1180px] px-4 py-6 sm:px-6 lg:px-8">
      <div className="mb-6">
        <AppNav active="review" />
      </div>

      <section className="glass-panel max-w-3xl p-6 sm:p-8">
        <span className="rounded-full bg-parchment-50/[0.06] px-2.5 py-1 text-[11px] font-semibold text-parchment-300 ring-1 ring-inset ring-warm-100/15">
          Inactive
        </span>
        <h1 className="mt-4 text-2xl font-semibold tracking-tight text-parchment-50 sm:text-3xl">
          Business Review is inactive
        </h1>
        <p className="mt-3 text-sm leading-6 text-parchment-400">
          This app now focuses on one workflow: upload the four InvestWell files,
          review benchmark mappings and local benchmark data, then open the
          benchmark cluster graph. Detailed portfolio analytics remain in
          InvestWell.
        </p>
        <p className="mt-2 text-sm leading-6 text-parchment-400">
          The local backend and its review calculations are unchanged. This page
          remains only so old bookmarks do not break.
        </p>
        <div className="mt-6 flex flex-wrap gap-2">
          <Link className="btn-primary px-4 py-2 text-sm" href="/">
            Upload files
          </Link>
          <Link className="btn-secondary px-4 py-2 text-sm" href="/graph">
            Open Graph
          </Link>
        </div>
      </section>
    </main>
  );
}
