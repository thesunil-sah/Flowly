import Link from "next/link";

import { MarketingMobileNav } from "@/components/marketing/mobile-nav";
import { MARKETING_LINKS } from "@/components/marketing/nav-links";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";

// Sticky marketing header — CSS-only stickiness, no scroll JS.
export function MarketingNav() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-4 px-4 sm:px-6">
        <MarketingMobileNav />
        <Link href="/" className="text-lg font-semibold tracking-tight">
          Flowly
        </Link>

        <nav className="ml-6 hidden items-center gap-1 md:flex">
          {MARKETING_LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              {l.title}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-1.5">
          <ThemeToggle />
          <Button variant="ghost" size="sm" asChild className="hidden sm:inline-flex">
            <Link href="/sign-in">Sign in</Link>
          </Button>
          <Button size="sm" asChild>
            <Link href="/sign-up">Start for free</Link>
          </Button>
        </div>
      </div>
    </header>
  );
}
