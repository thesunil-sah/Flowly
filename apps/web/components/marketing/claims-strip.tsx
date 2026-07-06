import { CookieIcon, Feather, Lock, ShieldCheck } from "lucide-react";

// Honest social-proof substitute (no customers yet, no fake logos): the
// product claims that matter, in one muted strip.
const CLAIMS = [
  { icon: CookieIcon, text: "No cookies" },
  { icon: Feather, text: "~1 KB script" },
  { icon: ShieldCheck, text: "No consent banner needed" },
  { icon: Lock, text: "GDPR-friendly" },
] as const;

export function ClaimsStrip() {
  return (
    <section className="border-y border-border/60 bg-muted/40">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center justify-center gap-x-10 gap-y-3 px-4 py-6 sm:px-6">
        {CLAIMS.map((c) => (
          <span key={c.text} className="flex items-center gap-2 text-sm text-muted-foreground">
            <c.icon className="size-4" aria-hidden />
            {c.text}
          </span>
        ))}
      </div>
    </section>
  );
}
