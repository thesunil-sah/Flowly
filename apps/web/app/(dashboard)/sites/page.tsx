"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { ErrorText, Field, Submit } from "@/components/form";
import { InstallGuide, StatusPill } from "@/components/install";
import { TableSkeleton } from "@/components/skeletons";
import { Button } from "@/components/ui/button";
import { useCreateSite, useSites, useSiteStatus } from "@/hooks/useSites";
import type { Site } from "@/lib/api";

function InstallStep({ site, onBack }: { site: Site; onBack: () => void }) {
  // Freeze the poll start so the ~3-min auto-poll cap is measured from arrival.
  const [startedAt] = useState(() => Date.now());
  const status = useSiteStatus(site.site_id, startedAt);
  const connected = status.data?.connected ?? false;

  return (
    <div className="flex flex-col gap-4">
      <Button variant="link" className="self-start px-0" onClick={onBack}>
        ← All sites
      </Button>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{site.domain}</h1>
          <p className="text-sm text-muted-foreground">Install the snippet to start tracking.</p>
        </div>
        <StatusPill connected={connected} />
      </div>

      <InstallGuide snippet={site.snippet} />

      {connected ? (
        <div className="flex items-center gap-3 text-sm">
          <span className="text-muted-foreground">🎉 We received your first pageview.</span>
          <Link href="/dashboard" className="underline">
            Go to dashboard →
          </Link>
        </div>
      ) : (
        <Button
          variant="link"
          className="self-start px-0"
          onClick={() => status.refetch()}
          disabled={status.isFetching}
        >
          {status.isFetching ? "Checking…" : "Still waiting? Check again"}
        </Button>
      )}
    </div>
  );
}

function SiteList({ sites, onOpen }: { sites: Site[]; onOpen: (site: Site) => void }) {
  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold text-muted-foreground">Your sites</h2>
      {sites.map((s) => (
        <div
          key={s.id}
          className="flex items-center justify-between rounded-lg border border-border bg-card p-4 shadow-card"
        >
          <span className="font-medium">{s.domain}</span>
          <Button variant="ghost" size="sm" onClick={() => onOpen(s)}>
            Open
          </Button>
        </div>
      ))}
    </div>
  );
}

function AddStep({ onCreated }: { onCreated: (site: Site) => void }) {
  const create = useCreateSite();
  const [domain, setDomain] = useState("");

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    create.mutate({ domain }, { onSuccess: onCreated });
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold">Add a site</h1>
        <p className="text-sm text-muted-foreground">
          Enter the domain you want to track. It&apos;s just a label — you&apos;ll get a snippet to
          install next.
        </p>
      </div>
      <form onSubmit={onSubmit} className="flex max-w-sm flex-col gap-4">
        <Field
          label="Domain"
          placeholder="example.com"
          required
          maxLength={255}
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          autoComplete="off"
        />
        {create.isError ? <ErrorText>{create.error.message}</ErrorText> : null}
        <Submit pending={create.isPending}>Add site</Submit>
      </form>
    </div>
  );
}

export default function SitesPage() {
  const { data: sites, isLoading } = useSites();
  // The site whose install/status screen is open; null shows the list + add form.
  const [viewing, setViewing] = useState<Site | null>(null);

  if (isLoading) {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <TableSkeleton rows={4} />
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
      {viewing ? (
        <InstallStep site={viewing} onBack={() => setViewing(null)} />
      ) : (
        <>
          {sites && sites.length > 0 ? <SiteList sites={sites} onOpen={setViewing} /> : null}
          <AddStep onCreated={setViewing} />
        </>
      )}
    </div>
  );
}
