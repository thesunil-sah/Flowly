"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { ErrorText, Field, Submit } from "@/components/form";
import { InstallGuide, StatusPill } from "@/components/install";
import { useCreateSite, useSites, useSiteStatus } from "@/hooks/useSites";
import type { Site } from "@/lib/api";

function InstallStep({ site, onBack }: { site: Site; onBack: () => void }) {
  // Freeze the poll start so the ~3-min auto-poll cap is measured from arrival.
  const [startedAt] = useState(() => Date.now());
  const status = useSiteStatus(site.site_id, startedAt);
  const connected = status.data?.connected ?? false;

  return (
    <div className="flex flex-col gap-4">
      <button type="button" onClick={onBack} className="self-start text-sm text-gray-600 underline">
        ← All sites
      </button>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{site.domain}</h1>
          <p className="text-sm text-gray-600">Install the snippet to start tracking.</p>
        </div>
        <StatusPill connected={connected} />
      </div>

      <InstallGuide snippet={site.snippet} />

      {connected ? (
        <div className="flex items-center gap-3 text-sm">
          <span className="text-gray-600">🎉 We received your first pageview.</span>
          <Link href="/dashboard" className="underline">
            Go to dashboard →
          </Link>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => status.refetch()}
          disabled={status.isFetching}
          className="self-start text-sm text-gray-600 underline disabled:opacity-50"
        >
          {status.isFetching ? "Checking…" : "Still waiting? Check again"}
        </button>
      )}
    </div>
  );
}

function SiteList({ sites, onOpen }: { sites: Site[]; onOpen: (site: Site) => void }) {
  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold text-gray-600">Your sites</h2>
      {sites.map((s) => (
        <div
          key={s.id}
          className="flex items-center justify-between rounded border border-gray-300 p-4"
        >
          <span className="font-medium">{s.domain}</span>
          <button
            type="button"
            onClick={() => onOpen(s)}
            className="text-sm text-gray-600 underline"
          >
            Open
          </button>
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
        <p className="text-sm text-gray-600">
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
    return <main className="flex flex-1 items-center justify-center p-6">Loading…</main>;
  }

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 p-6">
      {viewing ? (
        <InstallStep site={viewing} onBack={() => setViewing(null)} />
      ) : (
        <>
          {sites && sites.length > 0 ? <SiteList sites={sites} onOpen={setViewing} /> : null}
          <AddStep onCreated={setViewing} />
        </>
      )}
    </main>
  );
}
