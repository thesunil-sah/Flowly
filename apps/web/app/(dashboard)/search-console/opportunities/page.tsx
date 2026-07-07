"use client";

import { ReportShell } from "@/components/dashboard/report-shell";
import { SearchReport } from "@/components/searchconsole/search-report";

export default function OpportunitiesPage() {
  return (
    <ReportShell
      title="Opportunity keywords"
      description="Queries ranking just off page one (position ~5–20) with the most impressions — the cheapest wins."
    >
      {(siteId) => <SearchReport siteId={siteId} report="opportunities" />}
    </ReportShell>
  );
}
