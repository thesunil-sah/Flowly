"use client";

import { AudienceReport } from "@/components/dashboard/report-views";
import { ReportShell } from "@/components/dashboard/report-shell";

export default function LanguagesPage() {
  return (
    <ReportShell title="Languages" description="Browser languages your visitors use.">
      {(siteId) => <AudienceReport siteId={siteId} dimension="language" />}
    </ReportShell>
  );
}
