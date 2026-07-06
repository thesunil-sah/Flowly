"use client";

import { ChannelReferrersReport } from "@/components/dashboard/report-views";
import { ReportShell } from "@/components/dashboard/report-shell";

export default function AiPlatformsPage() {
  return (
    <ReportShell title="AI platforms" description="Traffic from AI assistants like ChatGPT and Perplexity.">
      {(siteId) => <ChannelReferrersReport siteId={siteId} channel="ai" />}
    </ReportShell>
  );
}
