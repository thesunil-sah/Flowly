"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { readyNavGroups } from "@/lib/navigation";
import { cn } from "@/lib/utils";

// Shared nav body: rendered inside the desktop <aside> and the mobile Sheet.
export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-4 p-4">
      {readyNavGroups().map((group, gi) => (
        <div key={group.title ?? gi} className="flex flex-col gap-1">
          {group.title && (
            <div className="px-2 pb-1 text-xs font-medium tracking-wide text-muted-foreground uppercase">
              {group.title}
            </div>
          )}
          {group.items.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors",
                  active
                    ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                    : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
                )}
              >
                <item.icon className={cn("size-4", active && "text-primary")} />
                {item.title}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

export function AppSidebar() {
  return (
    <aside className="sticky top-0 hidden h-svh w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar lg:flex">
      <div className="flex h-14 items-center border-b border-sidebar-border px-6">
        <Link href="/dashboard" className="text-lg font-semibold tracking-tight">
          Flowly
        </Link>
      </div>
      <div className="flex-1 overflow-y-auto">
        <SidebarNav />
      </div>
    </aside>
  );
}
