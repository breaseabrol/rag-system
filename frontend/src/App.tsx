import { useEffect, useRef, useState } from "react";
import { queryBackend } from "./api/client";
import type { Turn } from "./types";
import ReactMarkdown from "react-markdown";

function makeId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export default function App() {
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [expandedSource, setExpandedSource] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const query = input.trim();
    if (!query) return;

    const id = makeId();
    setTurns((prev) => [...prev, { id, query, status: "pending" }]);
    setInput("");

    try {
      const response = await queryBackend(query);
      setTurns((prev) =>
        prev.map((t) =>
          t.id === id
            ? { ...t, status: "done", answer: response.answer, sources: response.sources }
            : t
        )
      );
    } catch (err) {
      setTurns((prev) =>
        prev.map((t) =>
          t.id === id
            ? {
                ...t,
                status: "error",
                error: err instanceof Error ? err.message : "Request failed",
              }
            : t
        )
      );
    }
  }

  return (
    <div className="console">
      <header className="console-header">
        <div className="console-title">
          RAG<span className="console-title-accent">//</span> retrieval console
        </div>
        <div className="console-subtitle">
          BM25 lexical + pgvector ANN, fused via reciprocal rank fusion
        </div>
      </header>

      <main className="transcript">
        {turns.length === 0 && (
          <div className="empty-state">
            <p>No queries yet. Ask something about the ingested documents below.</p>
          </div>
        )}

        {turns.map((turn) => (
          <div key={turn.id} className="turn">
            <div className="turn-query">
              <span className="prompt-glyph">&gt;</span> {turn.query}
            </div>

            {turn.status === "pending" && (
              <div className="turn-pending">retrieving and generating…</div>
            )}

            {turn.status === "error" && (
              <div className="turn-error">error: {turn.error}</div>
            )}

            {turn.status === "done" && (
              <div className="turn-response">
                <div className="turn-answer">
                  <ReactMarkdown>{turn.answer}</ReactMarkdown>
                </div>

                {turn.sources && turn.sources.length > 0 && (
                  <div className="sources">
                    {turn.sources.map((source, i) => {
                      const sourceKey = `${turn.id}-${i}`;
                      const isExpanded = expandedSource === sourceKey;
                      return (
                        <div key={sourceKey} className="source-block">
                          <button
                            className="source-chip"
                            onClick={() =>
                              setExpandedSource(isExpanded ? null : sourceKey)
                            }
                            aria-expanded={isExpanded}
                          >
                            <span className="source-index">[Source {i + 1}]</span>
                            <span className="source-title">{source.document_title}</span>
                          </button>
                          {isExpanded && (
                            <div className="source-detail">
                              <div className="source-content">{source.content}</div>
                              <a
                                className="source-link"
                                href={source.document_url}
                                target="_blank"
                                rel="noreferrer"
                              >
                                {source.document_url}
                              </a>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </main>

      <form className="input-bar" onSubmit={handleSubmit}>
        <span className="prompt-glyph">&gt;</span>
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="ask a question about the ingested documents"
          className="input-field"
          autoComplete="off"
        />
      </form>
    </div>
  );
}
