import type { Metadata } from "next";
import Link from "next/link";

// Public privacy / GDPR page documenting the cookieless approach (Phase 9). A
// Server Component with no data fetching — it states the product's privacy
// promise (§1/§9) plainly so it can double as the "why cookieless" marketing page.

export const metadata: Metadata = {
  title: "Privacy — Flowly",
  description: "How Flowly delivers cookieless, privacy-first web analytics.",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-lg font-semibold">{title}</h2>
      <div className="flex flex-col gap-2 text-sm leading-relaxed text-muted-foreground">{children}</div>
    </section>
  );
}

export default function PrivacyPage() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-8 p-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight">Privacy at Flowly</h1>
        <p className="text-muted-foreground">
          Flowly is analytics that respects your visitors. No cookies, no personal data, no consent
          banner needed. Here&apos;s exactly how that works.
        </p>
      </header>

      <Section title="No cookies, no consent banner">
        <p>
          Flowly sets no cookies and stores nothing on your visitor&apos;s device. Because we never
          store personal data or track people across sites, GDPR and ePrivacy don&apos;t require a
          cookie-consent banner for Flowly analytics.
        </p>
      </Section>

      <Section title="What we collect">
        <p>
          For each pageview we record the page path, referrer, UTM tags, and coarse device, browser,
          OS, and country — all derived at the moment of the request. We do not store raw IP
          addresses, email addresses, or any personal identifier.
        </p>
      </Section>

      <Section title="How visitors stay anonymous">
        <p>
          To count unique visitors without cookies, we compute a one-way hash of the IP address, the
          user agent, and a <strong>daily-rotating salt</strong>. The raw IP is never written to
          disk. Because the salt rotates every 24 hours, the same visitor cannot be linked from one
          day to the next — the identifier is anonymous and short-lived by design.
        </p>
      </Section>

      <Section title="Data retention">
        <p>
          Event data is kept only as long as your plan allows and is then permanently deleted on an
          automated schedule: 30 days on Free, 1 year on Pro, and 2 years on Business.
        </p>
      </Section>

      <Section title="Where data lives & our subprocessors">
        <p>
          Analytics events are stored in our ClickHouse database; account and billing metadata in
          Postgres. We use Stripe for payments and a transactional email provider for account and
          product emails. We never sell data or share it for advertising.
        </p>
      </Section>

      <Section title="Your control">
        <p>
          You can export or delete your data at any time, and every non-essential email carries a
          one-click unsubscribe link. Questions? Reach us at{" "}
          <a className="underline" href="mailto:privacy@flowly.app">
            privacy@flowly.app
          </a>
          .
        </p>
      </Section>

      <footer className="border-t border-border pt-4 text-sm">
        <Link href="/" className="text-muted-foreground underline">
          ← Back to Flowly
        </Link>
      </footer>
    </main>
  );
}
