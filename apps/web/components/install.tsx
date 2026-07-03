"use client";

import { useState } from "react";

// Per-platform "where to paste" notes. The snippet itself is identical
// everywhere (it's a plain <script> tag); only the placement guidance differs.
const PLATFORMS: { key: string; label: string; note: string }[] = [
  {
    key: "universal",
    label: "Universal",
    note: "Paste the snippet into the <head> of every page you want to track, just before </head>.",
  },
  {
    key: "nextjs",
    label: "Next.js",
    note: "Add it to app/layout.tsx inside <head>, or use next/script with strategy=\"afterInteractive\".",
  },
  {
    key: "wordpress",
    label: "WordPress",
    note: "Appearance → Theme File Editor → header.php, before </head> — or use a “header scripts” plugin.",
  },
  {
    key: "shopify",
    label: "Shopify",
    note: "Online Store → Themes → Edit code → layout/theme.liquid, paste before </head>.",
  },
  {
    key: "webflow",
    label: "Webflow",
    note: "Project Settings → Custom Code → Head Code, paste the snippet and publish.",
  },
  {
    key: "gtm",
    label: "GTM",
    note: "New Tag → Custom HTML, paste the snippet, trigger on All Pages, then publish the container.",
  },
];

export function SnippetBox({ snippet }: { snippet: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard blocked (insecure origin / permissions) — user can select manually
    }
  }

  return (
    <div className="flex items-start gap-2">
      <pre className="flex-1 overflow-x-auto rounded border border-gray-300 bg-gray-50 p-3 text-xs">
        <code>{snippet}</code>
      </pre>
      <button
        type="button"
        onClick={copy}
        className="shrink-0 rounded bg-black px-3 py-2 text-xs text-white"
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

export function InstallGuide({ snippet }: { snippet: string }) {
  const [active, setActive] = useState(PLATFORMS[0].key);
  const platform = PLATFORMS.find((p) => p.key === active) ?? PLATFORMS[0];

  return (
    <div className="flex flex-col gap-3 rounded border border-gray-300 p-4">
      <h2 className="text-sm font-semibold text-gray-600">Install the snippet</h2>
      <SnippetBox snippet={snippet} />
      <div className="flex flex-wrap gap-1">
        {PLATFORMS.map((p) => (
          <button
            key={p.key}
            type="button"
            onClick={() => setActive(p.key)}
            className={`rounded px-2 py-1 text-xs ${
              active === p.key ? "bg-black text-white" : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>
      <p className="text-sm text-gray-600">{platform.note}</p>
    </div>
  );
}

export function StatusPill({ connected }: { connected: boolean }) {
  return connected ? (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-3 py-1 text-sm text-green-700">
      <span className="h-2 w-2 rounded-full bg-green-500" />
      Connected
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1 text-sm text-amber-700">
      <span className="h-2 w-2 animate-pulse rounded-full bg-amber-500" />
      Waiting for first pageview…
    </span>
  );
}
