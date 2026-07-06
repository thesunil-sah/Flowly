"use client";

import { Button } from "@/components/ui/button";
import { oauthStartUrl } from "@/lib/api";

// Full-page links (not fetch): the browser must navigate to the provider.
export function SocialButtons() {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span className="h-px flex-1 bg-border" />
        or
        <span className="h-px flex-1 bg-border" />
      </div>
      <Button variant="outline" className="w-full" asChild>
        <a href={oauthStartUrl("google")}>Continue with Google</a>
      </Button>
      <Button variant="outline" className="w-full" asChild>
        <a href={oauthStartUrl("github")}>Continue with GitHub</a>
      </Button>
    </div>
  );
}
