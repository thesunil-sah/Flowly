"use client";

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

// Thin generic adapter over shadcn Tabs for controlled key/label toggles
// (date presets, audience dimensions…). Not a tabs implementation — just the
// shared call-site shape used by the dashboard and public share pages.
export function SegmentedTabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: T; label: string }[];
  active: T;
  onChange: (key: T) => void;
}) {
  return (
    <Tabs value={active} onValueChange={(v) => onChange(v as T)}>
      <TabsList>
        {tabs.map((t) => (
          <TabsTrigger key={t.key} value={t.key}>
            {t.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}
