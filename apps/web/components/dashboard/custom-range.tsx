"use client";

import { CalendarDays } from "lucide-react";
import { useState } from "react";

import { useRange } from "@/components/layout/range-context";
import { Button } from "@/components/ui/button";
import { rangeFromDates } from "@/lib/range";

// Custom date-range picker (Phase 10, frontend-only). Two native date inputs in
// a small popover — dependency-free and theme-agnostic — writing an explicit
// [from, to) window into the range context. The server already parses arbitrary
// ranges (core/timerange.py), so there's no backend work. Active state is shown
// by the button variant when the context is on a custom range.

export function CustomRange() {
  const { presetKey, setCustomRange } = useRange();
  const [open, setOpen] = useState(false);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  const today = new Date().toISOString().slice(0, 10);
  const valid = from !== "" && to !== "" && from <= to;

  const apply = () => {
    if (!valid) return;
    const range = rangeFromDates(from, to);
    setCustomRange(range.from, range.to);
    setOpen(false);
  };

  return (
    <div className="relative">
      <Button
        variant={presetKey === "custom" ? "secondary" : "ghost"}
        size="sm"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <CalendarDays className="size-4" />
        Custom
      </Button>

      {open && (
        <div className="absolute right-0 z-20 mt-2 w-64 rounded-lg border border-border bg-popover p-3 shadow-card">
          <div className="flex flex-col gap-2">
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              From
              <input
                type="date"
                value={from}
                max={to || today}
                onChange={(e) => setFrom(e.target.value)}
                className="rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-muted-foreground">
              To
              <input
                type="date"
                value={to}
                min={from || undefined}
                max={today}
                onChange={(e) => setTo(e.target.value)}
                className="rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground"
              />
            </label>
            <div className="mt-1 flex justify-end gap-2">
              <Button variant="ghost" size="xs" onClick={() => setOpen(false)}>
                Cancel
              </Button>
              <Button size="xs" onClick={apply} disabled={!valid}>
                Apply
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
