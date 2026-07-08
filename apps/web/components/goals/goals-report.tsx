"use client";

import Link from "next/link";
import { Sparkles, Target, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { useRange } from "@/components/layout/range-context";
import { TableSkeleton } from "@/components/skeletons";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useCreateGoal,
  useDeleteGoal,
  useEvents,
  useGoalConversion,
  useGoals,
} from "@/hooks/useGoals";
import { ApiError, type Goal, type GoalKind, type StatsRange } from "@/lib/api";
import { formatNumber, formatPercent } from "@/lib/format";

// A 402 from any premium endpoint means the account is on the free plan — show
// one upgrade prompt for the whole surface (mirrors the Phase 11 city gate).
function UpgradeGate() {
  return (
    <EmptyState
      icon={Sparkles}
      title="A premium feature"
      description="Custom events and conversion goals are available on a paid plan. Upgrade to track sign-ups, purchases, and any custom action."
      action={
        <Button asChild>
          <Link href="/billing">Upgrade</Link>
        </Button>
      }
    />
  );
}

function isPaywall(error: unknown): boolean {
  return error instanceof ApiError && error.status === 402;
}

// --- custom events table -------------------------------------------------
function EventsCard({ siteId, range }: { siteId: string; range: StatsRange }) {
  const events = useEvents(siteId, range);
  if (!events.data) return <TableSkeleton rows={5} />;
  const rows = events.data.rows;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Custom events</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No custom events yet. Call{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-xs">flowly(&apos;event&apos;, &apos;signup&apos;)</code>{" "}
            in your site to start tracking actions.
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Event</TableHead>
                <TableHead className="text-right">Count</TableHead>
                <TableHead className="text-right">Visitors</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.name}>
                  <TableCell className="font-medium">{r.name}</TableCell>
                  <TableCell className="text-right">{formatNumber(r.count)}</TableCell>
                  <TableCell className="text-right">{formatNumber(r.visitors)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

// --- one goal's row (its own conversion query) ---------------------------
function GoalRow({
  goal,
  siteId,
  range,
  onDelete,
}: {
  goal: Goal;
  siteId: string;
  range: StatsRange;
  onDelete: (id: string) => void;
}) {
  const conv = useGoalConversion(siteId, goal.id, range);
  return (
    <TableRow>
      <TableCell className="font-medium">{goal.name}</TableCell>
      <TableCell className="text-muted-foreground">
        {goal.kind === "custom" ? "Event" : "Pageview"}: {goal.target}
      </TableCell>
      <TableCell className="text-right">
        {conv.data ? formatNumber(conv.data.conversions) : "—"}
      </TableCell>
      <TableCell className="text-right">
        {conv.data ? formatPercent(conv.data.conversion_rate * 100) : "—"}
      </TableCell>
      <TableCell className="text-right">
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Delete ${goal.name}`}
          onClick={() => onDelete(goal.id)}
        >
          <Trash2 className="size-4" />
        </Button>
      </TableCell>
    </TableRow>
  );
}

// --- add-goal form -------------------------------------------------------
function AddGoalForm({ siteId }: { siteId: string }) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState<GoalKind>("custom");
  const [target, setTarget] = useState("");
  const create = useCreateGoal(siteId);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !target.trim()) return;
    create.mutate(
      { name: name.trim(), kind, target: target.trim() },
      {
        onSuccess: () => {
          toast.success("Goal created");
          setName("");
          setTarget("");
        },
        onError: (err) =>
          toast.error(
            err instanceof ApiError && err.status === 409
              ? "A goal with this target already exists."
              : "Couldn't create the goal.",
          ),
      },
    );
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Name</label>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Sign-ups"
          className="w-40"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Type</label>
        <Select value={kind} onValueChange={(v) => setKind(v as GoalKind)}>
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="custom">Custom event</SelectItem>
            <SelectItem value="pageview">Pageview</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">
          {kind === "custom" ? "Event name" : "Path"}
        </label>
        <Input
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder={kind === "custom" ? "signup" : "/thank-you"}
          className="w-48"
        />
      </div>
      <Button type="submit" disabled={create.isPending}>
        Add goal
      </Button>
    </form>
  );
}

// --- the whole surface ---------------------------------------------------
export function GoalsReport({ siteId }: { siteId: string }) {
  const { range } = useRange();
  const goals = useGoals(siteId);
  const del = useDeleteGoal(siteId);

  // Either query returning 402 → the account is free; show one upgrade prompt.
  if (isPaywall(goals.error)) return <UpgradeGate />;

  function handleDelete(id: string) {
    del.mutate(id, {
      onSuccess: () => toast.success("Goal deleted"),
      onError: () => toast.error("Couldn't delete the goal."),
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Conversion goals</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <AddGoalForm siteId={siteId} />
          {!goals.data ? (
            <TableSkeleton rows={3} />
          ) : goals.data.length === 0 ? (
            <EmptyState
              icon={Target}
              title="No goals yet"
              description="Add a goal above to measure how many visitors complete a key action."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Goal</TableHead>
                  <TableHead>Target</TableHead>
                  <TableHead className="text-right">Conversions</TableHead>
                  <TableHead className="text-right">Rate</TableHead>
                  <TableHead className="text-right sr-only">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {goals.data.map((g) => (
                  <GoalRow
                    key={g.id}
                    goal={g}
                    siteId={siteId}
                    range={range}
                    onDelete={handleDelete}
                  />
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <EventsCard siteId={siteId} range={range} />
    </div>
  );
}
