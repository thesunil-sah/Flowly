"use client";

import { useRouter } from "next/navigation";
import { LogOut, Menu, UserRound } from "lucide-react";
import { useState } from "react";

import { SidebarNav } from "@/components/layout/app-sidebar";
import { SiteSwitcher } from "@/components/layout/site-switcher";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { useLogout, useMe } from "@/hooks/useAuth";

function UserMenu() {
  const { data: me } = useMe();
  const logout = useLogout();
  const router = useRouter();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Account menu">
          <UserRound className="size-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        {me && (
          <>
            <DropdownMenuLabel className="truncate font-normal text-muted-foreground">
              {me.email}
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
          </>
        )}
        <DropdownMenuItem
          onClick={async () => {
            await logout();
            router.replace("/sign-in");
          }}
        >
          <LogOut className="size-4" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function AppHeader() {
  const [navOpen, setNavOpen] = useState(false);

  return (
    <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur lg:px-6">
      <Sheet open={navOpen} onOpenChange={setNavOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open navigation">
            <Menu className="size-4" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-64 p-0">
          <SheetTitle className="flex h-14 items-center border-b border-border px-6 text-lg font-semibold">
            Flowly
          </SheetTitle>
          <SidebarNav onNavigate={() => setNavOpen(false)} />
        </SheetContent>
      </Sheet>

      <SiteSwitcher />

      <div className="ml-auto flex items-center gap-1">
        {/* Date-range-picker slot: the global picker lands here in F1; until
            then pages keep their own preset controls. */}
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}
