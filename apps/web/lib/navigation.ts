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
  Share2,
  Smartphone,
  Sparkles,
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
      { title: "Pages", href: "/behavior/pages", icon: FileText, ready: false },
      { title: "Entry pages", href: "/behavior/entry", icon: ArrowDownRight, ready: false },
      { title: "Exit pages", href: "/behavior/exit", icon: ArrowUpRight, ready: false },
    ],
  },
  {
    title: "Acquisitions",
    items: [
      { title: "Channels", href: "/acquisitions/channels", icon: Network, ready: false },
      { title: "Referrers", href: "/acquisitions/referrers", icon: Link2, ready: false },
      { title: "Search", href: "/acquisitions/search", icon: Search, ready: false },
      { title: "Social", href: "/acquisitions/social", icon: Share2, ready: false },
      { title: "AI platforms", href: "/acquisitions/ai", icon: Sparkles, ready: false },
      { title: "Campaigns", href: "/acquisitions/campaigns", icon: Megaphone, ready: false },
    ],
  },
  {
    title: "Geographic",
    items: [
      { title: "Countries", href: "/geo/countries", icon: Globe, ready: false },
      { title: "Cities", href: "/geo/cities", icon: MapPin, ready: false },
      { title: "Languages", href: "/geo/languages", icon: Languages, ready: false },
    ],
  },
  {
    title: "Technology",
    items: [
      { title: "Browsers", href: "/tech/browsers", icon: AppWindow, ready: false },
      { title: "OS", href: "/tech/os", icon: Cpu, ready: false },
      { title: "Screens", href: "/tech/screens", icon: Monitor, ready: false },
      { title: "Devices", href: "/tech/devices", icon: Smartphone, ready: false },
    ],
  },
  {
    title: "Workspace",
    items: [
      { title: "Sites", href: "/sites", icon: LayoutGrid, ready: true },
      { title: "Billing", href: "/billing", icon: CreditCard, ready: true },
    ],
  },
];

/** Only the groups/items that have shipped — what the sidebar renders today. */
export function readyNavGroups(): NavGroup[] {
  return NAV_GROUPS.map((g) => ({ ...g, items: g.items.filter((i) => i.ready) })).filter(
    (g) => g.items.length > 0,
  );
}
