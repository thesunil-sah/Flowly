"use client";

import { useState } from "react";

import { SegmentedTabs } from "@/components/segmented-tabs";
import { Button } from "@/components/ui/button";

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
      <pre className="flex-1 overflow-x-auto rounded-md border border-border bg-muted p-3 text-xs">
        <code>{snippet}</code>
      </pre>
      <Button size="sm" className="shrink-0" onClick={copy}>
        {copied ? "Copied" : "Copy"}
      </Button>
    </div>
  );
}

export function InstallGuide({ snippet }: { snippet: string }) {
  const [active, setActive] = useState(PLATFORMS[0].key);
  const platform = PLATFORMS.find((p) => p.key === active) ?? PLATFORMS[0];

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4 shadow-card">
      <h2 className="text-sm font-semibold text-muted-foreground">Install the snippet</h2>
      <SnippetBox snippet={snippet} />
      <SegmentedTabs
        tabs={PLATFORMS.map((p) => ({ key: p.key, label: p.label }))}
        active={active}
        onChange={setActive}
      />
      <p className="text-sm text-muted-foreground">{platform.note}</p>
    </div>
  );
}

export function StatusPill({ connected }: { connected: boolean }) {
  // Green/amber are the legit up/waiting semantics here (§ token rules).
  return connected ? (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-success/30 bg-success/10 px-3 py-1 text-sm">
      <span className="h-2 w-2 rounded-full bg-success" />
      Connected
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-warning/30 bg-warning/10 px-3 py-1 text-sm">
      <span className="h-2 w-2 animate-pulse rounded-full bg-warning" />
      Waiting for first pageview…
    </span>
  );
}
