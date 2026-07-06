"use client";

import { animate, motion, useInView } from "motion/react";
import { useEffect, useRef, useSyncExternalStore, type ReactNode } from "react";

import { formatNumber } from "@/lib/format";

// F-track motion utilities. Rules (frontendClaude.md): purposeful and subtle,
// nothing over 500ms, transform/opacity only (zero layout shift), scroll
// reveals fire ONCE, and every export degrades to static content under
// prefers-reduced-motion. Wrappers accept only `children` so server-rendered
// sections pass through the client boundary without becoming client code.

const EASE = [0.25, 0.1, 0.25, 1] as const;

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeReducedMotion(onChange: () => void) {
  const mql = window.matchMedia(REDUCED_MOTION_QUERY);
  mql.addEventListener("change", onChange);
  return () => mql.removeEventListener("change", onChange);
}

// motion's useReducedMotion reads matchMedia on the first client render, so
// with the OS preference on it disagrees with the SSR HTML and the
// `reduced ? <div> : <motion.div>` branch hydration-mismatches (and shifts
// every downstream useId). useSyncExternalStore's server snapshot keeps the
// hydration render identical to SSR; the real value applies right after.
function useReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribeReducedMotion,
    () => window.matchMedia(REDUCED_MOTION_QUERY).matches,
    () => false,
  );
}

/** Scroll-reveal once: fade + 16px rise when the element enters the viewport. */
export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();
  if (reduced) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.4, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
}

const staggerParent = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.08 } },
};

const staggerChild = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: EASE } },
};

/** Mount-time stagger container (hero load) — pair with StaggerItem children. */
export function Stagger({ children, className }: { children: ReactNode; className?: string }) {
  const reduced = useReducedMotion();
  if (reduced) return <div className={className}>{children}</div>;
  return (
    <motion.div className={className} initial="hidden" animate="visible" variants={staggerParent}>
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className }: { children: ReactNode; className?: string }) {
  const reduced = useReducedMotion();
  if (reduced) return <div className={className}>{children}</div>;
  return (
    <motion.div className={className} variants={staggerChild}>
      {children}
    </motion.div>
  );
}

/**
 * Count-up number. The FINAL formatted value is in the initial markup (no
 * hydration mismatch, meaningful without JS); on first in-view it animates by
 * writing `textContent` through a ref — never setState (re-render churn and
 * the react-hooks/set-state-in-effect rule both forbid it).
 */
export function CountUp({
  value,
  format = formatNumber,
  duration = 0.5,
}: {
  value: number;
  format?: (n: number) => string;
  duration?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduced = useReducedMotion();
  const inView = useInView(ref, { once: true, amount: 0.5 });
  const played = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || !inView || reduced || played.current) return;
    played.current = true;
    const controls = animate(0, value, {
      duration: Math.min(duration, 0.5),
      ease: "easeOut",
      onUpdate: (v) => {
        el.textContent = format(v);
      },
    });
    return () => controls.stop();
  }, [inView, reduced, value, format, duration]);

  return (
    <span ref={ref} className="tabular-nums">
      {format(value)}
    </span>
  );
}
