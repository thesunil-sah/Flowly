"use client";

import { ChannelsReport } from "@/components/dashboard/report-views";
import { ReportShell } from "@/components/dashboard/report-shell";

export default function ChannelsPage() {
  return (
    <ReportShell title="Channels" description="How visitors reach you: direct, search, social, AI, referral.">
      {(siteId) => <ChannelsReport siteId={siteId} />}
    </ReportShell>
  );
}
