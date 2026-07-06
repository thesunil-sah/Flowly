"use client";

import Link from "next/link";
import { Check, ChevronsUpDown, Globe } from "lucide-react";

import { useActiveSite } from "@/components/layout/site-context";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function SiteSwitcher() {
  const { sites, activeSiteId, setActiveSiteId } = useActiveSite();
  if (sites.length === 0) return null;

  const active = sites.find((s) => s.site_id === activeSiteId) ?? sites[0];

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <Globe className="size-3.5 text-muted-foreground" />
          <span className="max-w-40 truncate">{active.domain}</span>
          <ChevronsUpDown className="size-3.5 text-muted-foreground" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        {sites.map((s) => (
          <DropdownMenuItem key={s.id} onClick={() => setActiveSiteId(s.site_id)}>
            <span className="truncate">{s.domain}</span>
            {s.site_id === active.site_id && <Check className="ml-auto size-4" />}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/sites">Manage sites</Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
