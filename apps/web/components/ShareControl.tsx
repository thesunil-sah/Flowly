"use client";

import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useCreateShare, useRevokeShare, useShareLink } from "@/hooks/useSites";

// Manage a site's public share link: create/rotate, copy, and revoke. The link
// is an unguessable token URL (a secret) — anyone with it can view this site's
// dashboard read-only, so revoke kills it immediately (Phase 8).

export function ShareControl({ siteId }: { siteId: string }) {
  const { data, isLoading } = useShareLink(siteId);
  const create = useCreateShare(siteId);
  const revoke = useRevokeShare(siteId);

  const url = data?.url ?? null;

  async function copy() {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      toast.success("Share link copied");
    } catch {
      // clipboard blocked (insecure origin / permissions) — user can select manually
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-card">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-muted-foreground">Public share link</h2>
        {url ? (
          <Button
            variant="destructive"
            size="xs"
            onClick={() => revoke.mutate()}
            disabled={revoke.isPending}
          >
            Revoke
          </Button>
        ) : null}
      </div>

      {isLoading ? (
        <Skeleton className="h-8 w-full" />
      ) : url ? (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <Input readOnly value={url} className="flex-1 text-xs" />
            <Button size="sm" onClick={copy}>
              Copy
            </Button>
          </div>
          <Button
            variant="link"
            size="sm"
            className="self-start px-0"
            onClick={() => create.mutate()}
            disabled={create.isPending}
          >
            Rotate link
          </Button>
          <p className="text-xs text-muted-foreground">
            Anyone with this link can view this site&apos;s dashboard, read-only. Rotate or revoke
            to disable it.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-muted-foreground">No public link yet.</p>
          <Button
            size="sm"
            className="self-start"
            onClick={() => create.mutate()}
            disabled={create.isPending}
          >
            {create.isPending ? "Creating…" : "Create share link"}
          </Button>
        </div>
      )}
    </div>
  );
}
