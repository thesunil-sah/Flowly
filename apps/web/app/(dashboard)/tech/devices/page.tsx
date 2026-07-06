"use client";

import { AudienceReport } from "@/components/dashboard/report-views";
import { ReportShell } from "@/components/dashboard/report-shell";

export default function DevicesPage() {
  return (
    <ReportShell title="Devices" description="Device types your visitors use.">
      {(siteId) => <AudienceReport siteId={siteId} dimension="device" />}
    </ReportShell>
  );
}
