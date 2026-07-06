import type { Metadata } from "next";

import { ProsePage, ProseSection } from "@/components/marketing/prose-page";

// Terms of Service (F6) — charging money without terms is a gap. Plain-language
// SaaS terms; a Server Component with no fetching.
export const metadata: Metadata = {
  title: "Terms of Service — Flowly",
  description: "The terms that govern your use of Flowly.",
};

export default function TermsPage() {
  return (
    <ProsePage
      title="Terms of Service"
      intro="These terms govern your use of Flowly. By creating an account you agree to them."
      updated="July 2026"
    >
      <ProseSection title="1. The service">
        <p>
          Flowly provides privacy-first, cookieless web analytics: a tracking script, an ingestion
          endpoint, and a dashboard of live and historical traffic reports. We may improve, change,
          or discontinue features over time; we&apos;ll give reasonable notice of material changes
          that affect paid accounts.
        </p>
      </ProseSection>

      <ProseSection title="2. Your account">
        <p>
          You are responsible for keeping your credentials secure and for all activity under your
          account. You must provide accurate information and be old enough to form a binding
          contract in your jurisdiction. One person or entity per account unless we agree otherwise.
        </p>
      </ProseSection>

      <ProseSection title="3. Acceptable use">
        <p>
          Only add sites you own or are authorized to measure. Don&apos;t use Flowly to collect
          personal or sensitive data through custom parameters, to send fraudulent or abusive
          traffic to the ingestion endpoint, or to attempt to breach, overload, or reverse-engineer
          the service. We may suspend accounts that put the platform or other customers at risk.
        </p>
      </ProseSection>

      <ProseSection title="4. Billing & trials">
        <p>
          Paid plans are usage-based, billed monthly by pageviews across all of your sites, and
          start with a 7-day free trial. Charges are handled by Stripe. You can cancel at any time
          from the customer portal; cancellation stops future charges but does not refund the
          current period unless required by law. Your first 1,000 pageviews each month are free.
        </p>
      </ProseSection>

      <ProseSection title="5. Data & privacy">
        <p>
          Our handling of visitor and account data is described in our{" "}
          <a className="underline" href="/privacy">
            Privacy Policy
          </a>
          , which forms part of these terms. You retain ownership of your analytics data and can
          export or delete it at any time.
        </p>
      </ProseSection>

      <ProseSection title="6. Warranty & liability">
        <p>
          Flowly is provided &ldquo;as is&rdquo; without warranties of any kind. To the maximum
          extent permitted by law, our aggregate liability for any claim relating to the service is
          limited to the amount you paid us in the three months before the claim.
        </p>
      </ProseSection>

      <ProseSection title="7. Changes & contact">
        <p>
          We may update these terms; continued use after an update means you accept the revised
          terms. Questions about these terms? Reach us on our{" "}
          <a className="underline" href="/contact">
            contact page
          </a>
          .
        </p>
      </ProseSection>
    </ProsePage>
  );
}
