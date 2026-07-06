import type { Metadata } from "next";

import { ProsePage, ProseSection } from "@/components/marketing/prose-page";

// About page (F6): the mission + why-we-exist story. Server Component.
export const metadata: Metadata = {
  title: "About — Flowly",
  description: "Why Flowly exists: privacy-first, cookieless web analytics that respects visitors.",
};

export default function AboutPage() {
  return (
    <ProsePage
      title="About Flowly"
      intro="Web analytics that respects the people it measures — no cookies, no personal data, no consent banner."
    >
      <ProseSection title="Why we built it">
        <p>
          Most analytics tools were built to follow people around the web. That model demands cookie
          banners, leaks personal data, and buries the one number you actually care about — how many
          real visitors you have right now. We wanted the opposite: a tiny script, honest numbers,
          and nothing creepy.
        </p>
      </ProseSection>

      <ProseSection title="How we&apos;re different">
        <p>
          Flowly is cookieless by design. A ~1 KB script sends a pageview; visitors are counted with
          a daily-rotating anonymous hash that can&apos;t be linked across days or sites. No cookies
          means no consent banner. You still get live visitors, sources, pages, geography, and
          devices — just without the surveillance.
        </p>
      </ProseSection>

      <ProseSection title="How we make money">
        <p>
          Simply: you pay for what you use, metered by pageviews, with your first 1,000 views each
          month free. No selling data, no ads, no upsell maze. Our incentives stay aligned with
          yours because the only thing we sell is the product.
        </p>
      </ProseSection>

      <ProseSection title="Say hello">
        <p>
          Flowly is a small, focused product built in the open. Have feedback or a feature request?
          We&apos;d love to hear it — reach us on our{" "}
          <a className="underline" href="/contact">
            contact page
          </a>
          .
        </p>
      </ProseSection>
    </ProsePage>
  );
}
