import Link from "next/link";
import { Check, CookieIcon } from "lucide-react";

// The cookieless / privacy USP block — the product's core promise, stated
// plainly (details live on /privacy).
const POINTS = [
  "No cookies, nothing stored on your visitors' devices",
  "Anonymous visitor hash that rotates every 24 hours",
  "Raw IP addresses are never written to disk",
  "No consent banner required under GDPR / ePrivacy",
] as const;

export function PrivacyUsp() {
  return (
    <section>
      <div className="mx-auto grid w-full max-w-6xl items-center gap-12 px-4 py-20 sm:px-6 lg:grid-cols-2 lg:py-28">
        <div>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Privacy isn&apos;t a setting. It&apos;s the architecture.
          </h2>
          <p className="mt-3 text-lg text-muted-foreground">
            Flowly was built cookieless from the first line of code — your analytics can&apos;t
            violate your visitors&apos; privacy, because the data simply isn&apos;t there.
          </p>
          <ul className="mt-6 flex flex-col gap-3">
            {POINTS.map((p) => (
              <li key={p} className="flex items-start gap-2.5 text-sm">
                <Check className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                {p}
              </li>
            ))}
          </ul>
          <Link
            href="/privacy"
            className="mt-6 inline-block text-sm font-medium text-primary hover:underline"
          >
            Read exactly how it works →
          </Link>
        </div>

        <div className="mx-auto w-full max-w-sm rounded-lg border border-border bg-card p-6 shadow-card">
          <div className="flex items-center gap-3">
            <div className="relative flex size-10 items-center justify-center rounded-lg bg-muted text-muted-foreground">
              <CookieIcon className="size-5" aria-hidden />
              <span className="absolute h-px w-8 rotate-45 rounded bg-destructive" aria-hidden />
            </div>
            <div>
              <div className="font-semibold">Consent banner</div>
              <div className="text-sm text-muted-foreground">Not needed</div>
            </div>
          </div>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            The banner your visitors never have to click, because the cookie it would ask about
            doesn&apos;t exist.
          </p>
        </div>
      </div>
    </section>
  );
}
