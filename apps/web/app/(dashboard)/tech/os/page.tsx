"use client";

import { AudienceReport } from "@/components/dashboard/report-views";
import { ReportShell } from "@/components/dashboard/report-shell";

export default function OsPage() {
  return (
    <ReportShell title="Operating systems" description="Platforms your visitors use.">
      {(siteId) => <AudienceReport siteId={siteId} dimension="os" />}
    </ReportShell>
  );
}
