import type { Metadata } from "next";

import { ProsePage, ProseSection } from "@/components/marketing/prose-page";

// Public privacy / GDPR page documenting the cookieless approach (Phase 9,
// restyled onto the shared prose layout in F6). Server Component, no fetching —
// it states the product's privacy promise (§1/§9) plainly.

export const metadata: Metadata = {
  title: "Privacy — Flowly",
  description: "How Flowly delivers cookieless, privacy-first web analytics.",
};

export default function PrivacyPage() {
  return (
    <ProsePage
      title="Privacy at Flowly"
      intro="Flowly is analytics that respects your visitors. No cookies, no personal data, no consent banner needed. Here's exactly how that works."
    >
      <ProseSection title="No cookies, no consent banner">
        <p>
          Flowly sets no cookies and stores nothing on your visitor&apos;s device. Because we never
          store personal data or track people across sites, GDPR and ePrivacy don&apos;t require a
          cookie-consent banner for Flowly analytics.
        </p>
      </ProseSection>

      <ProseSection title="What we collect">
        <p>
          For each pageview we record the page path, referrer, UTM tags, and coarse device, browser,
          OS, and country — all derived at the moment of the request. We do not store raw IP
          addresses, email addresses, or any personal identifier.
        </p>
      </ProseSection>

      <ProseSection title="How visitors stay anonymous">
        <p>
          To count unique visitors without cookies, we compute a one-way hash of the IP address, the
          user agent, and a <strong>daily-rotating salt</strong>. The raw IP is never written to
          disk. Because the salt rotates every 24 hours, the same visitor cannot be linked from one
          day to the next — the identifier is anonymous and short-lived by design.
        </p>
      </ProseSection>

      <ProseSection title="Data retention">
        <p>
          Event data is kept only as long as your plan allows and is then permanently deleted on an
          automated schedule: 30 days on Free, 1 year on Pro, and 2 years on Business.
        </p>
      </ProseSection>

      <ProseSection title="Where data lives & our subprocessors">
        <p>
          Analytics events are stored in our ClickHouse database; account and billing metadata in
          Postgres. We use Stripe for payments and a transactional email provider for account and
          product emails. We never sell data or share it for advertising.
        </p>
      </ProseSection>

      <ProseSection title="Your control">
        <p>
          You can export or delete your data at any time, and every non-essential email carries a
          one-click unsubscribe link. Questions? Reach us on our{" "}
          <a className="underline" href="/contact">
            contact page
          </a>
          .
        </p>
      </ProseSection>
    </ProsePage>
  );
}
