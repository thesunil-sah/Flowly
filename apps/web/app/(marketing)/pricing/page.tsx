import type { Metadata } from "next";

import { Faq } from "@/components/marketing/faq";
import { FinalCta } from "@/components/marketing/final-cta";
import { Pricing } from "@/components/marketing/pricing";
import { Reveal } from "@/components/motion";

// Dedicated pricing page (F5). Reuses the exact F1 pricing section — the same
// graduated table + interactive slider off lib/pricing.ts (one pricing truth),
// which the F5 billing UI's bill estimate also consumes.
export const metadata: Metadata = {
  title: "Pricing — Flowly",
  description:
    "Metered, pay-as-you-go analytics. Your first 1,000 pageviews every month are free; the rate falls as you scale. No plan cliffs.",
};

export default function PricingPage() {
  return (
    <>
      <Pricing />
      <Reveal>
        <Faq />
      </Reveal>
      <Reveal>
        <FinalCta />
      </Reveal>
    </>
  );
}
