"use client";

import { Check } from "lucide-react";

import { PricingSlider } from "@/components/marketing/pricing-slider";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useCheckout } from "@/hooks/useBilling";
import { FREE_MONTHLY_VIEWS } from "@/lib/pricing";
import { formatNumber } from "@/lib/format";

// The metered-upgrade surface. Driven by usage_summary flags: rendered as a
// NON-dismissible dashboard gate when status==="locked" (the server also 402s
// stats/live). The CTA opens Checkout for the single metered Price + 7-day trial.
const PERKS = [
  "Keep every report + live traffic",
  "The rate falls as you scale — no plan cliffs",
  "7-day free trial, cancel anytime",
] as const;

export function PaywallModal({
  open,
  onOpenChange,
  dismissible = true,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Phase 14 sets this false for the hard lock (can't click away from the wall). */
  dismissible?: boolean;
}) {
  const checkout = useCheckout();

  return (
    <Dialog open={open} onOpenChange={dismissible ? onOpenChange : undefined}>
      <DialogContent
        showCloseButton={dismissible}
        className="sm:max-w-md"
        onEscapeKeyDown={dismissible ? undefined : (e) => e.preventDefault()}
        onInteractOutside={dismissible ? undefined : (e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>Upgrade to keep your dashboard</DialogTitle>
          <DialogDescription>
            You&apos;ve passed the {formatNumber(FREE_MONTHLY_VIEWS)} free monthly pageviews.
            Ingestion never stops — but reports pause until you upgrade to metered pricing.
          </DialogDescription>
        </DialogHeader>

        <ul className="flex flex-col gap-2">
          {PERKS.map((p) => (
            <li key={p} className="flex items-start gap-2 text-sm">
              <Check className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
              {p}
            </li>
          ))}
        </ul>

        <div className="rounded-lg border border-border bg-muted/40 p-3">
          <PricingSlider />
        </div>

        <Button
          className="w-full"
          disabled={checkout.isPending}
          onClick={() => checkout.mutate()}
        >
          {checkout.isPending ? "Opening checkout…" : "Start your 7-day free trial"}
        </Button>
        {checkout.isError ? (
          <p className="text-sm text-destructive">{checkout.error.message}</p>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
