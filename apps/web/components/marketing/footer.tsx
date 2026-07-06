import Link from "next/link";

// Full marketing footer (F6): product / company / legal columns, social marks,
// and a "Powered by Flowly" self-promo. Brand marks are inline currentColor
// SVGs (brand assets, exempt from the no-raw-hex rule; they flip with theme).

type FooterLink = { title: string; href: string };
type FooterCol = { heading: string; links: FooterLink[] };

const COLUMNS: FooterCol[] = [
  {
    heading: "Product",
    links: [
      { title: "Features", href: "/#features" },
      { title: "Pricing", href: "/pricing" },
      { title: "Live demo", href: "/#demo" },
      { title: "Sign in", href: "/sign-in" },
    ],
  },
  {
    heading: "Company",
    links: [
      { title: "About", href: "/about" },
      { title: "Contact", href: "/contact" },
    ],
  },
  {
    heading: "Legal",
    links: [
      { title: "Privacy", href: "/privacy" },
      { title: "Terms", href: "/terms" },
    ],
  },
];

const SOCIALS: { label: string; href: string; path: string }[] = [
  {
    label: "Flowly on X",
    href: "https://x.com/flowly",
    path: "M18.9 1.6h3.68l-8.05 9.19L24 22.4h-7.4l-5.8-7.58-6.64 7.58H.48l8.6-9.83L0 1.6h7.6l5.24 6.93ZM17.6 20.2h2.04L6.48 3.7H4.3Z",
  },
  {
    label: "Flowly on GitHub",
    href: "https://github.com/flowly",
    path: "M12 .3a12 12 0 0 0-3.79 23.39c.6.11.82-.26.82-.58v-2.03c-3.34.73-4.04-1.61-4.04-1.61-.55-1.39-1.33-1.76-1.33-1.76-1.09-.74.08-.73.08-.73 1.2.09 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.5 1 .1-.78.42-1.31.76-1.61-2.66-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.52.11-3.18 0 0 1-.32 3.3 1.23a11.5 11.5 0 0 1 6 0c2.28-1.55 3.29-1.23 3.29-1.23.65 1.66.24 2.88.12 3.18.77.84 1.23 1.91 1.23 3.22 0 4.61-2.81 5.63-5.49 5.92.43.38.82 1.11.82 2.24v3.32c0 .32.21.7.82.58A12 12 0 0 0 12 .3Z",
  },
  {
    label: "Flowly on LinkedIn",
    href: "https://www.linkedin.com/company/flowly",
    path: "M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.42v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28ZM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13ZM7.12 20.45H3.55V9h3.57v11.45ZM22.22 0H1.77C.8 0 0 .78 0 1.75v20.5C0 23.22.8 24 1.77 24h20.45c.98 0 1.78-.78 1.78-1.75V1.75C24 .78 23.2 0 22.22 0Z",
  },
];

function SocialMark({ path }: { path: string }) {
  return (
    <svg viewBox="0 0 24 24" className="size-4" fill="currentColor" aria-hidden>
      <path d={path} />
    </svg>
  );
}

export function MarketingFooter() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto w-full max-w-6xl px-4 py-12 sm:px-6 lg:py-16">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-[1.5fr_1fr_1fr_1fr]">
          <div className="flex flex-col gap-3">
            <span className="text-lg font-semibold tracking-tight">Flowly</span>
            <p className="max-w-xs text-sm text-muted-foreground">
              Privacy-first, cookieless web analytics. Live visitors and clean reports from one
              ~1&nbsp;KB script — no cookies, no consent banner.
            </p>
            <div className="mt-1 flex items-center gap-3">
              {SOCIALS.map((s) => (
                <a
                  key={s.label}
                  href={s.href}
                  aria-label={s.label}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="text-muted-foreground transition-colors hover:text-foreground"
                >
                  <SocialMark path={s.path} />
                </a>
              ))}
            </div>
          </div>

          {COLUMNS.map((col) => (
            <div key={col.heading} className="flex flex-col gap-3">
              <h3 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                {col.heading}
              </h3>
              <ul className="flex flex-col gap-2 text-sm">
                {col.links.map((l) => (
                  <li key={l.title}>
                    <Link href={l.href} className="text-muted-foreground hover:text-foreground">
                      {l.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-10 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-6 text-sm text-muted-foreground">
          <span>© {new Date().getFullYear()} Flowly. All rights reserved.</span>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1 text-xs font-medium hover:text-foreground"
          >
            <span className="inline-block size-1.5 rounded-full bg-primary" aria-hidden />
            Powered by Flowly
          </Link>
        </div>
      </div>
    </footer>
  );
}
