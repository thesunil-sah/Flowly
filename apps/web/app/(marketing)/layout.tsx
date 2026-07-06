import type { ReactNode } from "react";

import { ChatWidget } from "@/components/ChatWidget";
import { MarketingFooter } from "@/components/marketing/footer";
import { MarketingNav } from "@/components/marketing/nav";

// Marketing chrome (nav + footer) for the public pages. No auth guard, no
// SiteProvider — those are dashboard concerns. The support chatbot floats over
// every marketing page (F7).
export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <MarketingNav />
      <main className="flex-1">{children}</main>
      <MarketingFooter />
      <ChatWidget />
    </>
  );
}
