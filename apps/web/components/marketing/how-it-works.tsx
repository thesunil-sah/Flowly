// Three steps to first data. The snippet shown is illustrative — real install
// snippets are built server-side per site (services/sites.py::build_snippet).
const STEPS = [
  {
    title: "Add your site",
    copy: "Create an account and enter your domain. You'll get a unique snippet for your site.",
  },
  {
    title: "Paste one line",
    copy: "Drop the script tag into your site's <head> — works with any stack, from plain HTML to Next.js, WordPress, or Shopify.",
  },
  {
    title: "Watch visitors live",
    copy: "Your dashboard lights up with the first pageview — live visitors now, full reports from day one.",
  },
] as const;

export function HowItWorks() {
  return (
    <section className="bg-muted/40">
      <div className="mx-auto w-full max-w-6xl px-4 py-20 sm:px-6 lg:py-28">
        <div className="mx-auto mb-12 max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">Live in two minutes</h2>
          <p className="mt-3 text-lg text-muted-foreground">
            No SDK, no build step, no configuration.
          </p>
        </div>

        <div className="grid gap-8 lg:grid-cols-3">
          {STEPS.map((s, i) => (
            <div key={s.title} className="flex flex-col gap-3">
              <div className="flex size-8 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                {i + 1}
              </div>
              <h3 className="font-semibold">{s.title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{s.copy}</p>
              {i === 1 && (
                <pre className="mt-1 overflow-x-auto rounded-lg border border-border bg-card p-3 font-mono text-xs text-muted-foreground shadow-card">
                  {'<script defer src="https://cdn.flowly.app/script.js"\n        data-site="your-site-id"></script>'}
                </pre>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
