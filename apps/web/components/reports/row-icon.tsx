"use client";

import {
  AppWindow,
  Compass,
  Cpu,
  Globe,
  Megaphone,
  Monitor,
  MousePointerClick,
  Smartphone,
  Tablet,
  type LucideIcon,
} from "lucide-react";
import { useState, type ReactNode } from "react";

// Every icon a report row can carry, in one place. All fallbacks are the
// muted Globe so a miss never looks broken.

function GenericIcon({ icon: Icon }: { icon: LucideIcon }) {
  return <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />;
}

/**
 * Referrer favicon via DuckDuckGo's public icon service. Privacy optics: this
 * makes the viewer's browser call a third party — DDG is the least-bad host;
 * consider proxying through our own API post-F1. Fixed 16px box + error
 * fallback so a 404 never shifts the row.
 */
export function Favicon({ domain }: { domain: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <GenericIcon icon={Globe} />;
  return (
    // eslint-disable-next-line @next/next/no-img-element -- 16px third-party favicon; next/image gains nothing and needs remotePatterns
    <img
      src={`https://icons.duckduckgo.com/ip3/${encodeURIComponent(domain)}.ico`}
      alt=""
      width={16}
      height={16}
      loading="lazy"
      className="size-4 shrink-0 rounded-sm"
      onError={() => setFailed(true)}
    />
  );
}

/**
 * Source labels are a mix (services/ingest.py::derive_source): a referrer
 * host, a utm_source string, or the literal "direct" — only domain-looking
 * labels get a favicon.
 */
export function SourceIcon({ label }: { label: string }) {
  if (label === "direct" || label === "") return <GenericIcon icon={MousePointerClick} />;
  if (label.includes(".")) return <Favicon domain={label} />;
  return <GenericIcon icon={Megaphone} />;
}

/** ISO-2 country code → emoji flag (regional indicators). "" → Globe. */
export function CountryIcon({ code }: { code: string }) {
  const iso = code.trim().toUpperCase();
  if (!/^[A-Z]{2}$/.test(iso)) return <GenericIcon icon={Globe} />;
  const flag = String.fromCodePoint(
    ...[...iso].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65),
  );
  return (
    <span className="w-4 shrink-0 text-center text-sm leading-none" aria-hidden>
      {flag}
    </span>
  );
}

const DEVICE_ICONS: Record<string, LucideIcon> = {
  desktop: Monitor,
  mobile: Smartphone,
  tablet: Tablet,
};

// lucide has no browser/OS brand marks — generic shapes, Globe fallback.
const BROWSER_ICONS: Record<string, LucideIcon> = {
  chrome: Globe,
  firefox: Compass,
  safari: Compass,
  edge: AppWindow,
  opera: Globe,
};

export function DeviceIcon({ label }: { label: string }) {
  return <GenericIcon icon={DEVICE_ICONS[label.toLowerCase()] ?? Monitor} />;
}

export function BrowserIcon({ label }: { label: string }) {
  return <GenericIcon icon={BROWSER_ICONS[label.toLowerCase()] ?? Globe} />;
}

export function OsIcon(): ReactNode {
  return <GenericIcon icon={Cpu} />;
}
