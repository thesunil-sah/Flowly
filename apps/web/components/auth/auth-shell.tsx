import {
  Box,
  Lock,
  ShieldCheck,
  Sparkles,
  User,
  UserPlus,
  Users,
  Zap,
  type LucideIcon,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

import { Reveal, Stagger, StaggerItem } from "@/components/motion";
import { cn } from "@/lib/utils";

// F2 auth shell — pixel-faithful rebuild of desgin/demo-registersystem.png:
// dark-violet cosmic scene (fixed in BOTH themes — reference-exact), left
// brand panel with gradient-word headline + feature tiles, right glass card
// with gradient segmented tabs. Every scene color lives in globals.css under
// .auth-scene (scoped token remap + .auth-* classes) — no raw hex here.
// The 3D art (cube-on-pedestal, gems) is the reference's own artwork cropped
// into public/auth/*.png — screen-blended + edge-masked in globals.css so the
// crops' dark backgrounds melt into the scene; planet/stars/orbit/sphere stay
// pure CSS. Gentle float/pulse/twinkle loops are all gated behind
// prefers-reduced-motion in globals.css.

const FEATURES: { icon: LucideIcon; title: string; body: string }[] = [
  { icon: Zap, title: "Blazing Fast", body: "Real-time reports built for speed" },
  { icon: ShieldCheck, title: "Private by Design", body: "Cookieless analytics you can trust" },
  { icon: Users, title: "Live Visitors", body: "Watch activity as it happens" },
];

const TRUST_ITEMS: { icon: LucideIcon; label: string }[] = [
  { icon: ShieldCheck, label: "Secure by design" },
  { icon: Lock, label: "Privacy focused" },
  { icon: Users, label: "Trusted by makers" },
];

function Wordmark({ className }: { className?: string }) {
  return (
    <Link href="/" className={cn("inline-flex items-center gap-2.5", className)}>
      <span className="auth-logo-mark flex size-8 items-center justify-center rounded-lg text-primary-foreground">
        <Box className="size-4.5" aria-hidden />
      </span>
      <span className="text-lg font-bold tracking-[0.25em] uppercase">Flowly</span>
    </Link>
  );
}

/** The reference's 3D art (cropped PNGs) + CSS ambience, all pointer-transparent. */
function SceneDecorations() {
  return (
    <div aria-hidden className="absolute inset-0 z-0">
      <div className="auth-stars" />
      <div className="auth-planet hidden md:block" />
      {/* floating gem between the panels */}
      <Image
        src="/auth/gem.png"
        alt=""
        width={170}
        height={170}
        className="auth-art auth-art--orb auth-float top-[10%] left-[41%] hidden w-32 lg:block"
      />
      {/* large gem cropped by the bottom-left corner */}
      <Image
        src="/auth/corner.png"
        alt=""
        width={196}
        height={180}
        className="auth-art auth-art--corner auth-float auth-float--rev bottom-0 left-0 hidden w-44 md:block"
      />
      {/* small sphere, left edge */}
      <div className="auth-sphere auth-float auth-float--slow top-[42%] left-[2.5%] size-11" />
      {/* glowing cube on its pedestal, with an orbit ring + pulsing glow */}
      <div className="hidden xl:block">
        <div className="auth-orbit bottom-[10%] left-[13%] h-56 w-120" />
        <div className="auth-glow bottom-[6%] left-[19%] h-72 w-96" />
        <Image
          src="/auth/cube.png"
          alt=""
          width={380}
          height={410}
          className="auth-art auth-art--soft auth-float auth-float--slow bottom-[2%] left-[21%] w-84"
        />
      </div>
    </div>
  );
}

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main className="auth-scene min-h-svh">
      <SceneDecorations />

      <div className="relative z-10 mx-auto grid min-h-svh w-full max-w-[90rem] lg:grid-cols-[1.1fr_1fr]">
        {/* Brand panel — hidden below lg, like the reference's left half. */}
        <aside className="hidden flex-col p-10 lg:flex xl:p-14">
          <Stagger className="flex h-full flex-col">
            <StaggerItem>
              <Wordmark />
            </StaggerItem>

            <div className="flex flex-1 flex-col justify-center">
              <div className="max-w-lg space-y-7">
                <StaggerItem>
                  <span className="auth-badge inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-semibold tracking-[0.18em] uppercase">
                    <Sparkles className="size-3.5" aria-hidden />
                    Welcome to Flowly
                  </span>
                </StaggerItem>
                <StaggerItem>
                  <h1 className="text-5xl leading-[1.08] font-bold tracking-tight xl:text-6xl">
                    Know your traffic
                    <br />
                    with <span className="auth-gradient-text">confidence</span>
                  </h1>
                </StaggerItem>
                <StaggerItem>
                  <p className="max-w-md text-lg text-muted-foreground">
                    Flowly is your privacy-first platform to see, understand, and grow your web
                    traffic — live, without cookies.
                  </p>
                </StaggerItem>
                <StaggerItem>
                  <ul className="space-y-5 pt-2">
                    {FEATURES.map(({ icon: Icon, title, body }) => (
                      <li key={title} className="flex items-center gap-4">
                        <span className="auth-tile flex size-12 shrink-0 items-center justify-center rounded-xl">
                          <Icon className="size-5" aria-hidden />
                        </span>
                        <span>
                          <span className="block font-semibold">{title}</span>
                          <span className="block text-sm text-muted-foreground">{body}</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                </StaggerItem>
              </div>
            </div>
          </Stagger>
        </aside>

        {/* Form column */}
        <section className="flex flex-col p-5 sm:p-8 lg:py-10">
          <div className="lg:hidden">
            <Wordmark />
          </div>

          <div className="flex flex-1 items-center justify-center py-8">
            <Reveal className="w-full max-w-[30rem]">{children}</Reveal>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-x-7 gap-y-2 text-xs text-muted-foreground lg:justify-end">
            {TRUST_ITEMS.map(({ icon: Icon, label }) => (
              <span key={label} className="inline-flex items-center gap-1.5">
                <Icon className="size-3.5" aria-hidden />
                {label}
              </span>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}

/** Segmented Sign In / Sign Up switch — route links styled as the reference's
 * pill toggle (active = purple gradient). */
export function AuthTabs({ active }: { active: "sign-in" | "sign-up" }) {
  const base =
    "flex h-12 items-center justify-center gap-2 rounded-xl text-sm font-semibold transition-colors";
  return (
    <div className="auth-tabs grid grid-cols-2 gap-1 p-1">
      <Link
        href="/sign-in"
        aria-current={active === "sign-in" ? "page" : undefined}
        className={cn(
          base,
          active === "sign-in" ? "auth-tab-active" : "text-muted-foreground hover:text-foreground",
        )}
      >
        <User className="size-4" aria-hidden />
        Sign In
      </Link>
      <Link
        href="/sign-up"
        aria-current={active === "sign-up" ? "page" : undefined}
        className={cn(
          base,
          active === "sign-up" ? "auth-tab-active" : "text-muted-foreground hover:text-foreground",
        )}
      >
        <UserPlus className="size-4" aria-hidden />
        Sign Up
      </Link>
    </div>
  );
}

export function AuthCard({
  tab,
  title,
  subtitle,
  children,
  footer,
}: {
  tab?: "sign-in" | "sign-up";
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="auth-card space-y-6 p-6 sm:p-9">
      {tab ? <AuthTabs active={tab} /> : null}
      <div className="space-y-1.5">
        <h2 className="text-[1.75rem] font-bold tracking-tight">{title}</h2>
        {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
      </div>
      {children}
      {footer ? <p className="text-center text-sm text-muted-foreground">{footer}</p> : null}
    </div>
  );
}
