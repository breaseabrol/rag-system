// Mirrors backend/app/schemas/model.py exactly -- keep these in sync
// if the API response shape ever changes.

export interface ChunkResult {
  chunk_id: number;
  content: string;
  document_title: string;
  document_url: string;
}

export interface QueryResponse {
  answer: string;
  sources: ChunkResult[];
}

// Frontend-only: one query/response exchange in the transcript.
export interface Turn {
  id: string;
  query: string;
  status: "pending" | "done" | "error";
  answer?: string;
  sources?: ChunkResult[];
  error?: string;
}
