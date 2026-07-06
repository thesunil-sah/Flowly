import { describe, expect, it } from "vitest";

import { rangeFromDates } from "./range";

// The custom date picker (Phase 10) turns two local `YYYY-MM-DD` dates into a
// [from, to) window whose `to` is made exclusive by advancing one day so the
// picked end date is fully included.

describe("rangeFromDates", () => {
  it("advances `to` by one day so the end date is inclusive", () => {
    const { from, to } = rangeFromDates("2026-07-01", "2026-07-03");
    // Local midnight → the from date's start.
    expect(new Date(from).getFullYear()).toBe(2026);
    // to is exclusive end-of-day: start of 2026-07-04 local.
    const toLocal = new Date(to);
    expect(toLocal.getDate()).toBe(4);
    expect(toLocal.getMonth()).toBe(6); // July (0-indexed)
  });

  it("produces a window spanning at least the selected days", () => {
    const { from, to } = rangeFromDates("2026-07-01", "2026-07-01");
    // A single-day pick still yields a full 24h window.
    expect(new Date(to).getTime() - new Date(from).getTime()).toBe(24 * 60 * 60 * 1000);
  });
});
