"use client";

import Link from "next/link";
import { Menu } from "lucide-react";
import { useState } from "react";

import { MARKETING_LINKS } from "@/components/marketing/nav-links";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

export function MarketingMobileNav() {
  const [open, setOpen] = useState(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open navigation">
          <Menu className="size-4" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-64 p-0">
        <SheetTitle className="flex h-14 items-center border-b border-border px-6 text-lg font-semibold">
          Flowly
        </SheetTitle>
        <nav className="flex flex-col gap-1 p-4">
          {MARKETING_LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className="rounded-md px-2 py-2 text-sm text-muted-foreground hover:bg-accent/60 hover:text-foreground"
            >
              {l.title}
            </Link>
          ))}
          <Link
            href="/sign-in"
            onClick={() => setOpen(false)}
            className="rounded-md px-2 py-2 text-sm text-muted-foreground hover:bg-accent/60 hover:text-foreground"
          >
            Sign in
          </Link>
        </nav>
      </SheetContent>
    </Sheet>
  );
}
