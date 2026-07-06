"use client";

import { AudienceReport } from "@/components/dashboard/report-views";
import { ReportShell } from "@/components/dashboard/report-shell";

export default function BrowsersPage() {
  return (
    <ReportShell title="Browsers" description="Browsers your visitors use.">
      {(siteId) => <AudienceReport siteId={siteId} dimension="browser" />}
    </ReportShell>
  );
}
