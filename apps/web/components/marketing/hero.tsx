import Link from "next/link";

import { Stagger, StaggerItem } from "@/components/motion";
import { DemoEmbed } from "@/components/public-dashboard/demo-embed";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

// Hero (demo-video pattern): badge pill → headline with ONE indigo word →
// subcopy → dual CTA → the framed live demo dashboard.
export function Hero() {
  return (
    <section className="mx-auto w-full max-w-6xl px-4 pt-16 pb-20 sm:px-6 lg:pt-24">
      <Stagger className="flex flex-col items-center gap-6 text-center">
        <StaggerItem>
          <Badge variant="outline" className="gap-1.5 rounded-full px-3 py-1 text-sm font-normal text-muted-foreground">
            Cookieless · no consent banner
          </Badge>
        </StaggerItem>

        <StaggerItem>
          <h1 className="max-w-3xl text-4xl font-bold tracking-tight text-balance sm:text-5xl lg:text-6xl">
            Know your traffic. <span className="text-primary">Instantly.</span>
          </h1>
        </StaggerItem>

        <StaggerItem>
          <p className="max-w-xl text-lg text-muted-foreground text-balance">
            Live visitors and clean reports from one tiny script — no cookies, no consent banner,
            no creepy tracking.
          </p>
        </StaggerItem>

        <StaggerItem>
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Button size="lg" asChild>
              <Link href="/sign-up">Start for free</Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link href="#demo">See the live demo</Link>
            </Button>
          </div>
        </StaggerItem>

        <StaggerItem className="mt-6 w-full max-w-4xl text-left">
          <div id="demo" className="scroll-mt-24">
            <DemoEmbed />
          </div>
        </StaggerItem>
      </Stagger>
    </section>
  );
}
