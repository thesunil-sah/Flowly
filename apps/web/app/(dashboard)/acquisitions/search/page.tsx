"use client";

import { ChannelReferrersReport } from "@/components/dashboard/report-views";
import { ReportShell } from "@/components/dashboard/report-shell";

export default function SearchPage() {
  return (
    <ReportShell title="Search" description="Search engines sending you traffic.">
      {(siteId) => <ChannelReferrersReport siteId={siteId} channel="search" />}
    </ReportShell>
  );
}
