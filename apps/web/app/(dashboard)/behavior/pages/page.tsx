"use client";

import { PagesReport } from "@/components/dashboard/report-views";
import { ReportShell } from "@/components/dashboard/report-shell";

export default function BehaviorPagesPage() {
  return (
    <ReportShell title="Pages" description="Most-viewed pages in this range.">
      {(siteId) => <PagesReport siteId={siteId} kind="top" title="Top pages" />}
    </ReportShell>
  );
}
