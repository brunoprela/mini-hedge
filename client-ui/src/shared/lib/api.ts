const BASE = "/api/proxy";

export async function apiFetch<T = void>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}/${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    let detail: string;
    try {
      const body = await response.json();
      detail = body.detail ?? body.message ?? JSON.stringify(body);
    } catch {
      detail = `API error ${response.status}`;
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as never;
  return response.json();
}
