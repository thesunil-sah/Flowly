"use client";

import { ReportShell } from "@/components/dashboard/report-shell";
import { SearchReport } from "@/components/searchconsole/search-report";

export default function SearchPagesPage() {
  return (
    <ReportShell
      title="Search pages"
      description="Which pages perform best in Google search."
    >
      {(siteId) => <SearchReport siteId={siteId} report="pages" />}
    </ReportShell>
  );
}
