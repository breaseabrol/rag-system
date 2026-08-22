import type { QueryResponse } from "../types";

// Override with a .env file (VITE_API_BASE_URL=...) if the backend
// isn't running on the default localhost:8000.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function queryBackend(query: string): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });

  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Request failed (${res.status}): ${detail || res.statusText}`);
  }

  return res.json();
}
