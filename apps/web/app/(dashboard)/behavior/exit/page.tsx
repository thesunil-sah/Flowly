"use client";

import { PagesReport } from "@/components/dashboard/report-views";
import { ReportShell } from "@/components/dashboard/report-shell";

export default function BehaviorExitPage() {
  return (
    <ReportShell title="Exit pages" description="Where sessions end.">
      {(siteId) => <PagesReport siteId={siteId} kind="exit" title="Exit pages" />}
    </ReportShell>
  );
}
