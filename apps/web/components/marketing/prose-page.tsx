import type { ReactNode } from "react";

// Shared layout for the static trust pages (Privacy, Terms, About) so they read
// as one consistent, premium set (F6). Presentation only — tokens throughout.

export function ProsePage({
  title,
  intro,
  updated,
  children,
}: {
  title: string;
  intro?: string;
  updated?: string;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-10 px-4 py-16 sm:px-6 lg:py-24">
      <header className="flex flex-col gap-3">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{title}</h1>
        {intro ? <p className="text-lg text-muted-foreground">{intro}</p> : null}
        {updated ? <p className="text-sm text-muted-foreground">Last updated {updated}</p> : null}
      </header>
      <div className="flex flex-col gap-8">{children}</div>
    </div>
  );
}

export function ProseSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-lg font-semibold">{title}</h2>
      <div className="flex flex-col gap-2 text-sm leading-relaxed text-muted-foreground">
        {children}
      </div>
    </section>
  );
}
