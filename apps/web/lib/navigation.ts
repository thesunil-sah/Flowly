import {
  AppWindow,
  ArrowDownRight,
  ArrowUpRight,
  CreditCard,
  Cpu,
  FileText,
  Globe,
  LayoutDashboard,
  LayoutGrid,
  Languages,
  Link2,
  MapPin,
  Megaphone,
  Monitor,
  Network,
  Radio,
  Search,
  Settings,
  Share2,
  Smartphone,
  Sparkles,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  title: string;
  href: string;
  icon: LucideIcon;
  /** Flips true when the report page ships (Phases 10–11 / F4). */
  ready: boolean;
};

export type NavGroup = { title: string | null; items: NavItem[] };

// The full sidebar IA from the F-track spec, encoded now so later phases only
// flip `ready` flags. Render rule: filter ready items, skip empty groups.
export const NAV_GROUPS: NavGroup[] = [
  {
    title: null,
    items: [
      { title: "Realtime", href: "/live", icon: Radio, ready: true },
      { title: "Overview", href: "/dashboard", icon: LayoutDashboard, ready: true },
    ],
  },
  {
    title: "Behavior",
    items: [
      { title: "Pages", href: "/behavior/pages", icon: FileText, ready: true },
      { title: "Entry pages", href: "/behavior/entry", icon: ArrowDownRight, ready: true },
      { title: "Exit pages", href: "/behavior/exit", icon: ArrowUpRight, ready: true },
    ],
  },
  {
    title: "Acquisitions",
    items: [
      { title: "Channels", href: "/acquisitions/channels", icon: Network, ready: true },
      { title: "Referrers", href: "/acquisitions/referrers", icon: Link2, ready: true },
      { title: "Search", href: "/acquisitions/search", icon: Search, ready: true },
      { title: "Social", href: "/acquisitions/social", icon: Share2, ready: true },
      { title: "AI platforms", href: "/acquisitions/ai", icon: Sparkles, ready: true },
      { title: "Campaigns", href: "/acquisitions/campaigns", icon: Megaphone, ready: true },
    ],
  },
  {
    title: "Search Console",
    items: [
      { title: "Keywords", href: "/search-console/keywords", icon: Search, ready: true },
      { title: "Search pages", href: "/search-console/pages", icon: FileText, ready: true },
      { title: "Opportunities", href: "/search-console/opportunities", icon: TrendingUp, ready: true },
    ],
  },
  {
    title: "Geographic",
    items: [
      { title: "Countries", href: "/geo/countries", icon: Globe, ready: true },
      { title: "Cities", href: "/geo/cities", icon: MapPin, ready: true },
      { title: "Languages", href: "/geo/languages", icon: Languages, ready: true },
    ],
  },
  {
    title: "Technology",
    items: [
      { title: "Browsers", href: "/tech/browsers", icon: AppWindow, ready: true },
      { title: "OS", href: "/tech/os", icon: Cpu, ready: true },
      { title: "Screens", href: "/tech/screens", icon: Monitor, ready: true },
      { title: "Devices", href: "/tech/devices", icon: Smartphone, ready: true },
    ],
  },
  {
    title: "Workspace",
    items: [
      { title: "Sites", href: "/sites", icon: LayoutGrid, ready: true },
      { title: "Billing", href: "/billing", icon: CreditCard, ready: true },
      { title: "Settings", href: "/settings", icon: Settings, ready: true },
    ],
  },
];

/** Only the groups/items that have shipped — what the sidebar renders today. */
export function readyNavGroups(): NavGroup[] {
  return NAV_GROUPS.map((g) => ({ ...g, items: g.items.filter((i) => i.ready) })).filter(
    (g) => g.items.length > 0,
  );
}
