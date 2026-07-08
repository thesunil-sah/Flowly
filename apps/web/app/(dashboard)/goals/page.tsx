"use client";

import { GoalsReport } from "@/components/goals/goals-report";
import { ReportShell } from "@/components/dashboard/report-shell";

export default function GoalsPage() {
  return (
    <ReportShell
      title="Goals & events"
      description="Track custom events and measure conversion rates for the actions that matter."
    >
      {(siteId) => <GoalsReport siteId={siteId} />}
    </ReportShell>
  );
}
