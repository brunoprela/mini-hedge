const API_URL = process.env.API_URL ?? "http://localhost:8000";

/** Server-side fetch — calls FastAPI directly with Bearer token */
export async function serverFetch<T>(
  path: string,
  accessToken: string,
  options?: { fundSlug?: string; method?: string; body?: unknown }
): Promise<T> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${accessToken}`,
    "Content-Type": "application/json",
  };
  if (options?.fundSlug) {
    headers["X-Fund-Slug"] = options.fundSlug;
  }

  const response = await fetch(`${API_URL}${path}`, {
    method: options?.method ?? "GET",
    headers,
    body: options?.body ? JSON.stringify(options.body) : undefined,
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`API error ${response.status}: ${detail}`);
  }

  return response.json();
}

/** Client-side fetch — calls BFF proxy (same-origin) */
export async function clientFetch<T>(
  path: string,
  options?: { fundSlug?: string; method?: string; body?: unknown }
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (options?.fundSlug) {
    headers["X-Fund-Slug"] = options.fundSlug;
  }

  const response = await fetch(`/api/proxy${path}`, {
    method: options?.method ?? "GET",
    headers,
    body: options?.body ? JSON.stringify(options.body) : undefined,
  });

  if (!response.ok) {
    if (response.status === 401) {
      window.location.href = "/login";
      throw new Error("Session expired");
    }
    const detail = await response.text();
    throw new Error(`API error ${response.status}: ${detail}`);
  }

  return response.json();
}
