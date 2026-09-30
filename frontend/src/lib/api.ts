import type { Page, Session } from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let csrf = "";
let identityVersion = 0;
export const currentIdentity = () => identityVersion;
export function identityChanged() {
  identityVersion += 1;
}
let bootstrap: Promise<Session> | undefined;
export function describeError(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(describeError).join(" ");
  if (value && typeof value === "object")
    return Object.entries(value)
      .map(
        ([key, item]) =>
          `${key === "detail" || key === "non_field_errors" ? "" : `${key.replaceAll("_", " ")}: `}${describeError(item)}`,
      )
      .join(" ");
  return "Something went wrong. Please try again.";
}

export async function session(): Promise<Session> {
  if (!bootstrap)
    bootstrap = api<Session>("/api/auth/session/").finally(() => {
      bootstrap = undefined;
    });
  return bootstrap;
}

export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  if (!path.startsWith("/api/"))
    throw new Error("Only same-origin API paths are supported.");
  const write = !["GET", "HEAD"].includes(method);
  const startedAs = identityVersion;
  const accountWrite =
    write &&
    !path.startsWith("/api/auth/session/") &&
    !path.startsWith("/api/auth/register/");
  if (write) await session(); // also refreshes CSRF after another tab logs in/out
  if (accountWrite && startedAs !== identityVersion)
    throw new ApiError(409, "Your account changed. Refresh before continuing.");
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      credentials: "same-origin",
      signal,
      headers: {
        Accept: "application/json",
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        ...(write ? { "X-CSRFToken": csrf } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new ApiError(
      0,
      write
        ? "Connection lost. Check your orders before submitting again; your request may have succeeded."
        : "Unable to connect. Check your connection and try again.",
    );
  }
  const data =
    response.status === 204 ? null : await response.json().catch(() => null);
  if (startedAs !== identityVersion && path !== "/api/auth/session/")
    throw new ApiError(
      409,
      "Your account changed. Refresh to see its current data.",
    );
  if (!response.ok) {
    if (response.status === 401 && path !== "/api/auth/session/")
      window.dispatchEvent(new Event("session-expired"));
    throw new ApiError(
      response.status,
      data
        ? describeError(data)
        : "Your request could not be completed. Refresh the page and try again.",
    );
  }
  if (path === "/api/auth/session/" && data?.csrf_token) csrf = data.csrf_token;
  return data as T;
}

// Used for complete form pickers, rather than silently truncating them at page one.
export async function allPages<T>(
  path: string,
  signal?: AbortSignal,
): Promise<T[]> {
  const items: T[] = [];
  let next: string | null = path;
  while (next) {
    const result: Page<T> = await api<Page<T>>(next, "GET", undefined, signal);
    items.push(...result.results);
    const url = result.next
      ? new URL(result.next, window.location.origin)
      : null;
    next = url ? url.pathname + url.search : null;
  }
  return items;
}
