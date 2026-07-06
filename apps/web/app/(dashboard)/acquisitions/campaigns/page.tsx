"use client";

import { CampaignsReport } from "@/components/dashboard/report-views";
import { ReportShell } from "@/components/dashboard/report-shell";

export default function CampaignsPage() {
  return (
    <ReportShell title="Campaigns" description="UTM-tagged campaign traffic.">
      {(siteId) => <CampaignsReport siteId={siteId} />}
    </ReportShell>
  );
}
