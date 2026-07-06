"use client";

import { OverviewReport } from "@/components/dashboard/overview";
import { ReportShell } from "@/components/dashboard/report-shell";
import { useFilters } from "@/components/layout/filter-context";
import { useRange } from "@/components/layout/range-context";
import { Button } from "@/components/ui/button";
import { downloadExportCsv } from "@/lib/api";

function ExportButton({ siteId }: { siteId: string }) {
  const { range } = useRange();
  const { filters } = useFilters();
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => downloadExportCsv(siteId, range, "overview", filters)}
    >
      Export CSV
    </Button>
  );
}

export default function DashboardPage() {
  return (
    <ReportShell title="Overview" actions={(siteId) => <ExportButton siteId={siteId} />}>
      {(siteId) => <OverviewReport siteId={siteId} />}
    </ReportShell>
  );
}
