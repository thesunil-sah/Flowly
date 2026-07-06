"use client";

import { ChannelReferrersReport } from "@/components/dashboard/report-views";
import { ReportShell } from "@/components/dashboard/report-shell";

export default function SocialPage() {
  return (
    <ReportShell title="Social" description="Social networks sending you traffic.">
      {(siteId) => <ChannelReferrersReport siteId={siteId} channel="social" />}
    </ReportShell>
  );
}
