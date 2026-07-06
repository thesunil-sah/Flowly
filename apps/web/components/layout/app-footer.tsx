import Link from "next/link";

// Slim in-app footer (F6): a quiet legal strip at the bottom of the dashboard
// shell, distinct from the rich marketing footer.
export function AppFooter() {
  return (
    <footer className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-t border-border px-4 py-3 text-xs text-muted-foreground lg:px-6">
      <span>© {new Date().getFullYear()} Flowly</span>
      <div className="flex gap-4">
        <Link href="/privacy" className="hover:text-foreground">
          Privacy
        </Link>
        <Link href="/terms" className="hover:text-foreground">
          Terms
        </Link>
        <Link href="/contact" className="hover:text-foreground">
          Contact
        </Link>
      </div>
    </footer>
  );
}
