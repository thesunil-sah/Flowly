import {
  Feather,
  LineChart,
  Network,
  Radio,
  Share2,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

// Feature grid — every card describes something that is SHIPPED today.
const FEATURES: { icon: LucideIcon; title: string; copy: string }[] = [
  {
    icon: Radio,
    title: "Live visitors",
    copy: "See who's on your site right now — a real-time counter, live feed, and current pages, streamed the second a visitor lands.",
  },
  {
    icon: LineChart,
    title: "Historical reports",
    copy: "Visitors, pageviews, sessions, bounce rate, and time on site — with period-over-period deltas so trends jump out.",
  },
  {
    icon: Network,
    title: "Sources & campaigns",
    copy: "Know where traffic comes from: referrers, search, social, and full UTM campaign breakdowns.",
  },
  {
    icon: ShieldCheck,
    title: "Cookieless by design",
    copy: "No cookies, no fingerprinting, no personal data stored. Visitors stay anonymous — by architecture, not by policy.",
  },
  {
    icon: Feather,
    title: "Featherweight script",
    copy: "One ~1 KB script with zero dependencies. Loads async, never blocks rendering, can never break your site.",
  },
  {
    icon: Share2,
    title: "Share & export",
    copy: "Give anyone a read-only public dashboard with one revocable link, or export aggregated reports as CSV.",
  },
];

export function Features() {
  return (
    <section id="features" className="scroll-mt-20">
      <div className="mx-auto w-full max-w-6xl px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto mb-12 max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Everything you need. Nothing creepy.
          </h2>
          <p className="mt-3 text-lg text-muted-foreground">
            The reports that actually matter, live from the moment you install.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="rounded-lg border border-border bg-card p-6 shadow-card transition-[transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-md motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <div className="mb-4 flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <f.icon className="size-5" aria-hidden />
              </div>
              <h3 className="mb-1.5 font-semibold">{f.title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{f.copy}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
