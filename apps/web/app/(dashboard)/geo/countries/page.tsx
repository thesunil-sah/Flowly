"use client";

import { AudienceReport } from "@/components/dashboard/report-views";
import { ReportShell } from "@/components/dashboard/report-shell";

export default function CountriesPage() {
  return (
    <ReportShell title="Countries" description="Where your visitors are.">
      {(siteId) => <AudienceReport siteId={siteId} dimension="country" />}
    </ReportShell>
  );
}
