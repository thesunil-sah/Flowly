"use client";

import { AudienceReport } from "@/components/dashboard/report-views";
import { ReportShell } from "@/components/dashboard/report-shell";

export default function ScreensPage() {
  return (
    <ReportShell title="Screen sizes" description="Viewport widths your visitors browse on.">
      {(siteId) => <AudienceReport siteId={siteId} dimension="screen" />}
    </ReportShell>
  );
}
