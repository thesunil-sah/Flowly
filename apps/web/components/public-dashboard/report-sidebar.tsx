"use client";

import {
  AppWindow,
  ArrowDownRight,
  ArrowUpRight,
  Cpu,
  FileText,
  Globe,
  LayoutDashboard,
  Megaphone,
  Network,
  Smartphone,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";

// The public dashboard's report sections — in-page state (repo convention),
// scoped to what the public share API can actually serve. Deliberately NOT
// lib/navigation.ts: the app IA contains routes with no public endpoint.

export type PublicSection =
  | "overview"
  | "pages-top"
  | "pages-entry"
  | "pages-exit"
  | "sources"
  | "campaigns"
  | "audience-country"
  | "audience-device"
  | "audience-browser"
  | "audience-os";

type SectionItem = { key: PublicSection; title: string; icon: LucideIcon };
type SectionGroup = { title: string | null; items: SectionItem[] };

export const PUBLIC_SECTIONS: SectionGroup[] = [
  {
    title: null,
    items: [{ key: "overview", title: "Overview", icon: LayoutDashboard }],
  },
  {
    title: "Behavior",
    items: [
      { key: "pages-top", title: "Top pages", icon: FileText },
      { key: "pages-entry", title: "Entry pages", icon: ArrowDownRight },
      { key: "pages-exit", title: "Exit pages", icon: ArrowUpRight },
    ],
  },
  {
    title: "Acquisitions",
    items: [
      { key: "sources", title: "Sources", icon: Network },
      { key: "campaigns", title: "Campaigns", icon: Megaphone },
    ],
  },
  {
    title: "Audience",
    items: [
      { key: "audience-country", title: "Countries", icon: Globe },
      { key: "audience-device", title: "Devices", icon: Smartphone },
      { key: "audience-browser", title: "Browsers", icon: AppWindow },
      { key: "audience-os", title: "OS", icon: Cpu },
    ],
  },
];

export function ReportSidebar({
  active,
  onSelect,
}: {
  active: PublicSection;
  onSelect: (section: PublicSection) => void;
}) {
  return (
    <>
      {/* Desktop: grouped vertical nav */}
      <nav className="hidden flex-col gap-4 lg:flex">
        {PUBLIC_SECTIONS.map((group, gi) => (
          <div key={group.title ?? gi} className="flex flex-col gap-1">
            {group.title && (
              <div className="px-2 pb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                {group.title}
              </div>
            )}
            {group.items.map((item) => {
              const isActive = active === item.key;
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => onSelect(item.key)}
                  aria-current={isActive ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-sm transition-colors",
                    isActive
                      ? "bg-accent font-medium text-accent-foreground"
                      : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                  )}
                >
                  <item.icon className={cn("size-4", isActive && "text-primary")} />
                  {item.title}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Mobile: horizontal scrollable pill row */}
      <div className="flex gap-1 overflow-x-auto pb-1 lg:hidden">
        {PUBLIC_SECTIONS.flatMap((g) => g.items).map((item) => {
          const isActive = active === item.key;
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => onSelect(item.key)}
              className={cn(
                "flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors",
                isActive
                  ? "border-primary/40 bg-accent font-medium"
                  : "border-border text-muted-foreground hover:bg-accent/60",
              )}
            >
              <item.icon className={cn("size-3.5", isActive && "text-primary")} />
              {item.title}
            </button>
          );
        })}
      </div>
    </>
  );
}
