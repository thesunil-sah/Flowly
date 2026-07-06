import type { Metadata } from "next";

import { ClaimsStrip } from "@/components/marketing/claims-strip";
import { Faq } from "@/components/marketing/faq";
import { Features } from "@/components/marketing/features";
import { FinalCta } from "@/components/marketing/final-cta";
import { Hero } from "@/components/marketing/hero";
import { HowItWorks } from "@/components/marketing/how-it-works";
import { Pricing } from "@/components/marketing/pricing";
import { PrivacyUsp } from "@/components/marketing/privacy-usp";
import { Reveal } from "@/components/motion";

export const metadata: Metadata = {
  title: "Flowly — privacy-first, cookieless web analytics",
  description:
    "Live visitors and clean reports from one ~1 KB script. No cookies, no consent banner, no creepy tracking. Your first 1,000 views every month are free.",
};

// The landing page: a Server Component composing server-rendered sections;
// motion wrappers (Reveal/Stagger) are thin client shells that pass server
// children through. Section order per the F1 spec.
export default function LandingPage() {
  return (
    <>
      <Hero />
      <ClaimsStrip />
      <Reveal>
        <Features />
      </Reveal>
      <Reveal>
        <HowItWorks />
      </Reveal>
      <Reveal>
        <PrivacyUsp />
      </Reveal>
      <Reveal>
        <Pricing />
      </Reveal>
      <Reveal>
        <Faq />
      </Reveal>
      <Reveal>
        <FinalCta />
      </Reveal>
    </>
  );
}
