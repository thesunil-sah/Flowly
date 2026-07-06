// FAQ content — SINGLE SOURCE. The landing page's FAQ accordion renders this,
// and Phase F7's support chatbot matches intents against these same canonical
// answers. Keep answers as plain strings (no JSX) so both consumers can use
// them verbatim.

export type FaqEntry = { question: string; answer: string };

export const FAQ: FaqEntry[] = [
  {
    question: "What is Flowly?",
    answer:
      "Flowly is privacy-first, cookieless web analytics. You add one tiny script to your site and get live visitor counts plus historical reports — visitors, sources, pages, geography, and devices — without cookies or personal data.",
  },
  {
    question: "Why don't I need a cookie consent banner?",
    answer:
      "Flowly sets no cookies and stores nothing on your visitors' devices. Unique visitors are counted with an anonymous hash that rotates every 24 hours, so nobody can be tracked across days or across sites. Because no personal data is stored, GDPR and ePrivacy don't require a consent banner for Flowly analytics.",
  },
  {
    question: "How does pricing work?",
    answer:
      "Your first 1,000 pageviews every month are free. Beyond that you pay only for what you use, with rates that drop as you grow: $0.99 per 1,000 views up to 10k, $0.10 per 1,000 up to 100k, $0.05 per 1,000 up to 1M, and $0.03 per 1,000 after that. For example, 100,000 views costs $17.91 a month. Upgrading starts with a 7-day free trial, and views from all your sites (up to 5) count together.",
  },
  {
    question: "Will the script slow down my site?",
    answer:
      "No. The tracking script is plain JavaScript with zero dependencies, about 1 KB minified. It loads asynchronously, never blocks rendering, and is built to fail silently — it can never break your site.",
  },
  {
    question: "What data does Flowly collect?",
    answer:
      "For each pageview: the page path, referrer, UTM tags, and coarse device, browser, OS, and country. Raw IP addresses are never stored, and there are no persistent identifiers of any kind.",
  },
  {
    question: "Can I share my stats or export them?",
    answer:
      "Yes. Every site can have a public, revocable share link — a read-only dashboard you can send to anyone — and you can export aggregated reports as CSV at any time.",
  },
  {
    question: "How many sites can I track?",
    answer:
      "Up to 5 sites per account, and their pageviews are summed together for billing — so small side projects effectively ride along with your main site.",
  },
];
