import Link from "next/link";

import { Button } from "@/components/ui/button";

// Closing CTA banner — tinted card, accent kept sparing.
export function FinalCta() {
  return (
    <section>
      <div className="mx-auto w-full max-w-6xl px-4 pb-20 sm:px-6 lg:pb-28">
        <div className="flex flex-col items-center gap-4 rounded-2xl bg-primary/5 px-6 py-14 text-center ring-1 ring-primary/20">
          <h2 className="text-3xl font-bold tracking-tight text-balance sm:text-4xl">
            Your first 1,000 views are on us.
          </h2>
          <p className="max-w-md text-lg text-muted-foreground text-balance">
            One line of code and you&apos;ll see your visitors live — no card required.
          </p>
          <Button size="lg" className="mt-2" asChild>
            <Link href="/sign-up">Start for free</Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
