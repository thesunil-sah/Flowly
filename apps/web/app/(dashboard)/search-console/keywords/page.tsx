"use client";

import { ReportShell } from "@/components/dashboard/report-shell";
import { SearchReport } from "@/components/searchconsole/search-report";

export default function KeywordsPage() {
  return (
    <ReportShell
      title="Search keywords"
      description="Queries your site ranks for in Google, from your Search Console."
    >
      {(siteId) => <SearchReport siteId={siteId} report="keywords" />}
    </ReportShell>
  );
}
