import { afterEach, describe, expect, it, vi } from "vitest";
import { api, allPages, describeError, identityChanged } from "./api";
afterEach(() => vi.unstubAllGlobals());
const response = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
describe("API boundary", () => {
  it("sends CSRF on writes and never automatically repeats a failed reservation", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        response({ csrf_token: "test-csrf", authenticated: true }),
      )
      .mockResolvedValueOnce(response({ detail: "Sold out." }, 409));
    vi.stubGlobal("fetch", fetcher);
    await expect(api("/api/orders/", "POST", {})).rejects.toMatchObject({
      status: 409,
      message: "Sold out.",
    });
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(fetcher.mock.calls[1][1]).toMatchObject({
      credentials: "same-origin",
      headers: { "X-CSRFToken": "test-csrf" },
    });
  });
  it("rejects a delayed mutation result after an account switch", async () => {
    let deliver!: (response: Response) => void;
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        response({ csrf_token: "test-csrf", authenticated: true }),
      )
      .mockImplementationOnce(
        () =>
          new Promise<Response>((resolve) => {
            deliver = resolve;
          }),
      );
    vi.stubGlobal("fetch", fetcher);
    const pending = api("/api/orders/1/pay/", "POST");
    const rejection = expect(pending).rejects.toMatchObject({ status: 409 });
    await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
    identityChanged();
    deliver(response({ tickets: [{ code: "private-old-account-code" }] }));
    await rejection;
  });
  it("loads every page of an organizer form picker", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          response({
            results: [{ id: 1 }],
            next: "http://testserver/api/venues/?page=2",
          }),
        )
        .mockResolvedValueOnce(response({ results: [{ id: 2 }], next: null })),
    );
    expect(await allPages("/api/venues/")).toEqual([{ id: 1 }, { id: 2 }]);
  });
  it("presents nested field validation without showing HTML", () => {
    expect(
      describeError({ items: [{ quantity: ["Too many tickets."] }] }),
    ).toBe("items: quantity: Too many tickets.");
  });
});
