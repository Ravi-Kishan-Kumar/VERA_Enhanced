export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); this.name = "ApiError"; }
}

/** Fetch a paginated list; the backend sends the unpaginated total in `X-Total-Count`. */
export async function apiPage<T>(path: string, options: RequestInit = {}): Promise<{ items: T[]; total: number }> {
  let total: number | null = null;
  const items = await api<T[]>(path, options, (response) => {
    const value = response.headers.get("X-Total-Count");
    if (value !== null) {
      const parsed = Number(value);
      if (Number.isSafeInteger(parsed) && parsed >= 0) total = parsed;
    }
  });
  return { items, total: total ?? items.length };
}

/**
 * JSON request against the same-origin `/api` proxy (see next.config.ts rewrites).
 * Throws `ApiError` with a user-safe message for network and HTTP failures.
 */
export async function api<T>(
  path: string,
  options: RequestInit = {},
  onResponse?: (response: Response) => void,
): Promise<T> {
  const timeout = AbortSignal.timeout(15_000);
  const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout;
  let response: Response;
  try {
    response = await fetch(`/api${path}`, { ...options, signal, cache: "no-store", headers: { "Content-Type": "application/json", ...options.headers } });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new ApiError("The service could not be reached. Check your connection and try again.", 0);
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null);
    const detail = body && typeof body === "object" && "detail" in body ? body.detail : null;
    const fallback = response.status === 404 ? "This record could not be found." : response.status === 429 ? "Too many requests. Please wait a moment and try again." : response.status === 422 ? "Some review details are invalid. Check the fields and try again." : "The service is temporarily unavailable. Please try again shortly.";
    throw new ApiError(typeof detail === "string" && detail.length < 300 ? detail : fallback, response.status);
  }
  onResponse?.(response);
  return response.json() as Promise<T>;
}

export const errorMessage = (error: unknown) => error instanceof Error ? error.message : "Something went wrong. Please try again.";

export function pause(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const abort = () => { clearTimeout(timer); reject(new DOMException("Cancelled", "AbortError")); };
    const timer = setTimeout(() => { signal.removeEventListener("abort", abort); resolve(); }, ms);
    if (signal.aborted) abort(); else signal.addEventListener("abort", abort, { once: true });
  });
}
