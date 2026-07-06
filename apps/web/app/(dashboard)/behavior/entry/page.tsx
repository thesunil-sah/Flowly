"use client";

import { PagesReport } from "@/components/dashboard/report-views";
import { ReportShell } from "@/components/dashboard/report-shell";

export default function BehaviorEntryPage() {
  return (
    <ReportShell title="Entry pages" description="Where sessions begin.">
      {(siteId) => <PagesReport siteId={siteId} kind="entry" title="Entry pages" />}
    </ReportShell>
  );
}
