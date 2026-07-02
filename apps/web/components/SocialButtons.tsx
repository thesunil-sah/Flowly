"use client";

import { oauthStartUrl } from "@/lib/api";

// Full-page links (not fetch): the browser must navigate to the provider.
export function SocialButtons() {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3 text-xs text-gray-400">
        <span className="h-px flex-1 bg-gray-200" />
        or
        <span className="h-px flex-1 bg-gray-200" />
      </div>
      <a
        href={oauthStartUrl("google")}
        className="flex w-full items-center justify-center rounded border border-gray-300 px-3 py-2 text-sm hover:bg-gray-50"
      >
        Continue with Google
      </a>
      <a
        href={oauthStartUrl("github")}
        className="flex w-full items-center justify-center rounded border border-gray-300 px-3 py-2 text-sm hover:bg-gray-50"
      >
        Continue with GitHub
      </a>
    </div>
  );
}
