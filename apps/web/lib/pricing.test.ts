import { describe, expect, it } from "vitest";

import { estimateMonthlyBill, estimateMonthlyBillCents, formatUsd } from "./pricing";

// These are the ADVERTISED numbers (frontendClaude.md Phase 14 schedule).
// A wrong boundary here is a marketing/billing trust problem, not a rounding
// nit — pin them exactly.
describe("estimateMonthlyBillCents (graduated tiers)", () => {
  it("free tier: 0 and 1,000 views cost nothing", () => {
    expect(estimateMonthlyBillCents(0)).toBe(0);
    expect(estimateMonthlyBillCents(1_000)).toBe(0);
  });

  it("boundary bills match the advertised schedule", () => {
    expect(estimateMonthlyBillCents(10_000)).toBe(891); // $8.91
    expect(estimateMonthlyBillCents(100_000)).toBe(1_791); // $17.91
    expect(estimateMonthlyBillCents(1_000_000)).toBe(6_291); // $62.91
  });

  it("beyond 1M continues at 3¢ per 1k", () => {
    // 1M base ($62.91) + 1,000k extra views × 3¢/1k = $30.00
    expect(estimateMonthlyBillCents(2_000_000)).toBe(6_291 + 3_000); // $92.91
  });

  it("just over a boundary bills only the marginal views", () => {
    // 1 view into the 99¢/1k tier = 0.099¢ → rounds to 0
    expect(estimateMonthlyBillCents(1_001)).toBe(0);
    // 500 views into it = 49.5¢ → rounds to 50¢
    expect(estimateMonthlyBillCents(1_500)).toBe(50);
  });

  it("negative and fractional inputs are clamped/floored", () => {
    expect(estimateMonthlyBillCents(-5)).toBe(0);
    expect(estimateMonthlyBillCents(10_000.9)).toBe(891);
  });
});

describe("display helpers", () => {
  it("estimateMonthlyBill returns dollars", () => {
    expect(estimateMonthlyBill(10_000)).toBe(8.91);
  });

  it("formatUsd renders US currency", () => {
    expect(formatUsd(8.91)).toBe("$8.91");
    expect(formatUsd(0)).toBe("$0.00");
  });
});
