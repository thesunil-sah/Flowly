import Link from "next/link";

// Minimal placeholder — the full multi-column footer (legal, about, contact,
// social) is Phase F6.
export function MarketingFooter() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-8 text-sm text-muted-foreground sm:px-6">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-foreground">Flowly</span>
          <span>· Privacy-first, cookieless web analytics</span>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/privacy" className="hover:text-foreground">
            Privacy
          </Link>
          <span>© {new Date().getFullYear()} Flowly</span>
        </div>
      </div>
    </footer>
  );
}
