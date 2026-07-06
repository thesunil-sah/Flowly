"use client";

import { ReferrersReport } from "@/components/dashboard/report-views";
import { ReportShell } from "@/components/dashboard/report-shell";

export default function ReferrersPage() {
  return (
    <ReportShell title="Referrers" description="Where your visitors came from.">
      {(siteId) => <ReferrersReport siteId={siteId} />}
    </ReportShell>
  );
}
