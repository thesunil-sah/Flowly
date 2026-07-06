"use client";

import { AudienceReport } from "@/components/dashboard/report-views";
import { ReportShell } from "@/components/dashboard/report-shell";

export default function CitiesPage() {
  return (
    <ReportShell title="Cities" description="Where your visitors are, city-level (paid).">
      {(siteId) => <AudienceReport siteId={siteId} dimension="city" />}
    </ReportShell>
  );
}
