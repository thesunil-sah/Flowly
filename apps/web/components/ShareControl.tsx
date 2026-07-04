"use client";

import { useState } from "react";

import { useCreateShare, useRevokeShare, useShareLink } from "@/hooks/useSites";

// Manage a site's public share link: create/rotate, copy, and revoke. The link
// is an unguessable token URL (a secret) — anyone with it can view this site's
// dashboard read-only, so revoke kills it immediately (Phase 8).

export function ShareControl({ siteId }: { siteId: string }) {
  const { data, isLoading } = useShareLink(siteId);
  const create = useCreateShare(siteId);
  const revoke = useRevokeShare(siteId);
  const [copied, setCopied] = useState(false);

  const url = data?.url ?? null;

  async function copy() {
    if (!url) return;
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="rounded border border-gray-300 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-600">Public share link</h2>
        {url ? (
          <button
            onClick={() => revoke.mutate()}
            disabled={revoke.isPending}
            className="text-xs text-red-600 underline disabled:opacity-50"
          >
            Revoke
          </button>
        ) : null}
      </div>

      {isLoading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : url ? (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <input
              readOnly
              value={url}
              className="flex-1 rounded border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-700"
            />
            <button
              onClick={copy}
              className="rounded bg-black px-3 py-1 text-xs text-white"
            >
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <button
            onClick={() => create.mutate()}
            disabled={create.isPending}
            className="self-start text-xs text-gray-600 underline disabled:opacity-50"
          >
            Rotate link
          </button>
          <p className="text-xs text-gray-400">
            Anyone with this link can view this site&apos;s dashboard, read-only. Rotate or revoke
            to disable it.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-gray-500">No public link yet.</p>
          <button
            onClick={() => create.mutate()}
            disabled={create.isPending}
            className="self-start rounded bg-black px-3 py-1.5 text-sm text-white disabled:opacity-50"
          >
            {create.isPending ? "Creating…" : "Create share link"}
          </button>
        </div>
      )}
    </div>
  );
}
