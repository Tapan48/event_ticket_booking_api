import { describe, expect, it } from "vitest";
import { minutesLeft, money, safeNext, localDayStart } from "./format";
describe("reservation and navigation formatting", () => {
  it("rejects impossible dates from editable query strings", () => {
    for (const value of ["2026-99-01", "2026-02-31", "garbage", null])
      expect(localDayStart(value)).toBeNull();
    expect(localDayStart("2026-10-02")).not.toBeNull();
  });
  it("counts down from the server expiry and clamps elapsed reservations", () => {
    expect(
      minutesLeft("2026-10-01T10:15:00Z", Date.parse("2026-10-01T10:00:00Z")),
    ).toBe("15:00");
    expect(
      minutesLeft("2026-10-01T10:15:00Z", Date.parse("2026-10-01T10:14:59.5Z")),
    ).toBe("0:01");
    expect(
      minutesLeft("2026-10-01T10:15:00Z", Date.parse("2026-10-01T10:16:00Z")),
    ).toBe("0:00");
  });
  it("keeps redirects on this site", () => {
    expect(safeNext("/orders/23")).toBe("/orders/23");
    for (const next of [
      "//evil.example",
      "/\\evil.example",
      "https://evil.example",
      null,
    ])
      expect(safeNext(next)).toBe("/");
  });
  it("formats exact decimal prices in INR", () => {
    expect(money("1499.50")).toBe("₹1,499.50");
  });
});
